# 프로파일 개요 & 검증

[summary] Hermes 프로파일 6개의 구성, 모델 매핑, MTP 설정, 컨텍스트 분기, 런타임 검증 결과.

## 1. 아키텍처

```
Hermes Gateway  (Ollama :11434/v1, GB10 128GB 통합메모리)
├── default      ──  qwen3.8:27b-mtp-q8_0_256k
├── joons        ──  qwen3.8:27b-mtp-q4_K_M_256k
├── coding       ──  qwen3.6:35b-a3b-coding-mtp-q4_K_M   (코딩 특화, 세대 유지)
├── english      ──  gemma4:e4b-it-q4_K_M_64K
├── researcher   ──  qwen3.8:27b-mtp-q8_0
└── teacher      ──  qwen3.8:27b-mtp-q8_0_256k
```

각 프로파일은 `~/.hermes/profiles/<name>/` 아래에 `config.yaml` · `SOUL.md` ·
`system_prompt.md` · `memory/`를 보유하고, Discord 채널마다 독립 Gateway로 구동된다.
`default`는 `~/.hermes/config.yaml`(루트)에 직접 존재.

## 2. 프로파일 매트릭스

| 항목 | default | joons | coding | english | researcher | teacher |
|---|---|---|---|---|---|---|
| 페르소나 | — | SWE 멘토 | Senior SWE + 코드리뷰 | Sam (영어 대화) | 리서치 | 교육 |
| 모델 | `qwen3.8:27b-mtp-q8_0_256k` | `qwen3.8:27b-mtp-q4_K_M_256k` | `qwen3.6:35b-a3b-coding-mtp-q4_K_M` | `gemma4:e4b-it-q4_K_M_64K` | `qwen3.8:27b-mtp-q8_0` | `qwen3.8:27b-mtp-q8_0_256k` |
| 컨텍스트 | 256K | 256K | 128K | 64K | 기본 | 256K |
| MTP (draft) | 4 | 4 | 2 | — | — | 4 |
| temperature | 0.3 | 0.2 | 0.2 | 0.7 | — | — |
| Discord 채널 | — | `…776` | `…776` | `…302` | — | — |

> ⚠️ **실측 기반 (2026-09-02):** 위 모델명은 `profiles/*/config.yaml` 실값.
> `coding`은 코딩 특화 모델로 의도적으로 qwen3.6 세대를 유지한다.

## 3. MTP (Multi-Token Prediction)

GGUF에 MTP 가중치가 내장되어 있어, `draft_num_predict`을 세야 실제로 스펙ulative decoding이 활성화된다.

| Ollama 모델 | draft_num_predict | decode (측정값) | MTP 효과 |
|---|---|---|---|
| `qwen3.8:27b-mtp-q4_K_M_256k` | 4 | OFF 12.1 → ON **26.3 tok/s** | +117% |
| `qwen3.8:27b-mtp-q8_0_256k` | 4 | OFF 8.0 → ON **19.1 tok/s** | +139% |
| `qwen3.6:35b-a3b-coding-mtp-q4_K_M` | 2 | — (별도 미측정) | — |

> 💡 **측정 조건:** GB10, thinking off, temperature 0, num_predict 256, num_ctx 8K, 3회 중앙값.
> 모델 단독 측정 필수 — 다중 모델 동시 적재 시 VRAM 대역폭 공유로 값이 흔들림.

## 4. Modelfile 컨텍스트 분기

`ollama create`로 컨텍스트 변형 모델 등록:

```bash
# 예시
ollama create qwen3.8:27b-mtp-q4_K_M_256k \
  -f /home/joons/ollama-modelfiles/Modelfile.qwen3.8:27b-mtp-q4_K_M_256k
```

위치: `/home/joons/ollama-modelfiles/`

## 5. config 병합 규칙

| 규칙 | 설명 |
|---|---|
| `provider: custom` | 필수 — 없으면 엔드포인트 미발견으로 실행 불가 |
| `base_url` 명시 | `http://localhost:11434/v1` — 단독 실행 안정화 필수 |
| `ollama_num_ctx` 삭제 | Modelfile의 `PARAMETER num_ctx`와 중복 → 제거 |
| `draft_num_predict` | Modelfile에 기록 — 없으면 MTP 비활성 |

## 6. 핵심 트러블슈팅

> 💡 **데스크톱 모델 드롭다운 = 세션 단위 오버라이드:** 입력창의 모델 드롭다운은
> 프로파일 기본 모델보다 우선순위가 높다. 세션 시작 전 해당 드롭다운을 목표로한 모델로
> 반드시 맞춰야 한다. (우선순위: ① 세션 오버라이드 → ② 채널 오버라이드 → ③ 프로파일 기본)

> ⚠️ **모델은 세션 시작 시점에 고정:** 시작 후로는 중간 변경 불가(프롬프트 캐시 무결성).

> ⚠️ **MTP는 이름 ≠ 활성화:** 모델명에 `-mtp`가 들어있어도 `draft_num_predict`이
> Modelfile에 없으면 실제로 스펙ulative decoding이 안 된다.

> 🔒 **비밀번호/시크릿:** 각 프로파일 `.env`의 `DISCORD_BOT_TOKEN` · `DISCORD_ALLOWED_USERS`
> 등 시크릿은 위키 렌더링 시 자동 마스킹된다.

## 7. 디렉토리 구조

```
/home/joons/ollama-modelfiles/
├── Modelfile.qwen3.8:27b-mtp-q4_K_M_256k    (FROM qwen3.8:27b-mtp-q4_K_M + num_ctx 262144 + draft_num_predict 4)
├── Modelfile.qwen3.8:27b-mtp-q8_0_256k       (FROM qwen3.8:27b-mtp-q8_0 + num_ctx 262144 + draft_num_predict 4)
└── ...
```
