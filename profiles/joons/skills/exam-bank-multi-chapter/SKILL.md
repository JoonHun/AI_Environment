---
name: exam-bank-multi-chapter
description: "Multi-chapter combined exams with even per-chapter splits."
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
4. **Answer-key pattern:** `place_all()` in `render_exam.py` assigns ①②③④ positions via MD5-based deterministic hash, then post-processes to break any consecutive 1-2-3-4 or 4-3-2-1 sequence. **Verify with a per-round distribution scan** — every round must show ①②③④ counts summing to 20 with no 4-consecutive run.
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

## Pitfalls

- **`split_by_chapter` classifier is hardcoded to ch4/ch5 topic sets.** `render_exam.py`'s `split_by_chapter()` classifies MCQs by matching the `topic` field against a hardcoded `ch4_topics` set. For a **different chapter pair** (e.g. 3장+5장), you MUST patch `split_by_chapter` to accept the correct first-chapter topic set — or pass `ch3_topics`/`chN_topics` explicitly. If you don't, every question falls into the "other" bucket and the split is 100:0, not 50:50. The function signature already accepts `ch3_topics=None, ch5_topics=None` as keyword args (added during the 3+5 session) — use them instead of relying on the default `ch4_topics` set.
- **Lopsided chapter split (the big one).** A bank authored by copying one chapter's questions and appending a few from the other ships 90:10 or 52:12. The user explicitly wants **50:50 per round** — verify per-round counts in the simulation step, not just the total.
- **`split_by_chapter` classifies by topic tag, not by list position.** If a 5장 question is tagged with a 4장 topic keyword (e.g. "성질" for a 5장 question about material properties), it gets misrouted to the 4장 pool. Tag questions with their **own chapter's** subject keywords only.
- **Pool exhaustion at the last round.** `ch4[r*n4:(r+1)*n4]` silently returns fewer items if the pool is short. The simulation step catches this; the render does NOT (it just renders fewer questions and the page count is off by a bit).
- **`place_all()` pattern-breaking is a 1-pass fix.** If the initial hash produces 1-2-3-4 at positions 5-8, it bumps position 8. But if the bump creates a new 4-consecutive at positions 6-9, the loop re-checks. In practice this resolves in 1-2 iterations for N=20. For N>50, verify with the scan above.
- **SA split is NOT automatic.** `render_exam.py` takes SA as a flat list and slices `sa[r*5:(r+1)*5]` — it does NOT split by chapter. If 4장 has 12 SA and 5장 has 3, rounds 1-2 are mostly 4장 and round 3 is mostly 5장. **Interleave the SA list** (4장, 5장, 4장, 5장, …) so each round gets a mix.

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
