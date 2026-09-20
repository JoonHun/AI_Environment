# 이메일 발송 (SMTP)

[summary] Gmail SMTP를 통한 AI Agent 메일 발송 서비스 — 16자리 App Password, 중앙 `.env`, `smtp_sender.py`, 자동 AI 안내 푸터.

## 1. 개요

| 항목 | 값 |
|---|---|
| 위치 | `/home/joons/.hermes/services/smtp-service/` |
| 발신 | Gmail SMTP (`smtp.gmail.com:587`) |
| 재사용 | 전체 Hermes 프로파일 공통 (단일 `.env`) |
| 스킬 | `email-sender` (cross-profile) |

## 2. 자격증명 (`.env`)

```bash
# /home/joons/.hermes/services/smtp-service/.env  (chmod 600, git 제외)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<gmail 주소>
SMTP_PASS=[App Password 16자리]
```

> 🔒 **보안:** App Password는 16자리 무작위 문자열, **실제 값은 원본 `.env`에만** 보관.
> 위키 렌더 시 자동 마스킹. `.gitignore`에 반드시 `.env` 등록.

## 3. App Password 발급

1. Google 계정 → [2단계 인증](https://myaccount.google.com/signinoptions/two-factor) 활성화
2. [앱 비밀번호 발급](https://myaccount.google.com/apppasswords) → 16자리 문자열 복사
3. `SMTP_PASS`에 저장

## 4. `smtp_sender.py` 사용

### CLI

```bash
python3 /home/joons/.hermes/services/smtp-service/smtp_sender.py \
  "to@example.com" \
  "메일 제목" \
  "메일 본문" \
  "/path/to/html/file.html"
```

| 파라미터 | 필수 | 설명 |
|---|---|---|
| `to` | O | 수신자 |
| `subject` | O | 제목 |
| `body` | O | 본문 (HTML 파일 있으면 대체) |
| `html_file_path` | X | HTML 파일 → 파일 내용을 본문으로 삽입 |

### Python 호출

```python
from smtplib import SMTP
import os
# (실제는 smtp_sender.send_email() 또는 terminal 호출)
```

## 5. 자동 푸터

모든 메일 하단에 자동 삽입:

> *이 메일은 AI Agent에 의해 자동 발송되었습니다. 직접 회신하셔도 답변이 불가합니다.*
> *This email was sent automatically by AI Agent. Replies will not be processed.*
> *문의: [이메일 마스킹됨]*

## 6. 보안·운영 규칙

| 항목 | 규칙 |
|---|---|
| 파일 권한 | `600` (owner 읽기/쓰기만) |
| Git | `.env` 절대 추적 금지 |
| Cross-profile | 중앙 `.env` 공유, `cross_profile=True` 옵트아웃 |
| 전송 한도 | Gmail 약 500통/일 |
| 로그 | `smtp.log` (성공/실패, 타임스탬프, 수신자, 제목) |
| SPF/DKIM | Gmail 기본 적용 / 대량 발송 시 Google Workspace 고려 |

## 7. 구조

```
/home/joons/.hermes/services/smtp-service/
├── .env                # 자격증명 (600, git 제외)
├── .env.example        # 템플릿
├── .gitignore
├── smtp_sender.py      # 전송 코어 (smtplib)
├── smtp.log
├── test/market_brief.html
└── document/
    ├── README.md / plan.md / final_report.md / security_policy.md
```

## 8. 결과 (2026-08-29)

> ✅ **테스트:** 테스트 메일 발송 성공 (00:04), HTML 파일 로드·전송 성공 (00:17).
> 모든 프로파일에서 `email-sender` 스킬로 재사용 완료.
