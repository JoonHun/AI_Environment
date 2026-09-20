---
name: ollama-multi-model-setup
description: Plan Ollama concurrent models, shared GPU memory, and MTP speed tuning
version: 1.0.0
author: Hermes Agent (autonomous)
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ollama, gpu, memory, unified, concurrent-models]
    related_skills: [ollama-monitor-dashboard]
---

# Ollama Multi-Model Setup

## When to Use

The user asks about **running Ollama on a shared machine**, **loading multiple models simultaneously**, or **planning GPU/memory capacity** for local AI inference. Covers GB10-style unified memory systems and traditional discrete-GPU setups.

When the user wants to **run Ollama on a shared machine**, or asks about running **multiple models at once**, this skill gives the reference for:

1. How much VRAM / unified memory each model needs (GGUF 4-bit approximation).
2. Which Ollama env vars control concurrent loading (`OLLAMA_MAX_LOADED_MODELS` etc.).
3. Hardware-capacity planning (unified-memory systems like GB10 vs discrete VRAM).
4. Runtime monitoring (`ollama list`, `nvidia-smi`, `free -h`).

## Quick decisions

### Will multiple models fit at once?

Approximate 4-bit GGUF sizes:

| Parameters | Model size on disk | RAM/VRAM needed (inference) |
|------------|--------------------|-----------------------------|
| 7B         | ~5 GB              | ~6-8 GB                     |
| 13B        | ~9 GB              | ~10-14 GB                   |
| 26B        | ~17 GB             | ~18-24 GB                   |
| 35B        | ~23 GB             | ~24-30 GB                   |
| 70B        | ~45 GB             | ~48-56 GB                   |

**Rule of thumb**: allow +4–8 GB headroom per model for KV cache and context.

### Unified memory systems (GB10, Mac M-series)

CPU and GPU share one pool — no separate VRAM limit. The total available is the machine's RAM minus OS + other processes (~5-10 GB usually). This means:

```
Available = Total RAM - ~8GB overhead
Two-model load = model_1_RAM + model_2_RAM ≤ Available
```

### Discrete GPU systems (RTX 3090/4090, A-series, etc.)

Each GPU has its own VRAM ceiling. Models must fit in one GPU or use CPU offload (which drastically slows inference). Check: `nvidia-smi` for total VRAM per device.

## Ollama env vars

```bash
# Maximum models loaded simultaneously (default: 1)
export OLLAMA_MAX_LOADED_MODELS=3

# Total GPU memory to use (fraction, default all)
export OLLAMA_GPU_MEMORY_FRACTION=0.8

# Context window
export OLLAMA_CONTEXT_LENGTH=4096    # or higher for long-context models

# Host binding
export OLLAMA_HOST="0.0.0.0:11434"  # allow remote connections
```

Set these in `~/.bashrc`, `~/.profile`, or the systemd service overrides for persistence.

## Runtime monitoring

```bash
# Loaded models and status
ollama list          # shows all locally pulled models

# GPU VRAM usage per process
nvidia-smi           # check "Memory-Usage" column

# System RAM (for unified-memory systems)
free -h              # look at "available" line

# Per-process GPU memory (Linux with Nouveau/NVIDIA drivers)
watch -n 1 nvidia-smi
```

## Troubleshooting

### "OOM — out of memory" when loading models
- Too many models loaded simultaneously. Reduce `OLLAMA_MAX_LOADED_MODELS`.
- Discrete GPU: check `nvidia-smi`; if VRAM is full, unload unused models (`ollama stop <name>`).
- Unified memory: total RAM must fit all models + overhead. 128 GB can hold ~4 mid-size models (7B–35B) in 4-bit.

### Models appear to load but inference is slow
- CPU offload happened — check `ollama ps` for CPU vs GPU assignment.
- Memory bandwidth bottleneck on unified-memory systems. This is normal; 273 GB/s on GB10 beats PCIe copy overhead but still can't match dedicated VRAM speed.

