#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5장 요약용: 페이지 이미지 → gemma4 비전 API로 텍스트 추출"""
import base64, json, sys, urllib.request

API = "http://127.0.0.1:1536/v1/chat/completions"
MODEL = "gemma4-26b-a4b-mtp-q4_k_m"
PAGES = "/home/joons/.hermes/services/scrp_pdf/out/수학2/work/pages"

def vision(page, prompt, timeout=300):
    import subprocess, tempfile
    png = f"{PAGES}/{page:03d}.png"
    jpg = f"/tmp/vpage_{page:03d}.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", png,
                    "-vf", "scale=1280:-1", jpg], check=True)
    with open(jpg, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]}],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    req = urllib.request.Request(API, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]

if __name__ == "__main__":
    args = sys.argv[1:]
    prompt = "이 페이지의 내용을 한국어로 상세히 전사해줘."
    if args and not args[-1].lstrip("-").isdigit():
        prompt = args[-1]
        args = args[:-1]
    pages = [int(x) for x in args]
    for p in pages:
        print(f"===== PAGE {p} =====")
        try:
            print(vision(p, prompt))
        except Exception as e:
            print(f"ERROR: {e}")
        sys.stdout.flush()
