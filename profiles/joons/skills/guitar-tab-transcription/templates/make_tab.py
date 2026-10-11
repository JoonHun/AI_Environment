"""MIDI (basic-pitch) -> Electric Guitar TAB: text tab + Guitar Pro 5 (.gp5).
Onset-based chord clustering + energy filter + lead-line tracking +
power-chord-aware mapping.

Usage: make_tab.py MID [BPM] [OUT_TXT] [OUT_GP5] [T_START] [T_END] [FRACTION]
  T_START/T_END  optional time window in seconds — rewrite only that region
                 (e.g. the intro riff); name outputs with a _01/_02 version
                 suffix per attempt and never overwrite earlier versions.
  FRACTION       energy-filter aggressiveness; default 0.10. 0.30 cuts real
                 quiet riff notes — lower it when the user reports missing notes.
Expects a .mid from basic_pitch.inference.predict() -> midi_data.write(...).

Pipeline stages (each report its effect):
  1. guitar-range filter (E2..E6)
  2. time-window trim (optional) — recompute dur from surviving notes
  3. energy filter: drop weakest FRACTION by velocity (stem residual noise)
  4. onset clustering within CHORD_WIN
  5. lead tracking: strongest note/cluster, jumps > LEAD_JUMP need v >= LEAD_VEL
  6. place: 1 power chord/cluster (7-semitone pair, compact shape) + lead note
     on a high string; every other pitch is dropped
"""
import sys, collections
from pathlib import Path
import numpy as np
import pretty_midi as pm

MID = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/out.mid")
BPM = int(sys.argv[2]) if len(sys.argv) > 2 else 120
TXT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("out/guitar_tab.txt")
GP5 = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("out/guitar_tab.gp5")
T_START = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
T_END = float(sys.argv[6]) if len(sys.argv) > 6 else float("inf")

# ---- knobs ----
LO, HI = 40, 84      # E2..E6
FRACTION = float(sys.argv[7]) if len(sys.argv) > 7 else 0.10   # 0.30 drops real notes
CHORD_WIN = 0.15     # onset cluster window (s)
LEAD_JUMP = 12       # max lead-line step (semitones)
LEAD_VEL = 75        # velocity floor to accept a jump beyond LEAD_JUMP
CELL = 0.5           # display grid (s)

# ---- load + filter ----
mid = pm.PrettyMIDI(MID)
raw = [(n.start, n.end, n.pitch, n.velocity or 64)
       for inst in mid.instruments for n in inst.notes]
raw = [r for r in raw if LO <= r[2] <= HI]
raw.sort(key=lambda x: (x[0], -x[3], x[2]))
dur = mid.get_end_time()
print(f"notes (guitar range): {len(raw)}  dur {dur:.1f}s")

# ---- optional time-window trim (region rewrites, e.g. intro riff) ----
if T_START > 0 or T_END != float("inf"):
    before = len(raw)
    raw = [r for r in raw if r[0] >= T_START and r[1] <= T_END]
    dur = max((e for (_, e, _, _) in raw), default=0.0)
    print(f"trim [{T_START}, {T_END if T_END != float('inf') else 'end'}]: "
          f"{before} -> {len(raw)} notes")

# ---- energy filter ----
if raw:
    vels = np.array([v for (_, _, _, v) in raw], dtype=float)
    thresh = float(np.percentile(vels, 100.0 * FRACTION))
    before = len(raw)
    raw = [r for r in raw if r[3] >= thresh]
    print(f"energy filter: dropped {before - len(raw)} below vel {thresh:.1f} -> {len(raw)} remain")

# ---- string / fret mapping (tab convention: string 1 = high e) ----
STR = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}
LOWS = [6, 5, 4, 3, 2, 1]
def cands(p):
    return [(s, p - STR[s]) for s in LOWS if 0 <= p - STR[s] <= 24]

def pc_shapes(r, fiv):
    """(string_root, string_fifth, fret_root, fret_fifth) for a 5th: smallest
    fret offset first, then lowest strings. Same fret on adjacent strings is a
    4th, never a 5th — offset-0 combos are not real power chords."""
    best = None
    for (sa, fa) in cands(r):
        for (sb, fb) in cands(fiv):
            if sa == sb:
                continue
            key = (abs(fa - fb), sa, sb)
            if best is None or key < best[0]:
                best = (key, (sa, sb, fa, fb))
    return [best[1]] if best else []

# ---- onset clusters ----
clusters = []
for r in raw:
    s = r[0]
    if clusters and s - clusters[-1][0] <= CHORD_WIN:
        clusters[-1][1].append(r)
    else:
        clusters.append([s, [r]])
print(f"onset clusters: {len(clusters)}")

# ---- lead line tracking ----
lead = {}
last = None
for t0, notes in clusters:
    p, v = max(notes, key=lambda n: n[3])[2:4]
    if last is not None and abs(p - last) > LEAD_JUMP and v < LEAD_VEL:
        continue
    lead[t0] = (p, v)
    last = p
print(f"lead notes: {len(lead)}")

