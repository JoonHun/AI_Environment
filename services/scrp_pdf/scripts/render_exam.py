#!/usr/bin/env python3
"""render_exam.py — 시험문제 3회차 PDF 생성 (과목 무관 공용 스크립트)

문항 뱅크 파일을 받아 객관식/주관식 N회차 PDF를 만든다.
각 회차 = 객관식 20 + 주관식 5 + 문제풀이(새 페이지).

Usage:
  python3 render_exam.py \
      --bank  out/과학2/work/exam_bank.py \
      --outdir out/과학2 \
      --title "V. 식물과 에너지" \
      --subject "천재 중학 과학 2 · 5장 식물과 에너지" \
      --rounds 3

뱅크 형식 (exam_bank.py):
  MCQ = [(주제, 문항, 정답, [오답3], 해설), ...]   # 최소 20*rounds 개
  SA  = [(문항, 모범답안, [채점기준...]), ...]      # 최소  5*rounds 개
"""
import os, sys, subprocess

def _ensure_venv():
    try:
        import weasyprint  # noqa: F401
        return
    except ImportError:
        pass
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        for cand in (os.path.join(d, "venv", "bin", "python3"),
                     os.path.join(d, "..", "work", "venv", "bin", "python3"),
                     os.path.join(d, "work", "venv", "bin", "python3")):
            cand = os.path.abspath(cand)
            if os.path.exists(cand):
                os.execv(cand, [cand] + sys.argv)
        d = os.path.dirname(d)
    sys.exit("weasyprint not found, and no work/venv located above this script")

_ensure_venv()
import importlib.util
from weasyprint import HTML

NUMS = ["①", "②", "③", "④"]


def place(correct, wrongs, idx, seed=0):
    """정답 위치 배치 — ①②③④ 균등 분포. 시드 기반 결정적."""
    import hashlib
    h = hashlib.md5(f"{seed}:{idx}:{correct[:10]}".encode()).hexdigest()
    pos = int(h[0], 16) % 4
    ch = [None] * 4
    ch[pos] = correct
    ws = list(wrongs)
    for j, c in enumerate(h[1:4]):
        ws[j % len(ws)], ws[(int(c, 16) % len(ws))] = ws[(int(c, 16) % len(ws))], ws[j % len(ws)]
    for i, w in zip([j for j in range(4) if j != pos], ws):
        ch[i] = w
    return ch, pos


def place_all(cands, seed=0):
    """모두 배치 + 연속 1-2-3-4 패턴(①②③④) 제거."""
    import hashlib
    n = len(cands)
    pos = []
    for i, c in enumerate(cands):
        h = hashlib.md5(f"{seed}:{i}:{c[:10]}".encode()).hexdigest()
        p = int(h[0], 16) % 4
        pos.append(p)
    # 연속 1-2-3-4 / 4-3-2-1 패턴 제거 (1-pass)
    changed = True
    while changed:
        changed = False
        for i in range(n - 3):
            window = [pos[i], pos[i+1], pos[i+2], pos[i+3]]
            if window in ([0,1,2,3], [3,2,1,0]):
                # 마지막 위치를 다른 값으로 변경
                current = pos[i+3]
                pos[i+3] = (current + 1) % 4
                if [pos[i], pos[i+1], pos[i+2], pos[i+3]] in ([0,1,2,3], [3,2,1,0]):
                    pos[i+3] = (current + 2) % 4
                if [pos[i], pos[i+1], pos[i+2], pos[i+3]] in ([0,1,2,3], [3,2,1,0]):
                    pos[i+3] = (current + 3) % 4
                changed = True
                break
    return pos


