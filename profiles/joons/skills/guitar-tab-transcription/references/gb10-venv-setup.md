# GB10 (aarch64) venv setup for the tab pipeline

Python 3.14 has no working wheels for this stack; 3.12 + uv does.

```bash
cd ~/guitar-tab
uv venv --python 3.12 .venv
```

Install order (all via `uv pip install --python .venv/bin/python ...`):

1. `basic-pitch --no-deps` — a plain install pulls tensorflow, which has NO aarch64 wheels. The package auto-falls back to ONNX at runtime when TF is absent.
2. `onnxruntime` — the backend basic-pitch actually uses without TF.
3. Runtime deps that `--no-deps` skipped: `librosa mir_eval resampy pretty_midi scipy soundfile`
4. `pyguitarpro` — Guitar Pro writer/reader.

Smoke test:

```bash
./.venv/bin/python -c "import basic_pitch, librosa, mir_eval, resampy, pretty_midi, guitarpro; print('ok')"
```

First `predict()` call downloads the ONNX model (ICASSP_2022) to the basic-pitch cache — allow a minute.

ffmpeg for MP3 handling is at `~/.hermes/tools/ffmpeg-9.0.1-linux-arm64/bin/ffmpeg` if the system path lacks it.

## pretty_midi version quirks
- No `pretty_midi.note_names` import path and no top-level `note_name_to_midi_note_number` in current releases. Build note names locally: `NAMES=["C","C#",...]; f"{NAMES[p%12]}{p//12-1}"`.
