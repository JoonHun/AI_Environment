# llama-monitor — 시스템 요구사항 문서

| 항목 | 내용 |
|---|---|
| 문서 버전 | 0.1 (초안) |
| 작성일 | 2026-09-10 |
| 대상 | `/home/joons/.hermes/services/llama-monitor` |
| 참조 | `ollama-monitor` (같은 구조·패턴을 재사용) |

---

## 1. 목적 및 배경

### 1.1 문제 정의

원격(다른 PC의 브라우저)에서 llama.cpp 서버(`llama-server`)에 추론 요청을 보내면,
응답이 돌아오기까지 **상태를 알 수 없다**.

> "요청이 동작 중인가, 추론(생성) 중인가, 아니면 그냥 멈췄(hang)는가?"

이 3가지를 **눈으로 즉시 구분**할 수 있는 대시보드가 필요하다.

### 1.2 설계 원칙 (ollama-monitor에서 검증된 패턴)

1. **캐시 서빙** — 백그라운드 스레드가 N초 주기로 샘플링 → API는 캐시만 서빙.
   느린 subprocess(nvidia-smi 등)가 API 응답을 절대 막지 않는다.
2. **stale 플래그** — 샘플이 최신이 아니면 UI에 "stale" 표시. 침묵(freeze) 대신
   "마지막 알려진 값 + 오래됨 표시"를 보여준다.
3. **상태머신 가시화** — `idle / loading / prefill / decode / error` 단계 중
   **현재 단계**를 스테퍼로 표시. 이것이 "추론 중인가 멈췄나"의 1차 판단 근거다.
4. **로그 파싱** — 클라이언트 협조 없이도 **어떤 클라이언트가든**의 추론 속도를
   llama.cpp의 stdout(journal)에서 읽어온다.
5. **모든 수집기는 예외를 삼켜야 한다** — 한 수집기 죽음이 서비스 전체를 죽이지 않는다.

---

## 2. 범위

### 2.1 In-Scope
- `llama-server` 프로세스의 생존/상태/버전 감지
- 실시간 추론 상태 (단계, 진행 토큰, prefill t/s, decode t/s)
- 직전 완료 요청의 요약 (소요시간, 토큰 수, t/s)
- GPU / CPU / RAM / Storage 시스템 메트릭 (GB10 통합메모리 대응)
- 추이 그래프 (링 버퍼 기반)
- 헬스체크 API (외부 왓독용)
- config.yaml 기반 설정, systemd user service

### 2.2 Out-of-Scope
- 추론 요청 자체의 생성/중단 (읽기 전용 대시보드)
- 다중 llama-server 인스턴스 관리 (단일 엔드포인트. 추후 확장)
- 인증/접근제어 (LAN 신뢰망 가정. speed-test 등 쓰기 엔드포인트에만 선택적 secret)

---

## 3. 용어

| 용어 | 정의 |
|---|---|
| **llama-server** | llama.cpp의 OpenAI 호환 HTTP 서버 (`llama-server` binary) |
| **slot** | llama-server의 동시 요청 처리 단위. `idle`/`busy` 상태 |
| **prefill** | 입력(prompt) 토큰 처리 단계 |
| **decode** | 생성 토큰 단계 (토큰 1개씩 순차 생성) |
| **stale** | 샘플/로그가 최신이 아님 (마지막 갱신 이후 N초 초과) |

---

## 4. 기능 요구사항 (Functional Requirements)

### FR-1. 서비스 상태 감지
- **FR-1.1** `llama-server`의 `/health` 엔드포인트를 폴링하여 up/down 판단.
- **FR-1.2** 서버 버전 정보 노출 (`/v1/models` 또는 `--version` 로그에서).
- **FR-1.3** down 상태일 때 UI 상단에 **빨간 배너 + 실패 사유** 표시.
- **FR-1.4** `up` 판단 기준: `/health`가 2xx를 반환할 때. timeout 초과 = down.

### FR-2. 추론 상태머신 (핵심)
- **FR-2.1** 현재 상태를 다음 중 하나로 분류:
  `idle` → `loading`(모델 로드 중) → `prefill`(입력 처리) → `decode`(생성 중) → 완료/`idle`
