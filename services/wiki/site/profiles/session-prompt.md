# 세션 별 프롬프트

[summary] Hermes 대화 세션을 시작할 때 `@파일명` 단축어 또는 `prompts/` 디렉터리의 `.md` 페르소나 파일로 System Prompt를 즉시 주입하는 시스템.

## 1. 개념

각 채팅 세션은 시작 시점에 페르소나(System Prompt)를 결정한다. `prompts/` 폴더에
전문가 페르소나 `.md` 파일을 모아두면, 세션 시작 시 그 하나의 파일만 지정하면 된다.

```
prompts/
├── english.md    (영어 학습 선생님 — A2-B1, [교정] 규칙)
└── coding.md     (SW 전문가 — 코드 분석·구조 개선·테스트)
```

## 2. 세션 시작 법

Hermes 채팅에서 아래처럼 시작 문장을 사용한다:

```
prompts/coding.md 로 세션을 시작하자
or
prompts/english.md 로 대화를 시작하자
```

> 💡 **Tip:** `prompts/`는 영구 메모리(Hermes Memory)에 저장되어 있다. 별도 설명 없
> 이 이 표현을 보면 Hermes가 자동으로 `prompts/` 디렉터리를 찾아가서 파일 로드 후
> 현재 세션의 System Prompt로 즉시 적용한다.

## 3. `@` 단축어 시스템

사용자 메시지에 `@로 시작하는 단어`가 감지되면 Hermes가 자동으로:

| 단계 | 동작 |
|---|---|
| 1. 파일 경로 자동 완성 | `@english` → `prompts/english.md` |
| 2. 내용 자동 로드 | 해당 `.md` 텍스트를 세션 System Prompt로 즉시 적용 |
| 3. 실행 확인 | "English 모드로 전환되었습니다!" 등 알림 출력 |

## 4. 확장 법

> ✅ **추가 페르소나:** 새 `.md` 파일을 `prompts/` 폴더에 넣기만 하면 별도 코딩 없이
> 즉시 새로운 AI 페르소나로 호출 가능하다. `@파일명`으로 세션 시작.

## 5. 프로파일과의 관계

| 방식 | 대상 | 특성 |
|---|---|---|
| **프로파일** (`profiles/`) | `coding` / `english` | 고정 페르소나 + 모델 + Discord. 독립 Gateway |
| **세션 프롬프트** (`prompts/`) | 세션별 단발 페르소나 | 가볍고 유연. `@파일명`으로 즉시 전환 |

> ⚠️ **차이점:** 프로파일은 모델/디스코드/메모리를 모두 분리한 독립 구성인 반면,
> 세션 프롬프트는 현재 세션에만 페르소나를 주입하는 가볍고 유연한 방식이다.
> 프로파일 세부 구성은 [coding](/p/profiles/coding-profile) · [english](/p/profiles/english-profile)
> 페이지를 참조.
