#!/usr/bin/env python3
"""FINAL: melody-only GP5 from moon_mscz (Clear Liu piano cover, C major).
Staff0 = melody (treble). MuseScore 3.01 XML, Division=480/quarter.
PyGuitarPro semantics (empirically verified):
  - GP5 file ticks/quarter = 960; write beat.start = rel_start + dur (end tick)
  - string 1 = high e
"""
import xml.etree.ElementTree as ET, glob, sys
from collections import defaultdict
sys.path.insert(0, '/home/joons/guitar-tab/.venv/lib/python3.12/site-packages')
import guitarpro
from guitarpro.models import (Song, Measure, Beat, Note, Duration,
                              BeatStatus, TimeSignature, NoteType)

MS = glob.glob('/home/joons/.hermes/services/music_score/moon_mscz/*.mscx')[0]
OUT = '/home/joons/.hermes/services/music_score/out/moon_melody.gp5'
TXT = '/home/joons/.hermes/services/music_score/out/moon_melody.txt'

FILE_TQ = 960                       # GP5 file ticks per quarter
DUR = {'whole': 4, 'half': 2, 'quarter': 1, 'eighth': .5, '16th': .25,
       '32nd': .125, '64th': .0625, '128th': .03125}
NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def nm(p): return f"{NAMES[p%12]}{p//12-1}"

root = ET.parse(MS).getroot()
staff0 = root.find('Score').findall('Staff')[0]
measures = staff0.findall('Measure')

# ---- 1) parse melody: rel tick per measure (960 domain); Chords AND Rests advance ----
def dur_of(el):
    dt = el.findtext('durationType')
    if dt not in DUR:
        return None
    d = DUR[dt]
    nd = el.find('dots')                      # MuseScore 3: <dots>N</dots>, text = count
    if nd is not None and (nd.text or '').strip():
        d *= (1 + sum(1 / 2 ** i for i in range(1, int(nd.text) + 1)))
    return d

events = []        # (mi, start_tick, dur_ticks, [pitches])
for mi, m in enumerate(measures, 1):
    t = 0
    for el in m.iter():
        if el.tag == 'Chord':
            if el.get('grace'):            # grace notes: skip
                continue
            d = dur_of(el)
            if d is None:
                continue
            notes = [int(n.findtext('pitch')) for n in el.findall('Note')]
            if not notes:
                continue
            events.append((mi, t, int(d * FILE_TQ), notes))
            t += int(d * FILE_TQ)
        elif el.tag == 'Rest':
            d = dur_of(el)
            if d is not None:
                t += int(d * FILE_TQ)
print(f"measures={len(measures)} melody events={len(events)}")

# ---- 2) place on guitar (std E, strings 1-4, 1=high e, fret 0..15) ----
SOPEN = {1: 64, 2: 59, 3: 55, 4: 50}
def place_one(p):
    c = p
    if c - SOPEN[1] > 15:
        c -= 12
    if c - SOPEN[1] < 0:
        c += 12
    opts = [(s, c - SOPEN[s]) for s in (1, 2, 3, 4) if 0 <= c - SOPEN[s] <= 15]
    if not opts:
        return None
    opts.sort(key=lambda x: (abs(x[1] - 6), x[1], x[0]))   # mid-fret first
    return (opts[0][0], opts[0][1], c)

placed = []        # (mi, start, dur, [(s, f, pitch)])
for (mi, start, dur, ps) in events:
    cells, seen = [], set()
    for p in ps:
        r = place_one(p)
        if r and (r[0], r[1]) not in seen:
            seen.add((r[0], r[1]))
            cells.append(r)
    if not cells:
        continue
    if len(ps) > 1:                       # pair: keep top placed note
        cells = [max(cells, key=lambda r: r[2])]
    if start + dur > 4 * FILE_TQ:         # overfull measure: trim to bar end
        dur = 4 * FILE_TQ - start
    placed.append((mi, start, dur, cells))
print(f"placed={len(placed)}")

# ---- 3) write GP5 ----
song = Song()
song.title = "The Moon Represents My Heart - melody (C major, Clear Liu piano cover)"
song.tempo = 78
ts = TimeSignature(numerator=4, denominator=Duration(4))
while len(song.measureHeaders) < len(measures):
    song.newMeasure()
for mh in song.measureHeaders:
    mh.timeSignature = ts
track = song.tracks[0]
track.name = "Melody"
while len(track.measures) < len(measures):
    track.measures.append(Measure(track, song.measureHeaders[len(track.measures)]))