CSS = """
@page {
  size: A4;
  margin: 16mm 15mm 18mm 15mm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color: #8a94a6; }
}
* { box-sizing: border-box; }
body { font-family: 'Noto Sans CJK KR', sans-serif; font-size: 10.5pt; line-height: 1.6; color: #1a1f2e; }
h1 { font-size: 15pt; margin: 0 0 3pt; padding-bottom: 4pt; border-bottom: 2.5pt solid #2a5298; }
h1.sol { border-bottom-color: #2e7d32; color: #2e7d32; }
.meta { font-size: 9.5pt; color: #555; margin: 0 0 14pt; }
.section { font-size: 11.5pt; font-weight: bold; color: #2a5298; margin: 16pt 0 8pt; page-break-after: avoid; }
.q { margin-bottom: 11pt; page-break-inside: avoid; break-inside: avoid; }
.qnum { font-weight: bold; margin-right: 3pt; }
.stem { display: inline; }
.choices { display: grid; grid-template-columns: 1fr 1fr; gap: 3pt 16pt; margin-top: 3pt; }
.choice { display: block; font-size: 10pt; }
.sa-box { margin-top: 6pt; border: 0.8pt solid #8a94a6; height: 95pt; width: 100%; }
.sa-label { font-size: 9pt; color: #666; }
.sol-section { page-break-before: always; }
.sol-section .q { margin-bottom: 9pt; }
.sol-ans { font-weight: bold; color: #1a5c2a; }
.sol-exp { font-size: 9.5pt; color: #555; display: block; margin-top: 2pt; }
.sol-tag { font-size: 8.5pt; color: #888; margin-left: 4pt; }
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_round(rno, title, subject, mcq_list, sa_list):
    p = []
    p.append(f'<h1>{esc(title)} — 시험문제 <span style="font-size:11pt;color:#555;">(회차 {rno})</span></h1>')
    p.append(f'<p class="meta">{esc(subject)} | 객관식 {len(mcq_list)} + 주관식 {len(sa_list)} · 총 {len(mcq_list)+len(sa_list)}문항 | 회차 {rno} · {subject.split("·")[-1].strip() if "·" in subject else ""}</p>')

    # 전체 정답 위치를 한꺼번에 배치 (연속 1-2-3-4 패턴 방지)
    all_pos = place_all([q[2] for q in mcq_list], seed=rno)

    p.append(f'<div class="section">Ⅰ. 객관식 (1~{len(mcq_list)})</div>')
    for i, (topic, stem, answer, wrongs, explain) in enumerate(mcq_list):
        pos = all_pos[i]
        ch = [None] * 4
        ch[pos] = answer
        ws = list(wrongs)
        import hashlib
        h = hashlib.md5(f"{rno}:{i}:{answer[:10]}".encode()).hexdigest()
        for j, c in enumerate(h[1:4]):
            ws[j % len(ws)], ws[(int(c, 16) % len(ws))] = ws[(int(c, 16) % len(ws))], ws[j % len(ws)]
        for k, w in zip([j for j in range(4) if j != pos], ws):
            ch[k] = w
        chh = "".join(f'<span class="choice">{NUMS[j]} {esc(ch[j])}</span>' for j in range(4))
        p.append(f'<div class="q"><span class="qnum">{i+1}.</span><span class="stem">{esc(stem)}</span><div class="choices">{chh}</div></div>')

    sa0 = len(mcq_list) + 1
    p.append(f'<div class="section">Ⅱ. 주관식 ({sa0}~{len(mcq_list)+len(sa_list)})</div>')
    for j, (stem, model_ans, rubric) in enumerate(sa_list):
        qn = sa0 + j
        p.append(f'<div class="q"><span class="qnum">{qn}.</span><span class="stem">{esc(stem)}</span>'
                 f'<span class="sa-label">[답]</span><div class="sa-box"></div></div>')

    # 문제풀이 (새 페이지)
    p.append('<div class="sol-section">')
    p.append(f'<h1 class="sol">문제풀이 <span style="font-size:11pt;">(회차 {rno})</span></h1>')
    p.append(f'<p class="meta">{esc(subject)} | 객관식 {len(mcq_list)} + 주관식 {len(sa_list)} 문제풀이</p>')

    p.append('<div class="section" style="color:#2e7d32;">Ⅰ. 객관식 문제풀이</div>')
    for i, (topic, stem, answer, wrongs, explain) in enumerate(mcq_list):
        pos = all_pos[i]
        p.append(f'<div class="q"><span class="qnum">{i+1}.</span> '
                 f'<span class="sol-ans">{NUMS[pos]} {esc(answer)}</span>'
                 f'<span class="sol-tag">[{esc(topic)}]</span>'
                 f'<span class="sol-exp">{esc(explain)}</span></div>')

    p.append(f'<div class="section" style="color:#2e7d32;">Ⅱ. 주관식 문제풀이</div>')
    for j, (stem, model_ans, rubric) in enumerate(sa_list):
        qn = sa0 + j
        rh = " · ".join(esc(r) for r in rubric)
        p.append(f'<div class="q"><span class="qnum">{qn}.</span>'
                 f'<span class="sol-exp" style="color:#333;"><b>[채점 기준]</b> {rh}</span>'
                 f'<span class="sol-exp"><b>[모범 답안]</b> {esc(model_ans)}</span></div>')
    p.append('</div>')

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
{chr(10).join(p)}
</body></html>"""


