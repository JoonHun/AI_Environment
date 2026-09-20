# llama-server 로그 포맷 & 파서 계약 (검증됨)

> 2026-09-10에 **실제** `llama-server` (ggml-org/llama.cpp, MTP 빌드, port 11534)
> journal에서 캡처한 388줄 로그로 정규식을 검증했다.
> 검증 스크립트: `/tmp/validate_llama_parser.py` (388줄 전체에서 9/9 규칙 매칭)

## 1. 로그 라인 포맷 (실제 캡처)

### 1.1 진행 (약 3초마다, 태스크 실행 중)
```
63.53.883.369 I slot print_timing: id  3 | task 18379 | n_gen =    101, tg =  24.43 t/s, tg_3s =  24.68 t/s
```
| 필드 | 의미 |
|---|---|
| `id 3` | 슬롯 ID (llama-server는 동시 4 슬롯) |
| `task 18379` | 태스크 ID (요청 식별자) |
| `n_gen` | 이 태스크에서 생성한 토큰 누적 |
| `tg` | 태스크 전체 평균 t/s |
| `tg_3s` | 직전 3초 윈도우 t/s (실시간 감) |

### 1.2 태스크 시작
```
63.53.883.369 I slot launch_slot_: id  3 | task 18379 | processing task, is_child = 0
```
→ **prefill 시작 마커** (Ollama의 `init_sampler` 대응).

### 1.3 완료 요약 (태스크 종료 시 4연속 라인)
```
82.53.144.359 I slot print_timing: id  3 | task 22774 | prompt eval time =    5107.82 ms /  2668 tokens (    1.91 ms per token,   522.34 tokens per second)
82.53.144.363 I slot print_timing: id  3 | task 22774 |        eval time =   65322.16 ms /  1330 tokens (   49.15 ms per token,    20.35 tokens per second)
82.53.144.363 I slot print_timing: id  3 | task 22774 |       total time =   70429.97 ms /  3998 tokens
82.53.144.364 I slot print_timing: id  3 | task 22774 |    graphs reused =      22601
```
| 라인 | 의미 |
|---|---|
| `prompt eval time` | **prefill** (입력 처리) 시간/토큰수/tps |
| `eval time` | **decode** (생성) 시간/토큰수/tps |
| `total time` | 요청 전체 (prefill+decode) |

### 1.4 MTP 스펙뎁 통계 (MTP 빌드만, 완료 시 1줄)
```
82.53.144.367 I slot print_timing: id  3 | task 22774 | draft acceptance = 0.68627 (  770 accepted /  1122 generated), mean len =  2.37
```
| 필드 | 의미 |
|---|---|
| `draft acceptance` | 전체 채택률 (accepted/generated) |
| `mean len` | 스텝당 평균 채택 체인 길이 |

> **Ollama와의 차이**: Ollama는 `#gen drafts / #acc drafts / #mean acc len / #acc rate/pos` 형식.
> llama.cpp는 `draft acceptance = X ( A accepted / B generated), mean len = Y`. **정규식이 다르다.**

### 1.5 태스크 종료 (슬롯 해제)
```
82.53.145.613 I slot      release: id  3 | task 22774 | stop processing: n_tokens = 58119, truncated = 0
```
| 필드 | 의미 |
|---|---|
| `n_tokens` | **슬롯 컨텍스트 총 토큰** (세션 크기, 생성량이 아님) |
| `truncated` | 0=정상 종료, 1=길이 제한으로 컷 |

### 1.6 ⚠️ Ollama가 있고 llama.cpp엔 없는 것
- **`all slots are idle` 마커가 없다** (2000줄 스캔에서 0건).
  → idle 판정은 `/slots` API의 `is_processing==False` 또는 `release` 마커 이후로 도출.

## 2. 검증된 정규식 (Python, 검증 통과)

```python
import re

# 진행 (3초마다)
RE_NGEN   = re.compile(r"n_gen\s*=\s*(\d+)")
RE_TG     = re.compile(r"tg\s*=\s*([\d.]+)\s*t/s")
RE_TG3S   = re.compile(r"tg_3s\s*=\s*([\d.]+)\s*t/s")
RE_TASK   = re.compile(r"task\s+(\d+)")
RE_SLOTID = re.compile(r"id\s+(\d+)\s*\|")

# 완료 요약
RE_EVAL   = re.compile(r"(?<!prompt )eval\s+time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens")
RE_PROMPT = re.compile(r"prompt\s+eval\s+time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\s*\(\s*[\d.]+\s*ms\s+per\s+token,\s*([\d.]+)\s*tokens\s+per\s+second")
RE_TOTAL  = re.compile(r"total\s+time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens")

# MTP
RE_DRAFT  = re.compile(r"draft\s+acceptance\s*=\s*([\d.]+)\s*\(\s*(\d+)\s+accepted\s*/\s*(\d+)\s+generated\)\s*,\s*mean\s+len\s*=\s*([\d.]+)")

# 태스크 시작/종료
RE_START  = re.compile(r"launch_slot_:.*task\s+(\d+)\s*\|\s*processing")
RE_RELEASE= re.compile(r"release:.*task\s+(\d+)\s*\|.*n_tokens\s*=\s*(\d+)")
```