- **FR-2.2** 상태 판정 소스 (우선순위순, **검증됨**):
  1. **`GET /slots` API** — `is_processing`(바쁨/가끔) + `n_prompt_tokens_processed`
     vs `n_prompt_tokens`(prefill 진행량)으로 idle/prefill/decode 판정. **1차, 가장 견고.**
  2. journal 로그의 `launch_slot_`(시작) / `release`(종료) 마커 시퀀스 — **2차**, 속도 수치
  3. `model eval time` / `prompt eval time` 완료 라인 — **요약 수치**
  - ⚠️ llama.cpp엔 `all slots are idle` 마커가 **없다** (Ollama 특화) — idle은 `/slots`로.
  - 상세: [log-format.md](log-format.md)
- **FR-2.3** UI에 **3~4단계 스테퍼**로 현재 단계 강조 (ollama-monitor와 동일 UX).
- **FR-2.4** **hang 감지**: `decode` 상태에서 마지막 로그/토큰 갱신 후 N초(기본 10s)
  경과 시 UI에 "⚠ 응답 없음 — 멈췄을 수 있음" 경고 (stale 기반).

### FR-3. 실시간 토큰 속도
- **FR-3.1** journal에서 파싱 (**정규식 검증됨**, 상세 log-format.md):
  - prefill: `prompt eval time = X ms / N tokens ( ... Y tokens per second )`
  - decode: `eval time = X ms / N tokens ( ... Y tokens per second )` — ⚠️ `(?<!prompt )` lookbehind 필수
  - 진행중: `n_gen = N, tg = X t/s, tg_3s = Y t/s` (3초마다, Ollama와 동일 포맷)
  - MTP: `draft acceptance = A ( X accepted / Y generated), mean len = Z` — **Ollama 형식과 다름**
- **FR-3.2** 노출: prefill t/s + 입력 토큰 수, decode t/s + 생성 토큰 수, MTP 채택률/mean len.
- **FR-3.3** 폴링 주기 3초 (llama.cpp 로그 리듬과 동기).
- **FR-3.4** `last_seen` 타임스탬프 + stale 플래그 포함.

### FR-4. 요청 히스토리
- **FR-4.1** 직전 완료 요청 N개(기본 10개) 저장:
  시작/종료 시각, prompt 토큰, 생성 토큰, prefill t/s, decode t/s, 총 소요시간.
- **FR-4.2** `GET /api/requests`로 JSON 서빙. UI 테이블로 표시.
- **FR-4.3** 링 버퍼(데크)로 무한 성장 방지.

### FR-5. 시스템 메트릭
- **FR-5.1** GPU: util %, 온도, power (nvidia-smi), **프로세스별 VRAM**
  (`--query-compute-apps` — GB10 통합메모리 대응), llama-server PID 식별.
- **FR-5.2** CPU: util % (`/proc/stat` 델타), 최고 온도 (thermal_zone), 코어 수.
- **FR-5.3** RAM: total/used/available GiB (`/proc/meminfo`) — GB10에서 실질 VRAM 상한.
- **FR-5.4** Storage: 실제 파일시스템별 used/free GiB (`/proc/mounts` + `shutil.disk_usage`).
  가상 fs(/proc, /sys, tmpfs, snap 등) 필터.

### FR-6. 추이 그래프
- **FR-6.1** 링 버퍼(기본 1800점, 2초 주기 ≈ 1시간)로 GPU util % / RAM GB / CPU % 저장.
- **FR-6.2** `GET /api/history` (240점 이상이면 다운샘플).
- **FR-6.3** Chart.js 라인 차트, 15초 주기 갱신.

### FR-7. 헬스체크
- **FR-7.1** `GET /api/health` → `{status: ok|stale|initializing, ts, server_up}`.
- **FR-7.2** 200을 항상 반환 (왓독이 HTTP 에러로 오해하지 않게).
- **FR-7.3** 외부 cron/왓독이 이 엔드포인트만으로 "대시보드 자체" 생존을 판단.

### FR-8. 설정
- **FR-8.1** `config.yaml` (ollama-monitor와 같은 키 체계):
  `host`, `port`, `sample_interval_sec`, `history_points`,
  `http_timeout_sec`, `gpu_cmd_timeout_sec`, `log_*`, `live_token_poll_sec`,
  `live_token_tail_lines`, `stale_threshold_sec`, `speed_test{}`.
