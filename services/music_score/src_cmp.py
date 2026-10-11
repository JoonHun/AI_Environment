import glob, xml.etree.ElementTree as ET
from collections import defaultdict
import guitarpro

root = ET.parse(glob.glob("moon_mscz/**/*.mscx", recursive=True)[0]).getroot()
meas = defaultdict(lambda: {"1": [], "2": []})
for score in root.iter("Score"):
    for staff in [s for s in score if s.tag == "Staff"]:
        sid = staff.get("id")
        for mi, m in enumerate(staff.findall("Measure"), 1):
            for v in m.findall("voice"):
                tick = 0
                for el in v:
                    if el.tag not in ("Chord", "Rest"):
                        continue
                    d = {"whole":3840,"half":1920,"quarter":960,"eighth":480,
                         "16th":240,"32nd":120}[el.findtext("durationType")]
                    for i in range(int(el.findtext("dots") or 0)):
                        d += d >> (i+1)
                    if el.tag == "Chord":
                        meas[mi][sid].append([tick, int(el.findtext("Note/pitch")), d])
                    tick += d

lines = []
for f, sid_map in [("out/moon_tab_B.gp5", {"1": [1,2,3,4]}),
                   ("out/moon_tab_A.gp5", {"1": [1,2,3,4], "2": [4,5,6]})]:
    s = guitarpro.parse(f); t = s.tracks[0]
    mismatch = 0
    for mi, m in enumerate(t.measures, 1):
        # collect melody notes (voice 1) from GP5, map fret->pitch via strings
        STR = {1:64,2:59,3:55,4:50,5:45,6:40}
        got = set()
        for vi, v in enumerate(m.voices):
            for b in v.beats:
                for n in b.notes:
                    got.add((b.startInMeasure, STR[7 - n.string] + n.value))
        src = set()
        for tick, p, d in meas[mi]["1"]:
            src.add((tick, p))
        for tick, p, d in meas[mi]["2"]:
            src.add((tick, p+12 if p < 50 else p))
        # only check that every source (tick,pitch) is present in GP5 (placement may differ per string, but pitch same)
        got_p = {(t, p) for (t, p) in got}
        for (t, p) in src:
            if (t, p) not in got_p:
                mismatch += 1
                if mismatch <= 8:
                    lines.append(f"{f} m{mi}: MISSING src pitch@{t} p={p}")
    lines.append(f"{f}: missing source pitches = {mismatch}")
open("src_cmp.txt", "w").write("\n".join(lines))
