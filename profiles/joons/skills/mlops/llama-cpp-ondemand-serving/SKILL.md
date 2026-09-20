---
name: llama-cpp-ondemand-serving
description: GB10 llama.cpp on-demand serving via proxy and systemd.
version: 1.0.0
metadata:
  hermes:
    tags: [llama.cpp, GB10, systemd, tunnel-proxy, on-demand, MTP, multi-model, unified-memory]
---

# On-demand llama.cpp serving (GB10, multi-model)

This box serves several GGUF models via a local llama.cpp build. One model runs always-on (the default); each other model is **on-demand**: a tiny TCP tunnel proxy listens on the stable public port and starts/stops the backend llama-server on the first **inference request (POST)** — never on a mere connection or GET probe — releasing the box's unified memory when idle. This is NOT the standard Docker/NGINX deployment — it is a memory-reclaim scheduler for a 128 GB unified-memory SoC where every co-resident model steals bandwidth.

Reference layout (verify live with `ss -ltnp` / `systemctl --user list-units` before assuming):

```
public port 115XX (proxy, LAN 0.0.0.0)  ->  backend port 15XX (llama-server, 127.0.0.1)
proxy:      ~/llama-proxy/proxyXX.py                 ->  ~/.config/systemd/user/llama-proxy-XX.service
backend:    ~/.config/systemd/user/llama-server-XX.service   (proxy drives it via systemctl --user start/stop)
models:     ~/models/<family>-<params>-<quant>.gguf
binary:     ~/llama.cpp-build/llama.cpp/build/bin/llama-server
```

## Adding a new on-demand model — procedure

1. **Pick ports**: next free public 115XX, next free internal 15XX. `ss -ltnp` first.
2. **Download the GGUF** to `~/models/` from Hugging Face (background; ~35 MB/s here). Confirm the exact filename from the repo API (`/api/models/<repo>` siblings) before downloading — same repo can mix naming schemes and MTP variants.
3. **Clone the proven proxy** — do NOT rewrite from scratch if it exists. Copy the fixed `~/llama-proxy/proxyXX.py` (contains the Pitfalls 2, 3, 4, 9 fixes: recv-timeout clear, http.client, running-flag sync, POST-only start) and rewrite the FRONT/BACK/SERVICE constants. If `~/llama-proxy/` is absent (fresh box), writing one from scratch is acceptable ONLY if it implements all four fixes — the single most common regression is dropping the request line: the tunnel MUST forward the FULL original request (request line + headers + body) to the backend; forwarding only the body leaves the backend waiting forever (symptom: HTTP 000 after client timeout, backend log shows only `model loaded` with no task).
   - `~/llama-proxy/proxy38q8.py` is the legacy **connect-time-start** version — do NOT clone it (its Q8 backend is currently unrouted, default profile points at 11534).
   - Rewrite exactly the three constants: `FRONT = ("0.0.0.0", 115XX)`, `BACK = ("127.0.0.1", 15XX)`, `SERVICE = "llama-server-NEW.service"` (plus the log-tag string if it matters). Verify with `ast.parse` and `grep -E '^(FRONT|BACK|SERVICE)'`.
4. **Write the backend unit** `llama-server-NEW.service`:
   ```ini
   [Service]
   WorkingDirectory=~/llama.cpp-build/llama.cpp
   ExecStart=~/llama.cpp-build/llama.cpp/build/bin/llama-server \
     -m /home/joons/models/<model>.gguf \
     --n-gpu-layers 99 --ctx-size 131072 \
     --port 15XX --host 127.0.0.1 \
     --spec-type draft-mtp --spec-draft-n-max 2
   Restart=on-failure
   RestartSec=5
   ```
   No `[Install]` needed — the proxy starts/stops it. Backend stays loopback-only; the proxy is what exposes it.
5. **Write the proxy unit** `llama-proxy-NEW.service`:
   ```ini
   [Service]
   ExecStart=/usr/bin/python3 /home/joons/llama-proxy/proxyNEW.py
   Restart=always
   RestartSec=3
   ```
6. `systemctl --user daemon-reload && systemctl --user enable --now llama-proxy-NEW.service`, then **E2E test in this order**:
   a. `curl http://127.0.0.1:115XX/health` — must return `{"status":"standby"}` AND leave the backend **inactive** (a probe must not wake the model, Pitfall 9).
   b. A real `POST /v1/chat/completions` — **this is the call that starts the backend**. `max_tokens >= 500`, non-streaming, `-w "HTTP %{http_code}"`, generous `--max-time`. **Also the test that catches the tunnel-timeout bug (Pitfall 2)** — a hard cut at ~10 s while the backend log shows `stop: cancel task` means it regressed.
   c. Verify `systemctl --user is-active llama-server-NEW` = active, then read decode speed + MTP acceptance from the backend journal (see Diagnostics).
7. **LAN access**: only if the user wants remote access. Set proxy `FRONT` to `0.0.0.0`, restart proxy, then **verify from the LAN IP** (`curl http://192.168.219.115:115XX/health`), not loopback (Pitfall 8).

## Required llama-server flags (this build)

