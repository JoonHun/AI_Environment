# Strata (Qwen3.8-Flash-Next) 도입 계획

- 작성일: 2026-10-11
- 상태: **계획 수립됨 — 아직 설치/변경 없음**
- 목표: `Qwen3.8-Flash-Next`(125B MoE, 활성 6B)를 Strata 엔진으로 로컬 서빙하고,
  llama-monitor에서 load/unload 관리를 하며 Hermes 프로필에 연결한다.

---

## 1. 배경 · 현재 구조

```
Hermes Desktop (UI)
   └─ Hermes Gateway (이 머신: joons = 192.168.219.115)
        └─ llama.cpp llama-server  (llama-proxy raw-TCP 프록시 뒤)
             11534 joons    qwen3.8-27b-mtp Q4_K_M   (keep ON)
             11535 coding   qwen3.6-35b-a3b Q8_0
             11536 english  gemma4
             11537 q8       qwen3.8-27b Q8_0          (keep ON)
             11538 flash-next  Qwen3.8-Flash-Next UD-Q4_K_XL  (llama.cpp)
   └─ llama-monitor (port 5002)  →  unload/keep 버튼, journal 파싱
```

- **이 머신이 192.168.219.115 자체** → Gateway / llama-server / Strata 모두 같은 호스트.
- 현재 Hermes default 프로필: `model.base_url = http://192.168.219.115:11534/v1` (llama.cpp).
- Hermes config는 **프로필 단위**로 분리(`~/.hermes/profiles/<name>/config.yaml`)
  → 특정 프로필만 Strata로 바꾸면 gateway/다른 프로필 영향 없음.

## 2. Strata 개요 (확인됨)

- 오픈소스 C++ 추론 엔진 (Niko1221/Strata), **Qwen3.8-Flash-Next 전용 최적화**.
- 125B MoE를 **12-24GB NVIDIA GPU + 64GB RAM** 컨슈머 환경에서 실행.
  - GPU: attention/DeltaNet/로더/공유 전문가/MTP/KV-cache/adaptive expert cache
  - RAM: 24,576 experts 전부 pinned, CPU가 GPU에 없는 expert를 동시 계산(AVX-512/AVX2)
  - SSD: 28.8GB n-gram lookup table
- **런타임 모델 load/unload 지원** (v0.1.38~, 서버 프로세스는 유지):
  - `POST http://localhost:8080/unload`  → 모델 RAM/VRAM에서 해제
  - `POST http://localhost:8080/load`    → 재로딩 (30-90초)
  - `GET  /health`, `GET /status`, `GET /v1/models`
- OpenAI 호환 `http://localhost:8080/v1` + Anthropic 호환 `/anthropic/v1`.
- 설치: `./setup.sh` (Linux) / `START-HERE.bat` (Win). 모델(66-76GB) HF에서 자동 다운로드.

## 3. 이 머신 실사 결과 (2026-10-11)

| 항목 | 값 | Strata 요구 | 판정 |
|---|---|---|---|
| RAM | 121.6GB (81.4GB available) | ≥52GB | ✅ 충분 |
| GPU | **NVIDIA GB10** (driver 580.178.04, `memory.total` N/A = 통합 메모리) | 12-24GB | ⚠️ ARM Grace 기반 — 아래 §5-3 |
| CPU | **GB10 = ARM(Grace)** — `/proc/cpuinfo` model name/avx 플래그 비어옴 | AVX-512/AVX2(x86) decode 커널 | ⚠️ §5-3 |
| NVMe | 931GB, free 300GB | 모델 66-76GB + n-gram 28.8GB | ✅ 충분 |
| flash-next(1538) | `inactive` | — | ✅ 충돌 없음 |
| port 11538 | **python3(pid 2392) LISTEN 중** = llama-proxy 프록시 | — | ⚠️ §5-1 |
| keep 플래그 | `~/llama-proxy/keep/{11534,11537}` ON | — | ⚠️ §5-2 |

> GB10은 GPU/RAM 통합(약 121GB 풀). "VRAM + RAM"이 아니라 **하나의 메모리 풀**에서
> OS + llama.cpp 27b + Strata 125B가 경쟁 → §5-2 OOM 관리가 핵심.

## 4. llama-monitor unload/keep 메카니즘 ↔ Strata 대응

llama-monitor의 두 버튼은 **llama.cpp 특화**라 Strata에 그대로는 맞지 않음.

