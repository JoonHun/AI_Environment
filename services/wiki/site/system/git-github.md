# Git / GitHub

[summary] `~/.hermes` 전체(설정·스킬·메모리·서비스)를 Git으로 버전을 걸고 GitHub private 레포로 백업하는 구성.

## 1. 구성 요약

| 항목 | 값 |
|---|---|
| Git 버전 | 2.43.0 |
| 추적 대상 | `~/.hermes` (프로파일·스킬·메모리·서비스) |
| GitHub | `github.com/JoonHun/hermes-config` (private) |
| 브랜치 | `default` |
| 인증 | PAT (HTTPS) |

## 2. 기본 설정

```bash
git config --global user.name "joonhun"
git config --global user.email "[이메일 마스킹됨]"
git config --global init.defaultBranch default
```

## 3. `.gitignore` 분류

| 분류 | 처리 |
|---|---|
| 설정/스킬/메모리/서비스 | ✅ 추적 대상 |
| 동적 상태: `*.db`, `logs/`, `cache/`, `venv/`, `node/`, `hermes-agent/` | ❌ 제외 |
| 기밀: `.env`, `auth.json`, `*.token*`, `*.key*` | 🔒 절대 제외 |

> 🔒 **중요:** 자격증명·토큰·개인키 파일은 `.gitignore`로 반드시 차단한다.
> 추적 파일 1,432개 중 기밀 파일이 하나도 포함되지 않는 것이 확인된 상태다.

## 4. GitHub 인증

```bash
# ~/.git-credentials (chmod 600) → PAT 저장
git remote add origin https://github.com/JoonHun/hermes-config.git
git branch --set-upstream-to=origin/default default
```

> ⚠️ **PAT 주의:** 첫 PAT가 차단되어 두 번째 PAT로 인증에 성공한 이력이 있다.
> PAT는 별도 보관(로컬 `.git-credentials`), 코드/문에 노출 금지.

## 5. 디렉토리 분포 (첫 커밋 기준)

| 디렉토리 | 파일 수 |
|---|---|
| `profiles/` (coding + english) | 952 |
| `skills/` | 465 |
| `services/ollama-monitor/` | 3 |
| `attachments/`, `cron/`, `desktop-plugins/` | 5 |
| 루트 | 7 |

## 6. 복원/관리

```bash
git checkout <hash> -- <file>     # 파일 단위 복원
git diff <old> <new>              # 커밋 단위 비교
git revert <hash>                 # 커밋 취소
git checkout <init> -- .          # 초기 상태로 복원
```

> ✅ **결과:** PC 고장 대비 GitHub 백업 확보. 파일/커밋 단위 복원 가능.