- **FR-8.2** `config.yaml` 부재 시 내장 기본값 사용 + 경고 로그.
- **FR-8.3** deep-merge로 부분 오버라이드 허용.
- **FR-8.4** **서버 목록** (다중 인스턴스, 카드 순서 = 목록 순서):
  ```yaml
  servers:
    - port: 11534
      label: joons
      mode: resident          # resident | on-demand
      journal_unit: llama-server-38
    - port: 11535
      label: coding
      mode: on-demand
      journal_unit: llama-server-36
    - port: 11536
      label: fallback
      mode: on-demand
      journal_unit: llama-server-38q8
    - port: 11537
      label: english
      mode: on-demand
      journal_unit: llama-server-gemma
  ```
  - `mode: on-demand` 서버는 `up==false`를 **standby**(정상)로 처리, down으로 안 표시.
  - 각 서버의 journal unit이 달라야 로그를 서버별로 분리 파싱할 수 있다.

### FR-9. 서비스 운영
- **FR-9.1** systemd **user** service, `Restart=always`, `RestartSec=3`.
- **FR-9.2** venv 격리 (`venv/bin/python app.py`).
- **FR-9.3** 로테이팅 로그 (`RotatingFileHandler`, 1MB × 3).
- **FR-9.4** 포트 기본 **5002** (ollama-monitor 5000, wiki 5001과 충돌 방지 — 2026-09-10 포트 점유 확인).

### FR-10. 속도 테스트 (선택)
- **FR-10.1** `POST /api/speed-test` — 실제 N토큰 생성 후 t/s 실측 (ollama-monitor 동일).
- **FR-10.2** secret 헤더(`X-Monitor-Secret`) 선택적 인증.
- **FR-10.3** t/s는 서버가 보고한 stats로만 계산, **가짜 수치 생성 금지**.

---

## 5. 데이터 소스

| 소스 | 사용 항목 | 접근 |
|---|---|---|
| `GET {server}/health` | up/down | HTTP, timeout 6s ✅ |
| `GET {server}/v1/models` | 버전, 모델명, 크기, n_params, ftype | HTTP ✅ |
| `GET {server}/slots` | slot 상태 (is_processing), prefill 진행량, id_task | HTTP ✅ **1차 상태 소스** |
| `GET {server}/metrics` | (선택) 토큰 카운터, 로드시간 | HTTP ❌ 501 (이 빌드 비활성) |
| `journalctl -u {unit}` | prompt/eval time, n_gen/tg, draft acceptance, launch/release | subprocess ✅ |
| `nvidia-smi` | GPU util/temp/power, 프로세스 VRAM | subprocess |
| `/proc/stat` | CPU util | 파일 읽기 |
| `/proc/meminfo` | RAM total/available | 파일 읽기 |
| `/proc/mounts` + `shutil.disk_usage` | Storage | 파일 읽기 + 라이브러리 |
| `/sys/class/thermal/` | CPU 온도 | 파일 읽기 |

> **다중 서버**: llama-monitor는 단일 서버가 아닌 **4개 인스턴스**를 추적한다
> (11534 상시 + 11535~11537 온디맨드/proxy). config에 서버 목록 + 각 journal unit.
> 온디맨드 서버는 proxy가 idle 10분 후 stop하므로 "down"이 정상 상태일 수 있음 —
> UI에서 "온디맨드(standby)"로 표시.

---

## 6. API 명세

> **원칙: 포트(서버) 단위.** Ollama가 1포트에 N모델을 스왑하는 것과 달리
> llama.cpp는 **포트 1개 = 모델 1개** 고정. 그래서 모든 추론 데이터는
> `server`(포트) 단위로 묶고, UI는 1 포트 = 1 카드로 렌더링한다.

| 메서드 | 경로 | 응답 | 비고 |
|---|---|---|---|
| GET | `/` | HTML 대시보드 | |
| GET | `/api/health` | `{status, ts, servers_up, total_servers}` | 항상 200 |
| GET | `/api/servers` | **서버 목록** — 각 서버의 상태+모델+토큰 (아래 schema) | UI 카드의 1차 소스 |
| GET | `/api/servers/{port}` | 단일 서버 상세 (동일 schema) | 카드별 갱신용 |
| GET | `/api/history` | `[{t, cpu, util, ram}]` | ≤240점, 시스템 추이 |
| GET | `/api/requests` | 최근 완료 요청 (서버별 포함) | FR-4 |
| POST | `/api/speed-test` | `{server, tokens, tps, load_sec, prompt_tps}` | secret 선택 |

