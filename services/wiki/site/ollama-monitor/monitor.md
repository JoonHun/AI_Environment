# Ollama Status Monitor

[summary] `ai top atom`의 Ollama GPU/VRAM 추론 상태를 웹으로 보여주는 Flask 대시보드(포트 5000) — 모델 로드, token/s, 컨텍스트, 프로세스.

## 1. 개요

| 항목 | 값 |
|---|---|
| 위치 | `/home/joons/.hermes/services/ollama-monitor/` |
| 포트 | **5000** |
| 스택 | Flask + waitress + `pynvml` |
| 접근 | LAN — `192.168.219.115:5000` |
| 기동 | systemd user 서비스 |

## 2. 화면 구성 (상단 탭)

| 탭 | 내용 |
|---|---|
| **GPU** | GPU 명/드라이버, VRAM 사용/전체, GPU util %, 온/습도, fan |
| **모델** | 로드된 모델, 파라미터, token/s, 컨텍스트, 메모리 점유 |
| **프로세스** | Ollama PID, Uptime, PID당 CPU/메모리 |
| **설정** | `config.yaml` 편집 (refreshtime, speed-test 길이/모델) |

## 3. API 엔드포인트

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/status` | GPU + 모델 로드 상태 (메인 뷰) |
| `GET /api/speed-test` | `config.yaml` 모델로 token/s 측정 |
| `POST /api/config` | `config.yaml` 저장 |

## 4. `config.yaml`

```yaml
update_interval: 5          # 초
speed_test_length: 128      # token 수
speed_test_models: "gemma4:26b"   # 공백 구분 (없으면 아무 모델)
```

## 5. token/s 측정 방식

```
prompt: "The quick brown fox jumps over the lazy dog. " (반복으로 길이 조절)
completion: (모델이 이어 쓰기)
측정: (완료 token 수) / (완료 시간)  →  token/s
```

> 💡 **Tip:** `speed_test_models`는 공백 구분. 지정 없으면 Ollama에 있는 아무
> 모델을 사용한다. `update_interval`은 화면 업데이트 주기(초).

## 6. systemd user 서비스

```ini
# ~/.config/systemd/user/ollama-monitor.service
[Unit]
Description=Ollama Status Monitor (port 5000)

[Service]
Type=simple
WorkingDirectory=/home/joons/.hermes/services/ollama-monitor
ExecStart=/home/joons/.hermes/services/ollama-monitor/.venv/bin/python app.py

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now ollama-monitor
```

> ⚠️ **linger:** 자동 기동을 위해 `loginctl enable-linger joons`이 활성화되어 있어야 한다.
> 없으면 로그인 세션이 끝나면 서비스가 종료된다.

## 7. 주의할 점

| 이슈 | 설명 |
|---|---|
| `waitress` 단일 스레드 | 동시 요청 많지 않은 모니터링용이라 충분 |
| `pynvml` | NVIDIA GPU만. GB10은 통합 메모리라 VRAM = 통합 RAM |
| `speed_test` | 측정 중에는 해당 모델이 Ollama에서 잠금 → 다른 요청 대기 |
| LAN 접근 | 포트 5000은 LAN에서 `192.168.219.115:5000`로 접속 가능 |

## 8. 관련 문서

- [Ollama 설치](/p/system/ollama-setup)
- [다중 모델 서빙](/p/system/ollama-multimodel)
- [원격 Hermes 접속](/p/system/remote-hermes)
