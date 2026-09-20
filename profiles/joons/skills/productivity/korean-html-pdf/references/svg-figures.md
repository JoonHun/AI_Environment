# Inline SVG geometry figures in weasyprint quiz PDFs (working skeleton)

Verified working for this user's 4장 (삼각형/사각형) rounds 2–5: figures render as clean vector (no tofu, no raster). Keep one **shared figure-helper module** so every round-set of a geometry chapter reuses the same figures; only the per-round question data differs.

## Builder module (`figs_ch4.py`)
Copy and adapt. Key invariants: `_pt` is called with TWO numeric args everywhere (`_pt(A[0],A[1])`, never `_pt(A)`); every `<text>` sets a CJK `font-family`; no stray string-join artifacts.

```python
import math
def _pt(*a):                       # _pt(x,y) only
    if len(a)==1 and isinstance(a[0], tuple): x,y=a[0]
    else: x,y=a
    return f"{x:.1f},{y:.1f}"

def _lab(x,y,txt,big=False,fill="#1f2430",anchor="middle"):
    s = 12 if big else 10.5
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{s}"
            font-family="Noto Sans CJK KR,sans-serif" fill="{fill}">{txt}</text>')

def _arc(P,d1,d2,r,fill="#0b3d91"):     # angle arc at vertex P between two directions
    x0=P[0]+r*math.cos(math.radians(d1)); y0=P[1]+r*math.sin(math.radians(d1))
    x1=P[0]+r*math.cos(math.radians(d2)); y1=P[1]+r*math.sin(math.radians(d2))
    large=1 if abs(d2-d1)>180 else 0
    sweep=1 if (d2-d1)%360>0 else 0
    return f'<path d="M {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 {large} {sweep} {x1:.1f} {y1:.1f}" fill="none" stroke="{fill}" stroke-width="1.4"/>'

def _ra(C,u1,u2,s=16,fill="#8a4b0b"):  # right-angle square at C (u1,u2 = unit leg directions)
    # s=16 (NOT 9) — user explicitly asked for larger, more visible right-angle marks
    A=(C[0]+u1[0]*s, C[1]+u1[1]*s); B=(C[0]+u2[0]*s, C[1]+u2[1]*s)
    P=(C[0]+u1[0]*s+u2[0]*s, C[1]+u1[1]*s+u2[1]*s)
    return f'<path d="M {_pt(A[0],A[1])} L {_pt(P[0],P[1])} L {_pt(B[0],B[1])}" fill="none" stroke="{fill}" stroke-width="1.8"/>'

def _tri(A,B,C): return f'<path d="M {_pt(A[0],A[1])} L {_pt(B[0],B[1])} L {_pt(C[0],C[1])} Z" fill="#f5f8fd" stroke="#2c3546" stroke-width="1.6"/>'
def _quad(P,Q,R,S): return f'<path d="M {_pt(P[0],P[1])} L {_pt(Q[0],Q[1])} L {_pt(R[0],R[1])} L {_pt(S[0],S[1])} Z" fill="#f5f8fd" stroke="#2c3546" stroke-width="1.6"/>'
def _ptc(P,c="#0b3d91",r=3.4): return f'<circle cx="{P[0]:.1f}" cy="{P[1]:.1f}" r="{r}" fill="{c}"/>'
def _fig(inner,w=240,h=150):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" height="90" '
            f'style="background:#fbfcfe;border:1px solid #dbe2ec;border-radius:6px;">{inner}</svg>')
```

