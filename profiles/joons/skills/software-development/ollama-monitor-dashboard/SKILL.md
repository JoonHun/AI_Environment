---
name: ollama-monitor-dashboard
description: Maintain the GB10 status dashboards (ollama-monitor :5000, llama-monitor :5002) — shared design language, capacity units, and storage/render pitfalls.
---

# Ollama Monitor Dashboard

The LAN status dashboard for Ollama + GPU/CPU/RAM on the GB10 box (192.168.219.115).
Served by **waitress** on port **5000**, run as the **systemd user service** `ollama-monitor`
(linux, aarch64, NVIDIA aarch64 driver, no X — GPU via `nvidia-smi`, CPU/thermal via sysfs).

## Files
- `~/.hermes/services/ollama-monitor/app.py` — Flask app + background sampler thread
- `~/.hermes/services/ollama-monitor/templates/index.html` — single-page UI (inline JS, Tailwind CDN)
- `~/.hermes/services/ollama-monitor/config.yaml` — config (deep-merged over built-in defaults)
- `~/.config/systemd/user/ollama-monitor.service` — unit (WantedBy=default.target)
- Log: `~/.../ollama-monitor/app.log` (rotating). `venv/` has Flask, waitress, requests, PyYAML.

## Architecture (keep these invariants)
- A **daemon sampler thread** runs `sample_ollama()` + `sample_gpu()` + `sample_cpu()` every
  `sample_interval_sec` (default 2) and stores the sample in `STATE["latest"]` + a `HISTORY`
  deque. All API routes just serve that cache — they never block on slow `nvidia-smi`/REST.
- Routes: `GET /` (template), `GET /api/status` (latest sample), `GET /api/history`
  (downsampled ring for the trend chart — includes `t, cpu, util, vram`), `GET /api/health`,
  `POST /api/speed-test` (REAL inference via `/api/generate`, never faked).
- The UI polls `/api/status` every 5s and `/api/history` every 15s. `LAST_LOADED` in the JS
  mirrors the loaded-model list so the speed test stays pinned to a **loaded** model.
- To add a **live metric card**: sample it in the collector → expose on the sample dict →
  render in `updateDashboard()` (use the `setBar(numId, barId, pct)` helper for % bars) →
  for a **trend line**: add a field in `/api/history`, a `datasets[]` entry in `initChart()`,
  and a `datasets[N].data = items.map(...)` line in `loadChart()`.

## Workflow (the reliable path)
1. **Edit**, then validate: `venv/bin/python -c "import ast; ast.parse(open('app.py').read())"`.
   For index.html render-check (catches a stale/old template before it hides behind a live
   proc), see `references/ops-pitfalls.md`.
2. **Restart**: `systemctl --user restart ollama-monitor`; wait ~4s; `systemctl --user is-active`
   should read **active**.
3. **Verify the SERVED artifact, not the disk file** — the #1 gotcha is a stale live process
   serving old HTML/API. Grep the *fetched* page and the *fetched* API for your new tokens:
   `curl -s localhost:5000/ -o /tmp/p.html && grep -F '<your-new-token>' /tmp/p.html`
   and `curl -s localhost:5000/api/history -o /tmp/h.json` then parse the file (pipe-to-python
   gets a HIGH security flag).
4. Confirm a **single** monitor proc: `ps -eo pid,etimes,cmd | grep "ollama-monitor/venv/bin/python app.py" | grep -v grep`.

## Pitfalls (the ones that actually bit us — always read first)
- **Flask does NOT reload a template after it has rendered it once.** A template (or app.py)
  edit made while the service was already running is **invisible until `systemctl --user restart
  ollama-monitor`** — this session, a template fixed at 17:45 kept serving the old layout for
  hours (service had started 16:31) and `Ctrl+Shift+R` in the browser did NOT help (this is NOT
  a browser-cache problem). ALWAYS: edit → **restart** → verify the **served** output.
- **Never trust the disk file or user report as verification.** After every dashboard change,
  curl the *served* artifact and confirm your new token is present:
  `curl -s localhost:5000/ | grep -F '<new-token>'` and `curl -s localhost:5000/api/status
  | grep <new-field>`. "User says the screen is unchanged" + "file on disk is correct" ⇒ the
  live process predates the edit ⇒ stale proc, not a cache or a bug in your code.
- **Storage collector (`sample_storage()`)**: parse `/proc/mounts` and **skip virtual/pseudo
  filesystems** — `snap`, `loop*`, `tmpfs`, `efivarfs`, `udev`, `devpts`, `hugetlbfs`, `mqueue`,
  `sunrpc` — or the list balloons to 15+ entries (8 of them 0 GB). GB10 real mounts =
  `/` (nvme0n1p2, ~916 GB) + `/boot/efi` (nvme0n1p1, 0.5 GB). Use `shutil.disk_usage(mount)`.
