---
name: guitar-tab-transcription
description: Convert audio to guitar tab via basic-pitch and GP5.
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [audio, music, guitar, tab, basic-pitch, transcription]
    related_skills: []
---

## When to Use
- User wants an electric guitar TAB (text tab and/or Guitar Pro file) from an audio file (MP3/WAV).
- User wants audio transcribed to MIDI/note events on GB10 (aarch64), where tensorflow wheels are unavailable.
- User wants a STAFF-NOTATION score (LilyPond PDF), not a TAB — e.g. after the user finds the .gp5 'doesn't match the sound' and asks for a score from the guitar stem.
- User gives a SCORE PDF (staff notation, e.g. a piano cover) and wants a TAB from it — the vision path in `references/vision-score-transcription.md` (diagnose scan-vs-vector FIRST; LLM vision on low-dpi scans hallucinates).

Audio → electric guitar TAB pipeline (basic-pitch ONNX → MIDI → text tab + .gp5). Validated on GB10 (aarch64, Python 3.12, uv).

## Deliverable (user default)
- BOTH a readable text tab (.txt) AND a Guitar Pro 5 file (.gp5), delivered via MEDIA:.
- Always state accuracy caveats: band mixes transcribe as flat note lists — no chord detection, no technique markers (bend/vibrato/pick), tempo assumed 120bpm 4/4 unless the user gives BPM. Tell the user to verify by ear. Offer demucs guitar-stem separation as the accuracy-upgrade path (validated working on GB10; setup in `references/gb10-demucs-setup.md`).

