"""Measure BPM from the guitar stem (librosa beat_track)."""
import numpy as np, soundfile as sf, librosa
arr, sr = sf.read("/home/joons/.hermes/services/music_score/stem_guitar.wav")
y = arr.mean(axis=1) if arr.ndim == 2 else arr
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
t = tempo if np.ndim(tempo) == 0 else tempo[0]
print(f"BPM ~ {t:.1f}")
