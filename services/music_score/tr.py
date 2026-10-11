"""Transcribe a wav with basic-pitch -> MIDI. Usage: tr.py IN.wav OUT.mid"""
import sys, time
from basic_pitch.inference import predict
mid_out = sys.argv[2]
t0 = time.time()
model_output, midi_data, note_events = predict(sys.argv[1])
midi_data.write(mid_out)
mid = midi_data
total = sum(len(i.notes) for i in mid.instruments)
print(f"{sys.argv[1]}: {total} notes, dur {mid.get_end_time():.1f}s, "
      f"{time.time()-t0:.1f}s", flush=True)