### `GET /api/servers` 응답 (카드 = 1 항목)
```json
[
  {
    "port": 11534,
    "label": "joons",
    "mode": "resident",              // resident | on-demand
    "up": true,                      // /health 200
    "standby": false,                // on-demand 서버의 정상 standby (backend off)
    "model": "qwen3.8_27b-mtp-q4_K_M.gguf",
    "params": "27.3B",
    "quant": "Q4_K_M",
    "ctx": 131072,
    "vram_gib": 15.6,
    "state": "idle",                 // idle | prefill | decode | loading
    "stage": "idle",                 // 스테퍼용: idle | prefill | decode
    "active": false,
    "prompt_tokens": null,           // prefill 입력 토큰
    "prompt_tps": null,
    "decode_tokens": null,           // 생성 토큰 (진행중 누적 / 완료 final)
    "decode_tps": null,
    "mtp": { "acceptance": 0.69, "mean_len": 2.37, "acc": 770, "gen": 1122 },
    "session_tokens": null,          // 슬롯 컨텍스트 총량
    "last_task": {                   // 직전 완료 요청
      "task_id": 22774, "total_ms": 70429, "prompt_ms": 5107,
      "decode_ms": 65322, "prompt_tps": 522.3, "decode_tps": 20.35
    },
    "last_seen": "2026-09-10T00:46:30",
    "stale": false,                  // last_seen 이후 N초 초과
    "hang": false                    // decode 중 stale → true
  }
]
```

**상태 판정** (서버별, [log-format.md](log-format.md)의 검증 로직):
```
per server:
  if not up:                state = "down" (on-demand면 "standby")
  elif any slot is_processing:
       if n_prompt_processed < n_prompt_tokens: state = "prefill"
       else:                                     state = "decode"
  else:                     state = "idle"
  stale = (now - last_seen) > stale_threshold_sec
  hang  = state == "decode" and stale
```

---

## 7. UI 명세 (포트별 카드 레이아웃)

> **핵심 변화**: Ollama의 "Live Tokens + Loaded models" 2개 카드를
> **1 포트 = 1 통합 카드**로 바꾼다. 이유: llama.cpp는 포트가 곧 모델이므로
> "이 포트의 모델 + 그 상태 + 토큰"을 한 화면에서 함께 봐야 "멈췄나"를 판단할 수 있다.

### 7.1 화면 구성 (상단 → 하단)

```
┌────────────────────────────────────────────────────────────────────┐
│ 헤더: 타이틀 · 전체 상태 점 · Last Updated    [빨간 배너: down 시] │
├────────────────────────────────────────────────────────────────────┤
│ 1줄  │ [CPU]  [GPU]  [Memory]  [Storage]   ← 시스템 4카드 (grid-4) │
├────────────────────────────────────────────────────────────────────┤
│ 2줄  │ [ Trend : GPU util % · RAM GB · CPU % ]  ← 풀폭 차트        │
├────────────────────────────────────────────────────────────────────┤
│ 3줄  │ [ 11534 · joons · Qwen3.8-27B MTP  ]  ← 서버 카드 ×4        │
│ 4줄  │ [ 11535 · coding · Qwen3.6-35B     ]      (grid-1, 풀폭)     │
│ 5줄  │ [ 11536 · fallback · Q8_0          ]                        │
│ 6줄  │ [ 11537 · english · Gemma4 E4B     ]                        │
└────────────────────────────────────────────────────────────────────┘
```

### 7.2 시스템 카드 (1줄, 기존과 동일)
| 카드 | 내용 |
|---|---|
| CPU | util % 바 + 온도 + 코어 수 |
| GPU | util % 바 + 온도 + power (nvidia-smi) |
| Memory | used/free/total GiB 바 (GB10 통합메모리 = 실질 VRAM 상한) |
| Storage | used/free GiB 바 |

### 7.3 서버 카드 (2줄 이후, 1 포트 1 카드) — **핵심**

각 카드 = `GET /api/servers`의 1 항목. 카드 내부 구성:

```
┌──────────────────────────────────────────────────────────────────┐
│ 11534 · joons   [Qwen3.8-27B MTP · 27.3B Q4_K_M · ctx 128K]  ●   │
│  상태 스테퍼:  ( Idle ) → ( Prefill ) → ( Decode )   ← 현재=그린   │
│ ┌────────────┬────────────┬────────────┬────────────┐           │
│ │  Prefill   │  Decode    │  MTP       │  Session   │           │
│ │  522 t/s   │  20.4 t/s  │  69%       │  58,119    │           │
│ │  2,668 tok │  1,330 tok │  avg 2.37  │  ctx total │           │
│ └────────────┴────────────┴────────────┴────────────┘           │
│  직전 요청: 70.4s · last seen 00:46:30 · stale  ⚠hang 시 적색     │
└──────────────────────────────────────────────────────────────────┘
```

