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

## 9. 관련 문서

- [Ollama Status Monitor](/p/ollama-monitor/monitor)
- [llama.cpp 서버 (Ollama 전환)](/p/system/llama-cpp-setup)
- [다중 모델 서빙](/p/system/ollama-multimodel)
