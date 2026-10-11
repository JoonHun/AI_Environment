---
name: exam-bank-multi-chapter
description: "Exam PDFs from a question bank: single- or multi-chapter, even splits, multi-round. Use when generating 문제/시험 문제 뱅크 or 회차 series."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [exam, quiz, multi-chapter, bank, weasyprint, balanced-answers]
    related_skills: [scanned-doc-study-notes, korean-html-pdf]
---

# Multi-Chapter Combined Exam (통합 시험문제)

For generating a **combined exam** spanning N chapters (e.g. "4장, 5장 통합으로 문제를 생성해줘. 객관식 20개 주관식 5개. 3회차."). The question pool must be **evenly split per chapter** (50:50 for two chapters) in every round.

## Core rules

1. **Author a separate bank file** (e.g. `exam_bank_45.py`) that merges per-chapter MCQ/SA lists. Do NOT reuse a single-chapter bank — the split will be lopsided.
2. **Per-chapter MCQ count must satisfy the per-round split.** For 20 MCQ/round × 3 rounds = 60 MCQ total → **30 per chapter** for a 2-chapter exam. If a chapter's pool has fewer, author more questions for that chapter *before* rendering. A 52:12 split ships with 90% of one chapter and 10% of the other — the user will notice.
3. **Per-chapter SA count** proportional: 5 SA/round × 3 = 15 total → 4장 8 + 5장 7 (or 7+8). Author enough per chapter.
4. **Answer-key pattern:** `place_all()` in `render_exam.py` builds an **even base** (positions 0,1,2,3 repeated) then shuffles with `random.Random(seed)` (seed = round number), and post-processes to break any consecutive 1-2-3-4 or 4-3-2-1 sequence. For N=20 this guarantees ①②③④ = 5/5/5/5 **by construction** — the post-pass only swaps one position of a 4-run, so counts stay even. **Verify with a per-round distribution scan** (sum=20, even counts, no 4-consecutive run). Do NOT use a hash-derived position (e.g. `md5(seed:idx:stem) % 4`) — a hash of the stem text is not uniform in practice and produced a ④-heavy round (10/20) once; the even-base+shuffle approach eliminates that.
5. **Naming:** `N장_통합_문제_0{1,2,3}.pdf` (e.g. `4-5장_통합_문제_01.pdf`). Bank: `exam_bank_{chapters}.py` in `work/`.

## Procedure

1. **Author the merged bank** (`exam_bank_45.py`):
   - `MCQ = [ (주제, 문항, 정답, [오답3], 해설), ... ]` — per-chapter groups with topic tags matching the chapter's subject-matter keywords (used by `split_by_chapter` to classify).
   - `SA = [ (문항, 모범답안, [채점기준...]), ... ]` — same per-chapter grouping.
   - Total MCQ ≥ `mcq_per × rounds`, total SA ≥ `sa_per × rounds`.
   - **Per-chapter MCQ ≥ `mcq_per × rounds / N_chapters`** (e.g. 30 per chapter for 2-chapter × 20 × 3).
2. **Verify the split simulation** before rendering:
   ```python
   # Simulate split_by_chapter: per-round chapter counts
   import random
   for r in range(rounds):
       rng = random.Random(r * 7919)
       rng.shuffle(ch4_pool); rng.shuffle(ch5_pool)
       r4 = ch4_pool[r*n4:(r+1)*n4]; r5 = ch5_pool[r*n5:(r+1)*n5]
       print(f"round {r+1}: ch4={len(r4)}, ch5={len(r5)}")
   # ALL rounds must show n4/n5 (e.g. 10/10 for 20 MCQ)
   ```
   If any round is short (e.g. 10:9), the chapter pool is 1 question too small — author more before rendering.
3. **Render** via `render_exam.py` with `--ch4-ratio 0.5 --ch5-ratio 0.5` (or the N-chapter equivalent).
4. **Verify per-round answer distribution:**
   ```python
   # Scan each round's PDF text for ①②③④ answer badges
   # Assert: sum=20, no 4-consecutive ①②③④ or ④③②①
   ```
