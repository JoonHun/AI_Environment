#!/usr/bin/env python
"""Direct probe of the GB10 gemma4 vision backend (llama.cpp proxy 11536).
Usage: vision_test.py <image.png> "<question>"
Prints the model's answer, or 'ERR: …' on failure (batch scripts grep ^ERR).
Keep images under ~1MP or the mmproj backend crashes (see references/vision-score-transcription.md).
"""
import base64
import json
import sys
import urllib.request

MODEL = "gemma4-26b-a4b-mtp-q4_k_m"
URL = "http://127.0.0.1:11536/v1/chat/completions"


def main():
    img = base64.b64encode(open(sys.argv[1], "rb").read()).decode()
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": sys.argv[2]},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
        ]}],
        "max_tokens": 2048,
    }).encode()
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=590) as r:
            print(json.load(r)["choices"][0]["message"]["content"])
    except Exception as e:  # noqa: BLE001 - batch scripts key off the ERR prefix
        print(f"ERR: {e}")


if __name__ == "__main__":
    main()
