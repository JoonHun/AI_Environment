#!/usr/bin/env python3
"""
Joons Wiki — a self-contained, LAN-facing documentation server.

Design goals
------------
* One process, no build step. Reads *.md pages from ./site at request time,
  so editing a page is reflected on the next reload — no restart required.
* Auto-structured: the sidebar tree is derived from the directory layout of
  ./site plus a small `nav.yaml` that names/labels/guides sections and pages.
* Safe by default: any string that looks like a credential is masked in the
  rendered HTML (defense in depth — the source files keep their real values).

Run
---
    python3 server.py            # 0.0.0.0:5001 by default
    WIKI_HOST=127.0.0.1 WIKI_PORT=5001 python3 server.py

Only depends on: flask, markdown, waitress, pygments (all already present).
"""
from __future__ import annotations

import os
import re
import hashlib
import datetime
from pathlib import Path

import markdown
from flask import (
    Flask, render_template, abort, url_for, request, g
)

try:
    import yaml  # nav.yaml / config
    HAVE_YAML = True
except Exception:
    HAVE_YAML = False

# --------------------------------------------------------------------------- #
# Paths & config
# --------------------------------------------------------------------------- #
BASE = Path(__file__).resolve().parent
SITE = BASE / "site"
STATIC = BASE / "static"
NAV_FILE = BASE / "nav.yaml"

HOST = os.environ.get("WIKI_HOST", "0.0.0.0")
PORT = int(os.environ.get("WIKI_PORT", "5001"))

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")

# --------------------------------------------------------------------------- #
# Markdown renderer (tables + code highlighting, self-closing safe)
# --------------------------------------------------------------------------- #
_md = markdown.Markdown(
    extensions=[
        "extra",            # tables, fenced code, footnotes
        "sane_lists",
    ]
)
_md.reset()

FENCE_RE = re.compile(r"```(?P<lang>[\w+-]*)\n(?P<code>.*?)```", re.DOTALL)


def highlight_inner(code: str, lang: str) -> str:
    """Return pygments inline-styled spans only (no <pre> wrapper).

    Pygments' HtmlFormatter wraps the result in <pre>…</pre>; we strip that
    outer wrapper so we can embed the highlights inside our own
    <pre class="wiki-code"> element (cleaner borders, consistent line numbers).
    """
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, guess_lexer
        from pygments.formatters import HtmlFormatter
        try:
            lexer = get_lexer_by_name(lang)
        except Exception:
            lexer = guess_lexer(code)
        out = highlight(code, lexer, HtmlFormatter(noclasses=True, nowrap=True))
        # strip the leading <pre> and trailing </pre> the formatter adds
        import re as _re
        out = _re.sub(r"^<pre[^>]*>", "", out)
        out = _re.sub(r"</pre>$", "", out).strip("\n")
        return out
    except Exception:
        import html as _h
        return _h.escape(code)


def _code_sub(m: "re.Match") -> str:
    lang = m.group("lang") or ""
    inner = highlight_inner(m.group("code"), lang)
    attr = f' data-lang="{lang}"' if lang else ''
    return f'<pre class="wiki-code"{attr}><code>{inner}</code></pre>'


def md_to_html(text: str) -> str:
    text = text.lstrip("\ufeff")
    # Pre-highlight fenced code blocks so Pygments styling is inline (no external CSS needed)
    text = FENCE_RE.sub(_code_sub, text)
    _md.reset()
    return _md.convert(text)


# --------------------------------------------------------------------------- #
# Secret masking — never show real credentials in the rendered page.
# --------------------------------------------------------------------------- #
def _mask(val: str) -> str:
    v = val.strip()
    if len(v) <= 4:
        return "*" * len(v)
    return v[0] + "*" * (len(v) - 2) + v[-1]


# (regex, keep-group) — applied to the final HTML, before < and > are already
# in their final form. We target common credential shapes.
SECRET_PATTERNS = [
    # KEY=value   (env / .env / yaml / markdown tables)
    re.compile(
        r"""(?i)\b(?:BASIC_AUTH_(?:USERNAME|PASSWORD|SECRET)|
                 HERMES_DASHBOARD_BASIC_AUTH_USERNAME|
                 HERMES_DASHBOARD_BASIC_AUTH_PASSWORD|
                 HERMES_DASHBOARD_BASIC_AUTH_SECRET|
                 CODING_DISCORD_BOT_TOKEN|ENGLISH_DISCORD_BOT_TOKEN|
                 DISCORD_BOT_TOKEN|_TOKEN|TOKEN|API_KEY|SECRET|PASSWORD|PASS|
                 ALLOWED_USERS|ALLOWED_CHANNELS|FREE_RESPONSE_CHANNELS|USER_ID)
        (?P<sep>\s*[=:]\s*)
        (?P<val>[A-Za-z0-9_\-./+]+)""",
        re.VERBOSE,
    ),
    # Bearer / Authorization header literals
    re.compile(r"""(?i)\b(?:Bearer|Authorization)\s+(?P<val>[A-Za-z0-9_\-./+]{8,})"""),
    # long hex / base64-ish blobs that are pure secrets (>=24 chars, w/ key context)
    re.compile(r"""(?P<ctx>(?:SECRET|KEY|TOKEN|PASSWORD|PASS))\s*[=:]\s*(?P<val>[A-Za-z0-9_\-./+]{16,})""", re.I),
    # Discord/Slack snowflake IDs (17-19 digits) — PII, even when the key looks harmless
    re.compile(r"""(?i)(?P<sep>\s*[=:]\s*)(?P<val>\d{17,19})\b"""),
    # ghp_/gho_/ghe_/ghs_ GitHub tokens, sk- OpenAI-style keys (bare, no key= context)
    re.compile(r"""(?P<val>gh[posu]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{16,})"""),
]