5. **Deliver** 3 PDFs (or N PDFs for N rounds).

## Single-chapter exam (single 장 only)

When the request is ONE chapter (e.g. "4장에서 문제를 만들어줘"), the combined-exam split machinery is the wrong path. `render_exam.py`'s `split_by_chapter()` classifies every MCQ against the `ch3_topics`/`ch5_topics` sets; with a single-chapter bank neither set matches, so without a fallback every question lands in the "other" bucket and rounds come back empty.

- **Add a sequential fallback in `split_by_chapter`:** when `ch3` and `ch5` are BOTH empty, chunk `mcq_list` into consecutive per-round slices and shuffle each chunk with `random.Random(r * 7919)`. This is the general single-chapter path — do not special-case chapter numbers.
- **A single-chapter bank whose topics DO match one classifier set is NOT the both-empty case.** E.g. a 5장-only bank matches `ch5_topics`, so `ch3` is empty but `ch5` is full, and the 50:50 ratio silently pulls only `mcq_per × 0.5` per round (10 of 20). `render_exam.py` now auto-corrects this: when one pool is empty the ratio becomes 0/100 (or 100/0). **Still verify the rendered round has exactly `mcq_per` questions** (count the MCQ section in the PDF or HTML) — a wrong pool-match shows up as a half-size round, not an error.
- **Tag coverage is load-bearing in the one-pool path.** The matched pool contains ONLY MCQs whose topic tag is in the classifier set. Author new rounds' tags inside the set (or normalize pre-existing tags into it — a batch replace of the tag field is cheap), then assert `len(matched pool) == len(MCQ)` before rendering. One novel tag (e.g. `증산작용` or `물의 흡수` in a 5장 bank) silently drops that question out of the pool, shifts every later slice by one, and the newest round renders empty or full of stale questions — no error, just a wrong or missing round.
- **Slice the one-pool case sequentially, never shuffle-then-slice per round.** Each round takes a consecutive block of the pool; the LAST round takes the pool's final `mcq_per` items so the most recently appended round is the one rendered last (this also absorbs a bank whose size isn't a multiple of `mcq_per`). A per-round `shuffle(pool); pool[r*per:(r+1)*per]` takes a different random window of the SAME pool each round and produces inter-round duplicates — the user compares rounds side by side and notices.
- **No chapter split to verify** — skip the 50:50 simulation step entirely. Just ensure total MCQ ≥ `mcq_per × rounds` and total SA ≥ `sa_per × rounds`.
- **SA slicing is already flat** (`sa[r*sa_per:(r+1)*sa_per]`), so a single-chapter SA list works with no interleave.

## Filename suffix for multi-round series

The user generates exam series in rounds and wants the round number followed by a stable suffix so versions are distinguishable in the folder (e.g. `4장_…_문제_01 POST FIX.pdf`, `…_02 POST FIX.pdf`). `render_exam.py` exposes a `--suffix` flag (default `""`) that is appended to the round number in BOTH the HTML and PDF output filenames:

```
--tag "4장_삼각형과사각형의성질_문제" --suffix " POST FIX"   # → …_문제_01 POST FIX.pdf
```

Author the bank ONCE with more questions than one round needs (e.g. 41 MCQ for 20/round) so `--rounds 2,3…` can be raised later without re-authoring. Never delete earlier round PDFs when generating new rounds — the user keeps every version.

## Incremental rounds: `--start` (generate ONE later round without touching earlier ones)

The user typically asks for round 1, then "2회차", then "3회차" — one round per message, each a fresh invocation. `render_exam.py` exposes `--start N` so you render only round N and it slices the bank at index `N-1`:

```
--rounds 1 --start 3 --mcq-per 20 --sa-per 5 --tag "4장_…_문제"   # → …_문제_03.pdf
```

