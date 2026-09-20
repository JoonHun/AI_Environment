# Answer-box CSS (quiz `.sa-space`) — the recurring "space too small" bug

## The bug
Quiz HTML structure (every ch2–5 file):
```html
<p class="q"><span class="num">21.</span><span class="stem">…</span></p>
<div class="sa-space">✎ 답을 쓰시오</div>
```
The box `<div class="sa-space">` is a **sibling AFTER `</p>`**, not a child of `.q`.

If the stylesheet says `.q .sa-space { min-height: 130pt; }` (descendant selector), the rule **never matches** — there is no `.sa-space` descendant of `.q`. Result: the box renders with only its content height (~76pt, ~2.7cm) despite the min-height. CSS is *valid*, so no error appears; it just looks small.

This is why the user kept saying "답 쓰는 공간 더 넓게 / 2배로" across ch2→ch3→ch4→ch5 and it seemingly never got bigger — the height was a no-op the whole time. It only looked like a sizing preference; it was a selector bug.

## Correct form
```css
.sa-space { margin: 10pt 0 0 0; border: 1px dashed #b6c2d4; border-radius: 6pt; min-height: 150pt; background: #fbfcfe; padding: 8pt 10pt; }   /* plain selector */
.qsubj  { page-break-inside: avoid; margin: 8pt 0 2pt 0; }   /* optional binder, see below */
.qsubj .q { margin: 0 0 6pt 0; }
```
```html
<div class="qsubj">
  <p class="q"><span class="num">21.</span><span class="stem">…</span></p>
  <div class="sa-space">✎ 답을 쓰시오</div>
</div>
```
`.qsubj { page-break-inside: avoid }` keeps a question's stem + box on the same page (no page-straddling box) — important once boxes are tall.

## Verify the box ACTUALLY rendered tall (do this before shipping)
The text layer only tells you `✎ 답을 쓰시오` exists, NOT that the box has height. Measure the drawn rect with the venv python:
```python
import pymupdf
p = pymupdf.open("/tmp/chN_quiz.pdf")
for pi in range(len(p)):
    h = sorted({round(dr["rect"].height,1) for dr in p[pi].get_drawings() if dr["rect"].width>380 and dr["rect"].height>80}, reverse=True)
    if h: print(p+str(pi+1), h)   # expect the min-height pt value, e.g. 150.0 / 300.0
```
If the max height is ~76, the selector bug is present — switch `.q .sa-space` → `.sa-space` and re-render.

## User sizing history (2026-09)
- ch2 130pt (base) → ch3 260pt ("2배") → ch4 340pt → ch5 300pt… all while the selector bug meant the real height was ~76pt.
- 2026-09 session: user said boxes were "너무 커" (because a later pass finally fixed the selector, exposing the true 300pt). Settled **all ch1–6 at 150pt** (half) and unified ch1 (which had no boxes) up to match.
- **Rule: the height is a user dial. Don't auto-increase. Change min-height only on request, and always verify the rendered box height above.**

## Transport note (why this was hard to fix)
- Korean absolute paths truncate through `terminal`/`write_file`/`execute_code`. Build paths in Python: `D = os.path.dirname(glob.glob(os.path.join(os.path.expanduser("~"), ".hermes","services","*","output","*","ch1_*01.pdf"))[0])`. See `references/transport-workarounds.md`.
- `write_file` with a large mixed-Korean/ASCII payload tail-truncates (drops `</html>` or the CSS tail). Write small pieces ≤ ~1KB and assemble, or use `terminal` `cat > file << 'EOF'` for full-size HTML bodies (heredocs work fine and preserve Korean).