| 버튼 | 지금 동작 | Strata 대응 |
|---|---|---|
| `POST /api/unload` | `systemctl --user stop <unit>` → 프로세스 전체 stop | `POST localhost:8080/unload` → 모델만 RAM 해제, 프로세스 유지 |
| `POST /api/keep` | `~/llama-proxy/keep/<port>` 파일 → llama-proxy idle-watchdog 무력화 | **해당 없음** (unload 안 하면 이미 메모리에 상주) |
| (없음) | — | `POST localhost:8080/load` → 재로딩 30-90s (신규 버튼 필요) |

→ **app.py 수정 필요** (아래 §6). Strata 카드엔 unload(→HTTP /unload) + load(→HTTP /load),
   keep 버튼은 제거 또는 "상주 표시"로 대체.

## 5. 진행 전 반드시 해결할 것

1. **경로 확정 (11538 vs 8080)**
   - 11538 = llama.cpp flash-next(UD-Q4_K_XL) 프록시, 현재 python3가 LISTEN.
   - 8080 = Strata(새). 둘 다 flash-next를 서빙.
   - **정답을 하나 정해야 함** — Hermes가 어느 base_url을 쓸지.
   - 동시에 양쪽이 메모리 점유 시 OOM (§5-2).

2. **OOM/keep 정리**
   - keep ON인 11534(27b), 11537(27b Q8)는 Strata load 시 RAM을 잡아먹는 경쟁자.
   - **Strata `load` 전: 이 두 keep 플래그 OFF**(monitor keep 토글 또는 파일 삭제)
     → llama-proxy가 idle-unload 가능하게.

3. **ARM(Grace) 호환성 검증 — 최대 리스크**
   - Strata decode 커널은 AVX-512/AVX2(x86) 전제. GB10은 ARM.
   - docs는 "Linux" 지원만 명시, **ARM 명시 없음**.
   - → 실제 설치 후 `strata --help`/첫 로딩으로 **실동작 검증**해야 함.
     (실패 시 대체: x86 머신 배치, 또는 llama.cpp 11538 경로 유지)

## 6. 실행 단계 (승인 순서)

**단계 A — 설치 + ARM 검증**
1. `git clone https://github.com/Niko1221/Strata` (또는 zip)
2. `./setup.sh` → 모델 선택(Qwen3.8-Flash-Next) / 크기 / 컨텍스트 / image 여부
3. `strata --help`, `GET /health`, `GET /v1/models`로 ARM 동작 확인
   → **실패 시 중단, §5-3 대체안으로**

**단계 B — 모델 다운로드**
4. 66-76GB HF 다운로드 (중단 시 재실행으로 이어서 진행)
5. 첫 로딩 34-43GB 확인, 속도 벤치 (bench/results 기준)

**단계 C — monitor 수정**
6. `config.yaml` servers에 Strata 카드 추가:
   ```yaml
   - port: 8080
     backend_port: 8080
     label: strata-flash-next
     mode: resident
     engine: strata            # 신규 키 (unload/keep 경로 분기)
     journal_unit: ""          # Strata는 journal 파싱 없음 → HTTP /status 기반
   ```
7. `app.py`: `engine: strata`일 때
   - `/api/unload` → `POST http://127.0.0.1:8080/unload` (systemctl 대신)
   - `load` 엔드포인트 신규 → `POST http://127.0.0.1:8080/load`
   - keep 토글 비활성(해당 없음)
   - 상태 분류: `GET /health`·`GET /status`로 loaded/unloaded 판정
8. index.html에 Strata 카드 load 버튼 추가

**단계 D — Hermes 연결 (프로필 단위, gateway/타 프로파일 무영향)**
```bash
hermes --profile <이름> config set model.base_url http://localhost:8080/v1
hermes --profile <이름> config set model.default qwen3.8-125b-q4   # (실제 slug 확인)
hermes --profile <이름> config set model.provider llama            # OpenAI 호환, 유지
```
- `/load` 대기 30-90초 중 요청은 에러 → 호출 전 `GET /health` 확인
- default 프로필이 이 세션이므로, 시험은 별도 프로필 권장

## 7. 리스크 · 회피

| 리스크 | 영향 | 회피 |
|---|---|---|
| ARM decode 미지원 | Strata가 도래지 않음 | 단계 A에서 검증, 실패 시 llama.cpp 11538 유지 |
| 통합 메모리 OOM | 27b + 125b 동시 점유 | §5-2 keep OFF, 11538/8080 중 하나만 활성 |
| 모델 다운로드 66-76GB | 시간/디스크 | NVMe free 300GB 여유, 재개 지원 |
| `/load` 30-90초 | 호출 지연/에러 | 호출 전 health 게이트 |