# ---- place each cluster ----
placed_clusters = []
pc_count = 0
for t0, notes in clusters:
    byp = {}
    for (s, e, p, v) in notes:
        if p not in byp or v > byp[p][3]:
            byp[p] = (s, e, p, v)
    pitches = sorted(byp.keys())
    placed, bound = {}, set()
    # pass 1: one power chord (lowest root with a +7 partner)
    for p in pitches:
        if p in bound or (p + 7) not in pitches:
            continue
        for (sa, sb, fa, fb) in pc_shapes(p, p + 7):
            if sa not in placed and sb not in placed:
                placed[sa] = fa; placed[sb] = fb
                bound.add(p); bound.add(p + 7)
                pc_count += 1
                break
        break
    # pass 2: lead note on a high string, low fret (skip if the PC voiced it)
    if t0 in lead:
        p_lead, _ = lead[t0]
        if p_lead not in bound:
            for (s, f) in sorted(cands(p_lead),
                                 key=lambda t: (0 if 1 <= t[0] <= 3 else 1, t[1])):
                if s not in placed:
                    placed[s] = f
                    break
    # remaining pitches dropped (background noise)
    if placed:
        placed_clusters.append((t0, placed))
print(f"placed clusters: {len(placed_clusters)}  power chords: {pc_count}")

# ---- display grid ----
ncell = int(dur // CELL) + 1
grid = collections.defaultdict(dict)
for t0, placed in placed_clusters:
    grid[int(t0 // CELL)] = placed

# ---- text tab (30-cell / 15s blocks, 6-char fixed cells) ----
STR_LABELS = [1, 2, 3, 4, 5, 6]   # row top = string 1 (high e)
PER_LINE = 30
def header_cell(c):
    t = f"{int(c*CELL)//60:02d}:{int(c*CELL)%60:02d}" if c % 4 == 0 else ""
    return t.ljust(6)
lines = []
for block in range(0, ncell, PER_LINE):
    chunk = list(range(block, min(block + PER_LINE, ncell)))
    start_sec = int(block * CELL)
    lines.append(f"[{start_sec//60:02d}:{start_sec%60:02d}]  "
                 + "".join(header_cell(c) for c in chunk).rstrip())
    for st in STR_LABELS:
        cells = "".join(f"|{grid[c][st]:4d}|" if grid[c].get(st) is not None
                        else "|    |" for c in chunk)
        lines.append(f" {st}|-|-".ljust(8) + cells)
    lines.append("")
TXT.write_text(
    f"Electric Guitar TAB (auto)  |  {MID.name}  |  len {dur:.1f}s  |  {pc_count} power chords\n"
    "Rows: string 1(top)=highE ... 6=lowE. Number=fret, blank=rest.\n"
    "Lead line = tracked melody (high strings); power chord = root+fifth shape.\n"
    "NOTE: auto-transcribed -> approximate, verify by ear.\n\n"
    + "\n".join(lines), encoding="utf-8")
print("wrote", TXT)

# ---- GP5 ----
def build_gp5():
    from guitarpro.models import (Song, Measure, Beat, Note, Duration,
                                  BeatStatus, TimeSignature, NoteType)
    song = Song()
    song.title = "Auto Tab (basic-pitch)"
    song.tempo = BPM
    track = song.tracks[0]
    ts = TimeSignature(numerator=4, denominator=Duration(4))   # instances!
    TICKS_PER_QUARTER = 960
    cells_per_meas = int((60.0 / BPM) * 4 / CELL)
    nmeas = int(dur / (cells_per_meas * CELL)) + 2
    ticks_per_cell = int(CELL / (60.0 / BPM)) * TICKS_PER_QUARTER
    while len(song.measureHeaders) < nmeas:
        song.newMeasure()
    for mh in song.measureHeaders:
        mh.timeSignature = ts
    while len(track.measures) < nmeas:
        track.measures.append(Measure(track, song.measureHeaders[len(track.measures)]))
    for c in range(ncell):
        cells = {st: grid[c][st] for st in STR_LABELS if grid[c].get(st) is not None}
        if not cells:
            continue
        mi = c // cells_per_meas
        if mi >= len(track.measures):
            continue
        m = track.measures[mi]
        voice = m.voices[0]
        beat = Beat(voice=voice, notes=[], duration=Duration(8),
                    start=(c % cells_per_meas) * ticks_per_cell,
                    status=BeatStatus.normal)
        for st, f in cells.items():
            # GP5 string 1 = LOW E; tab labels flipped -> 7-st
            beat.notes.append(Note(beat=beat, value=f, string=7 - st,
                                   velocity=64, type=NoteType.normal))
        voice.beats.append(beat)
    return song

if __name__ == "__main__":
    import guitarpro
    song = build_gp5()
    guitarpro.write(song, str(GP5), version=(5, 1, 0))
    back = guitarpro.parse(str(GP5))
    nb = sum(len(b.notes) for m in back.tracks[0].measures
             for v in m.voices for b in v.beats)
    print(f"wrote {GP5}  (verified: notes={nb}, measures={len(back.tracks[0].measures)})")
