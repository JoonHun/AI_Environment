#!/usr/bin/env python3
"""Compare three sources of the melody for 月亮代表我的心:
  (A) user GP4  월량대표아적심(070528)-2.gp4  (tab sheet)
  (B) existing MuseScore mscx staff1 (vector, prior session)
  (C) current generated out/moon_melody_only.gp5
Print per-source note lists + pitch-set comparison so we can tell if they
are the same arrangement and whether (C) is correct.
"""
import sys, glob
sys.path.insert(0, '/home/joons/guitar-tab/.venv/lib/python3.12/site-packages')
import guitarpro
import xml.etree.ElementTree as ET

NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def nm(p): return f"{NAMES[p%12]}{p//12-1}"

# ---- (A) GP4 ----
gp4 = '/home/joons/.hermes/profiles/joons/attachments/월량대표아적심(070528)-2.gp4'
sa = guitarpro.parse(gp4)
OPEN = {1:40,2:45,3:50,4:55,5:59,6:64,7:69}  # 1=low e
a_seq, a_info = [], []
for ti, tr in enumerate(sa.tracks):
    n_notes = sum(len(b.notes) for m in tr.measures for v in m.voices for b in v.beats)
    a_info.append((ti+1, tr.name, len(tr.measures), n_notes))
print("== GP4 tracks ==")
for ti, name, nm_, nn in a_info:
    print(f"  track{ti} {name!r}: measures={nm_} notes={nn}")
# pick the track with the most notes in the upper strings = melody
def track_seq(tr):
    seq = []
    for m in tr.measures:
        for v in m.voices:
            for b in v.beats:
                for n in b.notes:
                    seq.append(OPEN[n.string] + n.value)
    return seq
best = max(sa.tracks, key=lambda t: sum(len(b.notes) for m in t.measures for v in m.voices for b in v.beats))
a_seq = track_seq(best)
print(f"GP4 melody track: notes={len(a_seq)} first10={a_seq[:10]} last6={a_seq[-6:]}")

# ---- (B) mscx staff1 ----
MS = glob.glob('/home/joons/.hermes/services/music_score/moon_mscz/**/*.mscx', recursive=True)[0]
root = ET.parse(MS).getroot()
b_seq = []
for staff in root.iter('Staff'):
    if staff.get('id') != '1':
        continue
    for m in staff.findall('Measure'):
        for v in m.findall('voice'):
            for el in v:
                if el.tag == 'Chord':
                    for n in el.findall('Note'):
                        b_seq.append(int(n.findtext('pitch')))
    break
print(f"mscx staff1: notes={len(b_seq)} first10={b_seq[:10]} last6={b_seq[-6:]}")

# ---- (C) generated gp5 ----
sc = guitarpro.parse('/home/joons/.hermes/services/music_score/out/moon_melody_only.gp5')
c_seq = track_seq(sc.tracks[0])
print(f"generated gp5: notes={len(c_seq)} first10={c_seq[:10]} last6={c_seq[-6:]}")

# ---- comparison (pitch classes, ignore octave) ----
def pc(seq): return [p % 12 for p in seq]
print("\n== pitch-class counts ==")
from collections import Counter
ca, cb, cc = Counter(pc(a_seq)), Counter(pc(b_seq)), Counter(pc(c_seq))
allpc = sorted(set(ca)|set(cb)|set(cc))
print(f"{'pc':>4} {'GP4':>5} {'mscx':>5} {'gp5':>5}")
for p in allpc:
    print(f"{NAMES[p]:>4} {ca[p]:>5} {cb[p]:>5} {cc[p]:>5}")
print(f"\nlen GP4={len(a_seq)} mscx={len(b_seq)} gp5={len(c_seq)}")
print("mscx vs gp5 exact:", b_seq == c_seq)
print("mscx vs gp5 pitchclass-equal:", pc(b_seq) == pc(c_seq))
print("GP4  vs gp5 pitchclass-equal:", pc(a_seq) == pc(c_seq))
