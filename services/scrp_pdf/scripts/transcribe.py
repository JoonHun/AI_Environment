#!/usr/bin/env python3
"""Transcribe a page JPEG with local gemma4-26b-a4b vision (llama.cpp 11540).
Usage: transcribe.py <image_path> [prompt]

llama.cpp OpenAI-compatible API. gemma4-26b is a reasoning model —
the transcription lands in `reasoning_content`, not `content`.
"""
import base64, json, sys, urllib.request, time

URL = "http://127.0.0.1:11540/v1/chat/completions"
MODEL = "gemma4-26b"
DEFAULT_PROMPT = (
    "Transcribe ALL text in this Korean middle-school textbook page, exactly, line by line. "
    "Include unit names, sub-unit names, concept explanations, problems, figures. "
    "Describe figures/diagrams as [Fig: ...] in one line. "
    "Keep formulas, units, numbers as-is. No omissions. "
    "Output ONLY the transcribed text, no commentary, no markdown formatting."
)

def main():
    img = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PROMPT
    b64 = base64.b64encode(open(img, "rb").read()).decode()
    body = json.dumps({
        "model": MODEL,
        "temperature": 0.1,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}},
        ]}],
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=900))
    except urllib.error.HTTPError as e:
        print(f"[transcribe {img} HTTP {e.code}]", file=sys.stderr)
        print(e.read().decode(errors="replace")[:500], file=sys.stderr)
        sys.exit(1)
    m = r["choices"][0]["message"]
    # reasoning model: result in reasoning_content; fallback to content
    text = (m.get("reasoning_content") or "").strip() or (m.get("content") or "").strip()
    if not text:
        print(f"[transcribe {img} EMPTY]", file=sys.stderr)
        sys.exit(1)
    print(text)

if __name__ == "__main__":
    main()