def mask_secrets(html: str) -> str:
    for pat in SECRET_PATTERNS:
        def repl(m):
            # preserve whatever the pattern captured as `val`
            val = m.groupdict().get("val", "")
            if val is None:
                return m.group(0)
            return m.group(0).replace(val, _mask(val), 1)
        html = pat.sub(repl, html)
    return html


# --------------------------------------------------------------------------- #
# Page model
# --------------------------------------------------------------------------- #
def slug_to_parts(slug: str):
    # strip .md, keep the relative path under SITE
    p = Path(slug)
    if not p.parts or p.parts[0] == ".":
        return []
    return [x for x in p.parts[:-1]] + [p.parts[-1]]


class Page:
    __slots__ = ("slug", "path", "section", "title", "summary", "html",
                 "body_text", "mtime", "nav", "toc")

    def __init__(self, path: Path):
        self.path = path
        rel = path.relative_to(SITE).as_posix()
        # slug = relative path WITHOUT the .md extension (kept for URLs/nav)
        self.slug = rel[:-3] if rel.endswith(".md") else rel
        self.section = self.slug.rsplit("/", 1)[0] if "/" in self.slug else "_root"
        self._parse_file()

    def _parse_file(self) -> None:
        raw = self.path.read_text(encoding="utf-8")
        self.html = md_to_html(raw)
        self.html = mask_secrets(self.html)
        # title: first H1, else filename
        m = re.search(r"^#\s+(.+)$", raw, re.M)
        self.title = m.group(1).strip() if m else Path(self.slug).stem.replace("-", " ").replace("_", " ")
        # summary: [summary] tag, else first plain paragraph line
        s = re.search(r"^\s*>?\s*\[summary\]\s*(.+)$", raw, re.M)
        if s:
            self.summary = s.group(1).strip()
        else:
            tail = raw.split("#", 2)[-1]
            para = re.search(r"^([^\n#>*\[\]`]+)$", tail, re.M)
            self.summary = (para.group(1).strip() if para else "")[:160]
        # plain text for search
        body = FENCE_RE.sub("", raw)
        body = re.sub(r"^#{1,6}\s+", " ", body, flags=re.M)
        body = re.sub(r"[*_`>\-+|]", " ", body)
        self.body_text = " ".join((self.title or "") + " " + (self.summary or "") + " " + body)
        self.mtime = self.path.stat().st_mtime
        self.nav = _nav_meta(self.slug)
        self.html, self.toc = inject_heading_ids(self.html)

    def url(self):
        return url_for("page", slug=self.slug)


def _slugify_id(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text).strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^\w\-]", "", s, flags=re.UNICODE)
    return s or "section"


def inject_heading_ids(html: str) -> tuple:
    """Give every H2–H4 a stable id (deduped); return (new_html, toc_list).

    The id must be on the rendered heading tag itself so the right-rail
    TOC anchors + the copy-link feature line up with the body.
    """
    out = []
    seen = set()
    heading_re = re.compile(
        r"(<h[2-4])([^>]*?)(>)(.*?)(</h[2-4]>)", re.S
    )

    def add(m):
        open_tag, attrs, gt, inner, close = m.groups()
        level = int(open_tag[2])
        title = re.sub(r"<[^>]+>", "", inner).strip()
        base = _slugify_id(title)
        key, n = base, 0
        while key in seen:
            n += 1
            key = f"{base}-{n}"
        seen.add(key)
        out.append({"id": key, "title": title, "level": level})
        if 'id="' in attrs:
            return m.group(0)
        return f'{open_tag}{attrs} id="{key}"{gt}{inner}{close}'

    return heading_re.sub(add, html), out


# nav.yaml: { order:[...], sections:{dir:{label,icon?}}, pages:{slug:{label,icon?,summary?}} }
_nav_cache = None
nav_loaded = 0


