"""Detect grand-staff systems in faint 200dpi scan."""
import numpy as np
from PIL import Image

for pg in (1, 2):
    im = Image.open(f"pdf2tab/d200-{pg}.png").convert("L")
    a = np.array(im)
    # staff lines: long horizontal dark runs. Count dark pixels per row.
    dark = (a < 160).sum(axis=1)
    W = a.shape[1]
    rows = np.where(dark > W * 0.25)[0]
    # cluster consecutive
    lines = []
    if len(rows):
        start = prev = rows[0]
        for r in rows[1:]:
            if r - prev > 4:
                lines.append((start + prev) // 2)
                start = r
            prev = r
        lines.append((start + prev) // 2)
    print(f"page {pg}: {len(lines)} candidate lines: {lines}")
    # group 5-line staves
    staves = []
    i = 0
    while i < len(lines):
        grp = [lines[i]]
        while i + len(grp) < len(lines) and (lines[i + len(grp)] - lines[i + len(grp) - 1]) < 35:
            grp.append(lines[i + len(grp)])
            if len(grp) == 5:
                break
        if len(grp) == 5:
            staves.append((grp[0], grp[-1]))
            i += 5
        else:
            i += 1
    systems = []
    i = 0
    while i < len(staves):
        if i + 1 < len(staves) and 25 < staves[i + 1][0] - staves[i][1] < 130:
            systems.append((staves[i][0], staves[i + 1][1]))
            i += 2
        else:
            systems.append((staves[i][0], staves[i][1]))
            i += 1
    print(f"page {pg}: {len(staves)} staves, {len(systems)} systems")
    for n, (y0, y1) in enumerate(systems):
        pad = 25
        c = Image.open(f"pdf2tab/d200-{pg}.png").crop((0, max(0, y0 - pad), im.width, min(im.height, y1 + pad)))
        c.save(f"pdf2tab/sys{pg}_{n}.png")
        print(f"  sys{pg}_{n}.png y={y0}-{y1} h={c.size[1]}")