| 구역 | 내용 | 데이터 필드 |
|---|---|---|
| 카드 헤더 | 포트 · 라벨 · 모델 · 파라미터 · quant · ctx · **상태 점** | `port, label, model, params, quant, ctx, up/state` |
| **상태 스테퍼** | Idle → Prefill → Decode, 현재 단계 그린 강조 | `stage` |
| Prefill 셀 | t/s + 입력 토큰 | `prompt_tps, prompt_tokens` |
| Decode 셀 | t/s + 생성 토큰 | `decode_tps, decode_tokens` |
| MTP 셀 | 채택률 + avg/step (MTP 모델만) | `mtp.acceptance, mtp.mean_len` |
| Session 셀 | 컨텍스트 총 토큰 | `session_tokens` |
| 푸터 | 직전 요청 소요시간 · last seen · stale/hang 경고 | `last_task.total_ms, last_seen, stale, hang` |

**상태별 카드 색 (한눈에 "멈췄나" 판단):**
| 상태 | 카드 테두리/점 | 의미 |
|---|---|---|
| `idle` | 청록(slate/green) | 대기 중 — 정상 |
| `prefill` | **파랑** (스테퍼 Prefill 그린) | 입력 처리 중 — 정상 진행 |
| `decode` | **그린** (스테퍼 Decode 그린) | 토큰 생성 중 — 정상 진행 |
| `standby` | 회색(dim) | on-demand 서버 정상 대기 (backend off) |
| `stale`/`hang` | **적색** + "⚠ 응답 없음 — 멈췄을 수 있음" | decode 중인데 로그 무갱신 → **멈춤 의심** |
| `down` | 적색 + 사유 | 서버 unreachable |

> **판단 공식**: `decode`(그린) + fresh = **추론 중**.
> `decode`(적색) + stale = **멈췄다**. `standby`/`idle` = **대기**.

### 7.4 기타
- 스택: Tailwind(CDN) + Chart.js(CDN), 다크 테마 (`#0f172a`).
- 폴링: `/api/servers` 3s (카드 갱신), `/api/history` 15s (차트).
- XSS 방어: 모든 동적 텍스트 `escapeHtml`.
- **카드 순서**: config의 서버 목록 순서 (11534 → 11537).
- MTP 셀: 해당 서버가 MTP 모델이 아니면 "n/a"로 표시 (Gemma 등).

---

## 8. 비기능 요구사항 (Non-Functional)

| 구분 | 요구사항 |
|---|---|
| **성능** | API 응답 < 50ms (캐시 서빙). sampler 느려져도 API는 즉시. |
| **가용성** | 수집기 예외는 서비스 죽임 불가. `Restart=always`. journal 읽기 실패 시 `log_ok=false`만 표시. |
| **안정성** | 모든 subprocess `timeout` 필수. 데몬 스레드 사용 (프로세스 차단 방지). |
| **보안** | 쓰기 엔드포인트(secret)만 보호, 읽기 엔드포인트는 LAN 공개 허용. secret은 config에 평문. |
| **유지보수** | single-file `app.py` 유지 (ollama-monitor와 동일 스타일). 수집기 단위 함수 분리. |
| **관측** | 로테이팅 로그. `/api/health`로 자기 상태 노출. |
| **크로스 호환** | GB10 통합메모리: nvidia-smi `[N/A]` 대응, `/proc/meminfo` 병행. |

---

## 9. 가정 및 제약

1. `llama-server`는 **같은 머신(GB10)**에서 실행, journalctl 접근 가능.
2. 동시 모델 1개 (llama.cpp 기본 동작). 다중 모델 동시 로드 시 `/v1/models` 목록은
   표시하되 "active" 모델은 요청 로그로 추론.
3. Ollama와 llama.cpp는 **동시에** 동작할 수 있음 (포트 분리: ollama 11434,
   llama-server 11534~11537, monitor 5000(ollama)/5002(llama)).
4. 브라우저는 **monitor만** 접근, llama-server는 직접 접근하지 않음 (LAN 분리).

---

## 10. ollama-monitor와의 차이점

