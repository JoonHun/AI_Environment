---
name: ollama-benchmarking
description: "GB10 Ollama: benchmark decode/prefill, MTP, Modelfiles."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ollama, benchmark, mlops, gb10, mtp, modelfile, speculative-decoding]
---

# Ollama model benchmarking & model ops (GB10)

## Standing rules (apply to every run)

1. **MTP name ≠ MTP active.** Speculative decoding runs only if `draft_num_predict` is set in the model's Modelfile. A tag containing `-mtp` with no `draft_num_predict` is a plain model. Verify before benchmarking: `ollama show <model> | grep draft_num_predict`.
2. **`ollama show` "context length" is the base max, not the effective `num_ctx`.** If the Modelfile omits `num_ctx`, Ollama runs at its small default → "context length exceeded" mid-session on long tasks. Always set `num_ctx` explicitly in custom models.
3. **Benchmark models solo.** Stop all other loaded models first — co-resident models share GB10 unified-memory bandwidth and corrupt decode numbers (co-resident runs measured ~half speed and swung wildly).
4. **Median of 2-3 runs, never min.** run1 is always cold-start (layer load into VRAM) and is an outlier; runs 2+ converge.
5. **Fair comparisons isolate ONE variable.** MTP A/B = same model, `draft_num_predict` 0 vs 4, everything else identical. Quantization comparisons hold MTP/draft constant.
6. **Stability check before ranking.** If a model's decode swings >5% across its own runs, flag it as non-deterministic on this build — do not fold it into a ranking as if stable. Re-test after an Ollama update before concluding.
7. **Destructive ops: list, then confirm.** Enumerate exactly which model tags/Modelfiles will be removed, show the surviving set, get confirmation before `ollama rm`.

## Benchmark procedure

1. Clear VRAM and verify it:
```bash
for m in $(curl -s localhost:11434/api/ps | python3 -c "import sys,json;[print(x['name']) for x in json.load(sys.stdin)['models']]"); do ollama stop \"$m\"; done
curl -s localhost:11434/api/ps   # expect "models": []
```
2. Run `scripts/bench.py` (stdlib-only; reads Ollama's non-streaming `prompt_eval_duration`/`eval_duration`):
```bash
python3 scripts/bench.py <model> [model...] --runs 3 --num-predict 256 --ctx 8192
python3 scripts/bench.py <model> --draft 0   # MTP off A/B
python3 scripts/bench.py <model> --draft 4   # MTP on A/B
python3 scripts/bench.py <model> --prompt-tokens 2048   # longer prefill stress
```
3. Report per-model median prefill/decode, call out run1 cold-start, flag instability per rule 6.

## Modelfile & custom-model workflow (user's layout)

- Modelfiles live in `~/ollama-modelfiles/`, named `Modelfile.<exact model:tag>`; the Modelfile is the source of truth for a custom model.
- Create: `ollama create <tag> -f <Modelfile>` — layers are shared blobs, so re-creates are instant.
- Rename = create new tag, then `ollama rm` the old one.
- Enable MTP on an existing model: add `PARAMETER draft_num_predict <N>`, re-create, verify with `ollama show`.
- Deriving a context variant (e.g. `_256k`) from a custom base: re-list the base's behavior params (`temperature`, `top_k`, `top_p`, `draft_num_predict`) explicitly in the child Modelfile so the file stays diffable and self-documenting.
- Point a profile at it: `hermes config set model.default <tag>` (profile-scoped HERMES_HOME). A live session's model is fixed at start — a NEW session is needed to pick up the change.

## Measured reference points (GB10, solo, thinking off) — sanity bounds

- Qwen 27B Q4_K_M: ~26 tok/s decode, ~1500 tok/s prefill (MTP on, draft=4)
- Qwen 27B Q8_0: ~19 tok/s decode (MTP on) — bandwidth-bound, expected slower than Q4
- MTP on this box: roughly +78~139% over no-draft decode for the 27B class
- Third-party NVFP4 (Blackwell FP4) tiers: decode was NON-deterministic (8~31 across runs); Q4_K_M-class GGUF was repeatable. Treat NVFP4 speed numbers as untrustworthy until the Ollama build stabilizes.
