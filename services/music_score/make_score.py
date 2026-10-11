"""MIDI (guitar stem) -> LilyPond score (staff notation) -> PDF.

Quantizes onsets to the 8th-note grid (BPM 89): unquantized stem
timing breaks LilyPond's sequential duration flow. Events sharing a
quantized slot merge into chords (max 3 voices, strongest kept).
"""
import collections
from pathlib import Path
import numpy as np
import pretty_midi as pm
import subprocess

HERE = Path("/home/joons/.hermes/services/music_score")
MID = HERE / "step4_guitar_only.mid"
LY = HERE / "moon_score.ly"
BPM = 89
EIGHTH = 60.0 / BPM / 2     # seconds per 8th note

NAMES = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]
def pitch(p):
    octv = p // 12 - 5      # fixed mode: `c` = C4
    return NAMES[p % 12] + ("'" * octv if octv >= 0 else "," * -octv)

mid = pm.PrettyMIDI(MID)
raw = [(n.start, n.pitch, n.velocity or 64)
       for i in mid.instruments for n in i.notes]
raw = [r for r in raw if 40 <= r[1] <= 84]

# energy cut: drop weakest 10%
v = np.array([r[2] for r in raw], float)
thr = float(np.percentile(v, 10))
raw = [r for r in raw if r[2] >= thr]

# onset clustering -> events
events = []
for s, p, vel in sorted(raw):
    if events and s - events[-1][0] <= 0.15:
        if p not in [x[0] for x in events[-1][1]]:
            events[-1][1].append((p, vel))
    else:
        events.append([s, [(p, vel)]])

# quantize to 8th grid; same slot -> merge into chord
slots = collections.defaultdict(list)
for s, notes in events:
    slot = round(s / EIGHTH)
    for p, vel in notes:
        if all(p != x[0] for x in slots[slot]):
            slots[slot].append((p, vel))

out = ['\\version "2.24.3"',
       "guitar = {",
       f"  \\tempo 4 = {BPM}",
       "  \\override Staff.TimeSignature.stencil = ##f",
       "  \\set Staff.instrumentName = \"Electric Guitar\"",
       ""]
n_events, n_chords = 0, 0
for slot in sorted(slots):
    notes = sorted(slots[slot], key=lambda x: -x[1])[:3]   # top 3 voices
    if len(notes) == 1:
        out.append(f"  {pitch(notes[0][0])}8")
        n_events += 1
    else:
        out.append("  < " + " ".join(pitch(p) for p, _ in notes) + " >8")
        n_chords += 1
out += ["}", "", "\\header {",
        '  title = "Moon Represents My Heart (auto score from guitar stem)"',
        "}", "", "\\score {",
        "\\new Staff \\with { instrumentName = \"\" } \\guitar",
        "  \\layout { }", "  \\midi { }", "}", ""]

LY.write_text("\n".join(out), encoding="utf-8")
print(f"events: {n_events} (chords {n_chords}), total slots {len(slots)}, vel cut < {thr:.0f}")

r = subprocess.run(["lilypond", "--output", str(HERE / "moon_score"),
                    str(LY)], capture_output=True, text=True)
print("lilypond rc:", r.returncode)
if r.returncode != 0:
    print("\n".join(l for l in r.stdout.splitlines() if "error" in l)[:500])
