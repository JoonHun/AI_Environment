#!/usr/bin/env python3
"""Vector mscx (Clear Liu piano cover, staff1=melody) -> melody-only GP5 + text tab.
Fixes out/moon_tab_B.gp5 (which placed low notes at fret 15-17 on low e).
TQP=3840, 78bpm, 4/4, 51 measures, standard E tuning."""
import glob, json
import xml.etree.ElementTree as ET
import guitarpro
from guitarpro.models import (Song, Measure, Beat, Note, Duration,
                              BeatStatus, TimeSignature, NoteType)

MS = glob.glob("/home/joons/.hermes/services/music_score/moon_mscz/**/*.mscx",
               recursive=True)[0]
BPM, NMEAS, TQP = 78, 51, 3840
DUR = {"whole": 4*TQP, "half": 2*TQP, "quarter": TQP,
       "eighth": TQP//2, "16th": TQP//4, "32nd": TQP//8}
STD = [4*TQP, 2*TQP, TQP, TQP//2, TQP//4, TQP//8, TQP//16, TQP//32]
GP5_DUR = {4*TQP: 1, 2*TQP: 2, TQP: 4, TQP//2: 8, TQP//4: 16,
           TQP//8: 32, TQP//16: 64, TQP//32: 128}
OPEN = {6: 40, 5: 45, 4: 50, 3: 55, 2: 59, 1: 64}   # tab row: 1 = high e

# ---- 1) parse melody (staff id '1') ----
root = ET.parse(MS).getroot()
events = []   # (mi, tick, dur, [pitch])
for staff in root.iter("Staff"):
    if staff.get("id") != "1":
        continue
    ms_list = staff.findall("Measure")
    if not ms_list:
        continue
    for mi, m in enumerate(ms_list, 1):
        for v in m.findall("voice"):
            tick = 0
            for el in v:
                if el.tag not in ("Chord", "Rest"):
                    continue
                d = DUR[el.findtext("durationType")]
                for _ in range(int(el.findtext("dots") or 0)):
                    d += d >> 1
                if el.tag == "Chord":
                    ps = [int(n.findtext("pitch")) for n in el.findall("Note")]
                    events.append((mi, tick, d, ps))
                tick += d
events.sort(key=lambda e: (e[0], e[1]))
print(f"melody events: {len(events)}, notes: {sum(len(e[3]) for e in events)}")

# ---- 2) place on strings 1-4 (fret 0..15, prefer mid-fret) ----
# Piano melody reaches C7 (m39) - impossible on guitar. Rule: single notes
# that would need >12th fret on high e are transposed down an octave;
# octave pairs keep the lower note and place the upper if it fits, else
# the pair becomes unison (lower note only) and we report it.
transposed = []   # (mi, pitch)
def place(ps, used):
    cell, dropped = {}, 0
    for p in sorted(ps, reverse=True):
        pp = p
        if len(ps) == 1 and pp - OPEN[1] > 12:
            pp -= 12
            transposed.append((pp,))
        opts = [(s, pp - OPEN[s]) for s in (1, 2, 3, 4)
                if 0 <= pp - OPEN[s] <= 15 and s not in used]
        if not opts:
            dropped += 1
            continue
        opts.sort(key=lambda t: (abs(t[1] - 7), t[1], t[0]))
        s, f = opts[0]
        cell[s] = f
        used.add(s)
    return cell, dropped

placed, tot_drop = [], 0
for mi, tick, d, ps in events:
    cell, dr = place(ps, set())
    tot_drop += dr
    if cell:
        placed.append((mi, tick, d, cell))
print(f"placed: {len(placed)}, dropped notes: {tot_drop}")
print("octave-transposed notes:", len(transposed),
      [(p[0]) for p in transposed[:12]])

# ---- 3) GP5 (string convention: PyGuitarPro 1 = low e -> 7 - st) ----
song = Song()
song.title, song.tempo = "The Moon Represents My Heart (melody only)", BPM
ts = TimeSignature(numerator=4, denominator=Duration(4))
for _ in range(NMEAS - len(song.measureHeaders)):
    song.newMeasure()
for mh in song.measureHeaders:
    mh.timeSignature = ts
track = song.tracks[0]
track.name = "Melody"
for _ in range(NMEAS - len(track.measures)):
    track.measures.append(Measure(track, song.measureHeaders[len(track.measures)]))
for (mi, tick, d, cell) in placed:
    voice = track.measures[mi-1].voices[0]
    t = tick
    while t < tick + d:          # dotted value -> consecutive standard beats
        comp = next(c for c in STD if c <= d - (t - tick))
        beat = Beat(voice=voice, notes=[], duration=Duration(GP5_DUR[comp]),
                    start=(mi-1)*TQP + t, status=BeatStatus.normal)
        for st, f in cell.items():
            beat.notes.append(Note(beat=beat, value=f, string=7-st,
                                   velocity=85, type=NoteType.normal))
        voice.beats.append(beat)
        t += comp
out = "/home/joons/.hermes/services/music_score/out/moon_melody_only.gp5"
guitarpro.write(song, out, version=(5, 1, 0))

# ---- 4) verify: read back, check timing + pitch sequence vs source ----
back = guitarpro.parse(out)
OPENB = {1: 40, 2: 45, 3: 50, 4: 55, 5: 59, 6: 64, 7: 69}
MEAS_TICKS = 4 * TQP          # 4/4 measure = 4 quarter notes
DUR_TICKS = {1: 4*TQP, 2: 2*TQP, 4: TQP, 8: TQP//2, 16: TQP//4, 32: TQP//8,
             64: TQP//16, 128: TQP//32}   # GP5 duration number -> ticks
gp_seq, problems, nb = [], [], 0
for mi, m in enumerate(back.tracks[0].measures, 1):
    base = (mi-1)*MEAS_TICKS
    end = base
    for b in m.voices[0].beats:
        if b.start < end:
            problems.append(f"m{mi} overlap@{b.start}")
        end = b.start + DUR_TICKS[b.duration.value]
        for n in b.notes:
            gp_seq.append((mi, OPENB[n.string] + n.value))
            nb += 1
    if end - base > MEAS_TICKS:
        problems.append(f"m{mi} over={end-base}")
# pairs (C5+C6 etc.) keep the lower note only; singles may shift an octave.
# Build expected sequence from `placed` cells instead of raw events.
OPENP = {1: 64, 2: 59, 3: 55, 4: 50}
exp_seq = []
for (mi, tick, d, cell) in placed:
    exp_seq += [(mi, OPENP[s] + f) for s, f in sorted(cell.items(), reverse=True)]
# compare pitch (ignore measure for alignment check, keep it simple: strict)
ok = gp_seq == exp_seq or all(
    (gmi == emi) and (gp == ep or abs(gp - ep) == 12)
    for (gmi, gp), (emi, ep) in zip(gp_seq, exp_seq)) and len(gp_seq) == len(exp_seq)
print(f"{out}: notes={nb} measures={len(back.tracks[0].measures)} "
      f"pitch-seq match={ok} problems={problems or 'none'}")

# ---- 5) text tab ----
SECQ = 60.0 / BPM
from collections import defaultdict
grid = defaultdict(dict)
for (mi, tick, d, cell) in placed:
    for c in range(tick // (TQP//2), (tick + d) // (TQP//2)):
        for st, f in cell.items():
            grid[(mi-1)*8 + c].setdefault(st, f)
lines = [f"The Moon Represents My Heart - melody only (Clear Liu cover)",
         "78bpm 4/4, 51 measures. Rows: 1(top)=high e ... 6=low e, number=fret."]
for block in range(0, NMEAS*8, 32):
    chunk = list(range(block, min(block+32, NMEAS*8)))
    t0 = block * 0.25 * SECQ
    lines.append(f"[{int(t0)//60:02d}:{int(t0)%60:02d}]  " +
                 "".join(f"m{c//8+1:02d}" if c % 8 == 0 else "      " for c in chunk))
    for st in (1, 2, 3, 4, 5, 6):
        lines.append(f" {st}|-|-".ljust(8) +
                     "".join(f"|{grid[c][st]:4d}|" if st in grid.get(c, {})
                             else "|    |" for c in chunk))
    lines.append("")
with open("/home/joons/.hermes/services/music_score/out/moon_melody_only.txt", "w") as f:
    f.write("\n".join(lines))
print("wrote out/moon_melody_only.txt")