| 항목 | ollama-monitor | llama-monitor |
|---|---|---|
| 대상 | Ollama (Go 래퍼 + llama.cpp) | llama.cpp `llama-server` (원격 API) |
| 인스턴스 | **단일** 포트(11434)에 N모델 스왑 | **다중** 포트(11534~11537), 포트=모델 1:1 고정 |
| API | `/api/ps`, `/api/tags`, `/api/generate` | `/health`, `/v1/models`, `/slots`, `/v1/chat/completions` |
| 로그 | `journalctl -u ollama` | `journalctl -u llama-server-N` (서버별 unit 분리) |
| **카드 구조** | "Live Tokens" + "Loaded models" **2개 카드** | **포트별 통합 카드 ×4** (모델+상태+토큰 1카드) |
| 상태 소스 | journal만 (idle 마커로 판정) | **`/slots` API(1차)** + journal(2차) |
| 모델 unload | `expires_at` 자동 | on-demand: proxy idle 10분 자동 stop / 상시: 수동 |
| MTP stats | `#gen drafts/#acc drafts/#mean acc len` | `draft acceptance = X (A/B), mean len = Y` (형식 다름) |
| 포트 | 5000 | **5002** (5001은 wiki 사용 중) |

---

## 11. 인수 기준 (Acceptance Criteria)

- [ ] `http://192.168.219.115:5002` 접속 시 대시보드 렌더링
- [ ] llama-server down → 빨간 배너 + `/api/health` `status: stale`
- [ ] 원격에서 요청 전송 → **3초 내** 해당 포트 서버 카드의 스테퍼가 `prefill`→`decode` 전환
- [ ] 4개 서버 카드가 config 순서(11534→11537)로 각각 모델+토큰 표시
- [ ] on-demand 서버(11535~11537) backend off 시 `standby`(회색) 표시, down으로 안 표시
- [ ] 특정 포트 decode 중 10초 이상 로그 무갱신 → 그 카드만 적색 hang 경고
- [ ] 요청 완료 후 직전 요청 요약 (t/s, 토큰, 소요시간) 표시
- [ ] GPU 100% busy + decode 상태 → "추론 중" 판단 가능 (스테퍼 + GPU 바)
- [ ] GPU 0% + decode 상태 + stale → "멈췄다" 판단 가능
- [ ] `systemctl --user restart llama-monitor` 후 10초 내 자동 복구
- [ ] app.log가 1MB×3를 초과하지 않음

---

## 12. 구현 전 확인할 것 (Open Questions)

> **2026-09-10에 1~3번을 실제 llama-server(11534)로 검증 완료했다.**
> 상세: [log-format.md](log-format.md) — 정규식 검증 + `/slots` API + MTP 포맷.

1. ~~llama-server 버전/빌드 옵션~~ → **검증됨**: ggml-org/llama.cpp, `--spec-type draft-mtp --spec-draft-n-max 2`, `--ctx-size 131072`, 4 슬롯. MTP 스펙뎁 활성.
2. ~~로그 포맷 캡처~~ → **검증됨**: 진행/완료/MTP/시작/종료 라인 포맷 + 정규식 9종 전부 매칭 통과 (388줄 샘플).
   - ⚠️ `eval time` 정규식에 `(?<!prompt )` lookbehind 필수 (prefill 라인 오인별 방지)
   - ⚠️ llama.cpp엔 `all slots are idle` 마커가 **없다** — `/slots` API로 대체
3. ~~`/slots`, `/metrics` 존재 확인~~ → **검증됨**: `/slots` ✅ (실시간 상태), `/metrics` ❌ 501 (이 빌드엔 비활성, `--metrics`로 활성화 가능 — 선택)
4. **모델 unload 정책**: 대시보드에서 unload 버튼(POST)을 넣을지 — 온디맨드 서버는 proxy가 idle 10분 후 자동 stop하므로, **상시 서버(11534)만** unload가 의미 있음.
5. **다중 프로파일(Hermes) 요청 구분**: llama.cpp는 클라이언트 IP를 로그에 남기지 않음 — **슬롯 ID + task ID로만 구분** (클라이언트 식별 불가).

### 12.1 검증으로 확정된 설계 변경 (2026-09-10)
- **포트**: `5001` → **`5002`** (5001은 wiki 서비스에 사용 중)
- **다중 인스턴스**: llama-monitor는 단일 서버가 아닌 **4개 llama-server**(11534~11537)를 추적.
  config에 서버 목록 + 개별 journal unit 이름.
- **상태머신 1차 소스**: `/slots` API (`is_processing` + `n_prompt_tokens_processed`) —
  journal 파싱은 2차(속도 수치). Ollama-monitor의 "journal만" 방식보다 견고.
- **MTP 파서**: Ollama 형식(`#gen drafts`)과 **다름** — `draft acceptance = X (A accepted / B generated), mean len = Y`
