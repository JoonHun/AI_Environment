# PyGuitarPro (guitarpro 0.11) writing pitfalls

Package: `pip install pyguitarpro`, `import guitarpro`. The PyPI package named `music` is a DIFFERENT, unrelated package — never install it for this.

## API shape
- Module functions, not a class: `guitarpro.write(song, path, version=(5, 1, 0))` and `guitarpro.parse(path)`. There is no `GuitarPro` class in 0.11.
- Models come from `guitarpro.models`: `Song, Measure, Beat, Note, Duration, BeatStatus, TimeSignature, NoteType`.

## The `.value` bomb (attrs vs class constants)
The writer calls `.value` on fields. Two traps:
- `Duration` is an attrs CLASS with class-level constants (`Duration.eighth == 8`, an int). Passing the constant means `duration.value` → `AttributeError: 'int' object has no attribute 'value'` deep inside writeSong. Always pass INSTANCES: `Duration(8)` for an eighth note, `Duration(4)` for quarter.
- Same for `TimeSignature`: `TimeSignature(numerator=4, denominator=Duration(4))`. `TimeSignature(4, 4)` puts an int in `denominator` and fails at `header.timeSignature.denominator.value`.
- `Note.type` defaults to `NoteType.rest` → pass `type=NoteType.normal` explicitly or the note is written as a rest.

## Song structure to fill in
- `song.tracks[0]` exists by default; `song.newMeasure()` appends measure headers; attach with `track.measures.append(Measure(track, song.measureHeaders[i]))`.
- Set `mh.timeSignature` on every header you add.
- Ticks: 960 per quarter note. 4/4 measure = 3840 ticks. At 120 bpm a measure is 2 s.
- **`Beat.start` is the offset from the MEASURE start**, so the four 4/4 quarter beats sit at 0, 240, 480, 720 (`beat_i * 240`). Multiplying by the full measure length (960 or 3840) collapses every beat onto the first slot — the file parses fine but renders in GP5 as 10/16 beats per bar with crowded first bars; a note-count check passes, only the start positions betray it. Caveat: `start` is COMPUTED by the parser from the written beat sequence + durations; `writeBeat` never serializes it — so it only validates an in-memory model, not the file. The file-level check is the per-measure duration sum (Verification below).
- **`Duration.value` is the NOTE DENOMINATOR, not a slot count**: `Duration(2)` = half note (1920 ticks), `Duration(4)` = quarter (960), `Duration(8)` = eighth (480), `Duration(16)` = sixteenth (240); dotted = `Duration(8, isDotted=True)`. Confusing the scale (e.g. mapping an eighth note to `Duration(2)`) silently doubles/quadruples every note — a 4/4 bar built from 8 eighths then sums to 9600–15360 instead of 3840 and renders as a bar 2–4× too long with notes bunched at the start. Same visible symptom as the start-collapse bug (10/16-beat bars) but the durations are wrong, not the positions: only the per-measure `duration.time` sum betrays it.
- Measure mapping for a time grid: `cells_per_measure = int(60/tempo*4/CELL)` (4 cells per 4/4 measure at 120bpm with 500ms cells), `tick_in_measure = (c % cells_per_measure) * int(CELL/(60/tempo))*960`.
- Chords = one Beat with multiple Notes. One Beat per grid cell, all strings sounding in that cell on the same Beat.
- GP5 string numbering: string 1 = LOW E (track.strings[0], pitch 40). Tab display convention is flipped (row on top = high e) — convert with `gp_string = 7 - tab_string` when building Notes; mixing the two conventions silently transposes the tab across strings.
- `Beat(voice=voice, notes=[...], duration=Duration(8), start=tick_in_measure, status=BeatStatus.normal)`.

## Chord-name annotations
- Attach `beat.effect.chord = Chord(length=6, root=PitchClass('C'), type=ChordType.power, name='C5', firstFret=f, strings=[-1,-1,-1,-1,f+7,f])` to the FIRST beat of the bar. `length` is the string count and is required; `firstFret` + `strings` (fret per string, −1 = muted) are what draw the diagram, so an empty strings list renders a name-only annotation.
- `PitchClass` is a NamedTuple-like class — `PitchClass('C')`, never `PitchClass.c`.
- Serialization lives in gp4's `writeBeat` (`writeChord(beat.effect.chord)`, guarded by `beat.effect.hasChord`); GP5File inherits it, so it works for `version=(5,1,0)` even though `gp5.py` itself mentions no chord code. `beat.text` is an alternative (written only when no chord is set), but a chord object also yields the diagram.

## ABC → GP5 duration mapping
When building a GP5 from an ABC file (YuE2 `score.abc` etc.): the number after a note name counts `L:` units (default 1 when omitted). For `L:1/8`: `C` = 1 eighth, `C2` = quarter, `C4` = half → sixteenth-units `l ∈ {1,2,4}` → `Duration({1:16, 2:8, 4:4}[l])`, ticks `l*240`; a dotted note (e.g. `C3` on an 8th grid) = `Duration(8, isDotted=True)`. Assert each parsed bar sums to the measure's 16th count (16 for 4/4 at L:1/8) BEFORE writing — a parse miss shows up as a bar that over/under-runs, and the GP5 renders broken bars with no error.

## Verification
After `guitarpro.write`, read back with `guitarpro.parse` and sum `len(b.notes)` over measures/voices/beats — that count is what you report. THEN check the per-measure duration sum: `sum(b.duration.time for v in m.voices for b in v.beats)` must equal the header length for EVERY measure (`MeasureHeader.length` = `numerator * denominator.time`, 3840 for 4/4) — a 3840 total is the file-level proof the bar fits; note counts and in-memory `beat.start` values both pass on a broken file. Report the bad-bar list (index, total) instead of a boolean.
