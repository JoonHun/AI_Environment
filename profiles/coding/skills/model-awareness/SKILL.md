---
name: model-awareness
description: Report the active LLM model in Hermes sessions.
version: 1.0.0
---

# Purpose
Accurately identify which LLM model is currently executing the assistant. Do **not** rely solely on the `default` entry in profile `config.yaml`; always verify the runtime model before stating it.

## Procedure
1. Query the running Hermes instance for the active model.
   - Preferred: `hermes --model` (or `hermes version` which prints the model line).
   - If a gateway service is active, inspect its recent logs:
     ```bash
     journalctl --user -u hermes-gateway-<profile>.service -n 5 | grep -i model
     ```
2. Parse the output to extract the model identifier (e.g., `gpt‑oss‑1128b‑MXFP4`).
   - Use a case‑insensitive regex like `(?i)model[:\s]+([\w\-]+)`.
3. Cache the result for the current turn to avoid repeated calls.
4. Respond concisely in Korean, e.g., "현재 실행 중인 모델은 **gpt‑oss‑1128b‑MXFP4**입니다."
5. If the query fails, fall back to the profile default **and** prepend a disclaimer: "(프로필에 지정된 기본값을 사용합니다.)"

## Pitfalls
- **Never trust the `default` entry** as truth; runtime overrides exist.
- **Multiple gateways** may run different models; always query the specific profile.
- **Parsing errors** can occur if CLI output contains extra text; use a robust regex.
- If the `hermes` CLI is unavailable, read the environment variable `HERMES_MODEL` as a fallback.

## Style Preference (User‑specific)
- Keep answers brief; avoid multi‑sentence explanations unless requested.
- Use Korean exclusively.
- Only surface the model name; omit technical details.

## References
- `references/model-query.md`
- `references/user-preferences.md`
