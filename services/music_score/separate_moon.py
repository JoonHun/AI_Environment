"""demucs htdemucs_6s stem separation + user-requested mixdowns.

Steps (each saved, intermediates kept):
  1. 6 stems: drums / bass / other / acoustic_guitar / electric_guitar / piano
  2. no_drums.wav       = original - drums
  3. no_drums_no_bass.wav = no_drums - bass
  4. guitar_only.wav    = electric_guitar stem (guitar alone)
"""
import time, subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import torch as th

HERE = Path("/home/joons/.hermes/services/music_score")
SRC = HERE / "source_moon.wav"
FFMPEG = "/home/joons/.hermes/tools/ffmpeg-9.0.1-linux-arm64/bin/ffmpeg"

from demucs.apply import apply_model
from demucs.pretrained import get_model

device = "cuda" if th.cuda.is_available() else "cpu"
print("device:", device, flush=True)
model = get_model("htdemucs_6s")
model.to(device).eval()

# 44.1kHz stereo wav (already is, but enforce)
wav_path = HERE / "input_44k.wav"
subprocess.run([FFMPEG, "-y", "-i", str(SRC), "-ar", "44100", "-ac", "2",
                str(wav_path)], check=True, capture_output=True)
arr, sr = sf.read(wav_path, dtype="float32")
if arr.ndim == 1:
    arr = np.stack([arr, arr], axis=1)
wav = th.from_numpy(arr).t().contiguous()
print("audio:", tuple(wav.shape), sr, "Hz", flush=True)

t0 = time.time()
with th.no_grad():
    sources = apply_model(model, wav[None].to(device), device=device,
                          shifts=1, split=True, overlap=0.25, progress=True)
print(f"separation done in {time.time()-t0:.1f}s", flush=True)

names = list(model.sources)
print("stems:", names, flush=True)
stems = {}
for i, name in enumerate(names):
    s = sources[0][i].cpu().numpy().T          # (T, 2)
    stems[name] = s
    p = HERE / f"stem_{name}.wav"
    sf.write(str(p), s, sr)
    print("wrote", p, flush=True)

def save(name, arr2d):
    p = HERE / name
    sf.write(str(p), arr2d, sr)
    print("wrote", p, flush=True)

drums = stems["drums"]
bass = stems["bass"]

# step 2: drums removed (reconstruct from all stems except drums)
no_drums = sum(stems[n] for n in names if n != "drums")
save("step2_no_drums.wav", np.ascontiguousarray(no_drums, dtype=np.float32))

# step 3: drums AND bass removed
no_d_no_b = sum(stems[n] for n in names
                if n not in ("drums", "bass"))
save("step3_no_drums_no_bass.wav",
     np.ascontiguousarray(no_d_no_b, dtype=np.float32))

# step 4: guitar only (electric guitar stem)
save("step4_guitar_only.wav", stems["electric_guitar"].astype(np.float32))

print("ALL DONE", flush=True)
