# Score PDF → TAB via vision (GB10)

For when the user's input is a SCORE (staff notation) PDF and the deliverable is a TAB. Vision backend: gemma4-26b-a4b-mtp-q4_k_m with mmproj via the llama.cpp proxy on 11536 (config `auxiliary.vision` → custom provider, base_url `http://192.168.219.115:11536/v1`). Do NOT route score vision through Ollama — the user explicitly moved off it.

## 1. Diagnose the PDF first (2 min, saves an hour)

```bash
pdfinfo in.pdf          # page count, size
pdfimages -list in.pdf  # embedded images + their real dpi
pdffonts in.pdf         # fonts present?
pdftotext in.pdf -      # text layer?
```

| Result | Type | Consequence |
|---|---|---|
| No images, fonts present | vector | render at 300dpi, crisp forever |
| 1 full-page image/page, ~100dpi | scan (low) | capped at source dpi — 300dpi render is interpolation, adds NOTHING |
| 1 full-page image, ≥200-300dpi | scan (good) | transcribe the 300dpi render directly |

**Low-dpi scan → find a vector copy first.** Search the exact title + arranger (e.g. `"Clear Liu Piano Cover" 月亮代表我的心 MuseScore`) — MuseScore hosts vector PDFs of most YouTube piano covers, often mirrored on static hosts (download with `curl -L`, re-check with `pdfimages -list`: zero images + fonts = vector). Verify it's the same arrangement by pages/measures/key before transcribing.

Why this matters: on a 103dpi scan the model's outputs are not just noisy — the same image read in one session produced 4 different readings of measure 1, and measures with beat totals exceeding the meter (11 eighths in 4/4) appear. That is hallucination from missing pixels; no prompt fixes it.

## 2. Render + crop (vector source)

```bash
pdftoppm -png -r 300 in.pdf out   # 2550x3300 per A4 page
```

Then crop per **grand-staff system** (row-profile of dark pixels; bands where >~8% of the row is dark, merge gaps <60px, 30px padding): page 1 of a 2-page score typically gives a thin title band + 4-5 systems, page 2 gives 4-5 systems.

**Size gate (hard, backend-dependent):** each image sent to the vision model must stay **under ~1MP** (width×height). The GB10 gemma4 mmproj backend crashes (`mtmd_helper_decode_image_chunk` abort → "Remote end closed connection without response", service goes inactive) at ~1.24MP (2550×486) while 1.02MP (1652×618) and 0.62MP (1275×486) survive. So split each system at its barline into left/right halves (~1275×500 each) when a system is wider than ~1MP. Check with `PIL` before the batch: `w*h > 950_000 → split`.

Faint-scan enhancement (only if you must transcribe the scan): contrast stretch `np.clip((a-30)*255/140, 0, 255)` then 2× upscale, then the same size gate (the 2× pushes most systems over 1MP — split first, enhance the halves).

## 3. Transcribe

Probe script: `scripts/vision_test.py <image> "<prompt>"` — base64-encodes the image and POSTs to `127.0.0.1:11536/v1/chat/completions` with a 590s timeout; prints `ERR: …` on failure (batch scripts grep for `^ERR`). One image ≈ 3-4 min at this backend — run the batch in the BACKGROUND with notify, never a foreground loop (a 2-image sequential probe already exceeds the 420s terminal timeout).

Working prompt (Korean, strict format, hallucination guard):

```
이 악보 조각을 전사. 형식: 마디N: T: <트레블> | B: <베이스>.
음표: 음이름+옥타브+길이 (G4.8=8분, C5.4=4분, G4.2=2분, A4.4d=4분부점, r8/r4/r2=쉼, < > = 오토).
실제로 보이는 것만, 불확실하면 (?). 설명 없이 전사만.
```

Batch pattern: bash loop over the sorted crop list, 3 attempts with `sleep 15` between, output appended to one .txt with `===== file =====` headers. Left half before right half per system; page 1 fully before page 2.

## 4. QA before converting to tab

- **Beat arithmetic**: every measure must sum to the meter (4/4 → 4 beats; 8th=0.5, 4th=1, dotted-4th=1.5, 2nd=2, whole=4, rX = rest). A measure over the meter = hallucinated run — re-crop that region larger or drop it, don't average it in.
- **Double-read agreement**: re-read one system once and diff the note names; systematic disagreement = resolution problem (go get the vector source), not a prompt problem.
- **Continuity across halves**: the right half's first measure must continue the left half's last (same system) — renumber measures globally (page1 sys1 = m1..m4, sys2 = m5..m8, …) before merging; per-crop numbering restarts at 1 and is unusable raw.
- After QA, the merged transcription is just a note list → feed it to the normal `make_tab.py` stage (string mapping, power chords) with the score's real key/tempo (read them from the first system: key signature + tempo marking).

## Pitfalls
- Equal-fraction page strips cut staff lines → invented notes. Always system-crop (row profile), never `h/4` slices.
- 300dpi rendering of a low-dpi scan is a no-op for quality — the user will ask "it's not even a bad-quality PDF, what's the problem"; the answer is the embedded-image dpi, shown by `pdfimages -list`.
- `pkill -f "ollama serve"` kills your own shell (the pattern matches the pkill command line itself) — use `pkill -f "[o]llama serve"` or match the exact process name.
- The proxy (11536) wakes the backend on demand; a cold first image request can take a minute — don't treat the first slow response as a crash. Distinguish: crash = connection RESET + `systemctl --user is-active llama-server-gemma` → inactive; slowness = connection stays open.
- vision_analyze in this profile routes to the configured auxiliary.vision (11536) — fine, but the raw probe script gives you stderr/timeout control for batches; use it for anything scripted.

## Validated state (2026-09)
Diagnosis, vector-source replacement, size gate, system-cropping, and per-crop transcription all validated on a 2-page/51-measure C-major piano cover. End-to-end (merged transcription → make_tab.py → .gp5/.txt) not yet exercised — the QA step is where this path is unproven.
