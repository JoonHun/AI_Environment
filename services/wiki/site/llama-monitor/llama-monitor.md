# llama.cpp Status Monitor

[summary] `ai top atom`의 llama.cpp 다중 인스턴스(11534~11537) 추론 상태를 웹으로 보여주는 Flask 대시보드(포트 5002) — 1 포트 1 모델 1 카드, idle/prefill/decode 스테이지, token/s, MTP, hang 감지.

## 1. 개요

| 항목 | 값 |
|---|---|
| 위치 | `/home/joons/.hermes/services/llama-monitor/` |
| 포트 | **5002** (ollama-monitor 5000, wiki 5001과 분리) |
| 스택 | Flask + waitress + requests + pyyaml |
| 접근 | LAN — `192.168.219.115:5002` |
| 기동 | systemd user 서비스 (`llama-monitor.service`) |
| 대상 | 4개 llama-server (11534 상시 + 11535~11537 온디맨드) |

> 💡 **ollama-monitor와의 차이:** Ollama은 단일 포트에 모델 스왑이라 "Live Tokens + Loaded models" 2카드.
> llama.cpp는 **포트 1개 = 모델 1개** 고정이라 **1 포트 = 1 통합 카드**(모델 + 상태 + 토큰을 한 화면에서).

## 2. 화면 구성 (상단 → 하단)

| 구역 | 내용 |
|---|---|
| 헤더 | 타이틀 · 전체 상태 점 · Last Updated |
| 시스템 1줄 | [CPU] [GPU] [Memory] [Storage] (grid-4) |
| Trend | GPU util % · RAM GB · CPU % (Chart.js 라인, 15s 갱신) |
| 서버 카드 ×4 | 11534 → 11537 (config 순서, 풀폭 1줄 1개) |

> ✅ **레이아웃 원칙:** 헤더·시스템·Trend는 **절대 고정**, **서버 카드 영역만 내부 세로 스크롤**
> (`body h-screen overflow-hidden`, `#servers flex-1 overflow-y-auto`). 페이지 스크롤 0.

## 3. 서버 카드 구성 (1 포트 1 카드 — 핵심)

```
┌──────────────────────────────────────────────────────────────────┐
│ 11534   Resident   qwen3.8-27b-mtp-q4_K_M.gguf    [Idle][Prefill][Decode] │
│ ┌────────────┬────────────┬────────────┬────────────┐           │
│ │  Prompt    │  Decode    │  3s avg    │  Generated │           │
│ │  522 t/s   │  21 t/s    │  17 t/s    │  154 tok   │           │
│ └────────────┴────────────┴────────────┴────────────┘           │
│  last: prompt 24 tok · 20.9 t/s · 282 tok     MTP 80% · 2.60    │
│  2026-09-10 16:37:42                                            │
└──────────────────────────────────────────────────────────────────┘
```

| 구역 | 내용 | 필드 |
|---|---|---|
| 헤더 | 포트 · mode(`Resident`/`standby`) · 모델이름(basename) · 스테이지 스테퍼 | `port, mode, model, stage` |
| 4칸 stats | Prompt t/s · Decode t/s · 3s avg t/s · Generated tok | `prompt_tps, tps, 3s_tps, tokens` |
| MTP + last | 직전요약(좌) · MTP 채택률/mean(우) 1줄 | `last_task, mtp` |
| 푸터 | 마지막 로그 시각(항상) · hang/err 경고 | `last_seen, hang, error` |

## 4. 스테이지 판정 (idle / prefill / decode)

```
per server:
  if not up:            state = "down"  (on-demand면 "standby" — 정상)
  elif any slot is_processing:
       stage = "decode"  (journal n_gen 진행이 권위)
       else stage = "prefill"
  else:                 stage = "idle"
  stale = (now - last_seen) > threshold
  hang  = stage == "decode" and stale
```

> ⚠️ **이 build의 `/slots` 특이사항:** `n_prompt_tokens`가 **decode 중에도 계속 증가**하고
> `n_prompt_tokens_processed`는 prefill 길이에서 멈춘다. 그래서 **prefill/decode 구분은
> API가 아닌 journal의 `n_gen` 진행이 권위** (decode 시작 3초마다 `n_gen` 출력, prefill에선 없음).

> ⚠️ llama.cpp엔 `all slots are idle` 마커가 **없다** (Ollama 특화) — idle은 `/slots`로.

## 5. API 엔드포인트

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/health` | `{status, ts, servers_up, servers_total}` (항상 200) |
| `GET /api/status` | 시스템 메트릭 (CPU/GPU/RAM/Storage) |
| `GET /api/servers` | **서버 목록** — 각 서버 상태+모델+토큰 (카드 1차 소스) |
| `GET /api/history` | 시스템 추이 (링 버퍼, ≤240점) |

## 6. `config.yaml` (서버 목록)

```yaml
port: 5002
sample_interval_sec: 3
servers:
  - { port: 11534, mode: resident,  journal_unit: llama-server-38 }
  - { port: 11535, mode: on-demand, journal_unit: llama-server-36 }
  - { port: 11536, mode: on-demand, journal_unit: llama-server-38q8 }
  - { port: 11537, mode: on-demand, journal_unit: llama-server-gemma }
```

> 💡 **on-demand standby:** backend off는 **정상**(`standby`) — down으로 오인 금지.
> proxy가 idle 10분 후 자동 stop하므로 "down"이 정상 상태일 수 있다.

## 7. 용량 단위 (GB, 소수 2자리)

| 항목 | 계산 |
|---|---|
| RAM | `/proc/meminfo` "kB"는 실체 **KiB(1024B)** → `kB*1024/1000³` |
| Storage | `shutil.disk_usage('/')` (true bytes) `÷1000³` |

> 💡 GB10 통합메모리: `MemTotal=125,439,980 kB` → **128.45 GB** (`free -b /1000³`과 일치).

## 8. systemd user 서비스

```ini
# ~/.config/systemd/user/llama-monitor.service
[Unit]
Description=llama.cpp Status Monitor (port 5002)

