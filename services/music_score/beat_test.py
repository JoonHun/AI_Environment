from guitarpro.models import Song, Beat, Note, Duration, BeatStatus
import guitarpro
s = Song(); s.newMeasure()
m = s.tracks[0].measures[-1]
for st, start in [(4, 0), (4, 3840), (2, 1920)]:
    b = Beat(voice=m.voices[0], notes=[Note(beat=None, value=5, string=6)],
             duration=Duration(st), start=start, status=BeatStatus.normal)
    m.voices[0].beats.append(b)
guitarpro.write(s, "/tmp/t.gp5", version=(5, 1, 0))
back = guitarpro.parse("/tmp/t.gp5")
with open("/tmp/beat_result.txt", "w") as fh:
    for b in back.tracks[0].measures[0].voices[0].beats:
        fh.write(f"start={b.start} dur={b.duration.value}\n")