def make_dur(d):
    """ticks on 960/quarter scale -> PGP Duration (dotted values via isDotted)."""
    for base in (1, 2, 4, 8, 16, 32, 64, 128):
        bt = 3840 // base
        if d == bt:
            return Duration(base)
        if d == bt + bt // 2:
            return Duration(base, isDotted=True)
    raise ValueError(f"unmappable duration {d}")

for (mi, start, dur, cells) in placed:
    voice = track.measures[mi - 1].voices[0]
    beat = Beat(voice=voice,
                notes=[Note(beat=None, value=f, string=s, velocity=90,
                            type=NoteType.normal) for (s, f, _p) in cells],
                duration=make_dur(dur),
                start=song.measureHeaders[mi - 1].start + start,   # absolute domain
                status=BeatStatus.normal)
    for n in beat.notes:
        n.beat = beat
    voice.beats.append(beat)

# ---- 3b) fill short measures (mscx has 8 measures < 4 beats) with trailing rest ----
filled = []
for mi, m in enumerate(measures, 1):
    tot = sum(d for (mmi, _s, d, _c) in placed if mmi == mi)
    if 0 < tot < 4 * FILE_TQ:
        gap = 4 * FILE_TQ - tot
        voice = track.measures[mi - 1].voices[0]
        rb = Beat(voice=voice, notes=[], duration=make_dur(gap),
                  start=song.measureHeaders[mi - 1].start + tot,
                  status=BeatStatus.rest)
        voice.beats.append(rb)
        filled.append((mi, tot, gap))
print(f"filled={filled}")
guitarpro.write(song, OUT, version=(5, 1, 0))

# ---- 4) verify: read back, check contiguity + pitch sequence ----
back = guitarpro.parse(OUT)
TPQF = back.music.timeDivision if back.music else 960
OPENB = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}   # string 1 = high e
seq, problems, nb = [], [], 0
for mi, m in enumerate(back.tracks[0].measures, 1):
    base = m.start
    prev_end = base
    total = 0
    for b in m.voices[0].beats:
        d = b.duration.time                     # ticks via 960/quarter fixed scale
        if b.start < prev_end - 1:
            problems.append(f"m{mi} overlap")
        prev_end = max(prev_end, b.start)
        total += d
        for n in b.notes:
            seq.append(OPENB[n.string] + n.value)
            nb += 1
    if abs(total - 3840) > 1:
        problems.append(f"m{mi} total={total}")
src_pc = [max(c[2] for c in cells) % 12 for (_mi, _s, _d, cells) in placed]
out_pc = [p % 12 for p in seq]
match = sum(1 for a, b in zip(src_pc, out_pc) if a == b) / max(1, min(len(src_pc), len(out_pc)))
print(f"VERIFY notes={nb} measures={len(back.tracks[0].measures)} "
      f"pitch-class match={match:.1%} problems={problems or 'none'}")
print("first 12:", " ".join(nm(p) for p in seq[:12]))
print("last 6:  ", " ".join(nm(p) for p in seq[-6:]))

# ---- 5) text tab (eighth-note cells) ----
SECQ = 60.0 / 78
grid = defaultdict(dict)
for (mi, start, dur, cells) in placed:
    c0, c1 = start // (FILE_TQ // 2), (start + dur) // (FILE_TQ // 2)
    for c in range(c0, c1):
        if c < len(measures) * 8:
            for (s, f, _p) in cells:
                grid[(mi - 1) * 8 + c][s] = f
lines = ["The Moon Represents My Heart - melody only (C major)",
         "78bpm 4/4, from Clear Liu piano cover (moon_mscz). Rows 1(top)=high e, 6=low e."]
for block in range(0, len(measures) * 8, 32):
    chunk = list(range(block, min(block + 32, len(measures) * 8)))
    t0 = block * 0.25 * SECQ
    lines.append(f"[{int(t0)//60:02d}:{int(t0)%60:02d}]  " +
                 "".join(f"m{c//8+1:02d}" if c % 8 == 0 else "      " for c in chunk))
    for s in (1, 2, 3, 4, 5, 6):
        lines.append(f" {s}|-|-".ljust(8) +
                     "".join(f"|{grid[c][s]:4d}|" if s in grid.get(c, {}) else "|    |"
                             for c in chunk))
    lines.append("")
open(TXT, 'w').write("\n".join(lines))
print("wrote", OUT)
print("wrote", TXT)