## 8. 결정 대기 (사용자)

- [ ] **정답 경로**: 11538(llama.cpp) 유지 vs 8080(Strata) 전환
- [ ] **진행 범위**: A(설치+검증) / A+B(다운로드까지) / A+B+C+D(전체)
- [ ] **Hermes 연결 대상 프로필**: default vs 신규/별도 프로필

---
---

# 추가 검토 (2026-10-11, 심화 심리 후 부기)

> 본 섹션은 위에 작성된 원문(§1-§8)을 **삭제·변경하지 않고** 심화 심리(원본 코드·
> 릴리스·GitHub 이슈/PR 실사, journal 확인) 결과로 부기(追加)한 것임.
> **최종 결정(사용자): 아직 공식 지원이 없으므로 시도하지 않고, 공식 지원 반영 후
> 나중에 재시도함. (2026-10-11)**

## 9. GB10(ARM) 호환성 — 원문 §5-3의 정정 및 최신 사실

원문 §5-3은 "ARM 미지정 → 최대 리스크, 실제 설치 후 검증"으로 기술되었으나, 심화
심리 결과 **GB10 포팅이 이미 존재**함:

| 근거 | 내용 |
|---|---|
| **PR #409** `arm-gb10-port` 브랜치 | "aarch64 / NVIDIA DGX Spark (GB10): build, run and set up with unified memory" — GB10 통합메모리 포팅 |
| **PR #1077** (2026-10-04~06) | aarch64 빌드 + **GB10 sm_121 실측 완료**: UD-IQ4_XS, 컨텍스트 262144, `NVIDIA GB10, 122 GB unified memory, compute capability 12.1`, expert cache 24576 experts(55.43 GiB) 전부 통합메모리, `:8080` server ready, **decode 47.0 tok/s 실측** |
| **Issue #1306** (2026-10-07, **open**) | "Strata currently has incomplete support for ARM64 (particularly GB10)" — ARM64(특히 GB10) 지원이 미완성이라는 이슈가 열려 있음 |
| **main 브랜치 setup.py** (직접 확인) | `PREBUILT_ASSET = "strata-linux-x64.zip"` 고정 — aarch64 경로 없음. CPU 판정도 AVX2/AVX-512(x86) 기준 |

**판정(정정)**: GB10 지원은 **PR에서 실동작 확인(빌드 성공 + 47 tok/s)되었으나,
최신 릴리스 v0.1.42(2026-10-10)에는 아직 미반영**. #1077은 close(미머지) 후
"port onto the new main" 상태로 유지자에게 반환됨. 머지 ETA 없음.
→ 즉, "사망 리스크"가 아니라 **"포팅 존재, main 미반영"** 상태.

