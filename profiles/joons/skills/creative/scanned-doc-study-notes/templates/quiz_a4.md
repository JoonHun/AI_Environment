# Template: Chapter quiz (A4, weasyprint)

Copy into `work/science/chN_quiz.html`, fill in `{{CH_NUM}}` / `{{CH_TITLE}}` / page-range and the questions. CSS is pre-tuned for A4 + the standing quiz preferences (wide subjective boxes, minimal blank, separate answer-key page).

```html
<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<style>
@page { size: A4; margin: 16mm 15mm 18mm 15mm;
  @bottom-right { content: counter(page) " / " counter(pages); font-size: 8pt; color: #8a8f98; }
  @bottom-left { content: "중학 과학 2 · {{CH_NUM}}장 {{CH_TITLE}} — 리뷰 시험"; font-size: 8pt; color: #8a8f98; } }
* { box-sizing: border-box; }
body { font-family: 'Noto Sans CJK KR','Noto Sans KR',sans-serif; font-size: 10.3pt; line-height: 1.6; color: #212529; }
#test-header { border-bottom: 3px solid #f6b93b; padding-bottom: 10pt; margin-bottom: 12pt; }
#test-header h1 { font-size: 20pt; color: #0b3d91; margin: 0 0 6pt 0; line-height: 1.3; }
#test-header .meta { font-size: 9.5pt; color: #5d6d7e; line-height: 1.7; }
#test-header .meta strong { color: #0b3d91; }
h2 { font-size: 14pt; color: #0b3d91; margin: 16pt 0 8pt 0; padding: 5pt 9pt; background: #eef3fb; border-left: 4px solid #0b3d91; page-break-after: avoid; }
.q { margin: 9pt 0 11pt 0; page-break-inside: avoid; }
.q .num { font-weight: 700; color: #0b3d91; margin-right: 4pt; }
.q .stem { margin: 0; }
/* 4지선다: 한 줄에 4개 안 들어갈 때 선택지 단위로 줄바꿈 (단어 중간 끊김 방지) */
.q .opt { display: flex; flex-wrap: wrap; align-items: baseline; margin: 4pt 0 0 1.1em; line-height: 1.55; }
.q .opt .o { margin-right: 14pt; white-space: nowrap; }
.q .opt .o b { color: #0b3d91; }
/* ANSWER-BOX: selector MUST be plain `.sa-space`, NOT `.q .sa-space` — the box div is a SIBLING
   AFTER `</p class=q>`, so the descendant form never matches and the box silently renders ~76pt
   (dead CSS). This exact bug shipped in ch2–5, which is why repeated "more space" requests
   appeared to have no effect. See references/answer-box-css.md */
.qsubj { page-break-inside: avoid; margin: 8pt 0 2pt 0; }
.qsubj .q { margin: 0 0 6pt 0; }
.sa-space { margin: 10pt 0 0 0; border: 1px dashed #b6c2d4; border-radius: 6pt; min-height: 150pt; background: #fbfcfe; padding: 8pt 10pt; color: #aab6c8; font-size: 9pt; }
#answer-key { page-break-before: always; }
#answer-key h1 { font-size: 18pt; color: #145a32; background: #eaf6ee; border-left: 5px solid #2e8b57; padding: 8pt 10pt; margin: 0 0 12pt 0; }
#answer-key h2 { color: #145a32; background: #eaf6ee; border-left: 4px solid #2e8b57; }
#answer-key .ans { margin: 11pt 0 14pt 0; page-break-inside: avoid; }
#answer-key .correct { display: inline-block; background: #2e8b57; color: #fff; padding: 1pt 8pt; border-radius: 9pt; font-weight: 700; margin-left: 6pt; }
#answer-key .qnum { font-weight: 700; color: #145a32; }
#answer-key .explain { margin: 5pt 0 0 0; font-size: 9.7pt; line-height: 1.55; }
#answer-key .explain ul { margin: 4pt 0 4pt 6pt; padding-left: 14pt; }
#answer-key .explain li { margin: 2pt 0; }
#answer-key .wrong { color: #a94442; font-size: 9.2pt; }
#answer-key .table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt 0; font-size: 9.3pt; }
#answer-key .table th { background: #145a32; color: #fff; padding: 4pt 6pt; text-align: left; }
#answer-key .table td { border: 1px solid #cdd7e0; padding: 4pt 6pt; vertical-align: top; }
strong { color: #0b3d91; } #answer-key strong { color: #145a32; }
hr { border: none; border-top: 1px solid #d0d7e0; margin: 14pt 0; }
</style></head><body>

<div id="test-header">
  <h1>{{CH_NUM}}장. {{CH_TITLE}} — 리뷰 시험</h1>
  <div class="meta">
    <strong>대상</strong>: 천재 중학 과학2 (2026 개정) · {{CH_NUM}}장 {{CH_TITLE}} (pp.XX-XX) &nbsp;|&nbsp;
    <strong>구성</strong>: 객관식 20문항 + 주관식 5문항 &nbsp;|&nbsp; <strong>시간</strong>: 50분 &nbsp;|&nbsp; <strong>만점</strong>: 100점
  </div>
</div>

<h2>I. 객관식 (20문항)</h2>
<p class="q"><span class="num">1.</span><span class="stem">…문제…</span>
  <span class="opt"><span class="o"><b>①</b> A</span><span class="o"><b>②</b> B</span><span class="o"><b>③</b> C</span><span class="o"><b>④</b> D</span></span></p>

<h2>II. 주관식 (5문항)</h2>
<!-- WRAP each subjective question in .qsubj so stem+box stay on one page (no split) -->
<div class="qsubj"><p class="q"><span class="num">21.</span><span class="stem">…설명하시오.</span></p>
<div class="sa-space">✎ 답을 쓰시오</div></div>

<hr>

<div id="answer-key">
<h1>{{CH_NUM}}장 {{CH_TITLE}} — 해답지 (분리 출력 가능)</h1>
<h2>I. 객관식 해답 (1~20)</h2>
<div class="ans"><span class="qnum">1.</span><span class="correct">①</span>
  <div class="explain"><b>해설</b>: …</div></div>
<h2>II. 주관식 모범 답안 (21~25)</h2>
<div class="ans"><span class="qnum">21.</span>
  <div class="explain"><b>모범 답안:</b> … <b>채점(4점)</b>: …</div></div>
<h2>📝 채점 팁</h2>
<div class="explain"><ul><li><b>객관식</b>: 단정, 부분점 없음.</li><li><b>주관식</b>: 핵심 키워드 포함 시 감점 없음.</li></ul></div>
</div>
</body></html>
```

## Render & verify
Render with the venv `render_summary_chN.py` pattern. Verify with `scripts/verify_pdf.py` (pages, tofu, foreign script, keywords + confirm `✎ 답을 쓰시오` appears in the text layer = CSS landed). Naming: `chN_문제_01.pdf`.

## Standing user preferences (follow the live request; these are the defaults)
- 객관식 20 + 주관식 5.
- 주관식 답쓰기 박스 높이 = user-tunable dial, NOT a fixed value. As of 2026-09 the user settled all of ch1–6 at `min-height: 150pt` after finding the earlier "widening" had never rendered (the `.q .sa-space` selector bug — references/answer-box-css.md). Do not auto-bump height; if the user asks wider/narrower change `min-height` and re-verify the RENDERED box height (pymupdf `dr['rect'].height`) before shipping.
- A4 공백 최소화 → `line-height: 1.6`, `margin: 16–18 mm` baseline; don't add extra `.q` margins.
- **해답지 별도 페이지** → `#answer-key { page-break-before: always; }` non-negotiable.
