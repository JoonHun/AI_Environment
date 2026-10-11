---
title: Writing symbolic score artifacts (ABC + MIDI + practice WAV)
author: hermes
license: MIT
---

# Writing symbolic score artifacts (ABC + MIDI + practice WAV)

## When to Use
Building the per-instrument part set (ABC, MIDI, practice WAV) for a generated YuE2 song — covers multi-voice ABC syntax, unit verification, mido byte/length pitfalls, and the numpy backing-track synth.

Authoring rules for the per-instrument part set: guitar (riff + power chords), riff solo, bass, drums. All three artifact kinds (ABC, MIDI, practice WAV) must come from ONE per-bar token structure — never build them independently.

## Token source of truth
- Model each bar per voice as a list of (start_tick, units, pitch_or_hit) tuples, PPQ 480 (quarter = 960, 16th = 240, 4/4 bar = 3840; 120 BPM → tempo 500000 µs/quarter — five zeros; a six-zero value plays at 12 BPM and only shows up in a tempo re-read, never in a duration check).
- Assert per-voice, per-bar unit sums == 16 (at L:1/16) BEFORE writing any file. This builder-side assertion is the authoritative ABC validation — do not spend time installing third-party ABC validators (abcmidi has no aarch64 wheel on this box).
- **Last-bar hold (every voice):** if the final bar's last note ends before the track end, the last note_off < TOTAL and the `last_off == TOTAL` assert fails (e.g. a bar ending in a rest, or a strum/hit grid whose last slot is short). Extend the final riff note to a whole bar, hold the last power-chord strum / bass note / drum hit to TOTAL, instead of adding a rest — the piece must not cut a beat early.

## Multi-voice ABC
- Declare every voice in the header, one line each: `V:Riff clef=treble name="Guitar Riff"`, `V:PC clef=bass name="Power Chords"`. Drums: one voice per element (`V:Kick clef=drum` …) — separate staves, not one drumline voice re-declared per section.
- Each body line = one bar, ALL voices joined by `/` in header declaration order. A line with one missing segment desynchronizes the renderer.
- One bar per line, always.
- Chord-name annotations (`"Am"`) go on the first beat of the bar; strip them before unit-counting.

## ABC unit-counting (only when parsing text)
- A note token = letter + octave marks (`,` down / `'` up) + accidental (`^ _ =`) + optional duration digits, consumed as ONE unit. The octave comma in `A,` is part of the name — never split on commas. `A,4` = one A, 4 sixteenth-units.
- `z`/`x` take the same digit-suffix rule; a bare token = 1 unit at the L: resolution.
- Re-parsing serialized ABC to verify is strictly weaker than the pre-serialization assert — it reintroduces exactly the parsing traps above.

## mido (MIDI) rules
- **Data-byte clamp:** velocity 0–127 AND the note-on delta byte 0–127. A tail note whose duration exceeds 127 ticks (final crash held to bar end, long bass) overflows the byte and corrupts the file — clamp the delta or write explicit note_on + note_off events.
- **Length verification per track:** `total = sum(m.time for m in track)`, compared against expected seconds via the tempo. Summing across ALL tracks double-counts a multi-track file (2-track guitar file reads as 2× length) — this produced a false 360 s vs 180 s failure.
- **Pad to full length:** if the last note ends before the track end, append `mido.MetaMessage("end_of_track", time=remaining_ticks)` — some players otherwise truncate the track (e.g. 179.8 s of 180 s).
- Round-trip verify with mido after saving; check both total length and per-track length, and re-read the `set_tempo` meta to confirm the BPM value actually written.

## numpy practice (bass+drums) track
- Per-event synthesis lengths must match exactly: generate noise at exactly `dur` samples; `np.diff(np.concatenate([[0.0], x]))` returns length len(x) — a `randn(dur+1)` against an `exp(-tt/dur)` envelope of length `dur` raises a shape mismatch.
- Hit patterns (grid, hits-per-bar per section) must equal the score tokens — same source, see top.
- 16-bit WAV, normalize to −1 dB; disclose to the user that it is a synthesized groove, not the original drum take.
