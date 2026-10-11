---
name: local-llm-serving
description: "Local llama.cpp serving, proxy ports, monitor, engine swaps."
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llm-serving, llama-cpp, llama-proxy, llama-monitor, model-swap, strata, local-inference]
---

# Local LLM Serving (llama.cpp + llama-proxy + llama-monitor)

## When to Use
- Adding, removing, or swapping the model engine behind a Hermes profile.
- Reading or changing load/unload/keep behavior in the llama-monitor dashboard.
- Diagnosing why a model is down, OOM'd, or not unloading on idle.
- Planning a new local inference engine (e.g. Strata) onto this box.
- NOT for: remote API providers (OpenRouter/Anthropic/etc.) — those don't use the proxy.

This box runs `llama.cpp llama-server` instances behind a **raw-TCP llama-proxy**.
Front ports `11534-11538` (what clients/Hermes hit) map to backends `1534-1538`
(the real servers). llama-monitor (Flask, port **5002**) is the ops dashboard that
reads their state and drives load/unload. Config lives at
`~/.hermes/services/llama-monitor/{config.yaml,app.py}`.

## Always-on rules (apply to every change in this area)

- **Probe the FRONT port, never the backend, for on-demand models.** The proxy is a
  raw-TCP tunnel: a connection to the backend port *boots* the backend and defeats the
  idle-unload watchdog. Resident/keep models can be probed either way, but stay on the
  front port to be uniform and safe. (llama-monitor already encodes this — read its
  `config.yaml` `backend_port` choice before trusting your own probe.)
- **Never hand-edit Hermes config.** Use `hermes --profile <name> config set KEY VAL`.
  Config is per-profile (`~/.hermes/profiles/<name>/config.yaml`); a `model.base_url`
  change is profile-scoped, not gateway-wide — that's how you swap ONE profile onto a
  new engine without touching the others.
- **Keep flags are file-based and shared.** `~/llama-proxy/keep/<front_port>` present
  = the proxy idle-watchdog will NOT unload that model, so it stays pinned in memory.
  Toggling keep does NOT load or unload by itself — it only arms/disarms auto-unload.
- **Memory is one shared pool here (GB10 = ARM + unified memory).** OS + every loaded
  model compete for it. Before loading a large model, free the pinned (keep-ON) ones.

## unload / keep mechanism (what the monitor actually does)

| Monitor endpoint | Effect |
|---|---|
| `POST /api/unload {port}` | `systemctl --user stop <journal_unit>` — **kills the backend process** (not just frees memory) |
| `POST /api/keep {port}` | creates/removes `~/llama-proxy/keep/<port>` — arms/disarms idle-unload; no load/unload action |

State classification (monitor, `/slots`-authoritative): `busy` (slot processing) / `idle`
(loaded, no task) / `standby` (on-demand, backend stopped — **normal**) / `down`.

## Swapping a profile onto a different engine (e.g. Strata)

1. Confirm the new engine's OpenAI-compatible endpoint + model slug (`GET /v1/models`,
   `GET /health`). Strata serves `http://localhost:8080/v1`, supports runtime
   `POST /load` / `POST /unload` (process stays up), and `GET /status`.
2. In the target profile: `hermes --profile <n> config set model.base_url http://localhost:8080/v1`,
   `... model.default <slug>`, keep `provider: llama` (OpenAI-compatible).
3. Gate calls on `GET /health` — `/load` takes 30-90s and requests in that window fail.

## Pitfalls that cost time

- **OOM from competing models.** A 125B-class load (Strata ~34-43GB RAM) against
  keep-ON 27B models on a unified-memory box will OOM. Turn OFF the keep flags for the
  models you're not using before loading the big one.
- **Don't conflate the two 'unload' mechanisms.** llama.cpp unload = stop the process.
  Strata unload = free the model, keep the server. A monitor button wired to
  `systemctl stop` is WRONG for a Strata card and vice-versa — branch on engine type.
- **Keep has no counterpart for always-on engines.** If an engine keeps the model
  resident by default (Strata), the 'keep' toggle is meaningless — model it as a status
  indicator, not a switch.
- **ARM host gotcha.** GB10/Grace has no x86 AVX flags; engines whose decode kernels
  assume AVX-512/AVX2 (Strata's CPU expert path) may not run. Verify on-device before
  committing to an engine — don't infer support from 'Linux' in the docs.

## Verify before claiming it works

- `systemctl --user is-active <unit>` for a backend's real state.
- `ss -tlnp | grep :<port>` to see who owns the front port (a `python3` listener is
  the proxy, not the model).
- `GET <front>/health` + `GET <front>/v1/models` to confirm the model is actually up.
