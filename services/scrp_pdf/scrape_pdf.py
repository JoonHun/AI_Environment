#!/usr/bin/env python3
"""Fetch all 167 page renders from StreamDocs and assemble into a single PDF via img2pdf."""
import io, os, sys, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import img2pdf

BASE = "https://view.chunjae.co.kr/streamdocs/v4/documents/Bg15FHYoXyKEheqrLbIL5FtYY7OomHoAYFmtAJP7vAk"
PAGES = 167
ZOOM  = 200
WORKERS = 8
WORK = "/tmp/pages"
os.makedirs(WORK, exist_ok=True)
OUT_PDF = "/home/joons/중학수학2_교과서.pdf"

def fetch(n, retries=3):
    url = f"{BASE}/renderings/{n}?zoom={ZOOM}&jpegQuality=optional"
    out = f"{WORK}/{n:03d}.png"
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return (n, os.path.getsize(out))
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            d = urllib.request.urlopen(req, timeout=90).read()
            if not d:
                raise RuntimeError("empty body")
            if d[0] == 1 and d[1:4] == b'PNG':
                d = bytes([0x89]) + d[1:]
            tmp = out + ".part"
            with open(tmp, "wb") as f:
                f.write(d)
            os.replace(tmp, out)
            return (n, len(d))
        except Exception as e:
            last = e
            time.sleep(1 + attempt * 2)
    return (n, None)

t0 = time.time()
ok = fail = 0
fails = []
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futs = [ex.submit(fetch, n) for n in range(PAGES)]
    for i, f in enumerate(as_completed(futs), 1):
        n, sz = f.result()
        if sz is None:
            fail += 1
            fails.append(n)
            print(f"  FAIL p{n}", flush=True)
        else:
            ok += 1
            if i % 25 == 0 or i == PAGES:
                print(f"  fetched {i}/{PAGES} (ok={ok} fail={fail})", flush=True)
print(f"fetch phase {time.time()-t0:.1f}s  ok={ok} fail={fail} fails={fails}", flush=True)
if fails:
    sys.exit(1)

# Assemble
files = [f"{WORK}/{n:03d}.png" for n in range(PAGES)]
for p in files:
    if not os.path.exists(p) or os.path.getsize(p) < 5000:
        print("MISSING file:", p, flush=True); sys.exit(1)

t1 = time.time()
data = img2pdf.convert(files)
with open(OUT_PDF, "wb") as f:
    f.write(data)
sz = os.path.getsize(OUT_PDF)
print(f"\nPDF OK  {OUT_PDF}")
print(f"  pages={PAGES}  size={sz/1024/1024:.1f} MB  assemble={time.time()-t1:.1f}s")
