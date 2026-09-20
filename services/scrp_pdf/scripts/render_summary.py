#!/usr/bin/env python3
"""render_summary.py — Markdown(요약) → HTML → A4 PDF (weasyprint)
범용 스크립트: 과목 무관. 어떤 과목의 work/ 폴더에 두고 사용.

Usage:
  python3 render_summary.py --md <요약.md> --html <요약.html> \
      --pdf <요약.pdf> --footer "천재 중학 과학 2 · 5장 식물과 에너지 요약"

- weasyprint가 없으면 상위 폴더에서 work/venv를 자동 탐색해 재실행 (venv 불필요).
- 중간 산출물(html)은 outdir의 work/에, 최종 pdf는 지정한 경로에 쓴다.
"""
import os, sys, subprocess

def _ensure_venv():
    """weasyprint가 없으면 상위에서 work/venv를 찾아 재실행."""
    try:
        import weasyprint  # noqa: F401
        return
    except ImportError:
        pass
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        for cand in (os.path.join(d, "venv", "bin", "python3"),
                     os.path.join(d, "work", "venv", "bin", "python3")):
            if os.path.exists(cand):
                os.execv(cand, [cand] + sys.argv)
        d = os.path.dirname(d)
    sys.exit("weasyprint not found, and no work/venv located above this script")

_ensure_venv()
from weasyprint import HTML
import markdown


CSS = """
@page {
  size: A4;
  margin: 16mm 15mm 18mm 15mm;
  @bottom-left  { content: "__FOOTER__"; font-family: 'Noto Sans CJK KR'; font-size: 7.5pt; color: #8a94a6; }
  @bottom-right { content: counter(page) " / " counter(pages); font-family: 'Noto Sans CJK KR'; font-size: 7.5pt; color: #8a94a6; }
}
* { box-sizing: border-box; }
body { font-family: 'Noto Sans CJK KR','Apple SD Gothic Neo',sans-serif;
       font-size: 10.5pt; line-height: 1.7; color: #1a1f2e; }
h1 { font-size: 15pt; margin: 0 0 4pt; padding-bottom: 5pt; border-bottom: 2.5pt solid #2a5298; }
h2 { font-size: 12pt; color: #2a5298; margin: 16pt 0 6pt; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; color: #1a1f2e; }
p  { margin: 5pt 0; }
ul,ol { margin: 4pt 0 4pt 2pt; padding-left: 18pt; }
li { margin: 2.5pt 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9.5pt; }
th,td { border: 0.5pt solid #c7cdd8; padding: 4pt 7pt; vertical-align: top; text-align: left; }
th { background: #eef2f9; font-weight: bold; }
tr:nth-child(even) td { background: #f7f9fc; }
strong { color: #14336b; }
code { font-family: 'Noto Sans Mono CJK KR', monospace; background: #f2f4f8; padding: 0 2pt; }
"""


def render(md_path, html_path, pdf_path, footer):
    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<style>{CSS.replace("__FOOTER__", footer)}</style>
</head>
<body>
{body}
</body></html>"""
    os.makedirs(os.path.dirname(html_path) or ".", exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    HTML(string=html).write_pdf(pdf_path)
    print(f"PDF_OK {os.path.getsize(pdf_path)//1024}KB -> {pdf_path}")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="요약 Markdown → A4 PDF")
    ap.add_argument("--md", required=True, help="입력 Markdown 파일")
    ap.add_argument("--html", required=True, help="중간 산출물 HTML 저장 경로")
    ap.add_argument("--pdf", required=True, help="최종 PDF 저장 경로")
    ap.add_argument("--footer", default="", help="하단 푸터 텍스트")
    a = ap.parse_args()
    render(a.md, a.html, a.pdf, a.footer)


if __name__ == "__main__":
    main()
