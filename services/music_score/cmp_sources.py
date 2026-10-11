#!/usr/bin/env python3
"""Are the user's GP4 melody and the prior mscx (Clear Liu) melody the same song?
Compare pitch-class sequences (octave-agnostic). Also isolate the GP4 'melody'
(top line) so we can build a clean melody-only GP5 from the user's own tab.
"""
import sys, glob
from collections import Counter
sys.path.insert(0, '/home/joons/guitar-tab/.venv/lib/python3.12/site-packages')
import guitarpro
import xml.etree.ElementTree as ET

NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def nm(p): return f"{NAMES[p%12]}{p//12-1}"
def pc(seq): return [p % 12 for p in seq]

# ---------- user GP4 ----------
gp4 = '/home/joons/.hermes/profiles/joons/attachments/월량대표아적심(070528)-2.gp4'
sa = guitarpro.parse(gp4)
tr = sa.tracks[0]
OPEN = {1:40,2:45,3:50,4:55,5:59,6:64,7:69}
# list every note with (measure, string, fret, pitch) in order
alln = []
for mi, m in enumerate(tr.measures, 1):
    for v in m.voices:
        for b in v.beats:
            for n in b.notes:
                alln.append((mi, n.string, n.value, OPEN[n.string]+n.value, b.duration.value))
print(f"GP4: {len(alln)} notes, {len(tr.measures)} measures")
# melody = top line: for each distinct beat-position keep only the highest note.
# Group by (measure, start) — but PyGuitarPro beat.start is absolute; use (mi, index-in-measure)
from itertools import groupby
# rebuild per measure with start positions
top = []   # melody notes
for mi, m in enumerate(tr.measures, 1):
    seen = {}
    for v in m.voices:
        for b in v.beats:
            key = b.start
            for n in b.notes:
                p = OPEN[n.string]+n.value
                if key not in seen or p > seen[key][0]:
                    seen[key] = (p, n.string, n.value, b.duration.value)
    for key in sorted(seen):
        p, s, f, dv = seen[key]
        top.append((mi, s, f, p, dv))
top_pc = [t[3] for t in top]
print(f"GP4 top-line (melody) notes: {len(top_pc)}")
print("  first 24:", " ".join(nm(t[3]) for t in top[:24]))

# ---------- mscx melody (proper: skip empty staves, no early break) ----------
MS = glob.glob('/home/joons/.hermes/services/music_score/moon_mscz/**/*.mscx', recursive=True)[0]
root = ET.parse(MS).getroot()
mel = []
for staff in root.iter('Staff'):
    if staff.get('id') != '1':
        continue
    ms_list = staff.findall('Measure')
    if not ms_list:
        continue
    for mi, m in enumerate(ms_list, 1):
        for v in m.findall('voice'):
            for el in v:
                if el.tag == 'Chord':
                    for n in el.findall('Note'):
                        mel.append(int(n.findtext('pitch')))
mel_pc = pc(mel)
print(f"mscx staff1 melody: {len(mel)} notes")
print("  first 24:", " ".join(nm(p) for p in mel[:24]))

# ---------- compare ----------
print("\n== pitch-class histograms ==")
ca, cm = Counter(pc([a[3] for a in alln])), Counter(mel_pc)
print(f"{'':>3} {'GP4-all':>8} {'GP4-top':>8} {'mscx':>6}")
for p in range(12):
    gt = Counter(pc(top_pc))[p]
    print(f"{NAMES[p]:>3} {ca[p]:>8} {gt:>8} {cm[p]:>6}")

# is mscx melody a subsequence (in order) of GP4 top-line pitch classes?
def is_subseq(sub, main):
    it = iter(main)
    return all(x in it for x in sub)
print("\nmscx-melody ⊆ GP4-top (subseq, pitchclass):", is_subseq(mel_pc, pc(top_pc)))
print("GP4-top  ⊆ mscx-melody (subseq, pitchclass):", is_subseq(pc(top_pc), mel_pc))
print("equal length pc:", len(mel_pc)==len(top_pc), "equal pc seq:", mel_pc==pc(top_pc))
