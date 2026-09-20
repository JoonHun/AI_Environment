# Hermes Agent 백엔드 설정

`[summary]` Gigabyte AI TOP Atom (GB10)에 Hermes Agent를 백엔드로 설치하고, Ollama 기반 로컬 LLM을 연동해 Windows PC(Dall)에서 LAN으로 원격 사용할 수 있도록 `systemd --user` + linger 로 자동 기동한 전체 과정.
> 💡 이 페이지는 **설치 → 모델 연동 → 원격 dashboard → 무인 자동 기동**의 백엔드 구축 전체를 다룹니다.

## 1. 목표 구조

**AI TOP Atom = 실제 연산과 스킬 자동화를 수행하는 백엔드 서버.** Windows PC(Dall)는 GUI 클라이언트로 SSH/LAN을 통해 이를 제어하는 구조입니다.

| 구분 | Dall (Windows) | Haee (AI TOP Atom · GB10) |
|---|---|---|
| 역할 | GUI 클라이언트 | 백엔드 서버 · 인퍼런스 호스트 |
| IP | — | `192.168.219.115` |
| 주요 포트 | — | `:9119` dashboard · `:11434` Ollama |

## 2. Hermes Agent 설치

Nous Research 공식 원라인 인스톨러 사용. `sudo` 없이도 `uv`, Python 3.11, 의존성을 자동 구성해 줍니다. 기본 설치 경로는 `~/.hermes/` 입니다.

```bash
# 1. 공식 원라인 인스톨러
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# 2. 터미널 환경 변경사항 적용
source ~/.bashrc
```

## 3. 로컬 LLM 연동 (Ollama)

GB10의 128GB 통합 메모리를 쓰는 백엔드 LLM 공급처를 설정합니다. `hermes model` 마법사로 설정합니다.

1. **Provider 선택** — `Ollama` 또는 `Custom / OpenAI Compatible`
2. **Endpoint** — 기본값 `http://localhost:11434` 확인
3. **Default Model** — 이미 pull한 모델명 (예: `llama3.1`, `gemma4`) 지정

```bash
# 대화형 모델/인프라 설정 마법사
hermes model
```

> 💡 **Tip:** 클라우드 API로 먼저 붙여볼 때는 [OpenRouter](https://openrouter.ai/) 선택 → API Key 입력이 가장 빠릅니다.

## 4. 상태 진단 & 첫 테스트

```bash
# 1. 인프라 · API 연결 상태 종합 진단
hermes doctor

# 2. 정상이면 인터랙티브 TUI로 구동
hermes --tui
```

- **테스트 입력:** “현재 디렉터리 파일 목록과 시스템 상태를 요약해 줘.”
- **체크포인트:** 에러 없이 로컬 파일시스템을 읽고 Tool Call을 수행하는지 확인.

## 5. 원격 Dashboard

원격에서 `hermes dashboard`로 접근해 서비스(채팅/파일/터미널)를 사용하는 방식입니다.

```bash
hermes dashboard --host 0.0.0.0 --port 9119
```

기본 인증(Basic Auth)은 `~/.hermes/.env`에 정의됩니다.

```env
HERMES_DASHBOARD_BASIC_AUTH_USERNAME=remoteUsr
HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=***
HERMES_DASHBOARD_BASIC_AUTH_SECRET=***
```

> 🔒 위 값들은 예시이며, 렌더링 시점에 실제 크레덴셜은 자동으로 마스킹됩니다.

### secret 생성
```bash
openssl rand -hex 16
```

## 6. 무인 자동 기동 (systemd user + linger)

매번 SSH로 접속해 dashboard를 실행하는 불편을 없애기 위해 **user-level systemd 서비스**로 등록합니다.

```bash
which hermes
# -> /home/joons/.local/bin/hermes
```

`~/.config/systemd/user/hermes-dashboard.service`:

```ini
[Unit]
Description=Hermes Agent Dashboard
After=network.target

[Service]
ExecStart=/home/joons/.local/bin/hermes dashboard --host 0.0.0.0 --port 9119
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

활성화 + **linger**(로그인 없이도 부팅 즉시 기동 — Dall 원격 접속의 핵심):

```bash
systemctl --user daemon-reload
systemctl --user enable hermes-dashboard
systemctl --user start  hermes-dashboard
loginctl enable-linger joons
```

> ✅ **결과:** PC를 켜기만 하면 별도 조작 없이 dashboard가 준비되고, 로그인 상태와 무관하게 `192.168.219.115:9119`에서 접속 가능.

## 7. 관리 명령어

| 작업 | 명령어 |
|---|---|
| 상태 확인 | `systemctl --user status hermes-dashboard` |
| 재시작 | `systemctl --user restart hermes-dashboard` |
| 시작 / 중지 | `systemctl --user start\|stop hermes-dashboard` |
| 로그 | `journalctl --user -u hermes-dashboard -e` |

- `-u`: 해당 unit 로그만 보기
- `-e`: 최신(맨 아래)으로 이동
