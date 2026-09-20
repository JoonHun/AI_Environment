# Joons Wiki — 진행 내역 상세 요약

> 작성일: 2026-08-30 · 작성자: Hermes Agent
> 대상: `/home/joons/.hermes/services/wiki/` (Joons Wiki 프로젝트)
> 상태: **프로젝트 완료 (19/19 페이지, systemd 서비스 운영 중)**

---

## 1. 목표

1. 홈 PC(aitopatom / AI TOP Atom GB10)의 시스템 셋업·작업 전부 문서화
2. 위키 스타일 웹 페이지로 서비스
3. **LAN에서 Dall(Windows PC, 192.168.219.101)이 `http://192.168.219.115:5001`로 접근**
4. 자격증명은 원본 유지, 렌더링 시 자동 마스킹

### 스택 결정

| 항목 | 결정 |
|---|---|
| 프레임워크 | Flask + waitress (프로덕션 HTTP 서버) |
| 마크다운/하이라이팅 | `markdown` + `pygments` |
| 의존 격리 | wiki 전용 venv (`wiki/.venv`) — 기존 서비스와 충돌 방지 |
| 문서 구조 | `site/<섹션>/<슬러그>.md` — `nav.yaml` 매니페스트로 사이드바 생성 |
| 자동 기동 | systemd user service + `loginctl enable-linger` |
| 스타일 기준선 | `hermes-agent-backend.md`(126L) — H1 + `[summary]` + numbered H2 + `> 💡`/`> ✅` 콜아웃 + 코드/테이블 원본 보존 + filler 문구 제거 |
| 문체 | 한국어, 전문 위키 톤, AI 흔적 제거, 타국어 한자 혼입 금지 |
| 자격증명 | 원본 파일 그대로, 렌더 시 `mask_secrets()` 자동 치환 |

### 소스 문서 6개 영역

1. `services/documents/*.md` (13개 .md)
2. `profiles/` (coding, english, default)
3. `services/ollama-monitor/`
4. `services/research/`
5. `services/smtp-service/`
6. `desktop-plugins/profile-model-follow/`

---

## 2. PHASE 진행 이력 (타임라인)

### Phase 1 — 인프라 (완료)

- `wiki/{site,static,templates}` 스캐폴딩, 포트 5001 확보 확인
- **`server.py`(약 420L)**:
  - `discover_pages()` — **매 요청마다** site/ 재탐사 → 새 .md 추가 시 재기동 불필요
  - `mask_secrets()` — 시크릿 패턴 자동 마스킹
  - `inject_heading_ids()` — heading에 id 부여 + TOC 배열 반환 (tuple 반환 구조)
  - waitress → Flask dev 서버 폴백
- `static/style.css`(약 410L), `static/wiki.js`(95L)
- 5개 템플릿: `base.html`, `home.html`, `page.html`, `search.html`, `404.html`
- `nav.yaml`(95L) — 6 섹션, 19개 슬러그 매핑
- 샘플 페이지 `system/hermes-agent-backend.md`(126L) → 위변성 스타일 기준선 설정

#### 인프라 단계에서 발생한 버그 & 수정 (모두 해결 확인)

| # | 증상 | 원인 | 수정 |
|---|---|---|---|
| 1 | 페이지 404 | `Page.slug`에 `.md` 확장자 포함 | slug 생성에서 `.md` 제거 |
| 2 | 홈 500 | Jinja 미지원 `{% cycle %}` | CSS `nth-child(1..6)`로 대체 |
| 3 | 페이지 500 | `toc_headings()` 미존재 | `page.toc` 사용으로 교체 |
| 4 | TOC 비어있음 | `build_toc()`이 HTML 미반환 | `inject_heading_ids()` (html, toc) 튜플 반환으로 재작성 |
| 5 | 모듈 누락 | `markdown`/`pyyaml` 미설치 | wiki 전용 venv 생성: `python3 -m venv .venv` + `pip install markdown~=3.6 pygments~=2.18 flask~=3.0 pyyaml~=6.0` |

### Phase 2 — 시스템 페이지 8개 (작성 완료)

