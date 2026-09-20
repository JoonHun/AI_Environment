#!/usr/bin/env python3
"""Batch transcribe chapter spreads with llama.cpp vision (11540).
Resumable: skips spreads already present in output file.
Usage: transcribe_batch.py <src_png_dir> <start> <end_incl> <out_txt>
"""
import base64, json, sys, urllib.request, time, os

URL = "http://127.0.0.1:11540/v1/chat/completions"
MODEL = "gemma4-26b"
PROMPT = (
    "Transcribe ALL text in this Korean middle-school textbook spread (two pages), exactly, line by line. "
    "Include unit names, sub-unit names, concept explanations, problems, figures. "
    "Describe figures/diagrams as [Fig: ...] in one line. "
    "Keep formulas, units, numbers as-is. No omissions. "
    "Output ONLY the transcribed text, no commentary, no markdown formatting."
)

def transcribe(img, max_tokens=2000, timeout=900):
    b64 = base64.b64encode(open(img, "rb").read()).decode()
    body = json.dumps({
        "model": MODEL, "temperature": 0.1, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
        ]}],
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=timeout))
    m = r["choices"][0]["message"]
    return (m.get("reasoning_content") or "").strip() or (m.get("content") or "").strip()

def main():
    SRC, START, END, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    SPREADS = list(range(START, END + 1))

    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                if line.startswith("===== spread "):
                    try: done.add(int(line.split()[2].rstrip("=")))
                    except: pass

    t0 = time.time()
    with open(OUT, "a", encoding="utf-8") as out:
        for s in SPREADS:
            if s in done:
                continue
            p = os.path.join(SRC, f"{s:03d}.png")
            ok = False
            for attempt in range(3):
                try:
                    txt = transcribe(p)
                    if len(txt) < 20:
                        raise ValueError(f"too short: {len(txt)}")
                    out.write(f"===== spread {s} =====\n{txt}\n\n")
                    out.flush()
                    print(f"[{s}] OK {len(txt)}ch ({time.time()-t0:.0f}s)", flush=True)
                    ok = True
                    break
                except Exception as e:
                    print(f"[{s}] attempt{attempt+1} FAIL: {e}", flush=True)
                    time.sleep(3)
            if not ok:
                out.write(f"===== spread {s} =====\n[TRANSCRIBE_FAILED]\n\n")
                out.flush()
                print(f"[{s}] GIVING UP", flush=True)
    print(f"DONE total {time.time()-t0:.0f}s", flush=True)
    with open(OUT, encoding="utf-8") as f:
        print("lines:", sum(1 for _ in f))

if __name__ == "__main__":
    main()
