import guitarpro
s = guitarpro.parse('/home/joons/.hermes/profiles/joons/attachments/월량대표아적심(070528).gp4')
lines = []
lines.append(f"tracks={len(s.tracks)} measures={len(s.measureHeaders)} title={s.title} tempo={s.tempo}")
t = s.tracks[0]
lines.append(f"track name={t.name}, voices per measure={len(t.measures[0].voices)}")
for mi, m in enumerate(t.measures, 1):
    for vi, v in enumerate(m.voices):
        if v.beats:
            seq = [(b.startInMeasure, b.duration.value,
                    [(n.string, n.value) for n in b.notes]) for b in v.beats]
            lines.append(f"m{mi:02d}v{vi}: {seq}")
open("gp4_dump.txt", "w").write("\n".join(lines))
print("done", len(lines))
