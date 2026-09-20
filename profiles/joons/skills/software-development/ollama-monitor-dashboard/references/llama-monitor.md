# llama-monitor (:5002) — llama.cpp multi-instance dashboard

Sibling of ollama-monitor (:5000), same design language. Flask + waitress, systemd **user**
service `llama-monitor`. Files: `~/.hermes/services/llama-monitor/{app.py, templates/index.html,
config.yaml}`, unit `~/.config/systemd/user/llama-monitor.service`. Config lists the llama-server
instances (resident + on-demand, e.g. 11534–11537), each backed by a `llama-server-*.service`.
Do NOT touch :5000 (ollama-monitor) while working here.

## Stage classification (prefill / decode / idle) — journal-first
- This build's `/slots` cannot distinguish prefill from decode:
  - `n_prompt_tokens` keeps rising during decode (cumulative),
  - `n_prompt_tokens_processed` stops at the prefill length,
  - `n_decoded` is `None` while processing.
  So `processed < total` reads "prefill" for the whole generation. Do NOT classify on these.
- Rule (implemented in app.py): when the API says `is_processing`, read the unit journal:
  - journal `n_gen` lines are flowing → **decode** (journal wins over the API),
  - no `n_gen` yet → **prefill** (prefill genuinely has no `n_gen` lines),
  - API idle → **idle**.

## Standby semantics — backend down is NORMAL
Stopping an on-demand llama-server (unload) is the healthy "standby" state, not a failure:
- API: for `status=standby` send `error=None` (a failed health probe's `ConnectionError` must
  NOT surface), and `active` from the journal only while the server is `up` (stale
  `active=true` residue makes a dead card look live).
- UI: never render the red `err:` line for standby; show a dim "model not loaded (standby)"
  row instead.
- Real failures (a resident server down, probe failing while `up`) must still show the error.

## UI conventions (user-set — do not revert)
- **English-only** UI text (ollama-monitor stays Korean).
- Card header order: **port → `Resident` (capital R) → model name**; model name styled
  `text-white text-lg font-bold font-mono truncate max-w-[480px]` (18px, white, bold).
- Last-seen timestamp: always shown when present, `YYYY-MM-DD HH:MM:SS` (space, not `T`),
  no "stale" wording.
- Layout v3: `body h-screen overflow-hidden flex-col`; only `#servers` is
  `flex-1 min-h-0 overflow-y-auto` (the page itself must not scroll).
- Capacity: decimal GB (1000³), 2 decimals, label "GB". RAM from `/proc/meminfo`: `kB` is KiB →
  `kB*1024/1000³`. Storage: pick the `/` mount (largest total), never `storage[0]`
  (`/boot/efi` sorts first and is ~0.5 GB).

## MTP tuning (GB10, qwen3.8-27b, `--spec-type draft-mtp`)
- `--spec-draft-n-max` is **non-monotonic**: 2≈3 < **4** (optimum), 6 slightly worse
  (measured ~23.8 → 26.8 → 26.2 t/s decode).
- A/B on a throwaway `llama-server` on a spare port (116xx) with a fixed-token benchmark;
  only then patch the production unit + `systemctl --user restart`. The resident instance may
  back a live chat session — a restart briefly interrupts it.
- Bench method: POST to `/v1/completions` with a fixed prompt, read `completion_tokens /
  completion_tokens_per_second` from the response — no streaming parse needed.
