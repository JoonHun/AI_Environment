#!/usr/bin/env python3
"""Parse MuseScore 3 .mscx (notes live in Score/Staff id=1,2) -> note list."""
import sys, xml.etree.ElementTree as ET

tree = ET.parse(sys.argv[1])
root = tree.getroot()
out = []
for score in root.iter("Score"):
    for staff in [s for s in score if s.tag == "Staff"]:
        sid = staff.get("id")
        for m_i, m in enumerate(staff.findall("Measure"), start=1):
            for v_i, v in enumerate(m.findall("voice")):
                for ch in v:
                    if ch.tag == "Rest":
                        dt = ch.findtext("durationType"); dts = ch.findtext("dots") or ""
                        out.append(f"m{m_i:02d} s{sid} v{v_i} R {dt}{dts}")
                    elif ch.tag == "Chord":
                        dt = ch.findtext("durationType"); dts = ch.findtext("dots") or ""
                        for n in ch.findall("Note"):
                            p = n.findtext("pitch")
                            out.append(f"m{m_i:02d} s{sid} v{v_i} N {p} {dt}{dts}")
print("\n".join(out))
print(f"TOTAL: {len(out)}", file=sys.stderr)