- The loop is `for r in range(rounds): idx = start-1+r; rn = start+r`, and the filename uses `rn` (the displayed round number), so `--start 3 --rounds 1` writes `_03`, not `_01`. Keep `--rounds 1` for the one-at-a-time pattern.
- **Sufficiency check semantics are easy to get wrong.** The pre-render check is `need_rounds = (start-1) + rounds`; it requires the bank to have `mcq_per × need_rounds` and `sa_per × need_rounds` items total. That is, `--start 3` demands a bank sized for ALL of rounds 1-3 (60 MCQ / 15 SA), NOT just 20/5 for round 3 — because round 3 consumes the *third* slice of the flat bank, the first two slices must exist even though their PDFs were already made. If the check fails with "뱅크 부족", extend the bank (see below); do not lower `--start` or `--rounds` to dodge it.
- **Extend the bank by APPENDING new rounds' questions at the end of `MCQ`/`SA`**, in round order. Because slicing is positional, round N always gets bank items `[(N-1)*per … N*per)`. Never insert into the middle of the list — that shifts every later round's slice and silently changes already-generated rounds. New round-N questions must not overlap earlier rounds (the user compares rounds; duplicates are noticed).
- **After ANY programmatic bank extension (script-splicing text at the closing `]`), import the bank module and assert `len(MCQ)`/`len(SA)` before rendering.** Regex splice at the list terminator routinely leaves a stray `,` line or an off-by-one slice — a SyntaxError at render time is the late symptom; `importlib` + count is the cheap early check. Also scan the new stems against the old list for duplicates.
- The single-chapter sequential fallback (below) and the even `place_all` apply unchanged per round.

## Pitfalls

- **Author a large bank (≥~100 MCQ) as part modules + aggregator, not one file.** A single `write_file` of a 100+ MCQ / 25 SA bank routinely truncates mid-list (SyntaxError or a cut-off tuple on import). Split into `exam_bank_{ch}_p1.py` / `_p2.py` each defining `MCQ_A`/`SA_A` and `MCQ_B`/`SA_B`, then an aggregator `exam_bank_{ch}.py` that `sys.path.insert(0, dirname)` + imports both and sets `MCQ = MCQ_A + MCQ_B`, `SA = SA_A + SA_B`. Verify with `importlib` + `len(MCQ)`/`len(SA)` and a structural check (`len(q)==5` for MCQ, `len(q)==3` for SA) before rendering.
- **Pre-merge bank QC: scan for stray CJK ideographs AND Japanese kana, plus duplicate options.** Generated Korean stems occasionally leak Chinese tokens (同样的, 越高, 和, 结实, 后者, …) *and* Japanese particles/kana (である, もの, 东升 is CJK, である is kana) that read as typos to the user. Before rendering, run `re.findall(r'[\u3040-\u30ff\u4e00-\u9fff]', text)` and assert zero matches — the `\u3040-\u30ff` range catches hiragana/katakana that a `\u4e00-\u9fff`-only scan misses. Also assert each MCQ's wrongs are distinct from the correct answer and from each other. Scan the MERGED bank (not just the new file) — a bad token in an older module is just as visible to the user.
- **Every MCQ must have EXACTLY 3 wrongs — and the renderer's pre-check will not catch a wrong count.** The renderer builds each question as `ch=[None]*4`, places the answer, then `zip`s the 3 remaining slots with the `wrongs` list: with only 2 wrongs one slot stays `None` and `esc(None)` raises `AttributeError: 'NoneType' object has no attribute 'replace'`; with 4 wrongs one is silently dropped (no error, just a missing option). Critically the `뱅크 부족` (bank-insufficient) pre-check validates list LENGTHS only (total MCQ/SA vs `per × rounds`), never per-question structure, so a malformed item passes the check and crashes MID-RUN — deferred to whichever round's positional slice happens to contain it (a 2-wrongs item at index 64 of a 100-item bank crashed at round 4, AFTER rounds 1–3 already wrote their PDFs). Run a full-bank structural scan on the MERGED bank before the FIRST render: `len(wrongs)==3`, `answer not in wrongs`, all wrongs non-empty `str`, `len(q)==5` for MCQ / `len(q)==3` for SA. If a mid-run crash does happen, re-render ALL rounds — the earlier round PDFs are stale and must not be left as partial output.

