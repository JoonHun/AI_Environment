# Context compression tuning

How Hermes auto-compresses a long session, the knobs, and the non-obvious pitfalls.
Use when a session stalls on "Summarizing thread" / "waiting on ... no output yet",
or when the user wants compression to fire earlier or later.

## Mental model (verified in source: agent/context_compressor.py)

- Compression is **Pre-API and blocking**: it runs *before* the provider call, so the user
  always waits for it to finish before any response token. Routing it to a different model
  shortens the wait (faster model, parallel process) but never removes it.
- Trigger is **token-based, not memory-based**: when estimated request tokens exceed a
  threshold, the session is summarized to a target ratio and a recent tail is kept.
  KV-cache quantization does NOT change the trigger — it only reduces memory usage.
- "Summarizing thread" (desktop `status.tsx`) and "waiting on ... no output yet" (backend
  heartbeat) are the same event seen from two sides: the compression pass.

## The 75% floor (the big pitfall)

`_effective_threshold_percent` raises the threshold to `max(set_value, 0.75)` for ANY model
whose context window is **< 512K** (`_SMALL_CTX_WINDOW_LIMIT = 512_000`,
`_SMALL_CTX_THRESHOLD_PERCENT = 0.75`).

Consequence: `compression.threshold: 0.50` (or 0.60) on a 128K/64K model is **silently
floored to 0.75** — the lower value has no effect. Setting a low *ratio* is a no-op on
sub-512K models. Do not keep lowering `threshold` expecting an earlier trigger.

### Workaround: `threshold_tokens` (absolute cap)

The effective trigger is the **minimum** of the ratio-computed value and
`threshold_tokens`. To make a sub-512K model compress at ~50%, set an absolute token cap
instead of a low ratio:

    compression:
      threshold_tokens: 65536   # e.g. half of a 128K window

Verify it took: the log line reads `... >= 65,536` (the cap, not the floored ratio value),
and the trigger token count drops accordingly.

## "Compress less, more often" vs "compress more, less often"

Lowering the trigger = more frequent but shorter compression passes, and — the real win —
the model spends more turns working on a *shorter* context (faster normal responses).
Total summarization work is roughly the same; the user-felt difference is stall length.

## Prompt size ≠ input size

A short user message can still be a large prompt. Composition (biggest first):
system persona → tool schemas (often 10–30K tokens) → memory/user profile → skills list →
full history + tool outputs → the actual input. To shrink it: lower the compression trigger
(history), `/new`, trim verbose tool outputs, or reduce tool/persona overhead — NOT
`think low` (that trims *output* reasoning tokens, not the input prompt).

## Auxiliary compression model — reality check

Pointing compression at a second model only helps if that model is **already loaded**.
On on-demand serving (proxy stays up, backend starts on first POST), the first compression
request pays a full model-load cost that can exceed just compressing with the resident
model. "Another model" is a way to shorten the wait, not to remove it.

## Verify

    grep "compression" ~/.hermes/profiles/<name>/logs/agent.log | tail
    # look for: "Pre-API compression: ~N tokens >= THRESHOLD" and "summary_generation_ms"
