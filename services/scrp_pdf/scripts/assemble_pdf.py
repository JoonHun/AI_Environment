#!/usr/bin/env python3
"""Assemble page PNGs into a single high-quality PDF (no compression)."""
import os, sys, time
import img2pdf

def main():
    work  = sys.argv[1]   # dir with 000.png..
    pages = int(sys.argv[2])
    out   = sys.argv[3]

    files = [os.path.join(work, f"{n:03d}.png") for n in range(pages)]
    missing = [p for p in files if not (os.path.exists(p) and os.path.getsize(p) > 5000)]
    if missing:
        print("MISSING:", missing[:5], "..."); sys.exit(1)

    t0 = time.time()
    data = img2pdf.convert(files)
    with open(out, "wb") as f:
        f.write(data)
    print(f"PDF OK {out} {os.path.getsize(out)/1024/1024:.1f} MB ({time.time()-t0:.1f}s)")

if __name__ == "__main__":
    main()