- **`split_by_chapter` classifier is hardcoded to ch4/ch5 topic sets.** `render_exam.py`'s `split_by_chapter()` classifies MCQs by matching the `topic` field against a hardcoded `ch4_topics` set. For a **different chapter pair** (e.g. 3장+5장), you MUST patch `split_by_chapter` to accept the correct first-chapter topic set — or pass `ch3_topics`/`chN_topics` explicitly. If you don't, every question falls into the "other" bucket and the split is 100:0, not 50:50. The function signature already accepts `ch3_topics=None, ch5_topics=None` as keyword args (added during the 3+5 session) — use them instead of relying on the default `ch4_topics` set.
- **Lopsided chapter split (the big one).** A bank authored by copying one chapter's questions and appending a few from the other ships 90:10 or 52:12. The user explicitly wants **50:50 per round** — verify per-round counts in the simulation step, not just the total.
- **`split_by_chapter` classifies by topic tag, not by list position.** If a 5장 question is tagged with a 4장 topic keyword (e.g. "성질" for a 5장 question about material properties), it gets misrouted to the 4장 pool. Tag questions with their **own chapter's** subject keywords only.
- **Pool exhaustion at the last round.** `ch4[r*n4:(r+1)*n4]` silently returns fewer items if the pool is short. The simulation step catches this; the render does NOT (it just renders fewer questions and the page count is off by a bit).
- **`place_all()` uses even-base + seeded shuffle, then a bounded pattern-breaking loop (≤50 passes).** Counts stay exactly even (e.g. 5/5/5/5 for N=20) because the shuffle only reorders an already-even multiset and the fixer only swaps one element of a detected 4-run. This is why a distribution scan should always come back even — if it doesn't (e.g. ④=10), you are running the old hash-based `place_all` and the fix was never applied. For N>50 (non-multiple-of-4), counts are within ±1 of even; still scan for the 4-run.
- **SA split is NOT automatic.** `render_exam.py` takes SA as a flat list and slices `sa[r*5:(r+1)*5]` — it does NOT split by chapter. If 4장 has 12 SA and 5장 has 3, rounds 1-2 are mostly 4장 and round 3 is mostly 5장. **Interleave the SA list** (4장, 5장, 4장, 5장, …) so each round gets a mix.
- **Inter-round duplicates: verify, don't assume.** After extending the bank and re-running the split, scan pairwise stem-set intersections across all rounds and assert they're empty, and assert the intended round's stems equal the expected bank slice (e.g. `MCQ[(N-1)*per : N*per]`). The distribution scan (even ①②③④, no 4-run) does NOT catch duplicates — it only checks positions within one round.

## Bank format reference

```python
# exam_bank_45.py
MCQ = [
    # 4장 questions (topic tag must match ch4_topics set in render_exam.py)
    ("물질의상태", "…", "정답", ["오답1", "오답2", "오답3"], "해설"),
    # 5장 questions (topic tag NOT in ch4_topics → classified as ch5)
    ("광합성", "…", "정답", ["오답1", "오답2", "오답3"], "해설"),
    # …
]
SA = [
    ("…", "모범답안", ["채점기준1", "채점기준2"]),
    # …
]
```

`ch4_topics` in `render_exam.py` is the classifier set: `{"물질의상태","원자분자","원소종류","원자구조","분리법","용액","성질"}`. Questions whose `topic` field is in this set go to the 4장 pool; all others go to 5장. For a different subject, update this set.

## See also
- `scanned-doc-study-notes` — the broader pipeline (transcribe → summary → exam).
- `korean-html-pdf` — weasyprint rendering + CJK layout verification.
