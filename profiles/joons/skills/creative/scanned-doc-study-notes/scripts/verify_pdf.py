#!/usr/bin/env python3
"""Verify a rendered study-note PDF: page count, first-page title, tofu, foreign-script
bleed, and required keyword presence.

Usage (run with the project venv python that has pymupdf):
    python verify_pdf.py OUT.pdf "EXPECTED_FIRST_PAGE_TITLE" KWD1 KWD2 ...

Exit code is 0 only if title present, tofu==0, no foreign script, and every keyword found.
"""
import sys
import re

import pymupdf

FOREIGN = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff\u3400-\u4dbf]')


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: verify_pdf.py OUT.pdf TITLE [KWD ...]", file=sys.stderr)
        return 2
    path, title = sys.argv[1], sys.argv[2]
    keywords = sys.argv[3:]

    doc = pymupdf.open(path)
    first = doc[0].get_text() if doc else ""
    full = "".join(pg.get_text() for pg in doc)

    ok = True

    npages = len(doc)
    print(f"pages            : {npages}")

    title_ok = title in first
    ok &amp;= title_ok
    print(f"title '{title}': {'OK' if title_ok else 'MISS'}")

    tofu = full.count("\uFFFD")
    ok &amp;= (tofu == 0)
    print(f"tofu             : {tofu}  {'OK' if tofu == 0 else 'FAIL'}")

    cjk = FOREIGN.findall(full)
    cjk_ok = not cjk
    ok &amp;= cjk_ok
    print("foreign script   :", "NONE" if cjk_ok else "".join(sorted(set(cjk))))

    for kw in keywords:
        kw_ok = kw in full
        ok &amp;= kw_ok
        print(f"  keyword {kw}: {'OK' if kw_ok else 'MISS'}")

    print("RESULT           : " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
