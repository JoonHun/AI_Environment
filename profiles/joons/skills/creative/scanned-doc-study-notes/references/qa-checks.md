# Markdown QA Checks (run BEFORE rendering)

Purpose: catch cross-script bleed and self-duplicates that slip into local-language
study notes. Run these over the generated markdown file, fix, re-run until clean,
*then* render. All checks are Python; run them with the project venv python
(the base `execute_code` interpreter is fine for these pure-stdlib checks too).

## 1. Foreign-script bleed (Hanja / Chinese / Japanese into the target language)

```python
import re
t = open("chN_요약.md", encoding="utf-8").read()
pat = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff\u3400-\u4dbf]')
hits = [(i, l.strip(), ''.join(pat.findall(l)))
        for i, l in enumerate(t.splitlines(), 1) if pat.findall(l)]
print("CJK bleed lines:", len(hits))
for i, l, c in hits:
    print(f"  L{i} [{c}]: {l[:80]}")
```

- Target: **0 hits** before rendering.
- Note: Hangul (가-힕) is NOT in this range, so legitimate Korean text passes.
- Real examples seen: `高度`→`높이`, `转变`→`전환`, `流`, `海王`→`해`, `綠葉體`→`엽록체`,
  `澱粉`→`전분`, and mixed-script typos `코il`, `하iperbolic`. Fix to pure Hangul.

## Mass-rewrite vs patch rule

- **Widespread bleed (> ~10 lines)** → **rewrite the whole file** with the target
  language only (a single clean pass is faster and lower-risk than dozens of patches,
  and avoids introducing more bleed while patching).
- **Few hits (≤ ~10)** → targeted `patch` per line.
- Re-run the regex after either; do not stop until the count is 0.

## 2. Self-duplicated words (word repeated inside its own parens)

These read as errors (e.g. `등급(등급)`, `인공위성(인공위성, …)`). Detect:

```python
import re
t = open("chN_요약.md", encoding="utf-8").read()
pat = re.compile(r'([\uac00-\ud7a3]{2,})\(\s*\1')   # Hangul word repeated in parens
seen = set()
for i, l in enumerate(t.splitlines(), 1):
    for m in pat.finditer(l):
        key = (i, m.group(1))
        if key in seen: continue
        seen.add(key)
        print(f"  L{i} [{m.group(1)}]: {l.strip()[:80]}")
```

- Fix each by removing the redundant repetition (keep the single term or a genuine
  alias, not the word twice).
- **Exception — legitimate near-dups:** some pairs are two related-but-distinct terms
  and are fine to keep, e.g. `시차(시차각)`, `나선(나선은하)`, `타원(타원형)`,
  `시등급/겉보기 등급`. Review, don't blindly delete.

## 3. Tofu / rendering (verify the RENDERED PDF, not just the markdown)

```python
import pymupdf
p = pymupdf.open("out.pdf")
full = "".join(pg.get_text() for pg in p)
print("pages:", len(p))
print("tofu:", full.count("\uFFFD"))            # want 0
```

- `tofu == 0` means no missing-glyph boxes.
- `pymupdf` is **not** in the `execute_code` sandbox — run with the project venv python
  (or `subprocess` into it). See `scripts/verify_pdf.py`.

## Full gate (all three together, markdown stage)

Before declaring a chapter's markdown ready for render, confirm: CJK bleed = 0,
self-dup = 0 (or all reviewed as legitimate), and the file matches the reference
chapter's format (blockquotes, tables, bold, consistent headings).
