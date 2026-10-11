#!/usr/bin/env python3
"""Extract ONLY the melody line (top voice) from the user's GP4 (D major)
and write a clean melody-only GP5 + text tab.
Source: 월량대표아적심(070528)-2.gp4  (1 track, melody + arpeggio together).
Melody = highest-pitch note in each beat; the rest = accompaniment (dropped).
"""
import sys
from collections import defaultdict
sys.path.insert(0, '/home/joons/guitar-tab/.venv/lib/python3.12/site-packages')
import guitarpro
from guitarpro.models import (Song, Measure, Beat, Note, Duration,
                              BeatStatus, TimeSignature, NoteType)

SRC = '/home/joons/.hermes/profiles/joons/attachments/월량대표아적심(070528)-2.gp4'
OUT = '/home/joons/.hermes/services/music_score/out/moon_melody_gp4.gp5'
TXT = '/home/joons/.hermes/services/music_score/out/moon_melody_gp4.txt'

NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def nm(p): return f"{NAMES[p%12]}{p//12-1}"

# ---- 1) read source, keep real tuning (PyGuitarPro string1 = high e) ----
src = guitarpro.parse(SRC)
tr = src.tracks[0]
OPEN = {s.number: s.value for s in tr.strings}   # {1:64 E4, 2:59 B3, ...}
NMEAS = len(tr.measures)
BPM = src.tempo
TQP = 3840                                        # GP5 ticks per quarter
DUR_TICKS = {1:4*TQP, 2:2*TQP, 4:TQP, 8:TQP//2, 16:TQP//4,
             32:TQP//8, 64:TQP//16, 128:TQP//32}

# ---- 2) melody = highest pitch per beat ----
events = []   # (mi, start, dur, pitch)
for mi, m in enumerate(tr.measures, 1):
    for v in m.voices:
        for b in v.beats:
            if not b.notes:
                continue
            top = max(b.notes, key=lambda n: OPEN[n.string] + n.value)
            p = OPEN[top.string] + top.value
            events.append((mi, b.start, b.duration.value, p))
print(f"melody events: {len(events)}  (measures={NMEAS}, bpm={BPM})")

# ---- 3) place on standard E tuning, strings 1-4, fret 0..15, prefer mid ----
SOPEN = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}   # 1 = high e
def place(p):
    # try to fit; if >15th fret needed on high e, drop an octave
    cand = p
    if cand - SOPEN[1] > 15:
        cand -= 12
    opts = [(s, cand - SOPEN[s]) for s in (1, 2, 3, 4)
            if 0 <= cand - SOPEN[s] <= 15]
    if not opts:
        return None
    opts.sort(key=lambda t: (abs(t[1] - 7), t[1], t[0]))
    s, f = opts[0]
    return (s, f, cand)

placed, dropped = [], 0
for (mi, start, dur, p) in events:
    r = place(p)
    if r is None:
        dropped += 1
        continue
    placed.append((mi, start, dur, r))
print(f"placed: {len(placed)}  dropped: {dropped}")

# ---- 4) build GP5 (PyGuitarPro string = 7 - tabstr) ----
song = Song()
song.title = "The Moon Represents My Heart (melody, D major)"
song.tempo = BPM
ts = TimeSignature(numerator=4, denominator=Duration(4))
while len(song.measureHeaders) < NMEAS:
    song.newMeasure()
for mh in song.measureHeaders:
    mh.timeSignature = ts
track = song.tracks[0]
track.name = "Melody"
while len(track.measures) < NMEAS:
    track.measures.append(Measure(track, song.measureHeaders[len(track.measures)]))
for (mi, start, dur, (s, f, cand)) in placed:
    voice = track.measures[mi - 1].voices[0]
    beat = Beat(voice=voice, notes=[Note(beat=None, value=f, string=7 - s,
                                          velocity=90, type=NoteType.normal)],
                duration=Duration(dur), start=start, status=BeatStatus.normal)
    for n in beat.notes:
        n.beat = beat
    voice.beats.append(beat)
guitarpro.write(song, OUT, version=(5, 1, 0))

# ---- 5) verify: timing contiguous + notes read back ----
back = guitarpro.parse(OUT)
OPENB = {1: 40, 2: 45, 3: 50, 4: 55, 5: 59, 6: 64, 7: 69}
problems, seq = [], []
for mi, m in enumerate(back.tracks[0].measures, 1):
    base = (mi - 1) * TQP
    end = base
    for b in m.voices[0].beats:
        if b.start < end:
            problems.append(f"m{mi} overlap@{b.start}")
        end = b.start + DUR_TICKS[b.duration.value]
        for n in b.notes:
            seq.append(OPENB[n.string] + n.value)
    if end - base > TQP:
        problems.append(f"m{mi} over={end - base}")
print(f"notes={len(seq)} measures={len(back.tracks[0].measures)} "
      f"problems={problems or 'none'}")
print("first 12 melody notes:", " ".join(nm(p) for p in seq[:12]))

# ---- 6) text tab ----
SECQ = 60.0 / BPM
grid = defaultdict(dict)
for (mi, start, dur, (s, f, cand)) in placed:
    c0 = start // (TQP // 2)
    c1 = (start + DUR_TICKS[dur]) // (TQP // 2)
    for c in range(c0, c1):
        if c < NMEAS * 8:
            grid[(mi - 1) * 8 + c].setdefault(s, f)
lines = ["The Moon Represents My Heart - melody only (D major, from GP4)",
         f"{BPM}bpm 4/4, {NMEAS} measures. Rows: 1(top)=high e ... 6=low e, number=fret."]
for block in range(0, NMEAS * 8, 32):
    chunk = list(range(block, min(block + 32, NMEAS * 8)))
    t0 = block * 0.25 * SECQ
    lines.append(f"[{int(t0)//60:02d}:{int(t0)%60:02d}]  " +
                 "".join(f"m{c//8+1:02d}" if c % 8 == 0 else "      " for c in chunk))
    for s in (1, 2, 3, 4, 5, 6):
        lines.append(f" {s}|-|-".ljust(8) +
                     "".join(f"|{grid[c][s]:4d}|" if s in grid.get(c, {})
                             else "|    |" for c in chunk))
    lines.append("")
with open(TXT, "w") as f:
    f.write("\n".join(lines))
print("wrote", OUT)
print("wrote", TXT)
