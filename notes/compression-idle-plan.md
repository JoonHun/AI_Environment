# Hermes Context Compression — Idle/Background Compaction Plan

> **Status**: PARKED — user decided to handle urgent tasks first, revisit later.
> Decision context: user wants compaction to happen in **idle time** so it never
> blocks the first response. Current `idle_compact_after_seconds` is NOT acceptable
> (it runs at the start of the next turn = first response is slow).

## Current state (as of 2026-09-19)

- Config: `~/.hermes/config.yaml` → `compression:` block
  - `threshold: 0.5` (compact at ~128K of 256K)
  - `target_ratio: 0.2`
  - `protect_last_n: 20`
  - `idle_compact_after_seconds: 0` (DISABLED)
- Compaction fires **at turn start** (preflight) or on overflow — always in the
  request path. Each pass = a real LLM call to Qwen3.8-27B on GB10
  (~26 t/s decode, minutes for large summaries).

## Why it fires so often (measured, 2h window)

- 164 requests, 48% with 50K+ token conversations, 84 releases >50K.
- Context grows to 70-77K per conversation → hits 128K threshold → compact.
- GB10 bandwidth-limited → long prefill/decode during summary = perceived lag.

## Rejected options (with rationale)

1. **`idle_compact_after_seconds: 300`** (built-in feature)
   - Fires at **next turn start** after N seconds idle.
   - User: "말하는 시점에 압축하면 반응 속도가 느리게 느껴질 것 같은데" → rejected.
   - Source: `agent/turn_context_compaction.py::_idle_compaction` — runs
     `agent._compress_context()` in the request path before the first API call.
2. **`threshold: 0.75`** (compact less often, but each pass is bigger/slower)
   - User asked "그럼 한번 압축할 때 더 오래 걸리겠지?" → rejected (slower per-pass).
3. **`target_ratio: 0.1`** (more aggressive, but still in request path)
   - "많이 압축" = summarize MORE text = LONGER per pass → rejected.

## What the user actually wants

- Compaction should happen **during idle windows**, BEFORE the user types,
  so that the next request starts with an already-compacted context.
- Acceptance criteria (user-stated):
  - First response latency unchanged (no summary work in request path)
  - Compaction still happens (context doesn't grow unbounded)
  - No manual intervention needed

## Implementation directions to explore (in priority order)

### Option A: Cron-based background compaction (RECOMMENDED)
- Use `cronjob_manage` to schedule a job every N minutes.
- Job logic (PSEUDO — needs real implementation):
  1. Read the active session's message list from the session store.
  2. Estimate tokens (reuse `estimate_messages_tokens_rough`).
  3. If `tokens > threshold_tokens` AND `tokens > floor + last_compaction`:
     - Call `agent._compress_context(messages, ...)` in a background thread.
     - Persist the compacted messages back to the session store.
  4. Next real user turn sees the compacted context, no waiting.
- Concerns:
  - Session store locking (compression uses a lease/fence — see
    `agent/compression_facade.py`). Cron must respect the same lease.
  - Multiple sessions: pick the most-recently-active one, or all.
  - Summary LLM cost: same Qwen3.8-27B call, but off-request-path.
- Files to touch:
  - `~/.hermes/config.yaml` → add a `background_compaction:` block
  - New: `~/.hermes/services/compression-cron/` (systemd + Python script)
  - Or: extend existing `hermes cron` to support a `compress` action

### Option B: Gateway hook — idle watcher thread
- Add a background thread to the gateway process that:
  1. Tracks `_last_activity_ts` per session.
  2. Every 30s: for each idle session past the threshold,
     kick off a compaction task in a thread pool.
  3. Use the same `_compress_context` path (lease-aware).
- Pro: no separate process, sees live session state.
- Con: requires code change in `gateway/` or `agent/` — more invasive.

### Option C: llama.cpp-side precompaction (NOT RECOMMENDED)
- llama.cpp has no native "summarize old context" feature.
- Would require a custom prompt pipeline. Rejected as overkill.

## Key source files (for whoever picks this up)

| File | What |
|------|------|
| `agent/turn_context_compaction.py` | `_idle_compaction` (line 143) — current idle path, request-bound |
| `agent/turn_context.py` | `_should_idle_compact` (line 355) — the pure predicate |
| `agent/compression_facade.py` | `compress_now`, lease/fence logic |
| `agent/conversation_compression.py` | `conversation_history_after_compression`, status templates |
| `agent/agent_init.py:1472` | reads `idle_compact_after_seconds` from config |
| `~/.hermes/config.yaml` lines 56-73 | `compression:` block |

## Open questions (ask user before implementing)

1. **Which session(s)?** Only the most-recently-active, or all open sessions?
2. **Idle threshold?** 5 min? 10 min? 30 min?
3. **Cost ceiling?** Max summary tokens per idle window to avoid a 10-min
   summary blocking the GPU for other work?
4. **Conflict with active turn?** If user starts typing while a background
   compaction is in flight, what wins? (Likely: background compaction
   completes, user turn sees the result — but verify lease behavior.)
5. **Visibility?** Should the UI show a "compacting in background…" indicator?

## Next step when user is ready

1. Confirm open questions above.
2. Pick Option A (cron) or B (gateway thread).
3. Spike: write a 50-line script that compacts ONE session in the background
   and verify the next turn sees it without waiting.
4. Integrate with systemd / hermes cron.
5. Update this doc with the chosen approach and mark DONE.
