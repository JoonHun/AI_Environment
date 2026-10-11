import guitarpro
# guitarpro native: 1 quarter note = 3840 ticks, so a 4/4 measure = 15360 ticks
DUR_TICKS = {1:15360, 2:7680, 4:3840, 8:1920, 16:960, 32:480, 64:240, 128:120}
MEAS = 4 * 3840   # 15360
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
                if e > MEAS:
                    bad += 1
                    if bad <= 8:
                        lines.append(f"{f} m{mi}v{vi} OVERFLOW end={e} (>{MEAS})")
                prev_end = e
    m1 = t.measures[0]
    for vi, v in enumerate(m1.voices):
        seq = [(b.startInMeasure, b.duration.value) for b in v.beats]
        lines.append(f"{f} m1v{vi}: {seq}")
    lines.append(f"{f}: notes={nb} measures={len(t.measures)} problems={bad}")
open("verify.txt", "w").write("\n".join(lines))