- **Storage card: never `storage[0]`.** The storage API returns an array of ALL real mounts
  (GB10: `/` ~916GB and `/boot/efi` ~0.5GB, with `/boot/efi` FIRST). `storage[0]` = the tiny
  `/boot/efi` → the card shows 0.5GB, not 916GB. Select the `/` mount (or the largest
  `total_gb`), or explicitly sum the array — never index `[0]`.
- **`pkill -f "<pattern>"` and `pgrep -f "<pattern>"` self-match the Hermes bash wrapper.**
  The command line you pass becomes part of `bash -c '…the pattern…'`, so `-f` matches your own
  shell and you SIGTERM yourself. Kill by **explicit PID** (`kill -9 $PID`), never by `-f` pattern.
- **A stale long-lived proc blocks the port + serves old code.** Symptoms: `is-active` stuck at
  `activating`, huge `NRestarts`, and the served page still shows the old layout. Cause: an old
  `app.py` proc (sometimes 3h+ old) never died, port 5000 stays bound, new spawns fail to bind
  and die. Fix: kill the explicit old PID, then restart. See references/ops-pitfalls.md.
- **`systemctl --user restart` alone does NOT swap a running proc that ignores it** — if the
  served output doesn't change after restart, the old proc is still in memory. Kill by PID.
- Never hardcode served IP in UI copy as the source of truth; read from config. (Current UI hardcodes 192.168.219.115 — known minor issue.)
- **llama-monitor standby: backend down is NORMAL, not an error.** Stopping an on-demand
  llama-server (unload) is the healthy state, but a failed health probe records
  `ConnectionError` and stale journal fields (`active`, `last_seen`) leak into the card — a
  red `err:` line + `active:true` that looks broken. Rule: for `status=standby` the API must
  send `error=None`, and `active` reflects the journal only while the server is `up`; the UI
  never renders an `err:` line for standby. Real failures (resident server down) still show.
  See references/llama-monitor.md.
- **This llama.cpp build's `/slots` cannot distinguish prefill from decode** — `n_prompt_tokens`
  keeps rising DURING decode and `n_prompt_tokens_processed` stops at the prefill length, so
  `processed < total` reads "prefill" for the whole generation. Classify stage from API
  `is_processing` + the unit journal: busy + journal `n_gen` flowing → **decode** (journal wins);
  busy + no `n_gen` → **prefill**; idle → idle. See references/llama-monitor.md.

## GB10 telemetry facts (use these, don't re-derive)
- `nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,power.draw` works; `--query-gpu=name` works.
- **VRAM is NOT readable** (`memory.used/total` = N/A on unified-memory GB10). Real "VRAM in use"
  = `nvidia-smi --query-compute-apps=pid,process_name,used_memory` (e.g. `llama-server`), plus
  `/proc/meminfo` for the unified pool (`MemTotal`/`MemAvailable`). This is the `gpu.ram` + `vram_proc_mib`.
- **CPU util**: no `top` needed — delta the aggregate `cpu` line of `/proc/stat`
  (`100 * (1 - d_idle/d_total)`), keep a `_PREV_CPU` baseline between samples.
- **CPU temperature**: hottest `acpitz` zone in `/sys/class/thermal/thermal_zone*/temp` (millideg, 6 zones).
  There are **7 `acpitz` zones** and **no RAPL/powercap** on this board → CPU **power is N/A** (do not fake it; surface `power n/a`).
- `os.cpu_count()` = 20 cores.
- Ollama is at `http://127.0.0.1:11434`; use `/api/version`, `/api/ps` (loaded: `size_vram`, `expires_at`),
  `/api/tags` (installed), `/api/generate` (real inference for speed test).
- **llama-server MTP on GB10 (qwen3.8-27b, draft-mtp)**: `--spec-draft-n-max 4` is the measured
  optimum — the curve is **non-monotonic** (2≈3 < 4, 6 slightly worse, ~23.8→26.8→26.2 t/s).
  A/B on a throwaway instance on a spare port before touching the resident unit.

## Model-list UI (Installed models box)
- Names are user-defined (`{name}_{paramsK}_{ctxK}_{quant}[_suffix]`, e.g. `qwen3.8_27B_128K_Q4_MTP`);
  Ollama auto-aliases share the same binary (`qwen3.8:27b`). **Both naming styles coexist for one binary.**
