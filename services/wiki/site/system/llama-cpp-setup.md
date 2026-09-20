# llama.cpp 서버 구축 (Ollama 전환)

[summary] Ollama(11434) 대비 2.5배 느린 추론을 해결하기 위해 llama.cpp를 직접 빌드해 4개 서버(11534~11537)를 올리고, Hermes 4개 프로필을 전부 전환했다. Ollama는 동결 백업으로 유지.

## 1. 왜 전환했나

| 구분 | Ollama (11434) | llama.cpp 직접 (11534) |
|---|---|---|
| Qwen3.8 Q4 decode | 10~12 t/s | **22.6 t/s** |
| MTP draft acceptance | 0.46~0.64 | **0.80** |
| 모델 로딩 | 36초 + prefill 지연 | 상시 기동 (11534) |

같은 모델, 같은 GGUF인데 2.5배 차이 — MTP(동적 토큰 예측) acceptance율이 반토막이 나는 것이 원인.

## 2. 전체 구성

| 포트 | 모델 | ctx | 기동 방식 | Hermes 프로필 |
|---|---|---|---|---|
| **11534** | Qwen3.8 Q4_K_M | 128K | **상시 ON** (0.0.0.0) | joons |
| **11535** | Qwen3.6 A3B (MTP) | 256K | on-demand (프록시) | coding |
| **11536** | Qwen3.8 Q8_0 (MTP) | 128K | on-demand (프록시) | default (폴백) |
| **11537** | Gemma4 E4B | 64K | on-demand (프록시) | english |
| 11434 | Ollama | — | **동결 백업** (로딩 0) | (전부 해제) |

> ✅ **메모리 원칙:** 11534만 상시 기동(26.5GB). 나머지 3개는 10분 유휴 시 프록시가 자동 stop.
> 동시 3개 로딩(93GB) 시 3.8이 8.75 t/s로 2.6배 하락 — **동시 추론 2개 이하가 안전선**.

## 3. 빌드 & 모델

```bash
# 빌드 (aarch64, CUDA 13.0, GNU 13.3.0)
/home/joons/llama.cpp-build/llama.cpp/build/bin/llama-server
# version: 0.4.0-dev (commit 304665f), CUDA ON
```

| GGUF | 크기 | 출처 |
|---|---|---|
| `qwen3.8-27b-mtp-q4_K_M.gguf` | 16.8GB | Jackrong/Qwen3.8-27B-MTP-GGUF |
| `qwen3.8-27b-mtp-q8_0.gguf` | 29.05GB | Jackrong/Qwen3.8-27B-MTP-GGUF |
| `qwen3.6-35ba3b-ud-q4_K_M.gguf` | 22GB | unsloth/Qwen3.6-35B-A3B-MTP-GGUF |
| `gemma-4-E4B-it-Q4_K_M.gguf` | 4.98GB | unsloth/gemma-4-E4B-it-GGUF |

> ⚠️ **MTP 플래그 필수** — `--spec-type draft-mtp --spec-draft-n-max 2`가 없으면
> `blk.64 unused tensor`으로 무시되어 2배 느려짐. Gemma는 MTP 미지원(플래그 없음).

## 4. 실행 명령

```bash
# 11534 (상시)
llama-server -m ~/models/qwen3.8-27b-mtp-q4_K_M.gguf \
  --n-gpu-layers 99 --ctx-size 131072 --port 11534 --host 0.0.0.0 \
  --spec-type draft-mtp --spec-draft-n-max 2

# 1536/1537/1538 (프록시 뒤, 127.0.0.1) — 같은 형식, 모델·포트만 교체
```

> ⚠️ `--ngl`은 인식 안 됨 — **`--n-gpu-layers`**를 쓸 것.

systemd 유닛: `~/.config/systemd/user/`
- `llama-server-38.service` — 상시 (`WantedBy=default.target`)
- `llama-server-{36,38q8,gemma}.service` — on-demand (내부 포트 1536/1537/1538)
- `llama-proxy-{36,38q8,gemma}.service` — 상시 프록시 (`Restart=always`)
- `llama-server-36.socket` — **무효** (disabled, 아래 §5)

## 5. 소켓 활성화 실패 → 프록시 전환 (핵심)

**시도:** systemd 소켓 활성화(`.socket` + `IdleTimeoutSec`)로 "요청 시 기동, 유휴 시 종료".

**실패 원인:** llama.cpp는 **LISTEN_FDS(fd 상속)를 지원하지 않음** — 소스 검색 0건.
요청 시 서버는 뜨지만 기본 포트 8080으로 자기 listen을 새로 함.

