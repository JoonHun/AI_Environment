# RAM accounting: why the RAM card ≠ sum of `size_vram`

User-reported "bug": the RAM card showed **78.3 GB used** while the Loaded models table
showed only **2.5 GB + 3.2 GB**. Verified on the GB10 (2026-08-27): **the numbers are
correct — different accounting scopes.**

## What each column/sensor actually measures

| Indicator | Scope |
|-----------|-------|
| RAM card (used) | `/proc/meminfo MemTotal − MemAvailable` — the WHOLE unified pool: model weights (wherever they sit), KV caches, page cache of model files, OS, Hermes desktop app, both Gateways, everything. |
| `size_vram` (Loaded models, from Ollama `/api/ps`) | **Only the tensor bytes Ollama placed in the GPU/VRAM slice** of the unified pool. The remainder of a model's weights + KV cache live in the CPU-RAM slice — invisible here. |

So `RAM used − Σ size_vram` = model weights/KV in the CPU slice + page cache +
OS + all other processes. That gap is **expected and healthy**, not a leak.

## Verified case study (GB10, 2026-08-27 23:21 KST)

Two models concurrently loaded via real `POST /api/generate` probes:

```
qwen3.8_27B_128K_Q8_MTP:latest        size_vram = 29.7 GB   (27.3B Q8_0 — the whole model fits the VRAM slice)
muse-glimmer_30B_128K_Q4_dflash       size_vram =  3.5 GB   (27.9B Q4_K_M — only part in the VRAM slice)
Σ size_vram = 33.1 GB
RAM used (monitor) = 78.6 GB
Gap = 45.5 GB → muse Q4 weights/KV in the RAM slice (~20–25 GB) + OS + Hermes + Gateways (~25–30 GB) ✓
```

**Why the Q8 MTP shows ~its full size but dflash models show tiny `size_vram`:**
Ollama splits layers between the GPU and CPU slices of the unified memory according to
the engine's offload decision. A dense Q8 model that fits gets (nearly) everything in
the VRAM slice → `size_vram` ≈ model size (looks "correct"). Slower/offloaded or
partially-offloaded setups leave most weights in the RAM slice → `size_vram` is a
small fraction (looks "broken"). Same model, same memory pool — the split is what moves.

## When debugging this

1. **Compare scopes before calling it a bug.** Pull both live:
   - `curl -s http://127.0.0.1:11434/api/ps` → per-model `size_vram`, `expires_at`
   - `curl -s http://localhost:5000/api/status` → `gpu.ram.used_gib/total_gib`
   - `free -h` → `MemTotal/MemAvailable`
2. **Force-load models to test** (safe probe, no `&` backgrounding in terminal): run
   `POST /api/generate` with `{"model":"...","prompt":"Hi","stream":false,
   "options":{"num_predict":1}}` sequentially with high `timeout`; then re-read `/api/ps`.
3. Remember `/ps` is **live state**: models expire (`expires_at`) and get evicted under
   `OLLAMA_MAX_LOADED_MODELS` pressure — a screenshot and a fresh `/api/ps` can describe
   different model sets entirely.
4. If the UI still confuses the user, add a total row to the Loaded models table
   (`Σ VRAM`) and/or label the column "In VRAM (slice)" — the accounting gap is the
   explanation, not a fix.
