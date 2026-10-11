# Cover / arrange a recording → score (YuE2 project docs)

The general YuE2 checkpoint does covers without cover-specific fine-tuning. Workflow:

## 1. Transcribe (SheetSage2 venv)
```bash
.venv-sheetsage2/bin/python models/SheetSage2/infer.py source.wav --output cover-score --melody-only
```
`--melody-only` keeps the Vocal + Ins melodies and DROPS chord symbols — recommended for style changes (gives the new accompaniment freedom). Check the exit status; transcription errors carry into the cover. Review `cover-score/score.abc` against the source before generating.

## 2. Cover (YuE2 venv)
A request JSON with `style`, `lyrics`, `cot`, `seed`, plus the transcribed ABC:
```bash
.venv/bin/python examples/generate.py --request cover-request.json \
  --abc-file cover-score/score.abc --cot melody --output outputs/cover
```
Or the staged API: `pipe(style=..., lyrics=..., abc=..., cot="melody", seed=...)`.

`cot` modes: `full` = editable melody+chord plan (new songs; the score carries chords); `melody` = melody plan + free accompaniment (covers — recommended); `off` = generate directly from lyrics+style.

## 3. Artifacts in `outputs/<job>/`
`audio.flac` (48 kHz stereo), `score.abc` (2-part melody; chords only in `full` mode), `plan.json`, `semantic.npy` / `latent.npy`. **No direct MIDI** — ABC is the editable score and the better → sheet-music input.

`truncated: true` in the result = the generation hit its context limit and the song is cut short. Retry with another seed or shorter lyrics.

## Guitar score from the cover
Don't transcribe the full cover mix (drum/bass bleed pollutes the lead). Pull the demucs `htdemucs_6s` guitar stem from the cover `audio.flac` and run the `guitar-tab-transcription` path (basic-pitch → GP5) on the stem for a cleaner lead.

## Score → sheet music
ABC maps 1:1 to staves (MuseScore / LilyPond); MIDI requires guessing. Prefer ABC.
