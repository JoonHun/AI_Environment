import guitarpro, os
DUR_TICKS = {1:3840, 2:1920, 4:960, 8:480, 16:240, 32:120, 64:60, 128:30}
lines = []
for f in ["out/moon_tab_A_v1.gp5", "out/moon_tab_A.gp5", "out/moon_tab_B.gp5"]:
    if not os.path.exists(f):
        lines.append(f"{f}: MISSING"); continue
    s = guitarpro.parse(f)
    t = s.tracks[0]
    m1 = t.measures[0]
    for vi, v in enumerate(m1.voices):
        seq = [(b.startInMeasure, b.duration.value) for b in v.beats]
        tot = sum(DUR_TICKS[b.duration.value] for b in v.beats)
        lines.append(f"{f} m1v{vi}: {seq}  total={tot}")
    # find any measure whose voice total != 3840 (excluding empty)
    odd = 0
    for mi, m in enumerate(t.measures, 1):
        for vi, v in enumerate(m.voices):
            if not v.beats:
                continue
            tot = sum(DUR_TICKS[b.duration.value] for b in v.beats)
            if tot != 3840:
                odd += 1
                if odd <= 5:
                    lines.append(f"  {f} m{mi}v{vi} total={tot} (not 3840)")
    lines.append(f"  {f}: non-4/4 measure-voices = {odd}")
open("cmp.txt", "w").write("\n".join(lines))
