#!/usr/bin/env python3
"""Split landscape spreads into per-page JPEGs (trim ~1% gutter each half).
Usage: prep_pages.py <src_png_dir> <start> <end_incl> <out_jpg_dir> [width]
"""
import os, sys
from PIL import Image

SRC, START, END, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
WIDTH = int(sys.argv[5]) if len(sys.argv) > 5 else 1200
os.makedirs(OUT, exist_ok=True)

seq = 0
for n in range(START, END + 1):
    p = os.path.join(SRC, f"{n:03d}.png")
    if not os.path.exists(p):
        print(f"skip (missing) {p}")
        continue
    im = Image.open(p).convert("RGB")
    w, h = im.size
    if w > h:  # landscape spread -> two pages
        gx = max(1, int(w * 0.01))
        mid = w // 2
        for box in [(0, 0, mid - gx, h), (mid + gx, 0, w, h)]:
            half = im.crop(box)
            nw, nh = WIDTH, max(1, round(h * WIDTH / (mid - gx)))
            half = half.resize((nw, nh), Image.LANCZOS)
            out = os.path.join(OUT, f"{seq:03d}.jpg")
            half.save(out, "JPEG", quality=88)
            seq += 1
    else:  # portrait sheet -> single page
        nw, nh = WIDTH, max(1, round(h * WIDTH / w))
        out = os.path.join(OUT, f"{seq:03d}.jpg")
        im.resize((nw, nh), Image.LANCZOS).save(out, "JPEG", quality=88)
        seq += 1
print(f"PREP_DONE seq=0..{seq-1}")
