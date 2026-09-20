---
name: scanned-doc-study-notes
description: "Vision-transcribe scanned pages into study-note A4 PDFs."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [PDF, Study-Notes, Textbook, Vision, weasyprint, QA]
    related_skills: [ocr-and-documents, pdf, nano-pdf]
---

# Scanned Document → Study-Note PDFs

For **generating** study notes/summaries as PDFs from a **scanned or image-only** document (no usable text layer). This skill is the generation + QA half; for pure text *extraction* use `ocr-and-documents`, for editing an *existing* PDF use `nano-pdf`/`pdf`.

Core loop (repeat per chapter/section):
1. **Boundaries** — confirm the section's page + spread range from the TOC *and* the body (TOC labels often differ from the in-text section names; a chapter may be split into multiple sections that the summary must all cover). **Physical-page index ≠ printed page number** when the textbook mixes portrait sheets (unit-intro, full-bleed photo pages) with landscape spreads: each portrait sheet adds one physical image but one printed page, so the offset between physical index and printed page **drifts by 1 at each portrait insert**. Read the printed page number at the corner of 2–3 boundary images to anchor the mapping per unit rather than computing it from the spread count.
2. **Prep images** — downscale the page PNGs you need to a vision-sized JPEG; generate only the spreads in the section (don't rebuild the whole book). For **DAP / chunjae textbooks** where most sheets are landscape 2-page spreads (~4268×2779 px) interspersed with portrait unit-intro pages: **split each landscape spread at centre** (trim ~1% gutter on each half), downscale each half to a readable width (e.g. 1200 px), and save as sequential per-page JPEGs (`000.jpg`, `001.jpg`, …). This gives one clean physical-page image per vision call. A verified prep pattern: `PIL` open each sheet → if `w > h`, crop `(0,0,mid−gx,h)` and `(mid+gx,0,w,h)`, resize to target width, save `quality=88`; portrait sheets pass through as-is. Save the prep script as an intermediate artifact in the work dir.
3. **Transcribe** — one spread per `vision_analyze` call, asking for a full lossless copy of all body text, figures, tables, and terms.
4. **Write** — author the section's markdown in the *target/local* language (e.g. pure Hangul), matching the format of a known-good reference chapter (blockquotes, tables, bold).
5. **QA the markdown** — screen for foreign-script bleed and self-duplicated words (see `references/qa-checks.md`). NOT optional: LLMs writing local-language text repeatedly bleed the source script.
6. **Render** — copy the reference render script and sed-swap every path/title, then run it with the project venv python.
7. **Verify the PDF** — page count, tofu (U+FFFD), foreign-script regex, and keyword presence. Every time.

> **Why a whole skill?** This is a high-touch pipeline where each step has a failure mode (path truncation, cross-script contamination, stale titles, wrong interpreter). The checklist below is what separates a clean PDF from a re-do.
>
> **Standing user preferences (this textbook set):** (a) Summaries must be **detailed enough to fully understand the content** — don't over-compress; include reading-passage plots, theme, literary devices, activity instructions, and side-box content ('이것만은 꼭', '스스로 확인하기', '단원 어휘만들기', etc.). The user explicitly rejects summaries that are too thin ("무리하게 내용 줄이지 말 것"). (b) **Save ALL intermediate artifacts** (per-page transcription notes, per-chapter markdown/HTML) alongside the final PDF in the same output dir — the user explicitly wants them kept ("중간 산출물 모두 저장").

## The checklist (do not skip)

- [ ] Section boundaries confirmed from TOC **and** the body spreads (not just the TOC).
- [ ] Only needed spreads prepared (perf) — `N=<max spread>`.
- [ ] Every spread transcribed 1-per-call (see Pitfalls: batching).
- [ ] Markdown matches the reference chapter's format.
- [ ] **Markdown QA passed**: foreign-script bleed = 0, self-dup words = 0 (regexes in `references/qa-checks.md`).
- [ ] **Every computed answer in worked solutions re-verified** (angles sum to 180°/360°, slope/length/coordinate recomputed) — see Pitfalls: generated worked-solution answers can be wrong.
- [ ] Render script has the **correct `<h1>` title** for *this* section (most common bug).
- [ ] Rendered with the project venv python (not the base interpreter).
- [ ] PDF verified: pages, tofu=0, foreign script=0, keywords OK.
- [ ] All prior sections re-checked for stale titles if their scripts were copied from an earlier chapter.

## Render-script pattern

Author one canonical `render_summary.py` (markdown→HTML → A4 weasyprint) for the first chapter, then for each new section:

```bash
cp render_summary.py render_summary_chN.py
sed -i "s#chREF_요약.md#chN_요약.md#g; \
       s#OUTPUT_REF.pdf#OUTPUT_chN.pdf#g; \
       s#REF.html#N.html#g" render_summary_chN.py
# THEN manually fix the <h1> title — sed often misses it (see Pitfalls).
(venv) python render_summary_chN.py
```

Verify the swap landed before running:
```bash
grep -nE "SRC = |OUT = |HTML_OUT = |<h1>" render_summary_chN.py
```

## Verification

```python
import pymupdf, re
full = "".join(pg.get_text() for pg in pymupdf.open(out_pdf))
print(len(pymupdf.open(out_pdf)))                # page count
print(full.count("\uFFFD"))                       # tofu, want 0
print(re.findall(r'[\u3040-\u30ff\u4e00-\u9fff\u3400-\u4dbf]', full))  # foreign script, want []
for kw in ["키워드1", "키워드2"]: print(kw, kw in full)
```

`pymupdf` is NOT in the `execute_code` sandbox — run this via the project venv python (or `subprocess` into it). See `scripts/verify_pdf.py` for a drop-in.

## Large textbooks: parallel subagent delegation

For a full textbook (100+ pages, 3+ chapters), sequential per-chapter vision work in one conversation is slow and risks context overflow. The proven pattern: **one subagent per chapter, all in parallel** via `delegate_task`.

Per-subagent instructions must be self-contained:
- Absolute paths to the per-page JPEGs for that chapter's physical-page range (from the prep step).
- The chapter's structure from the TOC (unit title, item titles with printed page numbers) — the subagent verifies against actual image page numbers.
- Output HTML + PDF paths (Korean filenames, same output dir as sibling chapters). Naming: `천재_중학<과목><등급>_<N>장_<단원명>_요약.pdf`.
- CSS reuse: copy the `<style>` block verbatim from a known-good sibling chapter's `요약.html`; change only the `@bottom-left` footer label.
- The venv python path for weasyprint rendering (from `korean-html-pdf` skill).
- An `output_schema` requiring `{chapter, pdf_path, html_path, pages, pages_read, verified}` so the parent can check all N results when they return.

The parent agent's job:
1. Prep all page images for the whole book (one `prep_pages.py` run).
2. Read the TOC (2–3 vision calls) to get chapter boundaries in both printed-page and physical-page space.
3. Verify 2–3 boundary images to confirm the physical↔printed mapping per unit.
4. Dispatch N subagents (one per chapter) in a single `delegate_task` call.
5. When results return: verify each PDF exists, has the right page count, and spot-check one page per chapter.
6. Deliver all PDFs.

Works well for 4-chapter textbooks (111–167 pages each). Subagents handle their own vision batching, HTML authoring, and rendering independently.

## Pitfalls (learned the hard way)

- **Cross-script bleed (the big one).** When writing the target language, the model leaks source-script glyphs — Hanja/Chinese/JP into Korean (e.g. `高度`, `转变`, `流`, `海王`) and mixed-script tokens (`코il`, `하iperbolic`). Strategy: run the bleed regex over the markdown *before* rendering. If it's widespread → **rewrite the whole file** (patching dozens is slower); if ≤ ~10 hits → patch. Re-run until 0. (Details + exact regexes: `references/qa-checks.md`.)
- **Deliberate Hanja glosses also trip the CJK-leak check — decide, don't blindly "fix".** The foreign-script regex can't tell an accidental leak from an *intentional* Hanja gloss you wrote yourself (e.g. `외심(外心)`, `성질(定理)`). Both show up as "CJK leaks" even though intentional Hanja renders fine (no tofu). So a non-zero leak count does not automatically mean a bug: either **strip the parenthetical Hanja to hold strict 0-leak parity** with the rest of the textbook set, or **keep it** and accept a small, deliberate non-zero count. Don't "repair" a gloss you added on purpose. (This session: ch4 요약 shipped 定理/外心/內心 as intentional Hanja — the leak check reported 6, and I stripped them to keep every chapter at 0 for consistency.)
- **Generated worked-solution answers can be WRONG — verify them.** Format QA (bleed/tofu/cjk-leak) is silent on a numerically-wrong-but-plausibly-formatted solution, so the "예상 시험 질문" / worked-solution sections are the highest-risk content in a math summary. This session: an isosceles-**trapezoid** angle problem was solved assuming ∠A=∠C (false for a trapezoid — that's an isosceles *triangle* property); the right derivation is equal base-angles ∠A=∠B then co-interior ∠C=180°−∠B, and it shipped wrong until re-derived. Rule: for every computed answer (angle, length, slope, intercept, coordinate) **re-derive it independently before rendering** and check the invariant (triangle→180°, quadrilateral→360°). A one-pass generated solution is untrusted; re-verify the key numbers on a second pass. (Same root as the `**`-in-code-blocks trap: content inside a formula/answer box is exactly where errors hide.)
- **Self-duplicated words in parens** (`등급(등급)`, `인공위성(인공위성, …)`). Catch with the self-dup regex and clean — they read as errors.
- **Stale `<h1>` title.** Copied render scripts keep the *previous* chapter's `<h1>…</h1>`, so the PDF's first-page heading is wrong even though the body is fine. sed usually does **not** touch the `<h1>` line — fix it explicitly, and when you fix chapter N, re-check every section whose script was derived from chapter N.
- **Batching vision calls truncates paths.** Issuing several `vision_analyze` calls (or typing a long absolute path) in one turn repeatedly produced truncated paths. Prefer **one spread per turn**; build long paths from short pieces or run from a working dir instead of typing the full path inline.
- **Wrong interpreter.** `pymupdf`/`weasyprint` live in the project venv; the default interpreter lacks them. Always run render + verify with the venv python.
- **Korean path segment truncation through tool transport.** Typing a long absolute path that contains a Korean segment (e.g. `국학류학`) as an argument to `terminal`/`read_file`/`write_file`/`execute_code`/`patch` can arrive truncated (the tool reports No-such-file on a file that `find` shows exists; ASCII paths on the same call work fine). Rotate workarounds instead of retrying the same call: (1) `execute_code` with a piece-built path via `os.path.join(home, ".hermes", "services", *, …)` or `os.path.expanduser`; (2) `terminal` with a relative path from a known `workdir`; (3) write to ASCII `/tmp` then `cp`/`shutil.copy2` into the Korean dir. Details: `references/transport-workarounds.md`.
- **TOC ≠ body structure.** A chapter's in-text section split (and which pages belong to which section) can differ from the printed TOC. Verify against the actual spreads; a whole section can be easy to miss.
- **Large HTML writes tail-truncate.** A long `write_file` of a full quiz/exam HTML can arrive cut at the tail, dropping the closing `</html>` (the file still renders but is malformed). After writing a large HTML, check the tail (`grep -c '</html>'` or `read_file` the last lines); if `</html>` is missing, append it before rendering. Same transport-truncation family as the Korean-path issue — a large *content* payload is also truncated, not just paths.
- **ANSWER-BOX dead CSS (the recurring "more space" bug).** The quiz HTML puts `<div class="sa-space">` as a sibling *after* `</p class=q>`, NOT inside it. So `.q .sa-space { min-height: … }` never matches and every box renders ~76pt (~2.7cm) — looking small. This made the user repeatedly ask for "more space" that silently never applied (ch2–5 all shipped this way). Two fixes: (1) selector must be plain `.sa-space`; (2) verify the RENDERED box height with pymupdf `dr['rect'].height` (expect your min-height pt), not just the text layer. Full detail + verification snippet: `references/answer-box-css.md`.

- **Low-DPI grid thumbnails misread chapter/section titles.** Building a contact-sheet grid of many pages at low DPI (e.g. 45–60) to scan a large chapter range is fine for *locating* a title page, but the rendered titles are small enough that you can confidently read the WRONG chapter name (this session: a 45-DPI grid was read as “Ⅱ 방정식” when it was actually a different chapter, costing a wrong starting index). Always **confirm the chapter title + section list at high DPI on the single cover page** before you anchor the page range and before authoring the summary. Cheap insurance against building the whole summary on a misread title.
- **Mine the existing `work/` artifacts FIRST — they encode the authoritative structure.** Before OCR-ing or vision-scanning a chapter from scratch, check the service `work/` dir for prior-session leftovers: an `chN_ocr.json` (page range already set = your chapter boundaries for free), a `chN_bank.py` / question-bank (its section/sub-chapter headers ARE the textbook’s own section list — the single most reliable source), helper libs, or even a half-built summary. Reading a 20-line bank’s section headers is faster and more accurate than reconstructing structure from noisy OCR text. Reuse the OCR JSON instead of re-OCR-ing when the page range matches.

## Exam / quiz generation (same pipeline, different output)

The same loop also produces **test papers** from the chapter summaries. Standing user constraints (repeated across sessions — follow the user's request, not the defaults):
- **객관식 N + 주관식 M** (e.g. 20 + 5) — match the requested counts exactly.
- **주관식 spacing:** each subjective question is followed by a wide dashed answer box (`.sa-space`, label `✎ 답을 쓰시오`). **The `min-height` is a user-tunable dial, not a fixed value** — the user scales it up per chapter until it's comfortably larger than the prior one, with the hard cap that the box must stay inside one page (no page-spanning box). Observed progression: ch2=130pt → ch3=260pt ("2배") → ch4=340pt ("chapter3 보다 더 넓게"). Default to whatever the user's latest instruction is; if they say "more space", bump `min-height` and re-verify the box doesn't cross a page (see Pitfalls: page-spanning box). Never ship a "small gap" — the user has complained boxes are too small repeatedly.
- **A4 blank minimisation:** `line-height ≈ 1.6`, `margin: 16–18 mm`, rely on `page-break-inside: avoid`. The last question page may be mostly answer boxes (user-requested whitespace, not a bug).
- **4지선다 줄바꿈 (user-corrected):** `.opt { display:flex; flex-wrap:wrap }` + 각 선택지를 `<span class="o">`(white-space:nowrap)로 감싸야 함. `display:block` 단일 블록으로 쓰면 단어 중간에 깨진다 (ch1_문제_01.pdf 기준). 2026-09: user explicitly corrected — "한 줄에 안 되면 세로로 ① ② ③ ④".
- **Answer key separate page:** `#answer-key { page-break-before: always; }` so it prints apart from the test. Explicitly and repeatedly asked for.
- **Answer key:** per objective = correct option + 1–2 line 해설 (+ optional 오답 정리); per subjective = 모범 답안 (table/list) + 채점 기준. Close with a `📝 채점 팁` block listing required key terms.

Start from `templates/quiz_a4.md` (CSS + layout tuned for A4). Render with the same venv `render_summary_chN.py` pattern; verify with `scripts/verify_pdf.py`. Naming: `chN_문제_01.pdf`.

## See also
- `references/qa-checks.md` — exact QA regexes (foreign-script bleed, self-dup, tofu) + the mass-rewrite-vs-patch rule.
- `references/answer-box-css.md` — the `.q .sa-space` dead-CSS box-height bug + how to verify rendered box height + user sizing history.
- `references/transport-workarounds.md` — Korean-path + large-write transport truncation.
- `scripts/verify_pdf.py` — drop-in PDF verifier (pages, tofu, foreign script, keywords).
