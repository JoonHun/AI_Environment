import guitarpro
DUR_TICKS = {1:3840, 2:1920, 4:960, 8:480, 16:240, 32:120, 64:60, 128:30}
lines = []
for f in ("out/moon_tab_A.gp5", "out/moon_tab_B.gp5"):
    s = guitarpro.parse(f)
    t = s.tracks[0]
    bad = 0
    nb = 0
    for mi, m in enumerate(t.measures, 1):
        for vi, v in enumerate(m.voices):
            if not v.beats:
                continue
            prev_end = 0
            for b in v.beats:
                nb += len(b.notes)
                st = b.startInMeasure
                e = st + DUR_TICKS[b.duration.value]
                if st < prev_end:
                    bad += 1
                    if bad <= 4:
                        lines.append(f"{f} m{mi}v{vi} OVERLAP @start={st}")
                if e > 3840:
                    bad += 1
                    if bad <= 8:
                        lines.append(f"{f} m{mi}v{vi} OVERFLOW end={e}")
                prev_end = e
    lines.append(f"{f}: notes={nb} problems={bad}")
open("verify.txt", "w").write("\n".join(lines))
