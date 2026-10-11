#!/usr/bin/env python3
"""Corrected comparison. PyGuitarPro string#1 = high e (E4=64).
Extract GP4 top-line (melody) with real tuning, compare to mscx staff1 melody.
"""
import sys, glob
from collections import Counter
sys.path.insert(0, '/home/joons/guitar-tab/.venv/lib/python3.12/site-packages')
import guitarpro
import xml.etree.ElementTree as ET

NAMES=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def nm(p): return f"{NAMES[p%12]}{p//12-1}"
def pc(seq): return [p%12 for p in seq]

gp4 = '/home/joons/.hermes/profiles/joons/attachments/월량대표아적심(070528)-2.gp4'
sa = guitarpro.parse(gp4)
tr = sa.tracks[0]
OPEN = {s.number: s.value for s in tr.strings}   # correct: 1=high e
print("OPEN (1=high e):", {k: nm(OPEN[k]) for k in sorted(OPEN)})

# ---- GP4 top line: per (measure, start) keep highest pitch ----
top = []
for mi, m in enumerate(tr.measures, 1):
    seen = {}
    for v in m.voices:
        for b in v.beats:
            for n in b.notes:
                p = OPEN[n.string] + n.value
                if b.start not in seen or p > seen[b.start][0]:
                    seen[b.start] = (p, n.string, n.value, b.duration.value)
    for k in sorted(seen):
        p, s, f, dv = seen[k]
        top.append((mi, p, dv))
top_pc = [t[1] for t in top]
print(f"GP4 top-line melody: {len(top_pc)} notes, {len(tr.measures)} measures")
print("  m1 :", " ".join(nm(t[1]) for t in top if t[0]==1))
print("  m2 :", " ".join(nm(t[1]) for t in top if t[0]==2))
print("  m3 :", " ".join(nm(t[1]) for t in top if t[0]==3))

# ---- mscx staff1 ----
MS = glob.glob('/home/joons/.hermes/services/music_score/moon_mscz/**/*.mscx', recursive=True)[0]
root = ET.parse(MS).getroot()
mel = []
for staff in root.iter('Staff'):
    if staff.get('id')=='1':
        for m in staff.findall('Measure'):
            for v in m.findall('voice'):
                for e in v:
                    if e.tag=='Chord':
                        for n in e.findall('Note'):
                            mel.append(int(n.findtext('pitch')))
        break
mel_pc = pc(mel)
print(f"\nmscx staff1 melody: {len(mel)} notes")
print("  first3m: " + " ".join(nm(p) for p in mel[:18]))

# ---- compare histograms ----
print("\n== pitch-class histograms (corrected) ==")
ct, cm = Counter(pc(top_pc)), Counter(mel_pc)
print(f"{'':>3} {'GP4-top':>8} {'mscx':>6}")
for p in range(12):
    print(f"{NAMES[p]:>3} {ct[p]:>8} {cm[p]:>6}")

def is_subseq(sub, main):
    it = iter(main); return all(x in it for x in sub)
print("\nmscx ⊆ GP4-top (pc subseq):", is_subseq(mel_pc, pc(top_pc)))
print("GP4-top ⊆ mscx (pc subseq):", is_subseq(pc(top_pc), mel_pc))
print("equal pc seq:", mel_pc == pc(top_pc))

# ---- key inference ----
def keyname(hist):
    # simple: most common pc
    if not hist: return "?"
    return NAMES[hist.most_common(1)[0][0]]
print("\nGP4-top most common pc:", keyname(ct), " mscx most common pc:", keyname(cm))
