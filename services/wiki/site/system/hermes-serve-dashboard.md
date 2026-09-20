# Hermes serve / dashboard 분리 (2026-09 업데이트)

[summary] 9/16 업데이트로 `hermes serve`(데스크톱 브릿지, 헤드리스)와 `hermes dashboard`(브라우저 웹UI)가 **서로 다른 프로세스**로 분리됨. serve는 더 이상 브라우저 UI를 서빙하지 않음. 브라우저 접속은 9120 포트.

## 1. 목적인가? — 왜 이 문서가 생겼나

2026-09-18(목) 아침, `http://192.168.219.115:9119/` 접속 시 다음과 같은 JSON 404가 반환됨:

```json
{"error":"Headless backend (hermes serve): web UI disabled — use `hermes dashboard` for the browser UI."}
```

리부팅 한 번으로 "제대로 되던 대시보드"가 죽었고, **업데이트가 이 구조 변경을 가져와도 어떤 알림도 없었음**.
이 페이지는 ① 새 구조를 이해하고, ② 같은 사고가 재발하지 않도록 systemd로 고정하고, ③ 진단 절차를 남기는 것.

## 2. 구조 변경 (before / after)

```
[Before — 2026-09-16 업데이트 이전]

  ┌────────────────────────────┐
  │ hermes serve  :9119        │  ← 하나면 됐음
  │  · 웹UI (브라우저 SPA)     │
  │  · 데스크톱 앱 JSON-RPC    │
  └────────────────────────────┘
  브라우저 http://192.168.219.115:9119/ ✓
  데스크톱 앱 (브릿지)            ✓

[After — 업데이트 이후]

  ┌────────────────────────────┐   ┌────────────────────────────┐
  │ hermes serve  :9119        │   │ hermes dashboard  :9120    │
  │  · 헤드리스 (headless)     │   │  · 브라우저 웹UI (SPA)     │
  │  · 데스크톱 앱 전용 브릿지 │   │  · API/설정 관리           │
  │  · 브라우저 접근 = 404     │   │  · dashboard.basic_auth    │
  └────────────────────────────┘   └────────────────────────────┘
  브라우저 → :9119 ✗ (404 JSON)        브라우저 → :9120 ✓
  데스크톱 앱 → :9119 ✓
```

**핵심 인과관계**: `hermes serve`가 헤드리스 전용으로 변경되면서, 리부팅 시 systemd가 serve만 자동 기동 → 브라우저 UI 프로세스(dashboard)는 부활하지 않음 → 9119 접속이 죽음.

## 3. 현재 운영 구성 (GB10, 2026-09-18 기준)

| 항목 | 값 |
|---|---|
| serve (데스크톱 브릿지) | `hermes-serve-9119.service` — `0.0.0.0:9119` |
| dashboard (브라우저) | `hermes-dashboard-9120.service` — `0.0.0.0:9120` |
| 브라우저 접속 주소 | **`http://192.168.219.115:9120/`** |
| 인증 | `dashboard.basic_auth` (config.yaml) — 사용자 `joons` |
| 부팅 자동 기동 | 둘 다 systemd user service, `Requires=llama-server-38.service` |

### dashboard 유닛 (`~/.config/systemd/user/hermes-dashboard-9120.service`)

```ini
[Unit]
Description=Hermes browser dashboard (hermes dashboard, port 9120)
After=network-online.target llama-server-38.service
Requires=llama-server-38.service

[Service]
Type=simple
WorkingDirectory=/home/joons/.hermes
Environment=HOME=/home/joons
Environment=PATH=/home/joons/.hermes/hermes-agent/venv/bin:...
ExecStart=/home/joons/.hermes/hermes-agent/venv/bin/python \
          /home/joons/.hermes/hermes-agent/hermes dashboard --host 0.0.0.0 --port 9120 --no-open
Restart=on-failure
RestartSec=10
KillSignal=SIGINT
TimeoutStopSec=30

[Install]
WantedBy=default.target
```

설치/관리:

```bash
systemctl --user enable --now hermes-dashboard-9120   # 기동+부팅 등록
systemctl --user status hermes-dashboard-9120          # 상태
systemctl --user stop hermes-dashboard-9120            # 정지
```

## 4. 함정 (실전 경험)

1. **`hermes update`가 구조 변경을 무음으로 적용함**
   - 업데이트(9/18 02:31 코드 스왑)가 들어오고도, 이미 돌던 구코드 프로세스는 계속 서빙 → "아직 멀쩡하다"는 착시.
   - 리부팅 시점에야 systemd가 **새 코드의 serve만** 기동하면서 사고가 표면화.
   - `~/.hermes/logs/update_receipts/`는 **비어있어** 사후 확인 불가.
   - 교훈: `hermes update` 직후에는 **리부팅 없이도** `hermes dashboard --status`로 실행 중인 서빙 프로세스를 확인해야 함.

2. **serve = 헤드리스는 의도된 설계**
   - `hermes_cli/web_server_dashboard.py::mount_spa()` — `HERMES_SERVE_HEADLESS=1`이면 어떤 경로도 SPA를 주지 않음 (JSON 404만).
   - 즉 "9119에서 웹UI를 켜는 옵션"은 **없음**. 브라우저 UI는 반드시 `hermes dashboard` 프로세스.

3. **인증은 `--insecure`가 아님**
   - `hermes dashboard --insecure`는 2026-06 보안 강화 이후 **무효화**됨 (DEPRECATED/NO-OP).
   - LAN 접속은 `dashboard.basic_auth`(config.yaml)의 scrypt 해시 인증을 거침 — 이미 설정되어 재사용.
   - 로그인 로그: `~/.hermes/logs/dashboard-auth.log`.

4. **수동 기동(`nohup`/터미널)은 리부팅에 취약**
   - 처음 9120을 터미널 배경 프로세스로 띄웠으나, 이 방식은 **리부팅 후 사라짐**.
   - 반드시 systemd user service로 고정할 것 (본 문서 2절).

## 5. 진단 절차 (접속 안 될 때)

```bash
# 1) 포트 누가 켜고 있는가
ss -tlnp | grep -E '9119|9120'

# 2) 서빙 프로세스 현황
hermes dashboard --status     # [serve] / [dashboard] 프로세스 목록

# 3) dashboard가 죽었는가
systemctl --user status hermes-dashboard-9120

# 4) revive
systemctl --user start hermes-dashboard-9120

# 5) 검증
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://127.0.0.1:9120/
#   → 302 /login?next=%2F  = 정상 (기본 인증 ON)
#   → 200 /login           = 로그인 페이지
#   → 404 + JSON error     = serve(헤드리스)에 접속한 것 → 포트/호출 대상 오인
```

## 6. 참고

- 변경 발발일: 2026-09-18 (코드 스왑은 09-18 02:31, 빌드 `64ea66b` = 2026-09-16)
- 이전 주소 `:9119`는 이제 데스크톱 앱 브릿지 전용 — 브라우저에서 접속하면 JSON 404.
- 관련: `system/hermes-agent-backend` (백엔드 개요), `profiles/*` (프로파일).
