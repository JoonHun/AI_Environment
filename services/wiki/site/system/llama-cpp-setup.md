# llama.cpp 서버 구축 (Ollama 전환)

[summary] Ollama(11434) 대비 2.5배 느린 추론을 해결하기 위해 llama.cpp를 직접 빌드해 4개 서버(11534~11537)를 올리고, Hermes 4개 프로필을 전부 전환했다. Ollama는 동결 백업으로 유지. **9/21: 상주 인스턴스(1538) 제거로 "상주 0" 구조로 확정** — 모든 모델이 on-demand(프록시)로만 로드.

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
| **11534** | Qwen3.8 Q4_K_M | 128K | on-demand (프록시) | joons |
| **11535** | Qwen3.6 A3B (MTP) | 256K | on-demand (프록시) | coding |
| **11536** | Qwen3.8 Q8_0 (MTP) | 128K | on-demand (프록시) | default (폴백) |
| **11537** | Gemma4 E4B | 64K | on-demand (프록시) | english |
| 11434 | Ollama | — | **동결 백업** (로딩 0) | (전부 해제) |

> ✅ **메모리 원칙 (9/21 확정):** **상주 모델 0개.** 부팅 후 GPU 점유는 Xorg/GNOME만(~25MiB).
> 모든 27b/A3B/Gemma는 프록시 요청 시에만 로드, 유휴 300s 시 프록시가 자동 stop.
> 동시 3개 로딩(93GB) 시 3.8이 8.75 t/s로 2.6배 하락 — **동시 추론 2개 이하가 안전선**.
>
> ⚠️ **왜 상주를 없앴나:** 27b 1개가 ~27GB를 상시 점유 → 128GB 통합메모리에서
> 큰 모델(40B+/70B+) 테스트나 동시 2개 추론 시 대역폭/용량 경쟁.
> on-demand 전환 후 **부팅 직후 즉시 회수되는 27GB**가 상시 확보됨.

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
# 11534 (joons, on-demand) — 프록시 뒤, 127.0.0.1
llama-server -m ~/models/qwen3.8-27b-mtp-q4_K_M.gguf \
  --n-gpu-layers 99 --ctx-size 131072 --port 1534 --host 127.0.0.1 \
  --spec-type draft-mtp --spec-draft-n-max 4 --reasoning off --no-reasoning-preserve

# 1535/1536/1537 — 같은 형식, 모델·포트만 교체
```

> ⚠️ `--ngl`은 인식 안 됨 — **`--n-gpu-layers`**를 쓸 것.

systemd 유닛: `~/.config/systemd/user/`
- `llama-server-{34,35,36}.service` — on-demand 백엔드 (내부 포트 1534/1535/1536)
- `llama-proxy-{34,35,36}.service` — 상시 프록시 (`Restart=always`)
- ~~`llama-server-38.service`~~ — **9/21 삭제** (아래 §11, 상주 인스턴스 제거)

> 💡 **on-demand의 실용 가치:** 128GB 통합메모리에서 **용량이 큰 모델(40B+, 70B+ 등)을 임시로 올려 테스트**할 수 있다.
> 테스트 끝나면 `↓ Unload` 버튼 또는 watchdog이 자동 해제 → 메모리 즉시 회수.
> 상시 모델(11534)과 **동시 추론 시 대역폭 경쟁**만 유의하면, 128GB가 허락하는 한 어떤 모델이라도 올려볼 수 있다.
>
> 💡 **on-demand 관리:** proxy watchdog(300s idle) + `↓ Unload` 버튼(즉시) + 재로딩(proxy 자동 start).
> llama-monitor 대시보드(5002)에서 실시간 확인 + Force Unload 가능. 상세: [llama.cpp Status Monitor](/p/llama-monitor/llama-monitor)
> ⚠️ **monitor probe 함정:** config.yaml의 `backend_port`는 **프론트(1153x)여야** 한다.
> 백엔드(153x)로 하면 monitor probe가 모델을 깨워서 idle stop이 무력화된다.

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
systemctl --user status llama-server-34 llama-proxy-34 llama-server-35
systemctl --user start|stop llama-server-34      # on-demand 수동 제어
journalctl --user -u llama-server-34 -f           # 로그
systemctl --user restart hermes-gateway*.service  # 프로필 변경 후
# Ollama 복귀: systemctl --user enable --now ollama + 프로필 base_url 11434로
```

## 10. 남은 과제

- llama.cpp가 LISTEN_FDS를 지원하면 프록시 없이 `.socket`으로 단순화 가능 (업데이트 시 재확인)
- Ollama 완전 종료는 미실행 — `로딩 0` 백업 상태 유지 중
- AI TOP Atom 쿨링 3D 프린팅 STL 설계 (도식 `~/diagrams/cooling_v6.excalidraw` 완성)

## 11. 9/21 상주 인스턴스 제거 ("상주 0" 구조 확정)

**배경:** 9/20 on-demand 전환을 진행했지만, **상주 인스턴스 1개(1538)가 남아** 있었다.
`llama-server-38.service`가 `WantedBy=default.target`(static)이라 부팅마다 자동 기동,
`hermes-serve-9119`·`hermes-dashboard-9120`의 `Wants= llama-server-38.service`가
이것을 부팅 시 함께 띄웠다. → 27b 2개(1538+1534) 동시 = ~55GB 상시 점유.

**진행 (9/21 14:00):**

| 단계 | 동작 |
|---|---|
| 1 | `systemctl --user stop llama-server-38.service` (PID 2332 종료) |
| 2 | `hermes-serve-9119.service` / `hermes-dashboard-9120.service`에서 `After=/Wants= llama-server-38.service` 참조 **삭제** |
| 3 | unit 파일 아카이브 → `~/.config/systemd/user/disabled-38-20260921/` (server-38 + proxy-38 + .bak 2개) |
| 4 | `systemctl --user daemon-reload` + 검증: 1538 포트 비어있음, 활성 unit에 38 참조 0건 |

**결과:**

| | GPU 점유 | 시스템 메모리 |
|---|---|---|
| 제거 전 (1538+1534) | ~55GB (27b × 2) | 61Gi |
| 제거 후 (1534만) | ~27GB (27b × 1) | **39Gi** (22GB 회수) |

> ⚠️ **함정:** `Wants=`/`After=` 참조는 `disable`만으로 안 지워진다 — unit이 static이라
> `enable/disable` 자체가 불가. **참조하는 쪽(hermes-serve/dashboard)의 unit 본문에서
> 직접 제거**해야 부팅 시 재기동이 차단된다. `mask`도 unit 파일이 존재하면 실패한다.

> 💡 **교훈:** "on-demand 전환"을 했더라도 **부팅 시 자동 기동 경로를 전부 끊어야** 진짜 on-demand다.
> `systemctl --user list-units --state=running | grep llama` + `nvidia-smi`로 **부팅 직후**
> 실제로 떠있는 인스턴스를 확인하는 습관이 필요하다.

> **회복:** `disabled-38-20260921/`의 unit 파일을 다시 `~/.config/systemd/user/`로 복원 +
> hermes-serve/dashboard unit에 `Wants= llama-server-38.service` 재추가 + `daemon-reload`.

---
관련: [Ollama 설치](/p/system/ollama-setup) · [다중 모델 서빙](/p/system/ollama-multimodel) · [Hermes Agent 백엔드](/p/system/hermes-agent-backend) · [coding 프로파일](/p/profiles/coding-profile) · [english 프로파일](/p/profiles/english-profile)
