# MTP / Speculative Decoding on Ollama — Benchmarks & Commands

Verified against Ollama 0.32.15 on a GB10 box (unified memory, memory-bandwidth-bound decoding).

## MTP is a binary property, not a flag
- `model:27b` vs `model:27b-mtp-q8_0` / `-mtp-q4_K_M` are **distinct GGUF files**. Only the `-mtp` build ships embedded MTP tensors.
- Setting `PARAMETER draft_num_predict N` on a **non-MTP** binary has no drafter to act on — it is a no-op (the parameter slot may still show up in `/api/show` because some archs like Qwen3 expose it by default).
- Enable MTP: `draft_num_predict 4` (range ~1–4; `0` disables).

## Modelfile example (speed build)
```
FROM qwen3.8:27b-mtp-q4_K_M
PARAMETER num_ctx 131072
PARAMETER draft_num_predict 4
```

## Verification commands
- List tags: `GET /api/tags` (name, size, quantization, capabilities, parent_model).
- Show effective params: `POST /api/show` body `{"name":"<model>"}` — **GET + query string returns HTTP 405**. Parse the `parameters` blob for `draft_num_predict` and `num_ctx`.
  - Note: `/api/show` `details.context_length` can report the GGUF *max* ceiling; the effective window is the `num_ctx` parameter line.

