#!/usr/bin/env python3
"""Parse MuseScore .mscx -> plain note list (measure, pitch, duration)."""
import sys
import xml.etree.ElementTree as ET

path = sys.argv[1] if len(sys.argv) > 1 else \
    "moon_mscz/Teresa_Teng_-_The_Moon_Represents_My_Heart_Clear_Liu_Piano_Cover__Deng_Li_Yun__-_Yue_Liang_Dai_Biao_Wo_De_Xin__Liu_Qing_Qing_Gang_Qin_Zhao_.mscx"
tree = ET.parse(path)
root = tree.getroot()

def staff_of(voice_el):
    # walk up to find Staff id
    return voice_el.get("id")

out = []
for score in root.iter("Score"):
    for part in score.iterfind("Part"):
        pname = part.get("id")
        for staff in part.iterfind("Staff"):
            sid = staff.get("id")
            for m_i, m in enumerate(staff.iterfind("Measure"), start=1):
                beats = m.get("ticks")
                for v_i, v in enumerate(m.iterfind("Voice")):
                    for ch in v.iterfind("ChordRest"):
                        if ch.tag == "Rest":
                            d = ch.get("durationType")
                            dts = int(ch.get("dots") or 0)
                            out.append(f"m{m_i:02d} v{v_i} R {d}{dts}")
                        else:
                            d = ch.get("durationType")
                            dts = int(ch.get("dots") or 0)
                            notes = []
                            for n in ch.iterfind("Note"):
                                pc = n.get("pitch")
                                o = n.get("tpc")  # tpc not octave
                                acc = n.get("alter")
                                notes.append((pc, o))
                            for pc, o in notes:
                                out.append(f"m{m_i:02d} v{v_i} N pc={pc} tpc={o} d={d}{dts}")
print(f"part={pname} staff={sid}")
print("\n".join(out))
print(f"TOTAL: {len(out)} events")