## MTP / speculative decoding (speed)

Ollama (0.32.x) exposes Multi-Token Prediction via the Modelfile parameter `draft_num_predict` — no flag on the request side.

- **Separate binaries, not just a flag**: `model:27b` and `model:27b-mtp-q8_0` are distinct GGUFs. Only the `-mtp` build carries the embedded MTP tensors; `draft_num_predict N` on a non-MTP binary has no drafter to act on.
- **Enable**: `PARAMETER draft_num_predict 4` (0 disables). `1`–`4` is the usual range.
- **Verify it landed**: `POST /api/show` with body `{"name": "<model>"}` (GET + query string returns 405) — the `parameters` blob lists `draft_num_predict`.
- **Delete a model**: `DELETE /api/delete` with a **JSON body** `{"name":"<model>","tag":"<tag>"}` — **not** a query string (`...?name=` → `missing request body`). Success = empty 200 body; confirm via `GET /api/tags`.
- **`ollama create` is ~instant over a pulled base** — it reuses existing layer digests (`using existing layer sha256:...`), adding no extra disk. Batch-creating custom variants over one base is safe/cheap.
- **Benchmarking pitfall (learned the hard way)**: tok/s from `/api/chat` `eval_count / eval_duration` is dominated by **quantization**, not MTP — Q8_0 can measure *slower* than Q4_K_M on a memory-bandwidth-bound unified-memory box (observed 16.7 vs 25.8 tok/s on GB10, Q8+MTP vs Q4 plain). To isolate MTP's contribution, A/B at the **same quantization** (`...-q4_K_M` vs `...-mtp-q4_K_M`).
- **Disable thinking on Ollama SLMs**: put `/no_think` in the `system` field of `/api/chat` (benchmark-verified for Qwen3.8). Hermes desktop UI's Thinking toggle is the session-level equivalent.
- **User's Modelfile convention (final, user-corrected)**: files in `~/ollama-modelfiles/` named `Modelfile.<series>_<params>_<ctx>[_Q4|_Q8][_MTP][_dflash]` — **every filename carries its quantization** (`Q4`=q4_K_M, `Q8`=q8_0), and **any trailing suffix (`MTP`, `dflash`) is always the LAST component** (e.g. `Modelfile.qwen3.8_27B_128K_Q4_MTP`, not `..._MTP_Q4`). Custom server model name = the filename with the `Modelfile.` prefix dropped, verbatim (`Modelfile.gemma4_26B_64K_Q4` → model `gemma4_26B_64K_Q4`); create with `ollama create <name> -f <file>` (reuses already-pulled layers, ~instant). Legacy `qwen3.8-nctx-128k*` names predate this convention.
  - **Suffix preservation is non-negotiable (user-corrected 2026-08)**: when a base carries a distinguishing suffix (`-mtp`, `-dflash`, `-coding`), the custom name MUST keep it at the end — `muse-glimmer:30b-q8_0-dflash` → `muse-glimmer_30B_128K_Q8_dflash`, not `muse-glimmer_30B_128K_Q8`; `qwen3.6:35b-a3b-coding-mtp-q4_K_M` → `qwen3.6_35B_128K_Q4_CODING_MTP` (base `-coding-mtp` → tail `CODING_MTP`, quant `Q4` stays the penultimate component before suffixes). Dropping such tags is an explicit user correction, not a style preference.
  - **Renaming a created custom model**: `ollama create` has NO rename — recreate under the new name from the same Modelfile (cheap: layers shared, ~instant) and `ollama rm` the old one; `mv` the Modelfile file too.

## Support files

| File | Purpose |
|------|---------|
| `references/ubuntu-memory-planning.md` | GB10-style unified memory capacity planning results from live sessions |
| `references/ollama-mtp-benchmarks.md` | MTP setup, NVFP4 support, tier selection, benchmarks (GB10) |
