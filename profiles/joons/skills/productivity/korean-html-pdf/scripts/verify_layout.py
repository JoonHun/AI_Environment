#!/usr/bin/env python3
"""Verify a rendered Korean/CJK PDF: page count, tofu, CJK leak, answer-box heights.

Usage: verify_layout.py <file.pdf> [min_box_pt]

Prints per-page tall drawn-rect heights (the .sa-space answer boxes). If a page
that SHOULD have an answer box shows no rect in the expected band, a CSS selector
is wrong (sibling vs descendant) and the box did not actually get min-height.
Exit 0 if tofu==0 and no CJK leak; 1 otherwise.
"""
import re
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: verify_layout.py <file.pdf> [min_box_pt]", file=sys.stderr)
        return 2
    path = sys.argv[1]
    min_box = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0

    try:
        import pymupdf  # noqa: F401
    except ModuleNotFoundError:
        sys.exit("pymupdf not available in this interpreter")

    doc = pymupdf.open(path)
    print(f"pages: {doc.page_count}")

    full = "".join(doc[i].get_text() for i in range(doc.page_count))
    tofu = full.count("\ufffd")
    cjk = sorted(set(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf]", full)))
    print(f"tofu: {tofu}")
    print(f"cjk_leak: {''.join(cjk) if cjk else 'None'}")

    for i in range(doc.page_count):
        pg = doc[i]
        hs = sorted(
            {
                round(d["rect"].height, 1)
                for d in pg.get_drawings()
                if d["rect"].width > 380 and d["rect"].height > min_box
            },
            reverse=True,
        )
        nums = re.findall(r"(?<!\d)(2[1-5])\.", pg.get_text())
        if hs or nums:
            print(f"  page {i + 1}: boxes={hs} subj_nums={sorted(set(nums))}")

    ok = tofu == 0 and not cjk
    print("RESULT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
