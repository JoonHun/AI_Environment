#!/usr/bin/env python3
"""Format MuseScore 3 .mscx as readable per-measure score (chord-aware)."""
import sys, re
import xml.etree.ElementTree as ET
from collections import defaultdict

P = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
def m2n(m):
    return f"{P[m % 12]}{m // 12 - 1}"

tree = ET.parse(sys.argv[1])
meas = defaultdict(lambda: {"1": [], "2": []})
for score in tree.getroot().iter("Score"):
    for staff in [s for s in score if s.tag == "Staff"]:
        sid = staff.get("id")
        for m_i, m in enumerate(staff.findall("Measure"), 1):
            for v in m.findall("voice"):
                for ch in v:
                    if ch.tag == "Rest":
                        meas[m_i][sid].append(f"r{ch.findtext('durationType')}{ch.findtext('dots') or ''}")
                    elif ch.tag == "Chord":
                        names = [m2n(int(n.findtext("pitch"))) for n in ch.findall("Note")]
                        d = ch.findtext("durationType") + (ch.findtext("dots") or "")
                        meas[m_i][sid].append("/".join(names) + "." + d)

for mi in sorted(meas):
    print(f"m{mi:02d} | T: {' '.join(meas[mi]['1'])}")
    print(f"     | B: {' '.join(meas[mi]['2'])}")