| 파일 | 라인 | 내용 |
|---|---|---|
| `system/ollama-setup.md` | 68L | Ollama 설치, 환경 테이블, 첫 모델 검증 |
| `system/ollama-multimodel.md` | 70L | `OLLAMA_MAX_LOADED_MODELS`, 프로필별 모델, 동시 서빙 |
| `system/nvidia-sync.md` | 43L | NVIDIA Sync remote IDE/terminal/web |
| `system/ssh.md` | 59L | Dall→Haee SSH, 방화벽, VS Code Remote |
| `system/remote.md` | 32L | 종합 원격 접속 경로 (SSH/NVIDIA Sync/xRDP) |
| `system/remote-desktop.md` | 49L | xRDP, 동시 로그인 금지 경고 |
| `system/remote-hermes.md` | 64L | Dall Hermes Desktop → Haee Ollama LAN 연결 |
| `system/git-github.md` | 65L | `~/.hermes` git + GitHub private 백업 |

> 타국어 혼입 수정 2건: `nvidia-sync.md` "用户名"→"사용자 이름", `remote-hermes.md` "对外开放"→"LAN 노출"

### Phase 3 — 위임(delegation) 시도 4회 → 전부 실패 → 직접 작성 전환

| 시도 | 대상 | 결과 |
|---|---|---|
| 1 | system 8개 | 1063s, `max_iterations`+180s timeout, **0개 파일** |
| 2 | profiles 6 + services 3 + plugin 1 | 1311s, `max_iterations`+180s timeout, **TRUNCATED** |
| 3 | (재시도) | 동일 패턴 실패 |
| 4 | (재시도) | `TRUNCATED: hit max_iterations` |

**결론**: 자식 subagent가 부모와 동일한 **로컬 Qwen 3.8:27B** 모델을 물려받아 일괄 문서 작성(긴 생성 + 반복 tool call)으로 `max_iterations`에 도달. → **부모 에이전트가 소스를 직접 읽고 전수 작성**으로 전환. 이후 모든 페이지는 부모가 직접 작성.

### Phase 4 — 나머지 11개 페이지 직접 작성 (완료)

| 파일 | 내용 |
|---|---|
| `profiles/profiles-overview.md` | 3프로파일 구성, 모델 매핑, 컨텍스트 분기, 검증 결과 |
| `profiles/coding-profile.md` | 시니어 SWE 멘토 페르소나, `[코드 리뷰]` 구조, qwen3.6 |
| `profiles/english-profile.md` | Sam(중2 A2-B1) 페르소나, `[교정]` 구조, gemma4 |
| `profiles/session-prompt.md` | `promots/` 페르소나 파일 + `@파일명` 단축 시스템 |
| `profiles/english-prompt.md` | Sam 페르소나 완전 스펙 (7개 상호작용 규칙) |
| `profiles/discord-connect.md` | 멀티봇 2채널, 모델 격리, Gate 3개 트러블슈팅 |
| `ollama-monitor/monitor.md` | Flask 대시보드(5000), GPU/VRAM/token/s |
| `research/researcher.md` | 시장 브리핑 파이프라인 (탭 3 × 기사 5 → Gmail) |
| `smtp/email.md` | Gmail SMTP, App Password, `smtp_sender.py`, 자동 푸터 |
| `plugin/profile-model-follow.md` | Desktop 모델 피커가 프로필 `model.default`를 따르는 플러그인 |

> 작성 중 혼입 발견하여 수정: `coding-profile.md` "コメント"→"주석", `english-profile.md` "вовлечение"→"참여 유도", "철학 오류"→"철자 오류", `researcher.md` "规约"→"규칙", `hermes-agent-backend.md` "状態で"→"상태와"

### Phase 5 — 최종 검증 (완료)

```
PAGES: pass=19 fail=0
HOME  : 200
SEARCH: 200
sidebar links: 25개 정상
```

- 시크릿 렌더 검사: discord 페이지의 사용자 snowflake·토큰 패턴 모두 차단 (채널 ID 2개는 설정 값이라 의도적 유지)
- 한자(中/日) 잔재 전수 스캔 → 수정 후 0건
- filler 문구(소스 답사문구) 스캔 → 0건
- nav 매핑 cross-check: **19/19 매핑 누락 0**

### Phase 6 — systemd 운영 전환 (완료)

- `~/.config/systemd/user/joons-wiki.service` (22L) 등록
  - `ExecStart=.venv/bin/python server.py`, `Restart=always`, `WorkingDirectory=wiki/`
- `waitress` venv 설치 (초기 Flask dev fallback → waitress 8스레드 프로덕션 서빙)
- `systemctl --user enable --now joons-wiki.service` → **active (running)**
- `Linger=yes` 확인 → 재부팅 후 자동 기동
- `0.0.0.0:5001` LISTEN → **Dall(192.168.219.101)에서 실제 HTTP 요청 성공** 확인 (로그: `GET /p/smtp/email 200`)