[Service]
Type=simple
WorkingDirectory=/home/joons/.hermes/services/llama-monitor
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/joons/.hermes/services/llama-monitor/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now llama-monitor
systemctl --user restart llama-monitor      # 재기동
```

> ⚠️ **`pkill -f` 금지** — 문자열이 shell 자신을 포함해 자기 종료. `systemctl --user restart` 사용.
> ⚠️ **ollama-monitor(5000)은 건드리지 말 것.** 이 서비스는 5002 전용.

## 9. 함정 — `backend_port`가 프론트(port)여야 모델이 안 깨어남

**사건 (2026-09-20):** 11534 카드가 `backend_port: 11534`(프론트) + `mode: resident`로 설정되어 있었다.
llama-monitor는 **모든 카드를 `backend_port`로 HTTP probe**(`GET /health`, `GET /v1/models`, `GET /slots`)한다.

```
llama-monitor → 11534(프론트/proxy) → GET /health
  → proxy는 standby면 자체 200 응답 (backend 안 깨움)
  → proxy는 active면 backend(1534)로 전달 (llama-server 깨움)
```

**`backend_port`를 `1534`(백엔드)로 바꾸면:**
```
llama-monitor → 1534(llama-server) → GET /health
  → llama-server가 직접 응답 (모델 로딩 = GPU 점유)
```

**결과:** `backend_port: 1534`로 바꾼 후 llama-monitor의 probe가 **llama-server를 주기적으로 깨워서**
idle 300초 watchdog이 stop해도 30초 내 재기동 → **GPU 88% 유지, 모델이 메모리에서 안 내려감.**

**원리:**
- `backend_port` = **프론트(1153x)** → probe는 proxy가 처리 → standby면 backend 안 깨움 ✓
- `backend_port` = **백엔드(153x)** → probe가 llama-server 직접 도달 → **모델 깨움** ✗

**원칙: on-demand 카드의 `backend_port`는 반드시 프론트 포트(1153x)여야 한다.**
백엔드 포트(153x)로 설정하면 monitor probe가 모델을 깨워서 idle stop이 무력화된다.

> ⚠️ **config.yaml 수정 전 반드시 확인:** `backend_port`가 프론트(1153x)인지 백엔드(153x)인지.
> on-demand 서버는 **프론트 포트**여야 한다. 백엔드 포트로 바꾸면 monitor probe가 모델을 깨운다.

## 10. Force Unload 버튼 (사용자 편의성)

**동기:** 11534는 `backend_port`를 프론트로 설정해서 monitor probe가 모델을 깨우지 않도록 했다.
그렇다 보니 **watchdog의 300초 idle 타이머가 유일한 자동 종료 경로**가 되는데,
"지금 당장 모델을 내리고 싶다"는 시나리오에 5분을 기다릴 이유가 없다.

**해결:** 각 모델 카드에 `↓ Unload` 버튼을 추가.

```
┌──────────────────────────────────────────────────────────────────┐
│ 11534   IDLE   On-demand   qwen3.8-27b...  [Idle][Prefill][Decode] │
│  ↓ Unload                                                    ← 빨간색(로딩 중) │
│  ...stats...                                                    ← 회색(standby) │
└──────────────────────────────────────────────────────────────────┘
```

**동작:**
```
클릭 → POST /api/unload {"port": 11534}
     → systemctl --user stop llama-server-34
     → 모델 RAM 해제 (27.7GB → 0)
     → GPU 0%

재요청 → proxy34 standby → systemctl start llama-server-34 → 모델 로딩 → 정상 응답
```

**버튼 색 규칙 (자동 갱신, 2초 주기):**

| 모델 상태 | 버튼 색상 | 의미 |
|-----------|-----------|------|
| 로딩 중 (idle/busy/prefill/decode) | **빨간색** (`text-red-400`) | 클릭하면 즉시 해제 |
| standby / down / degraded | **회색** (`text-slate-600`) | 이미 안 올라가 있음 |

**구현:**
- `app.py`: `POST /api/unload` 엔드포인트 — `config.yaml`의 `journal_unit`으로 `systemctl --user stop`
- `index.html`: `forceUnload(port, btn)` 함수 — 버튼 클릭 → API 호출 → 성공 시 `✓ unloaded` 표시 (3초 후 복귀)
- confirm 다이얼로그 없음 — 즉시 실행

**API:**
```bash
curl -X POST http://127.0.0.1:5002/api/unload \
  -H 'Content-Type: application/json' \
  -d '{"port": 11534}'
# → {"action":"stopped","port":11534,"status":"ok","unit":"llama-server-34"}
```

> 💡 **on-demand 관리 3중 체계:**
> 1. **자동:** 300초 idle → watchdog `systemctl stop` (기본)
> 2. **수동:** `↓ Unload` 버튼 → 즉시 `systemctl stop` (사용자 편의)
> 3. **재로딩:** 다음 요청 → proxy 자동 `systemctl start` (투명)
>
> **monitor probe는 프론트(1153x)로만** — 백엔드(153x) probe 금지 (§9 함정).

## 11. 관련 문서

- [Ollama Status Monitor](/p/ollama-monitor/monitor)
- [llama.cpp 서버 (Ollama 전환)](/p/system/llama-cpp-setup)
- [다중 모델 서빙](/p/system/ollama-multimodel)
