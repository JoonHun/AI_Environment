# GB10 (NVIDIA Grace Blackwell) Unified Memory Capacity Planning

> Session reference: 2025-08-26 — Discord profile split analysis + Ollama concurrent model loading on Gigabyte AI TOP ATOM.

## Hardware Summary

| Item | Value |
|------|-------|
| CPU | 20-core Arm (10x Cortex-X925 + 10x Cortex-A725) |
| GPU | NVIDIA Blackwell (6,144 CUDA cores, 5th Gen Tensor Cores) |
| **Memory** | **128 GB unified LPDDR5X** (CPU+GPU shared, 273 GB/s bandwidth) |
| TDP | 180 W peak ~207 W |

## Key Architecture Point

**No separate VRAM.** CPU and GPU access the same physical memory through NVLink-C2C coherence. This means:
- Model weights load once into unified pool, no PCIe copy between CPU→GPU
- KV cache shares the same pool as model weights (long context fits easily)
- Available = total RAM minus OS + other processes (~10 GB headroom typically)

## Capacity Planning for Concurrent Models (GGUF 4-bit approx.)

| Model | Params | Disk Size | Inference Need | Two-model with qwen35B |
|-------|--------|-----------|----------------|----------------------|
| qwen3.6-nctx-128k | ~35B | ~23 GB | ~24–30 GB ✓ | — (base model) |
| gemma4:26b | 26B | ~17 GB | ~18–24 GB ✓ | Total ~50 GB / 128 = OK |
| llama3.3:70b | 70B | ~45 GB | ~48–56 GB ⚠️ | With gemma26b: ~80+ GB, tight |

**Verdict from session**: Two mid-size models (qwen35B + gemma26b) fit comfortably with KV cache headroom. Three or more may approach limits depending on context length.

## Ollama Concurrency Findings

- `OLLAMA_MAX_LOADED_MODELS` defaults to **1** — must be set >1 for concurrent access
- GB10 unified memory handles multiple GPU loads transparently (no VRAM partitioning)
- Inference is sequential within a single model (LLM autoregressive, cannot parallelize per-token generation)
- Different models can run simultaneously if within total capacity

## Monitoring Commands

```bash
ollama list                    # all local models
ollama ps                     # currently loaded + memory used per model
free -h                       # check available unified RAM
nvidia-smi                    # GPU utilization (Blackwell-specific metrics)
watch -n 1 nvidia-smi         # live monitoring
```