def _load_nav() -> dict:
    global _nav_cache, nav_loaded
    if _nav_cache is not None:
        return _nav_cache
    nav: dict = {"order": [], "sections": {}, "pages": {}}
    if HAVE_YAML and NAV_FILE.exists():
        try:
            nav.update(yaml.safe_load(NAV_FILE.read_text(encoding="utf-8")) or {})
        except Exception as e:
            print(f"[wiki] nav.yaml ignored: {e}")
    elif NAV_FILE.exists():
        # minimal no-yaml fallback: treat as "order" lines = section dirs
        for i, line in enumerate(NAV_FILE.read_text(encoding="utf-8").splitlines()):
            line = line.strip("# \t")
            if line:
                nav["order"].append(line)
    _nav_cache = nav
    nav_loaded += 1
    return nav


def _nav_meta(slug: str) -> dict:
    n = _load_nav().get("pages", {}).get(slug, {})
    return n


def discover_pages():
    pages = []
    if not SITE.exists():
        return pages
    for p in sorted(SITE.rglob("*.md")):
        if p.name.startswith("_"):
            continue
        rel = p.relative_to(SITE).as_posix()
        if "node_modules" in rel or rel.startswith("."):
            continue
        pages.append(Page(p))
    # sort by nav order where provided
    order = _load_nav().get("order", [])
    def keyf(pg: Page):
        sec = pg.section
        i = order.index(sec) if sec in order else (len(order)
                                                   if all(s in order for s in [pg.section])
                                                   else 999)
        return (i, pg.slug)
    pages.sort(key=keyf)
    return pages


def group_pages(pages):
    groups = {}
    order = _load_nav().get("order", [])
    for pg in pages:
        groups.setdefault(pg.section, []).append(pg)
    # order sections: nav order first, then alphabetical
    def sec_key(s):
        return (order.index(s) if s in order else 999, s)
    out = []
    for s, lst in sorted(groups.items(), key=lambda kv: sec_key(kv[0])):
        label = _load_nav().get("sections", {}).get(s, {}).get("label",
                                                                s.replace("-", " ").replace("_", " ").title())
        icon = _load_nav().get("sections", {}).get(s, {}).get("icon", "")
        out.append({"id": s, "label": label, "icon": icon, "pages": lst})
    return out


def search_index(pages):
    # id, title, url, section, haystack
    idx = []
    for pg in pages:
        hay = f"{pg.title} {pg.summary} {pg.body_text}"
        idx.append({
            "id": slug_hash(pg.slug), "title": pg.title, "url": pg.url(),
            "section": pg.section, "hay": hay.lower(),
        })
    return idx


def slug_hash(slug: str):
    return hashlib.sha1(slug.encode()).hexdigest()[:16]


def find_page(slug: str) -> "Page|None":
    for pg in discover_pages():
        if pg.slug == slug:
            return pg
    return None


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
def section_label(section: str) -> str:
    n = _load_nav()
    meta = n.get("sections", {}).get(section)
    if meta and meta.get("label"):
        return meta["label"]
    return section.replace("-", " ").replace("_", " ").title()


def section_icon(section: str) -> str:
    n = _load_nav()
    meta = n.get("sections", {}).get(section)
    return (meta or {}).get("icon", "")


@app.context_processor
def inject_globals():
    return {
        "now": datetime.datetime.now(),
        "section_label": section_label,
        "section_icon": section_icon,
        "host_label": "192.168.219.115",
        "port_label": "5001",
    }


@app.route("/")
def index():
    return render_template("home.html", groups=group_pages(discover_pages()))


@app.route("/search")
def do_search():
    q = (request.args.get("q", "") or "").strip()
    results = []
    if q:
        ql = q.lower()
        for pg in discover_pages():
            hay = (f"{pg.title} {pg.summary} {pg.body_text}").lower()
            if ql in hay or all(tok in hay for tok in ql.split()):
                results.append(pg)
    return render_template("search.html", q=q, results=results,
                           groups=group_pages(discover_pages()))


@app.route("/p/<path:slug>")
def page(slug: str):
    cur = find_page(slug)
    if cur is None:
        abort(404)
    groups = group_pages(discover_pages())
    # prev/next in reading order
    flat = [p for g in groups for p in g["pages"]]
    try:
        i = flat.index(cur)
        prev = flat[i - 1] if i > 0 else None
        nxt = flat[i + 1] if i < len(flat) - 1 else None
    except ValueError:
        prev = nxt = None
    return render_template("page.html", page=cur, groups=groups,
                           prev=prev, nxt=nxt, active_slug=slug)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html", groups=group_pages(discover_pages())), 404


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # waitress is preferred (stable, threaded, real HTTP/1.1) for LAN serving
    try:
        from waitress import serve
        print(f"[wiki] waitress serving on http://{HOST}:{PORT}")
        serve(app, host=HOST, port=PORT, threads=8)
    except Exception as e:
        print(f"[wiki] waitress unavailable ({e}); falling back to Flask dev")
        app.run(host=HOST, port=PORT, threaded=True)
