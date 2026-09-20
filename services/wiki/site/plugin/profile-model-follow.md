# profile-model-follow (Desktop Plugin)

[summary] Hermes Desktop에서 프로필을 선택하면 그 프로필의 `model.default`(지정된 AI 엔진)가 composer 모델 피커에 자동으로 따라붙는 플러그인.

## 1. 문제 정의

> "프로필별 AI 모델을 설정해 뒀는데, Hermes Desktop에서 **새 세션을 열면 AI 엔진이
> 프로필에 설정된 것으로 자동 바뀌지 않는다**는 문제."

- 각 프로필 `config.yaml`의 `model.default`는 **이미 정상적으로 설정되어 있다**
- 문제는 Desktop UI의 모델 선택이 프로필 기본값을 자동 따르지 않는 것
- 목표: 프로필 선택 → 그 프로필의 `model.default`가 composer에 항상 따라붙도록 **UI 수준에서 강제**

| 프로필 | `model.default` | gateway |
|---|---|---|
| default | `qwen3.8_27B_128K_Q8_MTP` | running |
| coding | `qwen3.6_35B_128K_Q4_CODING_MTP` | running |
| english | `gemma4:e4b-it-q4_K_M` | running |

## 2. Root Cause (Desktop 소스)

### 2.1 composer 모델은 global(localStorage)

```ts
// src/store/session.ts
export const COMPOSER_MODEL_KEY = 'hermes.desktop.composer.model'
export const COMPOSER_PROVIDER_KEY = 'hermes.desktop.composer.provider'
export const COMPOSER_MODEL_SOURCE_KEY = 'hermes.desktop.composer.model-source'
export type ComposerModelSource = 'default' | 'manual'
```

이 상태는 **per-profile이 아니라 global**로 저장된다.

### 2.2 수동 선택이 기본값 리셋을 막음

```ts
// use-hermes-config.ts
const manualSource = localStorage.getItem(COMPOSER_MODEL_SOURCE_KEY)
const keepManualPick = manualSource === 'manual'   // 수동 선택을 보전
  && !!activeSessionId && model === currentModel
refreshCurrentModel({
  provider, model,
  keepCurrent: force || keepManualPick || manualPickRemoved,
  force: force && !keepManualPick
})
```

- `refreshCurrentModel({keepCurrent: true})` → **`if (!force && keepCurrent) return`**
  (기본값으로의 리셋이 **스킵**됨)
- 즉 사용자가 한 번 모델 피커에서 수동으로 고르면, 이후 프로필 전환에도
  그 수동 값이 고착되고 기본값이 덮어쓰기되지 않는다.

```ts
function refreshCurrentModel({ provider, model, keepCurrent=false, force=false }) {
  const currentModel = $currentModel.get()
  if (!force && keepCurrent && currentModel) return   // ← 수동값을 유지 (버그 지점)
  // ...
}
```

## 3. 플러그인 해결 방향

플러그인이 할 일 — **프로필 전환 시점마다 수동 source를 `default`로 리셋**해
기본값 리셋이 실행되도록 한다.

| 시점 | 플러그인 동작 |
|---|---|
| 프로필 목록에서 다른 프로필 선택 | `COMPOSER_MODEL_SOURCE_KEY`을 `default`로 재설정 |
| (선택) 세션 새로 생성 | 동일 리셋 |
| 모델 캐탈로그 갱신 후 | `getEffectiveComposerModel()`이 새 프로필 기본값 반환 |

> 💡 **핵심:** `localStorage`의 `source='manual'` 플래그만 리셋하면,
> 기존 UI 로직(`refreshCurrentModel`)이 자동으로 새 프로필 기본값을 피커에 반영한다.
> 별도 상태 저장 로직을 만들 필요 없이 **기존 early-return을 우회**하는 것이 최소 침투 방식이다.

## 4. 위치 & 해시

| 항목 | 값 |
|---|---|
| 위치 | `~/.hermes/desktop-plugins/profile-model-follow/plugin.js` |
| 크기 | 11,640 byte |
| SHA256 | `513410b7...958` |
| 작성 | 2026-08-29 · Researcher 프로필 (Hermes Agent) |

## 5. 관련

- [coding 프로파일](/p/profiles/coding-profile) — `model.default` 설정 예
- [english 프로파일](/p/profiles/english-profile) — 페르소나 Sam
- [프로파일 개요 & 검증](/p/profiles/profiles-overview) — 모델/컨텍스트 매트릭스

> ⚠️ **주의:** 이 플러그인은 Hermes Desktop GUI 플러그인이며,
> Gateway/CLI 세션의 모델 선택과는 무관하다. CLI에서는 `hermes -p <profile>`으로
> 프로파일 기본값이 그대로 적용된다.