- The "Installed models" table **groups by model family** (e.g. `qwen3.6`, `qwen3.8`, `llama3.3`)
  with a group header row, then lists variants sorted alphabetically. Family = the token before the
  **first** `_`/`:`. See `references/model-name-convention.md` — **get the family split right or
  `qwen3.6`/`qwen3.8` collapse into one wrong `qwen3` group** (that bug: a leading-alphanumeric regex
  stops at the non-word `.`; use `name.split(/[_:]/)[0]` or the first-underscore index instead).

## Design conventions (match existing)
- **House style for ALL GB10 dashboards** — the user invests heavily in this look and wants
  visual consistency across monitors. A sibling dashboard (e.g. `llama-monitor`, llama.cpp
  multi-instance, :5002, systemd `llama-monitor`) must match it: Tailwind CDN + Inter, slate
  bg `#0f172a`, cards `#1e293b` / border `#334155`, the 4 bar colors, Chart.js. Do NOT ship a
  fresh bespoke theme for a new monitor — reuse this design language.
- Cards row = `grid grid-cols-1 md:grid-cols-4` (4 cards: CPU · GPU · RAM · Storage).
  Card bar colors: **CPU = blue** (`bg-blue-400`), **GPU = red** (`bg-red-400`),
  **RAM = green** (`bg-emerald-400`), **Storage = amber** (`bg-amber-400`).
- **UNIFIED card layout (user preference, 2026-08)**: EVERY card is the same shape —
  one progress bar on top, then exactly **3 rows** of `label (left, `text-slate-500 text-sm`)`
  + `value (right, `text-2xl font-bold font-mono`)`. Rows 1–2 are white values, row 3 has a
  `border-t border-slate-700/50 pt-3` divider and a slightly dimmer value (`text-slate-300`).
  Do NOT revert to the old "big % number + one-line meta" card style or the per-mount table —
  the user explicitly asked for the clean 3-row format and asked to **remove** the Mount table.
  - CPU:  Used % · Temp °C · Cores
  - GPU:  Used % · Temp °C · Power W   (nvidia-smi; CPU power has NO sensor on GB10 → N/A, don't fake)
  - RAM:  Used GB · Free GB · Total GB
  - Storage:  Used GB · Free GB · Total GB  (summed across real mounts — see sample_storage pitfall)
  JS fills 3 `getElementById` spans per card (ids like `cpu-pct`/`ram-num-used`/`storage-num-total`).
- Trend chart: `CPU %` (blue `#60a5fa`, axis y), `GPU %` (red `#ef4444`, axis y), `RAM GB`
  (green `#34d399`, axis y1). Left axis `y` 0–100 ticks **white** (`#ffffff`); right axis `y1`
  0–128 ticks **green** (`#34d399`). RAM card subtitle = `shared (unified)`.
- RAM bar = `used_gib / total_gib` percentage (not `vram_proc`).
- Korean UI, dark slate theme, Tailwind CDN + Chart.js.
- **llama-monitor (:5002) UI text is English-only** (user choice; ollama-monitor stays Korean).
  Card header order: **port → `Resident` (capital R) → model name**; model name styled
  `text-white text-lg font-bold font-mono truncate max-w-[480px]`. Last-seen timestamp always
  shown when present, `YYYY-MM-DD HH:MM:SS` (no `T`, no "stale" wording). Layout v3: `body
  h-screen overflow-hidden flex-col`, only `#servers` scrolls internally. Details in
  references/llama-monitor.md.
- **Capacity units (user preference)**: compute **decimal GB (1000³)** and label **"GB"**
  (user chose this over GiB/1024³). `llama-monitor` now computes GB (1000³); `ollama-monitor`
  still computes GiB (1024³) — align it on request, don't silently flip.

## Pointers
- `references/ops-pitfalls.md` — full diagnosis of the stale-proc/port-bound loop, the
  self-pkill trap, the clean "render-check a template while a live proc holds it" recipe,
  and the exact GB10 sensor inventory.
- `references/api-name-resolution.md` — why "Loaded" (`/api/ps` base name) and "Installed"
  (`/api/tags` tag) show different names for the same binary, and the parent_model mapping.
- `references/model-name-convention.md` — the `{name}_{paramsK}_{ctxK}_{quant}` naming scheme,
  and the correct family-split rule for grouping (the qwen3.6/qwen3.8 pitfall).
- `references/ram-memory-accounting.md` — why the RAM card and the Loaded-models
  `size_vram` column disagree (normal, not a bug); the verified GB10 accounting.
- `references/llama-monitor.md` — the :5002 monitor specifics: stage classification
  (journal-`n_gen`-first), standby error/active rules, English-only UI conventions, layout v3,
  and `--spec-draft-n-max` A/B tuning.
