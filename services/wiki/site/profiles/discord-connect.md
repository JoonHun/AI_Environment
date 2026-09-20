# Discord 연결

[summary] Hermes Gateway를 Discord에 멀티봇으로 연결 — 채널별 독립 페르소나(영어/코딩) + 모델 격리, 3가지 Gate 트러블슈팅 포함.

## 1. 아키텍처

```
Discord 채널 #english    ──→  Gateway #1 (profile: english)  ──→  gemma4 (64K)
Discord 채널 #coding     ──→  Gateway #2 (profile: coding)   ──→  qwen3.6 (128K)

Hermes Gateway #1 → port 8601
Hermes Gateway #2 → port 8602

Ollama (GB10, 128GB 통합 메모리)
  OLLAMA_MAX_LOADED_MODELS=3 → 두 모델 동시 상주
```

## 2. 핵심 구성

| 항목 | 내용 |
|---|---|
| Gateway 포트 | 영어 `8601`, 코딩 `8602` (포트 충돌 방지) |
| 모델 동시 상주 | `OLLAMA_MAX_LOADED_MODELS=3` |
| 봇 토큰 | `english-bot` 토큰 A, `coding-bot` 토큰 B |
| config.yaml | `gateway.discord.channels`에 채널 ID, `platforms.discord.token-env` |

## 3. Discord Developer Portal 설정

1. [Developer Applications](https://discord.com/developer/applications) 접속
2. `New Application` → 이름 입력 (`english_bot` / `coding_bot`) → **Bot** 탭 → `Add Bot`
3. `Reset Token` 클릭 → 토큰 복사
4. **Message Content Intent** 토글 활성화 (없으면 메시지 침묵)
5. Bot Permissions: `Send Messages` · `Read Message History` · `Use Application Commands` 체크
6. OAuth2 → URL Generator → `bot` + `applications.commands` 체크 → URL 복사 → 봇 초대

> 🔒 **토큰 보안:** `DISCORD_BOT_TOKEN`은 각 프로파일 `.env`에만 저장, `config.yaml`에는
> `token-env: CODING_DISCORD_BOT_TOKEN`(환경변수 참조 키)만 남긴다. 위키 렌더 시 자동 마스킹.

## 4. `config.yaml` 필수 구조

```yaml
# 각 프로파일 config.yaml
gateway:
  discord:
    channels:
      - '<CHANNEL_ID>'    # 예: '1542009729327435776'
platforms:
  discord:
    token-env: CODING_DISCORD_BOT_TOKEN  # .env에서 이 키로 토큰 로드
```

## 5. `.env` 필수 키

```bash
# profiles/coding/.env (예)
DISCORD_BOT_TOKEN=<토큰 값>
# DISCORD_ALLOWED_CHANNELS=<채널 ID>        # 선택
# DISCORD_FREE_RESPONSE_CHANNELS=<채널 ID>  # 선택 — 멘션 없이도 반응하는 채널
DISCORD_ALLOWED_USERS=<사용자 snowflake>     # 허용 사용자 ID
```

> ⚠️ **시크릿:** `DISCORD_BOT_TOKEN`(hex/베이스64 토큰)과 `DISCORD_ALLOWED_USERS`
> (17~19자리 Discord snowflake = PII)는 위키 렌더 시 **자동 마스킹**된다.

## 6. Gateway 병렬 기동

```bash
hermes gateway run --profile english --port 8601 &
hermes gateway run --profile coding  --port 8602 &
# 각 채널에서 테스트 메시지 전송 → 모델/페르소나 응답 확인
```

## 7. 게이트웨이 3대 트러블슈팅 (해결 완료)

| # | 증상 | 원인 | 해결 |
|---|---|---|---|
| 1 | 봇이 메시지 무시 | `DISCORD_IGNORE_NO_MENTION=true`(기본)가 멘션 없는 메시지와 무시 | `DISCORD_FREE_RESPONSE_CHANNELS={<채널ID>}` 등록 |
| 2 | `Unauthorized user` | `DISCORD_ALLOWED_USERS`에 사용자 snowflake 없음 | 사용자 ID 추가 등록 |
| 3 | 토큰 미적용 | `token-env: CODING_DISCORD_BOT_TOKEN`(custom 키명) 무시됨 | 프로파일 `.env`에 **고정키 `DISCORD_BOT_TOKEN`**으로 직접 입력 |

> 💡 **핵심 교훈:** Discord 플러그인은 `token-env`(custom)이 아닌 **고정키 `DISCORD_BOT_TOKEN`**으로만
> 토큰을 조회한다. 반드시 고정키로 `.env`에 직접 입력해야 한다.

## 8. 점검 결과 (변경 불필요)

| 프로필 | 지정 모델 | 온도 | 상태 |
|---|---|---|---|
| `english` | `gemma4-nctx-64k:latest` | 0.7 (대화) | ✅ |
| `coding` | `qwen3.6-nctx-128k:latest` | 0.2 (코드) | ✅ |
