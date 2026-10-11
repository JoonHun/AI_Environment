# audio-separator / MVSEP 53-stem separation on GB10 (aarch64)

Validated: MVSEP mega 53-stem BS-Roformer via python-audio-separator 0.47.0 on GB10 (torch CUDA). A 4:35 song in ~3 min GPU. Produces a dedicated `electric-guitar` stem that is markedly cleaner than demucs 6s for dense rock mixes (keyboard bleed gone).

## Install
`uv pip install audio-separator audioread` into the pipeline venv. Torch already present from the demucs step.

## The 16-stem limit (main gotcha)
python-audio-separator hard-validates Roformer configs to `num_stems ∈ [1, 16]` — the 53-stem MVSEP mega model fails to load with a config error. The fix is local-only:
1. Edit `parameter_validator.py` in the installed package: `'num_stems': (1, 16)` → `(1, 64)`.
2. Delete stale `__pycache__` in the package's roformer dir before re-running.

## Register + load the local model
1. Download ckpt + yaml (e.g. `oulianov/mvsep_mega_53` from HuggingFace, ~1.4 GB) into a `models/` dir. Name the ckpt exactly as registered — a mismatch is a silent "model not found".
2. Register in the package `models.json` under `roformer_download_list`: `"<Display Name>": {"<ckpt filename>": "<yaml filename>"}`.
3. `Separator(model_file_dir="models", output_dir="out", output_format="WAV")` → `sep.load_model("<ckpt filename>")` → `sep.separate(src)`. Output: one WAV per stem, named `<song>_(<stem>)_<model>.wav`.

## Stem selection
- Verify which stem actually holds the guitar by energy: `ffmpeg -i stem.wav -af volumedetect -f null -` → `mean_volume`. On a rock track the right stem is ~13 dB louder than the lookalike (electric-guitar −25 dB vs acoustic −38 dB in one track). Don't assume the name.
- Use `electric-guitar` (not the generic `guitar` stem) for electric-guitar transcription.

## Known dead end
- Guitar-specific 2-stem Roformer checkpoints from the UVR5 era (e.g. mel-band guitar models) fail to load in audio-separator 0.47 with parameter-shape mismatches. Don't burn time hunting them — the 53-stem mega model is the working path.
- 2-guitar separation (lead vs rhythm) does not exist in any off-the-shelf model. State that plainly; the 53-stem model separates guitar from the rest, not guitar from guitar.
