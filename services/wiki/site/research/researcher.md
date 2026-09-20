# Researcher Bot

[summary] `researcher` 프로필이 주기적/요청 기반 시장 브리핑(탭 3개 × 기사 5개)을 만들어 Gmail로 발송하는 파이프라인.

## 1. 파이프라인

```
웹 검색 (web_search)                        ← 70% 국내 / 30% 국제기사
      ↓
기사 본문 fetch (curl / urllib)             ← web_extract는 search-only라 본문 미포함
      ↓
빌드 스크립트 (/tmp/build_brief_YYYY_MM_DD.py)  ← tabs dict 구성
      ↓
render_email_brief() (html_render.py)       ← 테이블·인라인 CSS·JS 없는 Gmail 호환
      ↓
result/email_YYYY_MM_DD.html
      ↓
smtp_sender.send_email()                    ← recipients.txt 전체 수신자
      ↓
Gmail (smtp.gmail.com:587)
```

## 2. 핵심 컴포넌트

| 파일 | 역할 |
|---|---|
| `html_render.py` (150줄, jinja2) | **공식 이메일 렌더러** — SMTP 발송용 |
| `test/render_market_brief.py` | 온스크린 탭 UI 렌더러 (데모용) |
| `recipients.txt` | 수신자 목록 (git 제외) |
| `result/` | 생성물 HTML 출력 (git 제외) |

## 3. 이메일 렌더러 규칙 (Gmail 호환)

| 항목 | 규칙 |
|---|---|
| 레이아웃 | **테이블 기반** (`<table role="presentation">`). flex/grid 금지 |
| 스타일 | **인라인 CSS만**, `<style>` 태그/외부 CSS 금지 |
| 스크립트 | JS 완전 제거 |
| 탭 처리 | 탭 UI가 아닌 **섹션을 상하 연속 배치** (전체 확장) |
| 컨테이너 | 최대 720px, 백그라운드 `#f4f4f7` |
| 출처 | `<a href="src_url">src_text</a>` — 링크 텍스트가 출처 |
| 푸터 | `본 문서는 AI에 의해 작성되었습니다.` (한/영) |

> ⚠️ **왜 이렇게:** Gmail 등 이메일 클라이언트는 `<style>` 블록을 잘라내고
> JavaScript를 비활성화한다. 그래서 이메일에는 테이블+인라인 CSS+무스크립트가 필수다.

## 4. 렌더링 계약 (data contract)

```python
def render_email_brief(date, tabs, output_path=None, output_dir=None):
    # date: '2026년 8월 29일 토요일'
    # tabs: [
    #   {'id':'haneconomy','name':'한국 경제','items':[{'title','summary','src_url','src_text'},...]},
    #   {'id':'kospi','name':'KOSPI','items':[...]},
    #   {'id':'ai','name':'AI Trend','items':[...]},
    # ]
```

- `autoescape=True` (jinja2) — 기사 본문 HTML 특수문자 자동 이스케이프
- `output_path` 미지정 시 `result/email_YYYY_MM_DD.html` 자동 생성
- 파일 경로를 `str`로 반환

## 5. 빌드 스크립트 패턴

- 1회성 스크립트(`/tmp/build_brief_YYYY_MM_DD.py`)가 그날 브리핑 데이터를 dict로 구성
- `render_email_brief()`에 전달해 HTML 생성
- 코드는 안정적으로 유지되며, 내용은 1회성 스크립트에서 관리 (상태 파일 거의 없음)

## 6. SMTP 연동

발송은 [SMTP 서비스](/p/smtp/email)의 `smtp_sender.py`가 담당한다.

```python
from smtp_sender import send_email
send_email(
    to="joonhun.shin@gmail.com",
    subject="Market Brief",
    html_file_path="result/email_2026_08_29.html",
)
```

> 📇 **수신자:** `recipients.txt`(git 제외)의 전체 주소로 대량 발송. AI 자동 발송
> 안내 문구는 수신 메일 하단에 자동 삽입된다.