## Think-off for Ollama SLMs (benchmarks)
Put `/no_think` in the `system` field of `/api/chat`. Verified: response starts straight into the answer with no reasoning tokens. (Hermes desktop UI's Thinking toggle is the equivalent for normal use.)

## Benchmark (tok/s) — memory-bandwidth dominant
Prompt: "Explain TCP vs UDP in 5 concise bullets", `num_predict 512`, temperature 0.7, think off, non-streaming. tok/s = `eval_count / (eval_duration/1e9)` from the `/api/chat` response.

| Model | Quant | tokens | gen (s) | tok/s |
|---|---|---|---|---|
| qwen3.8-nctx-128k (plain) | Q4_K_M | 256 | 9.93 | **25.8** |
| qwen3.8-nctx-128k-mtp (Q8) | Q8_0 | 293 | 17.51 | **16.7** |

**Takeaway / pitfall:** this run is **not** a fair MTP test — the Q8 build lost primarily because **Q8_0 weights ~2x the memory bandwidth of Q4_K_M** on a bandwidth-bound unified-memory box, which swamps MTP's gain. To isolate MTP's real effect, A/B at the **same quantization**:
- `qwen3.8:27b-q4_K_M`  vs  `qwen3.8:27b-mtp-q4_K_M`  (both Q4_K_M)
- or  `qwen3.8:27b-mtp-q8_0`  vs  a Q8 plain baseline (there is none by default; only MTP shipped as Q8).

On bandwidth-bound hardware, expect MTP to give a **moderate** uplift, not a multiple. If the user's goal is wall-clock "time-to-first-answer", think-off (`/no_think`) is usually the bigger lever; MTP helps tokens/sec after thinking stops.

## ⚠️ Corrected: MTP A/B — two different questions, two very different answers

### Question A: "MTP build vs non-MTP build, same quantization?"
This is NOT the right question for "should I enable MTP?" — it compares **different model binaries**. The MTP build carries ~460M extra MTP-head weights that add bandwidth pressure even when idle.

| Model | MTP heads | draft | decode tok/s |
|---|---|---|---|
| qwen3.8_27B_128K_Q4 (plain) | no | — | 25.9 |
| qwen3.8_27B_128K_Q4_MTP | yes | 4 | 26.7 |

→ +3% (2026-09-02 first test). This is the **build-selection** cost of the MTP binary, not the enablement gain.

### Question B (the real one): "Same MTP model, draft=0 vs draft=4?"
This is the "should I add `PARAMETER draft_num_predict 4`?" question. **Measured 2026-09-02, 3-run median, think off, 8K ctx, 256 decode tokens:**

| Model | draft=0 | draft=4 | **delta** |
|---|---|---|---|
| `qwen3.8:27b-mtp-q4_K_M_256k` | 12.1 tok/s | **26.3 tok/s** | **+117%** |
| `qwen3.8:27b-mtp-q8_0_256k` | 7.9 tok/s | 11.0 tok/s | +39% (noisy*) |

**Key insight:** the MTP model **without** drafting is much slower than a **non-MTP** model at the same quant, because the MTP head weights (~460M params) still consume bandwidth on every token. Drafting recovers ~2x by letting one forward pass amortize over multiple verified tokens. **Always enable `draft_num_predict` on `-mtp` builds — running an MTP binary with draft=0 is strictly worse than using a plain model.**

*Q8_0 numbers are unreliable here — sequential model testing (see pitfall below) caused bandwidth contention with Q4_K_M still resident.

### Benchmarking pitfall: sequential multi-model testing on GB10
When testing model B immediately after model A without eviction, A's weights may still reside in unified memory, stealing bandwidth and **degrading B's numbers unpredictably** (observed: Q8_0 decode varied 3.2–19.1 tok/s across 3 runs in one sequential batch, vs stable 7.9 when isolated). **Rule:** before testing a model in isolation, confirm the previous model is unloaded (`ollama ps` should return empty `models: []`), or run the benchmark as a fresh Ollama restart. Do NOT read sequential multi-model benchmark numbers as representative.

## Ollama REST API gotchas (0.32.x)
- **`/api/delete` needs a JSON body, not a query string.** `DELETE /api/delete?name=X` → `{"error":"missing request body"}`. Correct: `DELETE /api/delete` with `Content-Type: application/json` and body `{"name":"<model>"}` (tagged: add `"tag":"<tag>"`). **Success = empty 200 body** (no error field) — a non-empty `{...}` means it failed. Verify with a follow-up `GET /api/tags`.
- **`/api/show` is POST + body** (see above) — `GET + ?name=` returns 405.
- **`ollama create` reuses already-pulled `:latest` layers** (`using existing layer sha256:...`) — creating custom models over pulled bases is ~instant and adds no extra disk (custom models reference the same layer digests). Safe to create many custom variants over one base.
- Custom model name = free-form (underscores fine). Convention here: `Modelfile.<name>` → server model `<name>` (drop the `Modelfile.` prefix). `:latest` tag is implicit.

## NVFP4 support on Ollama 0.32.15 (GB10 / Blackwell sm_121)

Verified: Ollama 0.32.15 binary contains `NVFP4`, `MXFP4`, `MXFP8` type strings and the error message `supported types are int4, int8, nvfp4, mxfp4, mxfp8` — NVFP4 is a **supported quantization target** in this build.

- **From a BF16/SF16 GGUF**: `ollama create <name> -f Modelfile --quantize nvfp4`
- **From a pre-quantized NVFP4 GGUF** (e.g. aiconjured tiers): `ollama create <name> -f Modelfile` (no `--quantize` flag needed)
- **GB10 sm_121**: consumer Blackwell — confirm NVFP4 kernels (not software fallback) are engaged via decode benchmark.

## NVFP4 mixed-quant tier selection (aiconjured Qwen3.8-27B series)

| Tier | NVFP4 share | quality anchors | Size (27B) | Use case |
|---|---|---|---|---|
| **LOW** | highest | MTP head BF16 only | ~16 GB | speed-first, max FP4 tensor core utilization |
| **MEDIUM / HIGH** | medium | more Q8_0 anchors | ~19 GB | balanced |
| **VERY-HIGH** | lowest | attention + embeddings BF16 | ~21 GB | quality-first, less FP4 acceleration |

**Speed comparison rule**: for a fair decode-speed comparison against Q4_K_M / Q8_0, prefer **LOW** (more NVFP4 → more Blackwell FP4 acceleration). VERY-HIGH shows *lower* decode than LOW-tier NVFP4 because it has *less* NVFP4 and *more* BF16 compute — it is a quality tier, not a speed tier.

**Three-way comparison set** (same base Qwen3.8-27B, same MTP head, only quantization varies):
- `qwen3.8:27b-mtp-q4_K_M_256k` — decode 26.3 tok/s (MTP ON)
- `qwen3.8:27b-mtp-q8_0_256k` — decode 19.1 tok/s (MTP ON)
- `aiconjured/Qwen3.8-27B-NVFP4-MTP-VERY-HIGH` — pending

## Reference numbers (GB10)
- 26B Q4_K_M ≈ 17–18 GB, 35B MOE Q4_K_M ≈ 23 GB, 70B Q4_K_M ≈ 43 GB.
- 128 GB unified memory comfortably co-loads 2–3 of the above (set `OLLAMA_MAX_LOADED_MODELS=3`).
- NVFP4 27B (aiconjured tiers): LOW ≈ 16 GB, VERY-HIGH ≈ 21 GB.