**관련 GB10 문제 (Issue #1056)**: GB10 + `--mmap-experts`에서 prefill 스테거 스핀으로
프롬프트 로드가 ~10배 느려짐(약 90 tok/s). 워크어라운드: `STRATA_STAGER_THREADS=4`
+ taskset. 패치는 PR #1057/#1101. **GB10에서 구동 시 `STRATA_STAGER_THREADS=4`
환경변수 적용 필수.**

**진행 경로 두 가지 (향후 재시도 시)**:
- **A. PR 브랜치 즉시 빌드**: clone → PR #1077 head 체크아웃 → Docker로 aarch64
  엔진 컴파일(테스트플랜 기준 54MB AArch64 ELF, archs [121]) → 실동작. 다만 #1306
  미완성 리스크 잔존.
- **B. 머지 대기 (선택)**: 유지자가 매우 활발(10일 만에 v0.1.36→v0.1.42).
  v0.1.43~ 에 GB10 포팅 포함될 가능성 높으나 ETA 없음.
  #1306에 머지 일정 확인 요청하는 것이 유일한 진행 수단.

**원문 §6 단계 A 정정**: `./setup.sh` 단독 실행은 불가(x64 고정) —
**PR #1077 체크아웃 + Docker 빌드** 경로로 변경 필요.

## 10. 모델 파일 — 원문 §2/§6-B 정정

- Strata 공식 추천 모델은 **ISTA-DASLab GSQ-RCO GGUF** (Q2_0 66GB / IQ2_XS 68 /
  IQ3_XXS 76GB). 원문 §6-B의 "66-76GB 신규 HF 다운로드"는 이 계열.
- 디스크에 이미 존재하는 모델: **Unsloth UD-IQ3_XXS (77GB)**
  (`/home/joons/models/UD-IQ3_XXS/`) + MTP Q8_0 (2.7GB) — **별개 파일**.
- **재사용 가능성**: PR #1077은 `UD-IQ4_XS`를 사용 → Strata의 `--gguf-dir`
  옵션으로 기존 Unsloth GGUF 재사용 가능할 것으로 보임. 성공 시 신규
  66~76GB 다운로드 불필요 (실행 전 해당 버전 setup.py에서 `--gguf-dir`
  지원 여부 재확인 필요).
  ⚠️ **2026-10-11 변경**: 재사용 예정이던 `UD-IQ3_XXS`(77GB)·MTP(2.6GB)·
  `UD-Q4_K_XL`(104GB) **모두 삭제됨**(사용자 지시) → Strata 재시도 시
  **신규 모델 다운로드 필수**(GSQ-RCO 또는 Unsloth 계열, 66~104GB).
- **결정(사용자)**: llama.cpp 구동 계획은 없음. 11538 시도는 "최신 버전으로
  빌드해서 시도해도 동작 안 함" — llama.cpp 경로는 폐기.
  (참고: journal 실측으론 llama-server-38은 모델 로드 단계에서 실패한 이력만
  존재 — `tensor 'token_embd.weight' not found`, 재시도 165회. 당시 빌드가
  9/17 커밋이었고 Qwen3.8-Flash-Next의 새 텐서 레이아웃 미지원이 원인.)

## 11. 11538(llama.cpp) 정리 대상 — 삭제 예정

11538은 폐기 확정. **2026-10-11 정리 완료** (아래 목록 수행):

| 대상 | 상태 | 조치 |
|---|---|---|
| `llama-server-38.service` | static, 미가동 | ✅ 삭제 |
| `llama-proxy-38.service` | enabled, 실행 중(11538 보유) | ✅ disable + stop + 삭제 |
| `~/llama-proxy/proxy38.py` | — | ✅ 삭제 |
| llama-monitor `config.yaml` (flash-next 카드) | — | ✅ 삭제 (비고 주석만 유지) |
| llama-monitor `app.py` fallback journal_unit | `llama-server-38`(잘못된 참조) → `llama-server-34` | ✅ 수정 |
| Hermes 프로파일 참조 | **없음** (확인) | — |
| 포트 11538 | python3(pid 2392) LISTEN | ✅ 해제 확인 |
| `/home/joons/models/UD-IQ3_XXS`(77GB) + `MTP/...-Q8_0`(2.7GB) | — | ✅ **2026-10-11 삭제** (사용자 지시) + `UD-Q4_K_XL`(104GB)도 동시 삭제 |

## 12. 원문 오류 정정 및 누락 사항

**문서 오류 (원문 그대로 두고 여기만 정정 기록):**
1. 원문 L40: Anthropic 호환 엔드포인트는 `/anthropic/v1`이 아니라
   **`POST /v1/messages`** (README 확인).
2. 원문 §3/§5-1의 "11538 inactive": 실제로는 **모델 로드 자체 실패로 정상 가동
   이력 0** (journal 확인, §10 참고).

**Strata 한계 (Hermes 에이전트 워크로드 관련, 원문에 없음):**
1. **대화 캐시 없음 (v1 한계)**: 매 요청마다 프롬프트 전체 재처리.
   벤치 기준 128K 프롬프트 ≈ 4분 TTFT. Hermes 세션(긴 컨텍스트)에서는
   턴당 지연이 큼 → **시험 목적 한정** 전제 필요.
2. **동시 1 요청 + greedy 전용 (temperature 무시)**: 병렬 도구 호출이 많은
   에이전트 워크로드에서 직렬 병목.
3. **동시성/멀티 컨버세이션**: same-conversation 체크포인트·parking은 1GPU에서
   동작하나 `--layer-split`(멀티 GPU)과 조합은 현재 거부(Issue #747) — GB10은
   1GPU라 해당 없음.

## 13. 향후 재시도 시 체크리스트 (대기 중)

- [ ] 릴리스 노트에서 **aarch64/GB10 포팅 머지** 여부 확인 (v0.1.43~)
  - 확인 시: setup.py가 aarch64를 인식하는지 먼저 확인 (PR #1077 머지 여부)
- [ ] GB10 구동 시 `STRATA_STAGER_THREADS=4` 적용 (Issue #1056)
- [ ] 모델: 재사용 재료 삭제됨(§10) → **신규 다운로드 필수** (GSQ-RCO 66~76GB 또는
  Unsloth 계열, NVMe free 480GB 여유)
- [x] 11538 정리(§11) — 2026-10-11 완료 (Strata 재시도 전 수행)
- [ ] OOM 관리(원문 §5-2)는 유효: 통합 메모리 121GB에서 27b(×2, keep ON) +
  Strata expert cache(약 55GB)가 경쟁 → Strata load 전 keep OFF

## 14. 추가 검토: GB10 실측 결과 수집 (2026-10-11 웹 조사)

공식 PR #1077(§9) 외에 **커뮤니티 GB10 포크 2건**에서 Strata 실측이 확인됨.
GB10에서 Strata는 SGLang과 동급~우위 속도로 이미 실동작하는 상태.

### 14.1 포크 A: `eelgaev/Strata-AC922` (가장 성숙)
- IQ2_XS + **UD-Q4_K_XL** 설치 테스트, llama-benchy 3회 반복(128K, `--kv int8`)

| Prompt | Prefill | Decode | MTP 수용률 |
|---|---|---|---|
| 2K | 928 tok/s | 58.7 tok/s | 78% |
| 8K | 1,356 tok/s | 62.0 tok/s | 81% |

- 전 expert GPU 캐시(IQ2_XS 33GiB / UD-Q4_K_XL 71.7GiB) → 통합메모리 특화
- `--mmap-experts` 필수 (RAM 아레나 기본값은 expert 이중 카피 → GB10에서 금지)
- 캐시 크기: `MemAvailable` - 6GiB 기준 자동(`STRATA_UMA_HEADROOM_GIB=N` 조절)
- KV streaming 비활성 (VRAM/RAM 분리 전제라 GB10에서 의미 없음)
- 설치: `./setup.sh`가 엔진 로컬 컴파일 (CUDA 13 + `-march=armv8.6-a+dotprod+i8mm+fp16`
  — gcc `-mcpu=native`는 GB10 ARM 기능 못 찾음, 명시 지정 필요)
- 문서: `docs/DGX_SPARK.md`, "experimental, community-tested on one Spark" 표기
- ⚠️ **UD-Q4_K_XL = 2026-10-11 삭제한 104GB 모델** — 재시도 시 이 포크를 쓰면
  해당 모델 재다운로드(또는 GSQ-RCO 계열) 필요

### 14.2 포크 B: `shi3z/Strata-DGX-Spark`
- ASUS GX10(=DGX Spark 동일 칩), 엔진 0.1.38, **IQ3_XXS + 비전(이미지) ON, 131K 컨텍스트**
- decode **38~42 tok/s** (6K~75K 프롬프트 무관하게 안정)
- prefill 1,196~1,338 tok/s (긴 프롬프트 기준)
- ⚠️ 단점: **짧은 프롬프트(1.5K/431) prefill 20배 느림**(56~61 tok/s) — 원인 미상
- 설치: `./setup.sh --family qwen --model IQ3_XXS --vision gpu --no-start`,
  디스크 85GB 필요, 엔진+image encoder 로컬 컴파일(최초 수십 분)
- `run-iq3_xxs.sh`로 기동 → `http://127.0.0.1:8080/v1` (OpenAI/Anthropic 호환)

### 14.3 비교 기준 (동일 GB10, 다른 엔진)
| 구성 | Decode |
|---|---|
| SGLang + NVFP4 (단일 GB10, code/math) | 47.9 tok/s |
| **Strata 포크 A (IQ2_XS, MTP 81%)** | **58.7~62 tok/s** |
| Strata 포크 B (IQ3_XXS+비전) | 38~42 tok/s |
| vLLM NVFP4 (듀얼 Spark TP2) | 99 tok/s |

### 14.4 해석
- **Strata GB10 동작은 기술적으로 확정** — 포팅 자체의 리스크는 낮음.
  남은 변수는 공식 머지 타이밍(§9, Issue #1306 open)뿐.
- 포크 A(8K prefill 1.3K tok/s)는 §12-1의 "128K ≈ 4분 TTFT"를 반박:
  GB10+포크 환경에서는 prefill이 충분히 빠름 → Hermes 긴 컨텍스트 워크로드
  부담이 원문 벤치(x86 PC)보다 작을 가능성.
- 포크 B의 짧은 프롬프트 prefill 저하는 Hermes 대화(매 턴 새 요청)에 직접
  영향 → 포크 B 선택 시 Issue #1056(`STRATA_STAGER_THREADS=4`)과 함께 관찰 필요.
- 공식 머지 전 선택지는 (a) 계속 대기 / (b) 포크 A 즉시 시도 — 사용자 결정 대기.