## Procedure
1. **Venv** (once): `uv venv --python 3.12` then install with the GB10-specific sequence in `references/gb10-venv-setup.md`. Plain pip on python3.14 fails; `--no-deps` basic-pitch + onnxruntime is the working path (no TF wheels on aarch64).
2. **Transcribe**: `basic_pitch.inference.predict(path)` returns `(model_output, midi_data, note_events)` — `midi_data` IS a PrettyMIDI object; call `midi_data.write(path)` yourself. Do NOT re-read a file predict() never wrote.
3. **Filter to guitar range**: MIDI 40 (E2) .. 84 (E6). Band mixes dump bass + drum bleed as notes; without this the tab is garbage. Report how many notes were dropped.
4. **Map note → (string, fret)**: standard E tuning string open pitches `{1:64, 2:59, 3:55, 4:50, 5:45, 6:40}`. Pick the mapping with fewest frets; break ties toward the higher (lighter) string; drop notes needing fret > 24.
5. **Cluster by onset, not a fixed 500 ms grid**: a fixed grid smears a fast riff into mush and drops syncopation — onset-based clustering (group notes whose start falls within CHORD_WIN ≈ 150 ms of the cluster start) is the validated shape. Within each cluster: (a) bind one power chord first — a pair exactly 7 semitones apart, most compact real shape over all (string_root, string_fifth) combos, smallest fret offset first (classic +2/−2 on adjacent strings), then lowest string; physical constraint: two notes at the SAME fret on ADJACENT strings are a 4th, not a 5th — same-fret 5th-binding can never match and silently yields 0 bound chords. (b) Then place the tracked lead note on a high string (1–3 preferred), low fret. (c) Drop all remaining pitches — placing every cluster note reproduces the "garbage everywhere" tab the user rejects. Count and report bound power chords.
6. **Clean the note list before mapping** (both steps validated; each alone is not enough): (a) energy filter — drop the weakest fraction of notes by velocity (basic-pitch velocity has real spread, e.g. 29–108; residual stem noise sits in the tail). Keep FRACTION tunable via argv and default it to ~0.10, NOT 0.30: 0.30 cuts real quiet riff notes (fast strums land at low velocity) — the user will report "many notes are missing". When the user reports missing notes in a passage, diagnose before re-tuning: count raw notes vs filter-survivors in that region (velocity percentile of the region's distribution) — that tells you whether it's the filter (lower FRACTION) or the transcription itself (basic-pitch missed weak/overlapping notes; say so and soften predict() defaults instead). (b) lead-line tracking — per cluster take the strongest note; accept it as the melody only if it is within LEAD_JUMP ≈ 12 semitones of the previous lead note, OR its velocity ≥ ~75 (real fast jumps are loud, noise jumps are quiet). Pitfall: never reserve the lead pitch from the power-chord pass — the lead of a riff is often the PC root itself, and reserving it kills the chord and leaves the intro empty. Pitfall: LEAD_JUMP too tight (≤ 6) breaks real riff chains; too loose with no velocity gate floods the tab with noise.
7. **Text tab**: one cell per 500 ms display slot. Lay out in 30-cell (15 s) blocks with a time header every 2 s, fixed-width 6-char cells (`|  2|`), string 1 (high e) on top, number = fret, blank = rest. A single unbroken 545-column line is unusable — the user must be able to read it in a terminal/preview.
8. **GP5**: build a Song via PyGuitarPro and `guitarpro.write(song, path, version=(5,1,0))`. **String convention is flipped**: PyGuitarPro string 1 = LOW E; the tab convention (string 1 = high e, top row) needs `string=7-st` when creating Notes, or the whole file plays a 12th off. All API pitfalls (Duration/TimeSignature/NoteType, no GuitarPro class, measure mapping) are in `references/gp5-writing.md`. A proven full script: `templates/make_tab.py`.
9. **Region-scoped rewrites**: when the user wants only a section (e.g. the intro riff), pass a start/end time window (argv) and trim the note list before filtering/mapping — and recompute `dur` from the surviving notes after trimming, or the GP5 stage emits a hundred-plus empty measures. Name the outputs with a version suffix that increments per attempt (`..._01.txt/.gp5`, `_02`, …) and NEVER overwrite the previous version — the user explicitly compares versions side by side.
10. **Verify by reading back**: `guitarpro.parse(path)`, count notes/measures, print the total. Never claim success on write alone.

## Separation-quality comparison protocol
When the user wants tabs from progressively stripped mixes to compare quality (full → no drums → no drums+bass → guitar stem), each step is an explicit deliverable — run them in order and save EVERYTHING (intermediates, MIDIs, all tab versions; the user keeps them, never delete):
1. demucs `htdemucs_6s` on the 44.1kHz stereo WAV → write all 6 `stem_*.wav`.
2. Mixdowns by summing stems (stems sum ≈ original): no-drums = sum of all-but-drums; no-drums-no-bass = all-but-drums-bass. Save each as a step WAV.
3. Transcribe the original + every step WAV with basic-pitch → one `.mid` per version.
4. Measure BPM from the guitar stem (`librosa.beat.beat_track`).
5. `make_tab.py <mid> <bpm> tab_<version>.txt tab_<version>.gp5 0 <dur> <fraction>` per version.
- Report a comparison table: notes transcribed, energy-filter survivors, placed notes, power-chord count per version, plus the expected-quality note (guitar stem = cleanest lead; full mix = drum/bass bleed inflates power chords). Deliver step WAVs + all tabs via MEDIA:.

## Score PDF → TAB (vision path)
When the input is a score PDF instead of audio:
1. **Diagnose the PDF before rendering anything**: `pdfimages -list` + `pdffonts` + `pdftotext`. No fonts and one full-page embedded image = a SCAN — its information is capped at the embedded image's dpi (a 103dpi scan renders identically "blurred" at any output dpi). Below ~150dpi, LLM vision transcription is untrustworthy (hallucinated measures, and re-reading the same image gives different notes). Before burning time on it: **search the web for a vector copy of the same arrangement** (MuseScore by exact title/arranger is the usual hit) and transcribe that instead — vector PDFs render crisp at 300dpi and read consistently.
2. **Keep every vision image under ~1MP.** The GB10 gemma4-26b mmproj backend (llama-server on 1536 / proxy 11536) hard-crashes in `mtmd_helper_decode_image_chunk` (connection reset, service drops) on images above ~1.2MP; 1650×620 worked, 2550×486 crashed. Crop each grand-staff system, then split wide systems at a barline into left/right halves (~1275×500 each).
3. **Crop per staff system, never equal page fractions.** Equal-height strips cut through the 5 staff lines and the model fills the missing line with invention. Detect systems with a row-profile of dark pixels (bands > ~8% of width dark, merge gaps < ~60px at 300dpi).
4. **QA by beat arithmetic + double-read.** In 4/4 each measure must sum to 4 beats — a measure with 11 eighth notes is a hallucination, not a duration misread. The same image read twice should agree on note names; disagreement means a resolution problem, not a prompt problem. Then feed the stable transcription to the normal `make_tab.py` stage.

Full procedure, crop scripts, and the working vision prompt: `references/vision-score-transcription.md`. Direct-call probe script (bypasses vision_analyze routing): `scripts/vision_test.py`.

## Standing rules
- **ABC deliverables: exactly one measure per line and the correct beat total per measure** (4 beats in 4/4). Program-verify every line by summing note values (strip `"C"`-style chord-name prefixes first — a naive note counter reads the chord letters as notes). Multi-measure lines or a 10-note "measure" render as broken barlines and the user reports 10/16-beat bars. Multi-voice ABC: declare staves ONLY in the header and join every voice per bar with `/` in body lines — a `V:` label mid-body desyncs the voices; full syntax + mido byte/length rules in `yue2-music-pipeline` → `references/abc-midi-writing.md`.
- Run in a dedicated dir (e.g. `~/guitar-tab/`) with its own `.venv`; keep `out.mid` as an intermediate so the tab stage can be re-run without re-transcribing (transcribe ≈ 1-2 min, tab stage is instant).
- If the user gives the real BPM/time signature, set `song.tempo` and TimeSignature accordingly and recompute measure mapping; do not ship a 120bpm file for a faster/slower song without saying so.
- For dense rock/metal mixes, separate before transcribing: start with demucs `htdemucs_6s` (setup + script in `references/gb10-demucs-setup.md`); when keyboard/piano bleed still pollutes the stem (user says "it's all mixed together"), upgrade to the MVSEP 53-stem model via audio-separator — a dedicated `electric-guitar` stem, much cleaner (setup in `references/gb10-mvsep-separation.md`). No off-the-shelf model splits 2 guitars (lead vs rhythm) — say so immediately instead of promising it.
- Measure the real BPM from the stem with `librosa.beat.beat_track` before building the GP5; never ship a default-120 file for a different tempo without saying so.
- When the user flags a bad passage, do per-region fixes rather than re-tuning global parameters blindly.
- **Staff notation (LilyPond) instead of TAB**: when the user wants a real score (staff + PDF) from a transcribed stem, follow `references/lilypond-score.md` — quantize onsets to the 8th-note grid before emitting durations, or LilyPond's sequential duration flow breaks every chord. Install: `sudo apt-get install lilypond` (aarch64 package exists on Ubuntu 24.04).
- Copy `templates/make_tab.py` into the work dir FRESH from the skill before each run — work-dir copies go stale (older arg positions / filter defaults silently change results: one stale copy applied a 30% energy filter and a broken trim window and produced empty tabs).
