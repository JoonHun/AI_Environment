#!/usr/bin/env python3
"""Fetch all page-render PNGs for a StreamDocs doc.

Usage:  python3 fetch_pages.py <docId> <numPages> <workdir>
Stdlib only — safe to run from any PATH (no third-party deps).
Resumable: existing non-trivial PNGs are skipped.
"""
import os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

def main():
    docId   = sys.argv[1]
    PAGES   = int(sys.argv[2])
    WORK    = sys.argv[3]
    WORKERS = 8
    ZOOM    = 200
    BASE    = f"https://view.chunjae.co.kr/streamdocs/v4/documents/{docId}"
    os.makedirs(WORK, exist_ok=True)

    def fetch(n, retries=5):
        path = f"{WORK}/{n:03d}.png"
        if os.path.exists(path) and os.path.getsize(path) > 5000:
            return (n, os.path.getsize(path))
        url = f"{BASE}/renderings/{n}?zoom={ZOOM}&jpegQuality=optional"
        last = None
        for a in range(retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                d = urllib.request.urlopen(req, timeout=120).read()
                if not d: raise RuntimeError("empty body")
                if d[0] == 1 and d[1:4] == b'PNG':
                    d = bytes([0x89]) + d[1:]   # server mangles PNG magic first byte
                tmp = path + ".part"
                with open(tmp, "wb") as f: f.write(d)
                os.replace(tmp, path)
                return (n, len(d))
            except Exception as e:
                last = e
                time.sleep(1 + a * 2)
        return (n, None, repr(last))

    t0 = time.time(); ok = fail = 0; fails = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, f in enumerate(as_completed([ex.submit(fetch, n) for n in range(PAGES)]), 1):
            r = f.result()
            if r[1] is None:
                fail += 1; fails.append(r); print(f"  FAIL p{r[0]}: {r[2]}", flush=True)
            else:
                ok += 1
            if i % 20 == 0 or i == PAGES:
                print(f"  fetch {i}/{PAGES} ok={ok} fail={fail}", flush=True)
    print(f"FETCH_DONE {time.time()-t0:.1f}s ok={ok} fail={fail}", flush=True)
    if fails:
        print("FAILURES:", fails, flush=True)
        sys.exit(1)
    print("ALL_FETCHED", flush=True)

if __name__ == "__main__":
    main()
