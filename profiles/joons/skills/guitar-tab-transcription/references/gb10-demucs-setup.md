# demucs guitar-stem separation on GB10 (aarch64)

Validated: htdemucs_6s on GB10 CUDA separated a 4:35 song in ~7s. Use it to extract `stem_guitar` before re-transcribing dense mixes (cuts bass/voices/drum bleed — 2,546→1,576 notes on one track).

## Install (into the pipeline venv, all `uv pip install --python .venv/bin/python ...`)
1. `torch` — plain install works: the aarch64 wheel auto-picks CUDA on GB10.
2. `demucs --no-deps` — plain install FAILS building the `sphn` Rust dep on aarch64. demucs only uses sphn as an audio reader and falls back to ffmpeg when it raises, so a stub is safe:
   ```python
   # sphn_stub/sphn.py
   def read(*args, **kwargs):
       raise RuntimeError("sphn stub: use ffmpeg fallback")
   ```
   Run with `PYTHONPATH=sphn_stub` and ffmpeg on `PATH` (`~/.hermes/tools/ffmpeg-9.0.1-linux-arm64/bin`).
3. Deps `--no-deps` skipped: `tqdm julius lameenc einops pyyaml torchaudio`.

## Usage
- `from demucs.pretrained import get_model; get_model("htdemucs_6s")` — loads the 6-stem model by name from HuggingFace (first run downloads the .th). Stems: drums, bass, other, vocals, **guitar**, piano. Plain `htdemucs` is only 4-way — guitar gets buried in `other`. `htdemucs_ft` uses different names (e.g. `electric_guitar`) — always read `model.sources` and index by that, never hard-code a stem name. Stems sum ≈ the original, so mixdowns of wanted stems (no-drums, no-drums-no-bass…) are just stem sums saved to WAV. Basic-pitch transcribe on GB10 ≈ 2s per 3:33 track once the ONNX model is cached — batch several versions in one loop.
- **Do NOT feed MP3 to torchaudio 2.11** — decode requires torchcodec (not installed). ffmpeg to 44.1kHz stereo WAV first, then `soundfile` read → `torch.from_numpy` (and `sf.write` for outputs).
- `apply_model(model, wav[None].to(device), device=device, shifts=1, split=True, overlap=0.25, progress=True)` — `shifts` is an INT (number of shifts, 0/1); the old `shift=True` kwarg raises TypeError. `sources[i].numpy().T` → (T,2) for soundfile.
- Script: `~/guitar-tab/separate.py` (SRC/OUT paths at top; writes `stem_guitar.wav` etc.).
