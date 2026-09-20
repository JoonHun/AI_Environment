# scrp_pdf — 교과서 스캔 → 요약 · 시험문제 PDF 파이프라인

교과서(스캔/StreamDocs)를 받아 **단원 요약 PDF**와 **시험문제 N회차 PDF**(객관식+주관식+문제풀이)를
생성하는 **공용 스크립트 모음**. 과목 무관 — 아래 절차만 따라 다른 과목에도 바로 재사용.

## 폴더 구조
```
scrp_pdf/
├── scripts/                 ← [공용 코드] 과목 무관 스크립트 (여기가 단일 소스)
│   ├── fetch_pages.py         StreamDocs 페이지 이미지 PNG 다운로드 (8스레드, retry)
│   ├── assemble_pdf.py        페이지 PNG → 고화질 원본 PDF (img2pdf, 무압축)
│   ├── prep_pages.py          스프레드 PNG → 페이지별 JPEG (비전 전사용, ~1200px)
│   ├── transcribe.py          로컬 gemma4:26b 비전으로 한글 전사 (Ollama 11434)
│   ├── render_summary.py      요약 Markdown → A4 PDF (weasyprint)
│   ├── render_exam.py         문항 뱅크 → N회차 시험문제 PDF (weasyprint)
│   └── README.md              이 문서
├── work/
│   └── venv/                 ← 공유 Python venv (weasyprint, pymupdf, markdown, img2pdf, Pillow)
└── out/
    └── <과목>/                 예) 과학2
        ├── <원본>_교과서.pdf   원본 고화질 (최종)
        ├── <단원>_요약.md      요약 소스 (최종)
        ├── <단원>_요약.pdf     최종 요약 PDF (최종)
        ├── <단원>_문제_01~03.pdf  최종 문제 PDF (회차별, 최종)
        ├── pages/              원본 페이지 PNG (중간)
        └── work/               [중간 산출물 + 과목별 데이터]
            ├── <단원>_전사본.txt  비전 전사본 (과목 데이터)
            ├── exam_bank.py     과목별 문항 뱅크 (MCQ/SA)
            └── *.html           렌더 중간 산출물
```
**원칙:** 코드는 `scripts/`에 공용 · 문항 뱅크/전사본(데이터)은 과목 `out/<과목>/work/`에 ·
최종 PDF만 `out/<과목>/` 최상위 · 중간 산출물은 `out/<과목>/work/`에 보관(삭제 금지).

## Python 환경
- 공용 venv: `scrp_pdf/work/venv` (weasyprint, pymupdf, markdown, img2pdf, Pillow).
- `render_summary.py`/`render_exam.py`는 weasyprint가 없으면 **자동으로** 상위 `work/venv`를
  찾아 재실행 → 일반 `python3 scripts/...`로 실행해도 됨.
  수동: `scrp_pdf/work/venv/bin/python3 scripts/...`
- 전사(1~3단계)는 Ollama 로컬 비전모델(`gemma4:26b`) 사용.
  `pip3 install --user --break-system-packages img2pdf Pillow` 필요.

---

## 단계별 절차 (다른 과목에 재사용)

### 0) StreamDocs 페이지 이미지 다운로드
```
cd scrp_pdf
python3 scripts/fetch_pages.py <docId> <페이지수> out/<과목>/pages
```
`pages/`에 `000.png…` 생성 (4268×2779px).

### 1) 원본 고화질 PDF 합성
```
python3 scripts/assemble_pdf.py out/<과목>/pages <페이지수> out/<과목>/<원본>_교과서.pdf
```

### 2) 비전 전사 (요약/문제 작성의 근거 텍스트)
```
# 스프레드 PNG → 페이지별 JPEG (1200px)
python3 scripts/prep_pages.py out/<과목>/pages <start> <end_incl> /tmp/jpg <width=1200>
# 각 JPEG → 한글 전사 (Ollama gemma4:26b, 12~28초/장)
python3 scripts/transcribe.py <jpeg> [커스텀 프롬프트]
```
> 페이지 매핑: 스프레드 `s` = 인쇄 페이지 `2s, 2s+1`. 목차로 단원 시작/끝 스프레드 확인 후 범위만 전사.
> 결과 텍스트는 `out/<과목>/work/<단원>_전사본.txt`에 보관.

### 3) 단원 요약 PDF
`out/<과목>/<단원>_요약.md` 작성(이해 가능한 수준, 표 활용) 후:
```
python3 scripts/render_summary.py \
  --md   out/<과목>/<단원>_요약.md \
  --html out/<과목>/work/<단원>_요약.html \
  --pdf  out/<과목>/<단원>_요약.pdf \
  --footer "천재 중학 과학 2 · 5장 식물과 에너지 요약"
```

### 4) 시험문제 N회차 PDF
먼저 과목별 문항 뱅크 `out/<과목>/work/exam_bank.py` 작성. 형식:
```python
# MCQ: (주제, 문항, 정답, [오답 3개], 해설)  — 객관식 회차수×20 개 (무중복 권장)
MCQ = [
  ("기본개념", "식물이 광합성에서 빛에너지를 화학에너지로 바꾸는 과정에 꼭 필요한 것은?",
   "엽록체", ["미토콘드리아", "핵", "리보솜"], "광합성은 엽록체에서 일어남."),
  # ... 60개
]
# SA: (문항, 모범답안, [채점기준...]) — 주관식 회차수×5 개
SA = [
  ("식물이 광합성에서 이산화탄소를 원료로 하는 이유를 설명", "광합성에서 탄소 고정이 필요…",
   ["이산화탄소 언급", "탄소 고정/무기탄소", "광합성 산물 연결"]),
  # ... 15개
]
```
그리고:
```
python3 scripts/render_exam.py \
  --bank    out/<과목>/work/exam_bank.py \
  --outdir  out/<과목> \
  --title   "V. 식물과 에너지" \
  --subject "천재 중학 과학 2 · 5장 식물과 에너지" \
  --rounds  3 \
  --tag     "5장_식물과에너지_문제"
```
- `--mcq-per`(기본 20)·`--sa-per`(기본 5)로 회차별 문항 수 조절
- `--htmlout` 생략 시 중간 산출물 HTML은 `<outdir>/work/`에 자동 저장
- 생성: `<tag>_01.pdf` ~ `<tag>_03.pdf` (최종, 최상위) + `work/<tag>_01.html` ~ (중간)

## 출력 규격 (과목 공통)
- A4, 한글 깨짐(tofu) 0, **문제 경계넘김 방지**(`page-break-inside: avoid`)
- 회차별 구성: **객관식 20**(①②③④ 2열, 정답 위치 균등 분포) + **주관식 5**(사각 박스 답란)
  + **문제풀이**(새 페이지부터, 객관식=번호+정답+해설 / 주관식=채점기준+모범답안)
- "풀이"가 아닌 **"문제풀이"** 문구 사용 · 본문 10.5pt(약간 크게)

## 검증
생성 후 pymupdf로 페이지 수/한글 깨짐/문제 분할 확인:
```
scrp_pdf/work/venv/bin/python3 -c "import pymupdf as f;d=f.open('out/과학2/5장_식물과에너지_문제_01.pdf');print('pages',len(d));[print(i,('□' in d[i].get_text())) for i in range(len(d))]"
```
로컬 비전으로 시각 확인: `scripts/transcribe.py <렌더된 png> "한글 깨짐/레이아웃 확인"`