### ⚠️ 파서 주의사항 (검증 중 발견)
1. **`RE_EVAL`에 `(?<!prompt )` negative lookbehind 필수** —
   `prompt eval time` 라인도 `eval time`을 포함하므로, 없으면 prefill 라인을
   final decode로 오인별한다. (검증 스크립트 v1에서 확인된 버그)
2. **라인 판별 순서**: `prompt eval` → `total time` → `draft acceptance` →
   `eval` 순으로 검사하면 lookbehind 없이도 안전하다.
3. `id  3`의 슬롯 ID와 `task NNNN`은 **여러 공백**이 있을 수 있음 → `\s+`로 처리.
4. 로그 앞부분의 `63.53.883.369 I`는 llama.cpp의 **uptime+level** (ISO timestamp가
   journal prefix에 있음: `Sep 10 00:46:30`) — 타임스탬프는 journal prefix에서 읽는다.

## 3. `/slots` API (실시간 상태 — 1차 소스)

```bash
curl http://127.0.0.1:11534/slots
```
```json
[
  {
    "id": 1,
    "n_ctx": 131072,
    "speculative": true,
    "is_processing": false,
    "id_task": 24461,
    "n_prompt_tokens": 65575,
    "n_prompt_tokens_processed": 0,
    "n_prompt_tokens_cache": 0,
    "params": { "temperature": 1.0, "top_k": 20, "speculative.types": "none,draft-mtp", ... }
  }
]
```

| 필드 | 활용 |
|---|---|
| `is_processing` | **슬롯이 지금 바쁜가** — hang 감지의 1차 근거 |
| `id_task` | 마지막/현재 태스크 ID (로그 task와 cross-ref) |
| `n_prompt_tokens` | 마지막 요청의 입력 토큰 (완료 후에도 유지됨) |
| `n_prompt_tokens_processed` | prefill 진행량 — **`>0 && <n_prompt_tokens`이면 prefill 중** |
| `speculative` | MTP 활성 여부 |
| `params` | 요청 파라미터 (temperature, top_k 등) — 디버깅용 |

**상태 판정 로직 (권장):**
```
for each slot:
  if is_processing:
      if n_prompt_tokens_processed < n_prompt_tokens:  stage = "prefill"
      else:                                             stage = "decode"
  else:                                                 stage = "idle"
overall_state = any(is_processing) ? "busy" : "idle"
```

## 4. 기타 API 확인 결과

| 엔드포인트 | 상태 | 비고 |
|---|---|---|
| `GET /health` | ✅ `{"status":"ok"}` | up/down 판정 |
| `GET /v1/models` | ✅ 상세 meta | `n_params`, `size`, `ftype`, `n_ctx` |
| `GET /slots` | ✅ 4 슬롯 | 실시간 상태 (상기) |
| `GET /metrics` | ❌ **501 Not Implemented** | 이 빌드/시작옵션엔 비활성. `--metrics` 플래그로 활성화 가능 (선택) |
| `GET /` | ❌ 415 (UI 필요) | 대시보드용 불필요 |

## 5. 환경 아키텍처 (llama-monitor 추적 대상)

| 포트 | 모델 | 프로파일 | 방식 |
|---|---|---|---|
| **11534** | Qwen3.8-27B MTP Q4_K_M | joons | 상시 (systemd `llama-server-38`) |
| 11535 → 1535 | Qwen3.6-35B-A3B | coding | 온디맨드 (proxy `llama-proxy-36`) |
| 11536 → 1537 | Qwen3.8-27B Q8_0 | fallback | 온디맨드 (proxy `llama-proxy-38q8`) |
| 11537 → 1538 | Gemma4 E4B | english | 온디맨드 (proxy `llama-proxy-gemma`) |

> **llama-monitor는 다중 인스턴스 추적을 지원해야 한다.**
> config에 서버 목록을 두고, 각 서버의 `/health` + `/slots` + journal을 개별 샘플링.
> 온디맨드 서버는 proxy가 idle 10분 후 backend를 stop하므로 "down"이 정상 상태일 수 있음.

## 6. Ollama-monitor와의 파서 차이 요약

| 항목 | Ollama | llama.cpp |
|---|---|---|
| 진행 | `n_gen/tg/tg_3s` | **동일** |
| prefill 완료 | `prompt eval time` | **동일** |
| decode 완료 | `eval time` | **동일** |
| MTP | `#gen drafts/#acc drafts/#mean acc len/#acc rate/pos` | **`draft acceptance = X (A/B), mean len = Y`** (형식 다름) |
| 태스크 시작 | `init_sampler` | **`launch_slot_`** |
| 태스크 종료 | `release: ... n_tokens` | **동일** |
| idle 마커 | `all slots are idle` | **없음** → `/slots` API 사용 |
| 실시간 상태 | journal에서만 | **`/slots` API (1차) + journal (2차)** |
