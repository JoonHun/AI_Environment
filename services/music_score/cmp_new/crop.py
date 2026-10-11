import sys, numpy as np
from PIL import Image
im = Image.open(sys.argv[1]).convert('L')
a = np.array(im)
dark = (a < 160).sum(axis=1)
W = a.shape[1]
rows = np.where(dark > W * 0.20)[0]
lines = []
if len(rows):
    start = prev = rows[0]
    for r in rows[1:]:
        if r - prev > 3:
            lines.append((start+prev)//2); start = r
        prev = r
    lines.append((start+prev)//2)
# group into 5-line staves
staves, i = [], 0
while i < len(lines):
    grp = [lines[i]]
    while i+len(grp) < len(lines) and lines[i+len(grp)]-lines[i+len(grp)-1] < 20:
        grp.append(lines[i+len(grp)])
        if len(grp) == 5: break
    if len(grp) == 5: staves.append((grp[0], grp[-1])); i += 5
    else: i += 1
systems, i = [], 0
while i < len(staves):
    if i+1 < len(staves) and 10 < staves[i+1][0]-staves[i][1] < 80:
        systems.append((staves[i][0], staves[i+1][1])); i += 2
    else: i += 1
print('staves:', staves)
print('systems:', systems)
for k, (y0, y1) in enumerate(systems):
    im.crop((0, max(0,y0-15), W, min(im.size[1], y1+15))).save(f'sys_{k}.png')