def split_by_chapter(mcq_list, mcq_per, chapter_split, ch3_topics=None, ch5_topics=None):
    """회차별 3장/5장 균등 분배.
    chapter_split: (ch3_ratio, ch5_ratio) — 예: (0.5, 0.5)
    각 회차에서 3장 mcq_per*ch3_ratio 개, 5장 mcq_per*ch5_ratio 개를 골라 섞음."""
    ch3_ratio, ch5_ratio = chapter_split
    n3 = round(mcq_per * ch3_ratio)
    n5 = mcq_per - n3

    # 3장/5장 그룹 분리 (주제 기반)
    if ch3_topics is None:
        ch3_topics = {"빛의반사","빛의굴절","거울","렌즈","색의합성","파동","소리"}
    if ch5_topics is None:
        ch5_topics = {"광합성","호흡","기공","무기염류","광합성실험","호흡실험","광합성조건","호흡조건","광합성산물","호흡산물"}
    ch3 = [q for q in mcq_list if q[0] in ch3_topics]
    ch5 = [q for q in mcq_list if q[0] in ch5_topics]

    # 회차별 분배
    import random
    rounds_mcq = []
    for r in range(len(mcq_list) // mcq_per):
        rng = random.Random(r * 7919)
        rng.shuffle(ch3)
        rng.shuffle(ch5)
        round3 = ch3[r*n3:(r+1)*n3]
        round5 = ch5[r*n5:(r+1)*n5]
        combined = round3 + round5
        rng.shuffle(combined)
        rounds_mcq.append(combined)
    return rounds_mcq


def main():
    import argparse
    ap = argparse.ArgumentParser(description="시험문제 N회차 PDF 생성 (과목 무관)")
    ap.add_argument("--bank", required=True, help="문항 뱅크 .py 경로 (MCQ, SA 정의)")
    ap.add_argument("--outdir", required=True, help="최종 PDF 저장 폴더")
    ap.add_argument("--htmlout", default=None, help="중간 산출물 HTML 폴더 (기본: <outdir>/work)")
    ap.add_argument("--title", required=True, help="단원명 (예: V. 식물과 에너지)")
    ap.add_argument("--subject", required=True, help="푸터/메타 (예: 천재 중학 과학 2 · 5장 식물과 에너지)")
    ap.add_argument("--rounds", type=int, default=3, help="회차 수 (기본 3)")
    ap.add_argument("--mcq-per", type=int, default=25, help="회차별 객관식 수 (기본 25)")
    ap.add_argument("--sa-per", type=int, default=5, help="회차별 주관식 수 (기본 5)")
    ap.add_argument("--tag", default="문제", help="파일명 접두 (예: 5장_식물과에너지_문제)")
    ap.add_argument("--ch4-ratio", type=float, default=0.5, help="4장 비율 (기본 0.5)")
    ap.add_argument("--ch5-ratio", type=float, default=0.5, help="5장 비율 (기본 0.5)")
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location("bank", a.bank)
    bank = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bank)
    MCQ, SA = bank.MCQ, bank.SA
    if len(MCQ) < a.mcq_per * a.rounds or len(SA) < a.sa_per * a.rounds:
        sys.exit(f"뱅크 부족: MCQ {len(MCQ)}/{a.mcq_per*a.rounds}, SA {len(SA)}/{a.sa_per*a.rounds} 필요")

    outdir = os.path.abspath(a.outdir)
    htmlout = a.htmlout or os.path.join(outdir, "work")
    os.makedirs(htmlout, exist_ok=True)

    # 4장/5장 균등 분배
    rounds_mcq = split_by_chapter(MCQ, a.mcq_per, (a.ch4_ratio, a.ch5_ratio))

    for r in range(a.rounds):
        mcq = rounds_mcq[r]
        sa = SA[r * a.sa_per:(r + 1) * a.sa_per]
        html = build_round(r + 1, a.title, a.subject, mcq, sa)
        html_path = os.path.join(htmlout, f"{a.tag}_0{r+1}.html")
        pdf_path = os.path.join(outdir, f"{a.tag}_0{r+1}.pdf")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        HTML(string=html).write_pdf(pdf_path)
        print(f"round{r+1}: {os.path.getsize(pdf_path)//1024}KB -> {pdf_path}")
    print("ALL_DONE")


if __name__ == "__main__":
    main()
