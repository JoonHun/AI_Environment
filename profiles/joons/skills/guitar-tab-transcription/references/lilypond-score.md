# LilyPond staff score from a transcribed guitar stem (GB10)

Use when the deliverable is a STAFF-NOTATION score (PDF), not a TAB — typically because the user compared the .gp5 against the audio and it 'doesn't match', so they ask for a score built directly from the cleanest stem (e.g. `stem_guitar.wav` → basic-pitch `.mid`).

## Install (once)
`sudo apt-get install lilypond` — the aarch64 package (2.24.x) installs fine on Ubuntu 24.04. Also `pdftoppm` (poppler-utils) to rasterize pages for spot-checks.

## Pipeline
1. basic-pitch the stem → `.mid` (same transcribe step as the TAB pipeline; the stem's MIDI is the input, never the full mix).
2. Filter to guitar range (MIDI 40..84) + light energy cut (weakest ~10% by velocity).
3. Onset-cluster (150 ms) → events.
4. **Quantize each event's onset to the 8th-note grid** at the measured BPM: `slot = round(start / (60/BPM/2))`. Events landing in the same slot merge into one chord (keep the top ~3 voices by velocity).
5. Emit LilyPond, render with `lilypond --output <name> <name>.ly` (rc 0 + `pdfinfo` page count is the success check).

## LilyPond pitfalls (each cost a full debug cycle)
- **Durations must flow sequentially — quantization is mandatory.** A plain note event carries only a duration symbol; unquantized real timings make adjacent durations not sum to the bar, and the first chord then fails with cascading `unexpected UNSIGNED` errors. The 8th-grid quantize step is what makes this work, not a LilyPond trick.
- **Chords (`< ... >`) need ONE shared duration** (use the longest note's), and that duration goes ONCE after the closing `>` — per-voice durations inside the braces are a syntax error.
- **Use a fixed-mode pitch function**: LilyPond's `c` = C4 (MIDI 60), so marks = `p // 12 - 5`; apostrophes up, commas down. Off-by-one in this formula shifts the whole score an octave and parses fine.
- **English note names**: `b`, not German `h` — Ubuntu's package is English by default; `h,` fails as `not a note name`.
- **Scaffolding**: `\title`/`\header` go OUTSIDE the music expression (in `\header {}`); `\tempo 4 = <bpm>` and overrides go INSIDE. Property paths need the dot: `\override Staff.TimeSignature.stencil = ##f` (the old `#'stencil` form errors in 2.24). `\set Staff.instrumentName = "Electric Guitar"` must be a plain string, not a `#\markup` expression. Minimal shape: `guitar = { ... }` + `\score { \new Staff \guitar \layout {} \midi {} }` — `\midi {}` also emits a playable `moon_score.mid` for free.
- **Debug loop**: on rc≠0, run `lilypond file.ly` directly and read the FIRST `error:` line — later lines are cascade noise; the real culprit is always the earliest one.

## Verify
- lilypond rc 0 + `pdfinfo` page count; `pdftoppm -png -r 100` a page and attach it via MEDIA: so the user can see it (the main model here may lack vision — don't rely on vision_analyze; deliver the image and let the user eyeball it).
- Accuracy caveat is bigger than for TABs: distortion harmonics make basic-pitch octave-errors likely; tell the user to flag specific bars and offer region-scoped fixes.