**대안 — Python TCP 터널 프록시:**

```
클라이언트(11535) ──> 프록시(상시) ──TCP터널──> llama-server(1536, on-demand)
                        │  첫 연결: systemctl start llama-server-36
                        │  10분 유휴: systemctl stop  llama-server-36
```

| 파일 | 경로 |
|---|---|
| 프록시 | `~/llama-proxy/proxy{36,38q8}.py`, `proxy_gemma.py` |
| 핵심 | `ensure_backend()`(기동+헬스체크 폴링) · `watchdog()`(600s 유휴 stop) · `main()`(is-active 동기화) |

## 6. 프록시 버그 2건

| 버그 | 증상 | 수정 |
|---|---|---|
| running 플래그 불일치 | 프록시 재시작 시 `running=False` 초기화 → watchdog이 백엔드 stop 실패, 58분간 메모리 방치 | `main()`에서 `systemctl is-active`로 상태 동기화 |
| 10초 recv 타임아웃 | `create_connection(timeout=10)`이 recv까지 적용 → 비스트리밍 긴 응답 10초 단절 | 연결 후 `upstream.settimeout(None)` |

> 💡 **교훈:** TCP 터널 프록시는 connect 타임아웃과 recv 타임아웃을 분리해야 한다. LLM 응답은 수분 걸리므로 recv 타임아웃은 없어야 한다.

## 7. 프로필 전환

| 프로필 | 이전 (Ollama) | 지금 |
|---|---|---|
| default | `qwen3.8:27b-mtp-q8_0_256k` | **11536** `qwen3.8-27b-mtp-q8_0` |
| coding | `qwen3.6:35b-a3b-coding-mtp-q4_K_M` | **11535** `qwen3.6-35b-a3b-mtp-q4_k_m` |
| english | `gemma4:e4b-it-q4_K_M_64K` | **11537** `gemma-4-E4B-it-q4_k_m` |
| joons | `qwen3.8:27b-mtp-q4_K_M_256k` | **11534** `qwen3.8-27b-mtp-q4_k_m` |
| researcher / teacher | — | **삭제** (git 백업 확인 후) |

> 💡 **모델명 규칙:** Ollama의 `:접두 + _256k 접미`를 llama.cpp 하이픈 규칙으로 통일.
> Hermes Desktop 모델 피커가 접미를 제거해 4개 모델이 하나로 수렴하던 문제도 함께 해결.

**검증 (리모트 PC 192.168.219.101 E2E):**
- coding → 11535 → 3.6 A3B: ✅ 54~74 t/s, MTP acc 0.77
- english → 11537 → Gemma4: ✅ 34~45 t/s, prefill 2500~3900 t/s
- 게이트웨이 재시작 후 Ollama **로딩 모델 0개** (18.5GB 회수)

## 8. 실측 벤치 (GB10)

| 모델 | decode | MTP acc | 메모리 |
|---|---|---|---|
| Qwen3.8 Q4_K_M | 22.6 t/s (직접) | 0.80 | 26.5GB |
| Qwen3.6 A3B | 22~95 t/s | 0.59~0.63 | 28.4GB |
| Qwen3.8 Q8_0 | 15.74 t/s | 0.69 | 37.6GB |
| Gemma4 E4B | 34~47 t/s (MTP 없음) | — | 3.1GB |

## 9. 관리 명령

```bash
systemctl --user status llama-server-38 llama-proxy-36 llama-server-36
systemctl --user start|stop llama-server-36      # on-demand 수동 제어
journalctl --user -u llama-server-36 -f           # 로그
systemctl --user restart hermes-gateway*.service  # 프로필 변경 후
# Ollama 복귀: systemctl --user enable --now ollama + 프로필 base_url 11434로
```

## 10. 남은 과제

- llama.cpp가 LISTEN_FDS를 지원하면 프록시 없이 `.socket`으로 단순화 가능 (업데이트 시 재확인)
- Ollama 완전 종료는 미실행 — `로딩 0` 백업 상태 유지 중
- AI TOP Atom 쿨링 3D 프린팅 STL 설계 (도식 `~/diagrams/cooling_v6.excalidraw` 완성)

---
관련: [Ollama 설치](/p/system/ollama-setup) · [다중 모델 서빙](/p/system/ollama-multimodel) · [Hermes Agent 백엔드](/p/system/hermes-agent-backend) · [coding 프로파일](/p/profiles/coding-profile) · [english 프로파일](/p/profiles/english-profile)
