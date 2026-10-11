# YuE2 install + on-demand serving (GB10)

## YuE2 (generation) — Python 3.12, torch cu128
```bash
git clone https://github.com/multimodal-art-projection/YuE.git ~/YuE
cd ~/YuE
python3.12 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install .          # pulls deps + torch — but on aarch64 torch is the CPU wheel
# Force the CUDA build:
.venv/bin/pip install --force-reinstall torch==2.10.0+cu128 --index-url https://download.pytorch.org/whl/cu128
# WITHOUT --no-deps, so pip also installs the matching nvidia-* libs. Chasing them by
# hand = version whack-a-mole: cusparse/nccl/nvjitlink/curand/cusolver each pin to a
# specific version torch needs.
```
Verify the GPU actually computes (GB10 sm_121 > torch's sm_120 max → a warning appears, but JIT makes it work):
```bash
.venv/bin/python -c "import torch; x=torch.randn(1024,1024,device='cuda'); y=x@x; torch.cuda.synchronize(); print(torch.cuda.is_available(), (x.bfloat16()@x.bfloat16()).dtype)"
```
The first `generate` downloads YuE2-3B + the VAE from HF (several GB) into `~/.cache/huggingface`.

Generation speed on GB10: ~40 tok/s. A ~57 s song took ~189 s; a fuller one ~344 s. Budget MINUTES, not seconds, for `--max-time`.

## On-demand serving (11540 front / 1540 back)
Reuse the tunnel-proxy pattern from the `llama-cpp-ondemand-serving` skill (POST-only wake, clear the tunnel connect timeout after connect, re-sync the `running` flag from `systemctl is-active`, forward the FULL original request line+headers+body). Two differences for YuE2:
- The backend is a **custom lazy-load HTTP server**, not llama-server. It binds :1540 immediately, loads `YuE2Pipeline` on the FIRST `POST /generate`, and **self-exits after the idle timeout** (default 30 min) to release unified memory.
- `GET /health` on the proxy returns `{"status":"standby"|"active"}` and must NEVER wake the backend; only `POST /generate` wakes it.

**The lock-deadlock (the one that bit):** in the backend's request handler the generation path is wrapped in `with _lock:`, and the lazy loader ALSO acquires `_lock`. Calling `load_pipeline()` inside the handler's `with _lock:` block deadlocks — the very first `POST /generate` hangs, the proxy tunnels the bytes but the backend logs nothing and `/health` stops answering. Fix: mark `busy` under the lock, call `load_pipeline()` OUTSIDE it (it acquires the lock itself), then set `last_use` under a fresh `with _lock:`:
```python
with _lock:
    _state["status"] = "busy"
pipe = load_pipeline()          # acquires _lock itself — do NOT nest
song = pipe(**kwargs)
song.save_artifacts(str(out_dir))
with _lock:
    _state["last_use"] = time.time()
```

Units: `yue2-backend.service` (Type=simple, WorkingDirectory=~/YuE, ExecStart=`~/YuE/.venv/bin/python ~/yue2/yue2-backend.py`, Restart=on-failure, env `YUE2_IDLE_TIMEOUT=1800`) and `yue2-proxy-40.service` (ExecStart=`/usr/bin/python3 ~/yue2/yue2-proxy.py`, Restart=always). Enable the proxy with `--now`; the backend is started/stopped BY the proxy, so it stays disabled.

E2E test order: `curl :11540/health` → `standby` and backend inactive. Then `curl -X POST :11540/generate` with a real style+lyrics payload and a generous `--max-time` (minutes). The first call is slow (HF model download on the very first run, then ~1 min pipeline load + generation).

## SheetSage2 (transcription) — Python 3.11, torch cu126
GB10 ships only Python 3.12; SheetSage2 wants 3.10/3.11. Get 3.11 via uv and build the venv with pip:
```bash
uv python install 3.11
cd ~/YuE
uv venv .venv-sheetsage2 --python 3.11 --seed     # --seed installs pip (uv venv does NOT by default)
# (or: uv pip install --python .venv-sheetsage2/bin/python pip huggingface-hub==0.36.0)
.venv-sheetsage2/bin/huggingface-cli download m-a-p/SheetSage2 --local-dir models/SheetSage2
.venv-sheetsage2/bin/python -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
.venv-sheetsage2/bin/python -m pip install -r models/SheetSage2/requirements.txt
```
`m-a-p/SheetSage2` is **gated** — `huggingface-cli login` + granted repo access required before the download. FFmpeg 6.1 + its shared libs are required; GB10 has ffmpeg n9.0 — re-confirm SheetSage2 accepts it (the model card pins 6.1).

NOTE: the full SheetSage2 install + the `infer.py` transcribe were NOT yet verified on GB10 as of writing — confirm the transcribe step works before relying on cover output.
