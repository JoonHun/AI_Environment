#!/usr/bin/env python3
"""Build a compressed (lightweight) PDF from a page-PNG dir.

Usage:  python3 compress_pdf.py <src_png_dir> <numPages> <out_pdf> [target_width] [jpeg_q]
Default: target_width=2200, jpeg_q=90  (user-approved quality).
Requires PIL + img2pdf.  Foreground python3 (system) or explicit /usr/bin/python3.
"""
import os, sys, time
from PIL import Image
import img2pdf

def main():
    SRC      = sys.argv[1]
    PAGES    = int(sys.argv[2])
    OUT      = sys.argv[3]
    TARGET_W = int(sys.argv[4]) if len(sys.argv) > 4 else 2200
    Q        = int(sys.argv[5]) if len(sys.argv) > 5 else 90
    OUT_JPG  = SRC.rstrip("/") + "_jpg"
    os.makedirs(OUT_JPG, exist_ok=True)

    t0 = time.time()
    files = []
    tot = 0
    for n in range(PAGES):
        p = f"{SRC}/{n:03d}.png"
        o = f"{OUT_JPG}/{n:03d}.jpg"
        if not (os.path.exists(o) and os.path.getsize(o) > 2000):
            with Image.open(p) as im:
                im = im.convert("RGB")
                w, h = im.size
                if w > TARGET_W:
                    im = im.resize((TARGET_W, max(1, round(h * TARGET_W / w))), Image.LANCZOS)
                im.save(o, "JPEG", quality=Q, optimize=True)
        files.append(o)
        tot += os.path.getsize(o)
        if (n + 1) % 40 == 0:
            print(f"  {n+1}/{PAGES} compressed ({tot/1024/1024:.1f} MB so far)", flush=True)
    print(f"images ready: {tot/1024/1024:.1f} MB in {time.time()-t0:.1f}s", flush=True)

    t1 = time.time()
    data = img2pdf.convert(files)
    with open(OUT, "wb") as f:
        f.write(data)
    print(f"PDF OK: {OUT}  {os.path.getsize(OUT)/1024/1024:.1f} MB  (assemble {time.time()-t1:.1f}s)")

if __name__ == "__main__":
    main()
