# Ollama API Name Resolution — Loaded vs Installed

## Problem
Dashboard "Loaded models" displays a different name than "Installed models" for the same binary.

Example: `qwen3.6-nctx-64k:latest` (installed/tag) → displayed in "Loaded" as `qwen3.6:35b`.

## Root Cause
Ollama `/api/ps` endpoint returns the **base model name embedded in the binary** (`"name": "qwen3.6:35b"`), not the user-assigned tag (`"qwen3.6-nctx-64k:latest"`). This is confirmed by checking both endpoints directly:

```bash
curl -s http://127.0.0.1:11434/api/ps
# → "name": "qwen3.6:35b"

curl -s http://127.0.0.1:11434/api/tags | jq '.models[] | select(.details.parent_model == "qwen3.6:35b")'
# → "name": "qwen3.6-nctx-64k:latest" (parent_model links to the same binary)
```

## Resolution Options
1. **Map loaded names back to tags**: In `sample_ollama()`, cross-reference `/api/tags` entries with `details.parent_model` against each loaded model's name, then display the tag.
2. **Alias map**: Maintain a static alias list (tag → base_name). Good for stable repos but breaks if aliases change.
3. **Accept divergence**: Both representations are correct — base binary identity vs convenience alias. Add a tooltip clarifying this.

## Decision
Option 1 is the cleanest fix: modify `sample_ollama()` to build a reverse-map from parent_model → name, then enrich loaded entries with their tag names when available. This keeps the dashboard informative without losing the ability to identify the actual binary.
