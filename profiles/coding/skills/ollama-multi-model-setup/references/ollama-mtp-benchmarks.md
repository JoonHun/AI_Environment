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

## Fair MTP A/B (same quantization) — the real number
To isolate MTP from the quantization effect, A/B was done at the **same Q4_K_M** quant (`qwen3.8_27B_128K_Q4` vs `qwen3.8_27B_128K_Q4_MTP`), think off (`/no_think`), same prompt, 3-run average. tok/s = `eval_count / (eval_duration/1e9)`.

| Model | Quant | MTP | decode tok/s | prefill tok/s |
|---|---|---|---|---|
| qwen3.8_27B_128K_Q4 | Q4_K_M | no | 25.9 | 242 |
| qwen3.8_27B_128K_Q4_MTP | Q4_K_M | yes (`draft_num_predict 4`) | **26.68** | **274** |

**Result: MTP ≈ +3% decode, +13% prefill on GB10.** Confirmed *working* (consistent, not noise) but **moderate** — on a memory-bandwidth-bound unified-memory box, MTP's "one forward pass verifies several draft tokens" gain is capped by shared LPDDR5X bandwidth. Discrete-VRAM GPUs (high bandwidth) see larger gains (1.5–2x reported elsewhere).

**Bottom line for the user's goal (perceived speed):** think-off (`/no_think`, or the Hermes desktop Thinking toggle) is the **dominant** lever — it removes the thinking-token count. MTP is a small top-up on tok/s. Don't over-promise MTP; set user expectations on think-off.

## Ollama REST API gotchas (0.32.x)
- **`/api/delete` needs a JSON body, not a query string.** `DELETE /api/delete?name=X` → `{"error":"missing request body"}`. Correct: `DELETE /api/delete` with `Content-Type: application/json` and body `{"name":"<model>"}` (tagged: add `"tag":"<tag>"`). **Success = empty 200 body** (no error field) — a non-empty `{...}` means it failed. Verify with a follow-up `GET /api/tags`.
- **`/api/show` is POST + body** (see above) — `GET + ?name=` returns 405.
- **`ollama create` reuses already-pulled `:latest` layers** (`using existing layer sha256:...`) — creating custom models over pulled bases is ~instant and adds no extra disk (custom models reference the same layer digests). Safe to create many custom variants over one base.
- Custom model name = free-form (underscores fine). Convention here: `Modelfile.<name>` → server model `<name>` (drop the `Modelfile.` prefix). `:latest` tag is implicit.

## Reference numbers (GB10)
- 26B Q4_K_M ≈ 17–18 GB, 35B MOE Q4_K_M ≈ 23 GB, 70B Q4_K_M ≈ 43 GB.
- 128 GB unified memory comfortably co-loads 2–3 of the above (set `OLLAMA_MAX_LOADED_MODELS=3`).
