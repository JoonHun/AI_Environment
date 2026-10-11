#!/usr/bin/env python3
"""MuseScore 4 .mscx (Clear Liu piano cover) -> electric guitar GP5 + text tab.
A: melody (high strings) + bass arpeggio accompaniment (bass staff +12st).
B: melody only.  78bpm 4/4, 51 measures.
Tick domain: 1 quarter note = 3840 ticks (GP5 native). Dotted values are split
into consecutive standard beats (no overlap, each voice sums to 3840/measure).
"""
import glob
import xml.etree.ElementTree as ET
from collections import defaultdict

MS = glob.glob("moon_mscz/**/*.mscx", recursive=True)[0]
BPM = 78
NMEAS = 51
TQP = 3840                                   # ticks per quarter (GP5 native)
DUR = {"whole": 4 * TQP, "half": 2 * TQP, "quarter": TQP,
       "eighth": TQP // 2, "16th": TQP // 4, "32nd": TQP // 8}
STD = [4 * TQP, 2 * TQP, TQP, TQP // 2, TQP // 4, TQP // 8, TQP // 16, TQP // 32]
GP5_DUR = {4 * TQP: 1, 2 * TQP: 2, TQP: 4, TQP // 2: 8,
           TQP // 4: 16, TQP // 8: 32, TQP // 16: 64, TQP // 32: 128}

# ---------- parse (.mscx, MuseScore 4: uppercase tags, no tick attrs) ----------
root = ET.parse(MS).getroot()
meas = defaultdict(lambda: {"1": [], "2": []})   # [tick, [pitch], dur]
for score in root.iter("Score"):
    for staff in [s for s in score if s.tag == "Staff"]:
        sid = staff.get("id")
        for mi, m in enumerate(staff.findall("Measure"), 1):
            for v in m.findall("voice"):
                tick = 0
                for el in v:
                    if el.tag not in ("Chord", "Rest"):
                        continue
                    d = DUR[el.findtext("durationType")]
                    for i in range(int(el.findtext("dots") or 0)):
                        d += d >> (i + 1)        # dots: +1/2, +1/4, ...
                    if el.tag == "Chord":
                        p = int(el.findtext("Note/pitch"))
                        meas[mi][sid].append([tick, [p], d])
                    tick += d

# ---------- string/fret mapping (tab row: 1=high e) ----------
STR = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}

def place_notes(pitches, strings, fmax):
    placed, dropped = {}, 0
    for p in sorted(pitches, reverse=True):
        opts = [(s, p - STR[s]) for s in strings
                if 0 <= p - STR[s] <= fmax and s not in placed]
        if not opts:
            dropped += 1
            continue
        opts.sort(key=lambda t: (abs(t[1] - 8), t[1], t[0]))
        placed[opts[0][0]] = opts[0][1]
    return placed, dropped

# ---------- build events: (mi, tick, dur, {tab_str: fret}, vel, voice_idx) ----------
eventsA, eventsB, tot_drop = [], [], 0
for mi in sorted(meas):
    for tick, ps, d in meas[mi]["1"]:            # melody: strings 1-3 (4 fallback)
        cell, dr = place_notes(ps, [1, 2, 3], 20)
        if not cell:
            cell, dr = place_notes(ps, [1, 2, 3, 4], 20)
        tot_drop += dr
        if cell:
            eventsB.append((mi, tick, d, cell, 85, 1))
            eventsA.append((mi, tick, d, cell, 85, 1))
    for tick, ps, d in meas[mi]["2"]:            # arpeggio: strings 4-6, +12st
        p2 = [p + 12 if p < 50 else p for p in ps]
        if max(p2) > 76:
            continue
        cell, dr = place_notes(p2, [4, 5, 6], 15)
        tot_drop += dr
        if cell:
            eventsA.append((mi, tick, d, cell, 55, 0))

# ---------- GP5 ----------
def build_gp5(events, title, out):
    from guitarpro.models import (Song, Measure, Beat, Note, Duration,
                                  BeatStatus, TimeSignature, NoteType)
    song = Song()
    song.title, song.tempo = title, BPM
    ts = TimeSignature(numerator=4, denominator=Duration(4))
    for _ in range(NMEAS - len(song.measureHeaders)):
        song.newMeasure()
    for mh in song.measureHeaders:
        mh.timeSignature = ts
    track = song.tracks[0]
    for _ in range(NMEAS - len(track.measures)):
        track.measures.append(Measure(track, song.measureHeaders[len(track.measures)]))

    for (mi, tick, d, cell, vel, voice_i) in events:
        voice = track.measures[mi - 1].voices[voice_i]
        t = tick
        while t < tick + d:                      # split dotted value into standard beats
            comp = next(c for c in STD if c <= d - (t - tick))
            beat = Beat(voice=voice, notes=[], duration=Duration(GP5_DUR[comp]),
                        start=(mi - 1) * TQP + t, status=BeatStatus.normal)
            for st, f in cell.items():
                beat.notes.append(Note(beat=beat, value=f, string=7 - st,
                                       velocity=vel, type=NoteType.normal))
            voice.beats.append(beat)
            t += comp
    import guitarpro
    guitarpro.write(song, out, version=(5, 1, 0))

    # ---- verify: each voice in each measure must be contiguous, sum <= 3840
    back = guitarpro.parse(out)
    nb, problems = 0, []
    for mi, m in enumerate(back.tracks[0].measures, 1):
        for vi, v in enumerate(m.voices):
            if not v.beats:
                continue
            base = (mi - 1) * TQP
            end = base
            for b in v.beats:
                if b.start < end:
                    problems.append(f"m{mi}v{vi} overlap@{b.start}")
                end = b.start + TQP // b.duration.value
                nb += len(b.notes)
            if end - base > TQP:
                problems.append(f"m{mi}v{vi} over={end - base}")
    print(f"{out}: notes={nb}, measures={len(back.tracks[0].measures)}",
          "| " + "; ".join(problems) if problems else "| timing OK (no overlap/overflow)")

build_gp5(eventsA, "Moon Represents My Heart - A (melody+arpeggio)", "out/moon_tab_A.gp5")
build_gp5(eventsB, "Moon Represents My Heart - B (melody only)", "out/moon_tab_B.gp5")

# ---------- text tab (8 eighth-note cells per measure) ----------
SECQ = 60.0 / BPM
def render(events, out, label):
    cells_per_meas = 8
    ncell = NMEAS * cells_per_meas
    grid = defaultdict(dict)
    for (mi, tick, d, cell, vel, _v) in events:
        for c in range(tick // (TQP // 2), (tick + d) // (TQP // 2)):
            if (mi - 1) * 8 + c >= ncell:
                break
            for st, f in cell.items():
                grid[(mi - 1) * 8 + c].setdefault(st, f)
    lines = []
    for block in range(0, ncell, 32):
        chunk = list(range(block, min(block + 32, ncell)))
        t0 = block * 0.25 * SECQ
        lines.append(f"[{int(t0)//60:02d}:{int(t0)%60:02d}]  " +
                     "".join(f"m{c // 8 + 1:02d}" if c % 8 == 0 else "      "
                             for c in chunk))
        for st in [1, 2, 3, 4, 5, 6]:
            lines.append(f" {st}|-|-".ljust(8) + "".join(
                f"|{grid[c][st]:4d}|" if st in grid[c] else "|    |" for c in chunk))
        lines.append("")
    with open(out, "w") as f:
        f.write(f"The Moon Represents My Heart - {label}\n"
                "78bpm 4/4, 51 measures. Rows: 1(top)=high e ... 6=low e, number=fret.\n\n")
        f.write("\n".join(lines))
    print("wrote", out)

render(eventsA, "out/moon_tab_A.txt", "A: melody + arpeggio accompaniment")
render(eventsB, "out/moon_tab_B.txt", "B: melody only")
print(f"events A={len(eventsA)} B={len(eventsB)}  dropped notes={tot_drop}")