- Flags required above: `--n-gpu-layers 99`, `--ctx-size`, `--port`, `--host`, and for MTP models `--spec-type draft-mtp --spec-draft-n-max 2`.
- The model file is fixed at launch; the `model` field in client requests is **ignored** — any value (or a filename) works. Do not try to make it match a client string.
- Reasoning models burn `max_tokens` on thinking first, so `content` can come back empty with a small `max_tokens`. For quick functional tests use `max_tokens >= 300`, and check `reasoning_content`. An empty `content` with a populated `reasoning_content` is NOT a failure.

## Pitfalls (rules first; why in a clause)

1. **No systemd socket activation for this llama.cpp build.** grep the source for `LISTEN_FDS` — it is absent. Without it the server silently falls back to port 8080 while systemd holds the intended port, so proxied requests hang in a socket that nothing serves, and the failure is invisible in the proxy log. Use the tunnel-proxy pattern, not a `.socket` unit.
2. **Clear the tunnel connect timeout immediately after `socket.create_connection(BACK, timeout=10)`: `upstream.settimeout(None)`.** A timeout left on a long-lived socket makes `recv` raise at 10 s, so any non-streaming generation needing >10 s of silence is killed on the client side while the backend log only shows `stop: cancel task` — it looks like a server hang but is the proxy's pipe. (Streaming masks this because bytes keep arriving.)
3. **Never use `with http.client.HTTPConnection(...) as c:`** — it has no context-manager protocol, so a `TypeError` fires inside a broad `except` and your health check reports "backend down" forever even though the backend is fine. Instantiate, `request`/`getresponse`/`read`, and `close()` in a `finally`.
4. **Re-sync the proxy's `running` flag from `systemctl is-active` at proxy startup.** Without it, a backend that survived a proxy restart is invisible to the watchdog (the idle-stop condition `running and idle > timeout` stays False), so it leaks 20–30 GB until someone notices a hot machine.
5. **On GB10, every co-resident llama-server steals memory bandwidth.** Decode speed can drop ~2.5x and MTP acceptance falls (observed 26 → 8.7 t/s; acceptance 0.80 → 0.58) with two extra models loaded idle, even at 0% visible utilization. Before benchmarking or before asking "why is it slow now", check `nvidia-smi --query-compute-apps` and stop idle backends. A hot PC with no active work = a leftover model process.
6. **MTP draft layers are silently skipped without `--spec-type draft-mtp --spec-draft-n-max 2`.** The log shows an "unused tensor" warning and generation runs at roughly half speed with no error. If measured speed matches the non-MTP baseline, the flag is missing.
7. **Use `--n-gpu-layers`, not `--ngl`.** This build rejects the short form with `invalid argument`.
8. **Verify LAN access from the LAN IP, not loopback.** `0.0.0.0` bind looks done in `ss -ltnp` but proves nothing until `curl http://<box-ip>:port` actually returns.
9. **Never start the backend on a bare TCP connection.** A tunnel proxy that calls `ensure_backend()` in `handle()` wakes the model on the Hermes gateways' boot-time start-probes — every on-demand model loads within ~30 s of boot (observed: 3 models, ~68 GB of unified memory) and only frees at the idle timeout. Peek the first request line instead: only `POST /v1/chat/completions` starts the backend; `GET /health` → 200 `{"status":"standby"}`, `GET /v1/models` → 200 `{"object":"list","data":[]}`, other GET → 503. Keep the read-ahead bytes in a buffer and prepend them when the tunnel starts, or the first POST line is lost. The default profile cannot be deleted (`profiles.py` hard-rejects) and its gateway runs for cron/dashboard with no messaging, so it always boots and always probes — this fix is mandatory, not optional.

## Benchmarks anchor (GB10, solo, MTP ON — re-measure before quoting)

| Model | quant | decode | MTP acceptance | notes |
|---|---|---|---|---|
| Qwen3.8 27B (dense) | Q4_K_M | ~22–26 t/s | 0.72–0.80 | decode winner (bandwidth-bound) |
| Qwen3.8 27B (dense) | Q8_0 | ~15–18 t/s | 0.59–0.69 | ~1.4x slower; quality headroom / fallback |
| Qwen3.6 35B-A3B (MoE) | Q4_K_M | ~22–95 t/s | 0.59–0.73 | prefill 800+ t/s (~3.5x the dense model) |

Q4_K_M is the decode winner on GB10 (bandwidth-bound); Q8_0 trades ~1.4x speed for a fallback. MoE A3B prefill is ~3.5x faster than the dense model.

## Diagnostics cheat

```bash
ss -ltnp | grep -E '1153|153'                    # who owns which port
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader  # memory hogs (unified mem: all visible)
nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader           # "no calculation but GPU hot" check
systemctl --user is-active llama-proxy-XX llama-server-XX
journalctl --user -u llama-server-XX --no-pager | grep -E 'new prompt|total time|eval time|draft acceptance'   # per-request timing: prefill vs decode + MTP acceptance
journalctl --user -u llama-proxy-XX --no-pager | tail                    # who connected (client IP), startup/shutdown transitions
```

Always anchor time before grepping `journalctl --since` (local timestamps), and pair `nvidia-smi` (is something running) with the backend journal (`grep -E 'total time'` — is something being computed) to separate "idle leftover" from "actively generating".

## Client IP reference (proxy logs)

- `127.0.0.1` — local to this box
- `192.168.219.115` — the box's own LAN IP (a local curl that went through the LAN interface)
- `192.168.219.101` — the user's remote VSCode / Windows PC