## Two example figures + a shared figure block
```python
def fig1():  # 이등변삼각형, 꼭짓각 A
    A=(120,18); B=(62,126); C=(178,126)
    s=_tri(A,B,C)+_arc(A,120,240,16)
    s+=_ptc(A)+_lab(120,10,"A",big=True)+_ptc(B)+_lab(54,134,"B",big=True)+_ptc(C)+_lab(186,134,"C",big=True)
    return _fig(s)

def fig2():  # 직각삼각형 ∠C=90, ∠A=30
    B=(55,120); C=(180,120); A=(110,32)
    def unit(P,Q):
        d=math.hypot(Q[0]-P[0],Q[1]-P[1]); return ((Q[0]-P[0])/d,(Q[1]-P[1])/d)
    s=_tri(A,B,C)+_ra(C,unit(C,A),unit(C,B))+_arc(A,90,150,14)+_arc(B,0,60,14)
    s+=_ptc(A)+_lab(104,22,"A",big=True)+_ptc(B)+_lab(47,130,"B",big=True)+_ptc(C)+_lab(188,130,"C",big=True)
    s+=_lab(96,110,"30°",fill="#0b3d91",anchor="end")
    return _fig(s)

FIGS=[ ("도 1","이등변삼각형 ABC (꼭짓각 ∠A)",fig1),
       ("도 2","직각삼각형 ABC (∠C=90°, ∠A=30°)",fig2) ]   # …도 3~9 (평행사변형/정사각형/사다리꼴/직사각형/내심/외심)

def fig_block():
    out=[]
    for name,cap,f in FIGS:
        out.append(f'<div style="display:flex;gap:8pt;align-items:center;page-break-inside:avoid;">'
                   f'<div style="flex:0 0 230px;">{f()}</div>'
                   f'<div style="flex:1;font-size:9.5pt;color:#2c3546;"><strong style="color:#0b3d91;">{name}</strong>. {cap}</div></div>')
    return '\n'.join(out)
```

## Wiring into the quiz
- In the FRONT, after the `I. 객관식` block and before `II. 주관식`, emit:
  `body.append('<h2>참고 도형 (도 1–9)</h2>'); body.append(figs_ch4.fig_block())`
- Cite figures inside question stems with `[도 N]` (e.g. `[도 3] 평행사변형 ABCD에서 ∠B=110°일 때…`); students read the figure from the shared section.
- Reuse the SAME `fig_block()` in every round-set (`2회`, `3회`, `4회`, `5회`) of the chapter — import the module rather than re-drawing. Figures shared, per-round MC/SBJ data differs.

## Verification (must be visual)
- `get_text()` finds the figure CAPTIONS but NOT the drawn geometry — text search & `verify_layout.py` stay silent about figure bugs. Locate the figure page by searching its caption ("참고 도형" / "도 1."), then `get_pixmap(dpi≈110)` + vision.
- In the vision check confirm, per figure: the shape is closed, vertex labels (A/B/C) present, any angle arc present, any right-angle square present; no missing/double labels (a stray `"_"` between dot and label is the classic artifact).

## Known pitfalls (all hit this session)
1. `_pt(A)` vs `_pt(A[0],A[1])` — a single wrong call style raises `TypeError: _pt() missing 1 required positional argument` on the FIRST figure, aborting the whole render. Keep one convention.
2. `"+"_""` string join left a literal underscore in the output (`_ptc(A)+"_"+_lab(...)` → label prefixed with `_`). Strip it.
3. SVG `<text>` without an explicit CJK `font-family` can fall back; always set `font-family="Noto Sans CJK KR,sans-serif"` per label.
4. The `#answer-key { page-break-before: always }` rule still applies — figures live in the FRONT, so they never bleed onto the answer-key page.
5. `_ra` default `s=9` is too small at 240×150 viewBox — user explicitly asked to make it bigger. **Always use `s=16, stroke-width=1.8`.** When retrofitting an existing HTML with the small right-angle squares: recompute the 3 path points with the new `s` value (e.g. for C=(180,120), u1≈(-0.44,-0.90), u2=(-1,0): `M 172.9,105.7 L 156.9,105.7 L 164.0,120.0`), and replace `stroke-width="1.2"` → `1.8` on the `#8a4b0b` path. Then just re-render the HTML to PDF — no need to rebuild the question data.