---

## 3. 최종 디렉토리 구조

```
/home/joons/.hermes/services/wiki/
├── .venv/                # markdown, pygments, flask, pyyaml, waitress
├── server.py             # Flask+waitress 서버, mask_secrets, discover_pages(per-request)
├── nav.yaml              # 6 섹션 / 19개 슬러그
├── verify.sh             # 통합 검증 스크립트
├── static/style.css      # 다크 테마, nth-child 액센트 스트립
├── static/wiki.js        # 검색·TOC rail
├── templates/            # base, home, page, search, 404
├── site/
│   ├── system/           # 9개 (hermes-agent-backend, ollama-setup, ollama-multimodel,
│   │                     #   nvidia-sync, ssh, remote, remote-desktop, remote-hermes, git-github)
│   ├── profiles/         # 6개 (overview, coding, english, session-prompt, english-prompt, discord-connect)
│   ├── ollama-monitor/   # 1개 (monitor)
│   ├── research/         # 1개 (researcher)
│   ├── smtp/             # 1개 (email)
│   └── plugin/           # 1개 (profile-model-follow)
├── documents/            # ← 본 요약서
└── (유보: maskcheck.py / test_masking.py — 미완성, 정리 대상)
```

---

## 4. 운영 정보

| 항목 | 값 |
|---|---|
| URL (LAN) | `http://192.168.219.115:5001` |
| 서비스 | `joons-wiki.service` (systemd user, enabled) |
| 프로세스 | `wiki/.venv/bin/python server.py` (waitress, 8 threads) |
| 기동 확인 | `systemctl --user status joons-wiki` |
| 재시작 | `systemctl --user restart joons-wiki` |
| 로그 | `journalctl --user -u joons-wiki -f` |
| 새 페이지 추가 | `site/`에 `.md` 추가 시 **재기동 불필요** (per-request discovery) |

---

## 5. 결정 사항 & 교훈 (Key Decisions)

1. **위임 → 직접 작성 전환**: 로컬 Qwen 자식은 일괄 문서 작성(task per batch)에서 반복 타임아웃. 같은 모델 환경에서는 **부모가 직접 작성**이 유일한 성공 경로. (4회 시도, 0 성공)
2. **시크릿 리터럴 하드코딩 금지**: write_file 시 특정 자격증명 패턴 포함 시 출력 필터 절단 현상 반복(6회). 소스에서 런타임 추출 방식으로만 검증.
3. **타국어 혼입 즉시 수정**: 한국어만 사용 원칙. 5건 발견·수정 (중국어 3, 일본어 1, 러시아어 1).
4. **버그 수정은 프론트 중심**: 백엔드 API surface 불확대.
5. **venv 격리**: 서비스마다 전용 venv (ollama-monitor, wiki 각각).
6. **`pkill -f` 주의**: 자식 shell 명령 자체를 매칭해 자기 종료(SIGTERM). PID 직접 지정으로 종료.
7. **`discover_pages()` per-request**: 파일 추가 즉시 반영 — 재기동 불필요.
8. **채널 ID(19자리)는 시크릿 아님**: `1542009729327435776` 같은 Discord **채널** ID는 설정 값이라 원문 유지. (사용자 snowflake만 마스킹)

---

## 6. 남은 정리 항목 (아님)

| 항목 | 설명 |
|---|---|
| `maskcheck.py` / `test_masking.py` | 미완성 테스트 스크립트 — 커밋 삭제 또는 완성 필요 |
| git 커밋 | 이번 19개 페이지 + server 수정을 선택 stage 커밋 (user 지시 대기) |
| Dall 최종 확인 | LAN 접속은 로그상 성공 확인 — 사용자의 최종 시각 확인만 남음 |

---

## 7. 최종 검수 체크리스트

- [x] 서버 5001 (waitress) LISTEN — 0.0.0.0
- [x] 19/19 페이지 200
- [x] 홈 / 검색 / 404 200
- [x] 시크릿 렌더 마스킹 (snowflake·토큰 차단)
- [x] 사이드바 19개 링크 + 추가 nav 25개
- [x] TOC 앵커 (heading id + rail 렌더)
- [x] 타국어(中/日/러) 한자 잔재 0건
- [x] filler 문구 0건
- [x] nav ↔ 파일 매핑 19/19
- [x] systemd enabled + active + Linger
- [x] waitress 프로덕션 서빙 (Flask dev fallback 아님)
- [x] **Dall(192.168.219.101) 실제 LAN 접속 로그 확인**
