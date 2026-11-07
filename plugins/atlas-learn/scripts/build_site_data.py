#!/usr/bin/env python
"""Build the per-site data file from the written pages (contracts §8, §9).

Usage: python build_site_data.py <siteDir> [--quiet]

Reads assets/site.json, assets/glossary.json, index.html and every page under <pagesDir> (the `_*.html` skeletons are
skipped), plus the optional per-site JSON files the builders name (assets/notation.json, assets/changelog.json …), and
writes assets/data.js:
  window.QC_DATA = { "generated": "<ISO timestamp>", <one key per builder> };
Each feature block below registers a builder with @builder. A builder reads ctx.pages and sets ctx.data[<key>]; it may
also write extra files under the site with ctx.write(rel, text) (assets/manifest.json, assets/media.json …). The
runtime (app.js) reads window.QC_DATA and renders the indexes page, backlinks, evidence tables, the concept map, the
changelog and the study planner; every renderer tolerates a missing key, so a site built before a builder existed
still works. scaffold.py --sync runs this script after regenerating site.js and glossary.js; the compose skill runs it
once more before the final validate.py so the data reflects the finished pages. bundle.py inlines assets/data.js like
the other local scripts.

A builder that raises is reported as an error (the other builders still run); a page that cannot be parsed is a
warning. Problems print as `<file>:<line> message`. Ends with
  RESULT: tool=build_site_data status=PASS|FAIL pages=n keys=<comma list> written=<files> errors=n warnings=n
"""
from __future__ import annotations

import argparse
import datetime
import html as html_mod
import json
import posixpath
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, load_json, result_line, usage_error  # noqa: E402
from _common import notation_rows  # noqa: E402  (E3 scholar: the shared notation-table reader)

DATA_JS_HEADER = ("/* Site data — GENERATED from the pages by build_site_data.py (run by scaffold.py --sync); do not edit.\n"
                  "   window.QC_DATA keys are optional: the runtime renders what is there. */\n")
BUILDERS: list = []


def builder(fn):
    """Register a builder: fn(ctx) sets ctx.data[key] (and may ctx.write extra files). Order = registration order."""
    BUILDERS.append(fn)
    return fn


# ------------------------------------------------------------------ helpers
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def strip_tags(fragment: str) -> str:
    """Plain text of an HTML fragment: tags removed, entities decoded, whitespace collapsed."""
    return WS_RE.sub(" ", html_mod.unescape(TAG_RE.sub(" ", fragment))).strip()


def attr(tag: str, name: str) -> str | None:
    """Value of attribute `name` in one opening tag, or None."""
    m = re.search(r'\b' + re.escape(name) + r'\s*=\s*"([^"]*)"', tag)
    return html_mod.unescape(m.group(1)) if m else None


def line_of(s: str, pos: int) -> int:
    return s.count("\n", 0, pos) + 1


def blank_keep_lines(m) -> str:
    return "\n" * m.group(0).count("\n")


def data_js(data: dict) -> str:
    return DATA_JS_HEADER + "window.QC_DATA = " + json.dumps(data, indent=1, ensure_ascii=False) + ";\n"


class Page:
    """One page as the builders see it. Positions in `text`/`no_script` are comparable (comments and script bodies are
    blanked line-preservingly), so line numbers from either refer to the file."""

    def __init__(self, rp: str, raw: str, regp: dict | None):
        self.rp, self.name, self.folder = rp, posixpath.basename(rp), posixpath.dirname(rp)
        self.depth = len([x for x in self.folder.split("/") if x]) if self.folder else 0
        self.raw = raw
        self.text = re.sub(r"<!--[\s\S]*?-->", blank_keep_lines, raw)
        self.no_script = re.sub(r"<script[\s\S]*?</script>", blank_keep_lines, self.text)
        self.ids = {m.group(1) for m in re.finditer(r'\sid="([^"]+)"', self.text)}
        tm = re.search(r"<title>([^<]*)</title>", self.text)
        self.title = strip_tags(tm.group(1)) if tm else self.name
        self.regp = regp
        mm = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", self.no_script)
        self.main_start = mm.start(1) if mm else 0
        self.main = mm.group(1) if mm else self.no_script
        self.headings = []        # (level, id or None, plain text, position in no_script)
        for m in re.finditer(r"<h([1-4])\b([^>]*)>([\s\S]*?)</h\1>", self.main):
            txt = strip_tags(re.sub(r'<a class="anchor-link"[\s\S]*?</a>', "", m.group(3)))
            self.headings.append((int(m.group(1)), attr(m.group(2), "id"), txt, self.main_start + m.start()))

    def line(self, pos: int) -> int:
        return line_of(self.no_script, pos)

    def href_to(self, other: "Page", anchor: str | None = None) -> str:
        """A link from this page to another (same layout rules as app.js href())."""
        rel = posixpath.relpath(other.rp, self.folder or ".")
        return rel + ("#" + anchor if anchor else "")


class Ctx:
    def __init__(self, site: Path, reg: dict, glossary: list, pages: list, pages_dir: str, home: str, single: bool, rep: Report):
        self.site, self.reg, self.glossary, self.pages = site, reg, glossary, pages
        self.pages_dir, self.home, self.single = pages_dir, home, single
        self.by_name = {p.name: p for p in pages}
        self.data: dict = {}
        self.written: list[str] = []
        self.rep = rep

    def warn(self, file, line: int, msg: str) -> None:
        self.rep.warn(file, line, msg)

    def error(self, file, line: int, msg: str) -> None:
        self.rep.error(file, line, msg)

    def write(self, rel: str, text: str) -> None:
        """Write an extra output under the site folder (e.g. assets/manifest.json)."""
        p = self.site / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        self.written.append(rel)

    def load_optional_json(self, rel: str, default=None):
        """A per-site JSON file that may be absent; invalid JSON is a warning and yields the default."""
        p = self.site / rel
        if not p.exists():
            return default
        obj, err = load_json(p)
        if err:
            self.warn(p, 1, err)
            return default
        return obj


# ==== BLOCK nav — (no builder expected; F3 bilingual terms come from glossary.json directly) ====

# ==== END nav ====



# ==== BLOCK learn — (B5 site-wide outcome matrix reads the sitewide manifest's per-page bloom counts) ====
# learn registers no builder and owns no data.js key: the site-wide outcome matrix (B5, data-outcomes="site") renders
# DATA.manifest.pages[].bloom, which the sitewide manifest builder (G4) counts from every page's data-bloom tags; the
# runtime shows a note when the manifest or its bloom counts are absent.
# ==== END learn ====



# ==== BLOCK scholar — E3 notation: data["notation"] from assets/notation.json + table.notation rows on pages ====
@builder
def notation(ctx) -> None:
    """E3 notation: data["notation"] = { entries: [...], pages: n }. Entries come from assets/notation.json first ({symbol, tex?,
    meaning, unit?, kind?, value?, page?, anchor?}; symbol + meaning required, the rest optional) and then from every row of the
    table.notation / table.constants blocks on the pages (symbol = plain text of td.sym, tex = its inline-maths source, meaning,
    unit, value, where = the Where-defined / Source cell, page, anchor = the table's id or the nearest h2 above it). `pages` counts
    the pages that carry such a table. The runtime renders notation.html and the site search from this key."""
    nj = ctx.site / "assets" / "notation.json"
    entries: list[dict] = []
    raw = ctx.load_optional_json("assets/notation.json", [])
    if not isinstance(raw, list):
        ctx.warn(nj, 1, "assets/notation.json must be a JSON array — ignored")
        raw = []
    for i, e in enumerate(raw):
        if not isinstance(e, dict) or not str(e.get("symbol") or "").strip() or not str(e.get("meaning") or "").strip():
            ctx.warn(nj, 1, f"notation entry {i + 1} skipped: symbol and meaning are required")
            continue
        entries.append({"symbol": str(e["symbol"]).strip(), "tex": str(e.get("tex") or "").strip(), "meaning": str(e["meaning"]).strip(),
                        "unit": str(e.get("unit") or ""), "kind": "constant" if e.get("kind") == "constant" else "symbol",
                        "value": str(e.get("value") or ""), "page": posixpath.basename(str(e.get("page") or "")) or None,
                        "anchor": str(e.get("anchor") or "") or None, "where": ""})
    pages_n = 0
    for p in ctx.pages:
        rows = notation_rows(p.no_script)
        if not rows:
            continue
        pages_n += 1
        for r in rows:
            anchor = r["table_id"] or next((h[1] for h in reversed(p.headings) if h[0] == 2 and h[1] and h[3] < r["pos"]), None)
            entries.append({"symbol": r["symbol"], "tex": r["tex"], "meaning": r["meaning"], "unit": r["unit"], "kind": r["kind"],
                            "value": r["value"], "page": p.name, "anchor": anchor, "where": r["where"]})
    ctx.data["notation"] = {"entries": entries, "pages": pages_n}
# ==== END scholar ====



# ==== BLOCK visual — (no builder expected) ====

# ==== END visual ====



# ==== BLOCK plots — (no builder expected) ====

# ==== END plots ====



# ==== BLOCK compute — (no builder expected) ====

# ==== END compute ====



# ==== BLOCK sitewide — A1 data["indexes"] · A3 data["backlinks"] · E5 data["evidence"] · G4 data["manifest"] + assets/manifest.json · H6 assets/media.json ====
# sitewide: A1 indexes · A3 backlinks · E5 claim → evidence trace · G4 site manifest (+ assets/manifest.json) · H6 assets/media.json.
# One builder scans every page's <main> once with attribute-order-tolerant regexes and fills ctx.data["indexes"],
# ["backlinks"], ["evidence"] and ["manifest"]; every shape is documented in skills/compose/components/sitewide/README.md.
import bisect

SW_BLOOM = ("remember", "understand", "apply", "analyze", "evaluate", "create")
SW_FIGURE_KINDS = ("diagram", "photo", "embed", "compare", "fnplot", "field", "sweep")
SW_MEDIA_KINDS = ("photo", "embed", "compare")
# Licence as writers put it in .credit after the source link ("…, CC BY-SA 3.0"). The same expression lives in the sitewide
# block of validate.py (the "media without a licence" warning) — keep the two in step.
SW_LICENCE_RE = re.compile(r"(CC[ -]?BY(?:[ -](?:NC|ND|SA))*(?:[ -]\d\.\d)?|CC0(?:[ -]1\.0)?|Public domain|©[^,;<]*|\(c\)[^,;<]*|"
                           r"All rights reserved|MIT licen[cs]e|GPL[^,;<]*|Apache[^,;<]*|OGL[^,;<]*|Unsplash licen[cs]e|Pexels licen[cs]e)", re.I)
SW_BLOCK_START_RE = re.compile(r"<(?:p|li|td|dd|dt|figcaption|div|h[2-5])\b")
SW_SVG_STYLE_RE = re.compile(r"<svg\b[\s\S]*?</svg>|<style\b[\s\S]*?</style>")


def sw_classes(tag: str) -> list[str]:
    m = re.search(r'\bclass\s*=\s*"([^"]*)"', tag)
    return m.group(1).split() if m else []


def sw_cls_re(name: str) -> str:
    """Regex for an opening tag carrying class `name` anywhere in its class list."""
    return r'<\w+\b[^>]*\bclass="(?:[^"]*\s)?' + re.escape(name) + r'(?:\s[^"]*)?"[^>]*>'


def sw_block(text: str, start: int, tag: str) -> tuple[int, int]:
    """(body_start, body_end) of the element whose opening tag starts at `start`, nesting-aware; end = len(text) when unclosed."""
    pat = re.compile(r"<" + tag + r"\b[^>]*>|</" + tag + r">")
    m0 = pat.match(text, start)
    body_start = m0.end() if m0 else start
    depth = 1
    for m in pat.finditer(text, body_start):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return body_start, m.start()
    return body_start, len(text)


def sw_section_of(page: Page, pos: int):
    """(id, text) of the nearest h2 at or before `pos` (a position inside page.main); (None, None) in the hero."""
    best = (None, None)
    for level, hid, txt, hpos in page.headings:
        if level == 2 and hpos <= page.main_start + pos:
            best = (hid, txt)
    return best


def sw_short(fragment: str, n: int) -> str:
    s = strip_tags(fragment)
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def sw_num(caption_text: str):
    m = re.match(r"\s*((?:Figure|Fig\.|Video|Photo|Model|Document|Map|Plot|Listing)\s+[0-9][0-9A-Za-z.]*)", caption_text, re.I)
    return m.group(1) if m else None


def sw_resolve(by_rp: dict, page: Page, link: str):
    """`other.html#id`, `#id` or `other.html` from `page` -> (target Page or None, anchor or None)."""
    link = (link or "").strip()
    file, _, anc = link.partition("#")
    if ":" in file or file.startswith("//"):
        return None, None
    if not file:
        return page, (anc or None)
    file = file.replace("\\", "/").split("?")[0]
    if not file.endswith(".html"):
        return None, None
    rp = posixpath.normpath(posixpath.join(page.folder, file)) if page.folder else posixpath.normpath(file)
    if rp.startswith("./"):
        rp = rp[2:]
    return by_rp.get(rp), (anc or None)


def sw_ref(page: Page, key: str):
    """Body of the <li id=key> on `page` (an ol.refs entry), or None when no such list item exists."""
    m = re.search(r'<li\b[^>]*\sid="' + re.escape(key) + r'"[^>]*>', page.main)
    if not m:
        return None
    s, e = sw_block(page.main, m.start(), "li")
    return page.main[s:e]


def sw_ref_label(body: str, key: str) -> str:
    """`Authors (year)` from an ol.refs entry, else its link text, else the id."""
    am = re.search(sw_cls_re("ref-authors") + r"([\s\S]*?)</span>", body)
    ym = re.search(r"\((\d{4}[a-z]?)\)", strip_tags(body))
    if am:
        return strip_tags(am.group(1)) + (f" ({ym.group(1)})" if ym else "")
    lm = re.search(r"<a\b[^>]*>([\s\S]*?)</a>", body)
    return sw_short(lm.group(1), 80) if lm else key


def sw_verified(body: str) -> bool:
    return bool(re.search(r'\bclass="(?:[^"]*\s)?verified(?:\s[^"]*)?"', body or ""))


@builder
def sitewide(ctx) -> None:
    by_rp = {q.rp: q for q in ctx.pages}
    order = {p.get("file"): i for i, p in enumerate(p for p in ctx.reg.get("pages", []) if isinstance(p, dict))}
    figures, tables, equations, code, concepts, media, man_pages = [], [], [], [], [], [], []
    backlinks: dict = {}
    ev_pages: dict = {}
    ev_refs: dict = {}
    for page in sorted(ctx.pages, key=lambda q: (order.get(q.name, 999), q.rp)):
        main, pos0 = page.main, page.main_start
        regp = page.regp or {}
        starts = [m.start() for m in SW_BLOCK_START_RE.finditer(main)]
        # ---- figures (A1) and media (H6)
        n_fig = 0
        for m in re.finditer(r"<figure\b[^>]*>", main):
            n_fig += 1
            tag = m.group(0)
            cls = sw_classes(tag)
            kind = next((k for k in SW_FIGURE_KINDS if k in cls), None)
            s, e = sw_block(main, m.start(), "figure")
            body = main[s:e]
            cm = re.search(r"<figcaption\b[^>]*>([\s\S]*?)</figcaption>", body)
            cap_html = cm.group(1) if cm else ""
            caption = sw_short(cap_html, 160) or None
            fid = attr(tag, "id")
            sec_id, _ = sw_section_of(page, m.start())
            if kind:
                figures.append({"page": page.name, "id": fid, "num": sw_num(strip_tags(cap_html)), "caption": caption, "kind": kind, "section": sec_id})
            if kind in SW_MEDIA_KINDS:
                img = re.search(r"<img\b[^>]*>", body)
                crm = re.search(sw_cls_re("credit") + r"([\s\S]*?)</span>", body)
                credit_html = crm.group(1) if crm else ""
                link = re.search(r'<a\b[^>]*\shref="([^"]*)"', credit_html)
                after = credit_html.split("</a>", 1)[1] if "</a>" in credit_html else credit_html
                lic = SW_LICENCE_RE.search(after) or SW_LICENCE_RE.search(credit_html)
                media.append({
                    "page": page.name, "id": fid, "kind": "hotspots" if "data-hotspots" in tag else kind,
                    "src": attr(tag, "data-src") if kind == "embed" else (attr(img.group(0), "src") if img else None),
                    "alt": attr(img.group(0), "alt") if img else None, "title": attr(tag, "data-title"), "caption": caption,
                    "credit": strip_tags(credit_html) or None, "creditUrl": html_mod.unescape(link.group(1)) if link else None,
                    "licence": lic.group(1).strip() if lic else None,
                })
        # ---- tables (A1): title from the wrapping .table-wrap's .tt-title, else <caption>, else the header row
        wraps = []
        for wm in re.finditer(sw_cls_re("table-wrap"), main):
            s, e = sw_block(main, wm.start(), "div")
            tm = re.search(sw_cls_re("tt-title") + r"([\s\S]*?)</span>", main[s:e])
            wraps.append((s, e, strip_tags(tm.group(1)) if tm else None))
        n_tab = 0
        for m in re.finditer(r"<table\b[^>]*>", main):
            n_tab += 1
            s, e = sw_block(main, m.start(), "table")
            body = main[s:e]
            title = next((t for ws, we, t in wraps if ws <= m.start() < we and t), None)
            if not title:
                cm = re.search(r"<caption\b[^>]*>([\s\S]*?)</caption>", body)
                title = strip_tags(cm.group(1)) if cm else None
            if not title:
                title = " · ".join(strip_tags(t) for t in re.findall(r"<th\b[^>]*>([\s\S]*?)</th>", body)[:6]) or None
            tb = re.search(r"<tbody\b[^>]*>([\s\S]*?)</tbody>", body)
            if tb:
                rows = len(re.findall(r"<tr\b", tb.group(1)))
            else:
                head = re.search(r"<thead\b[\s\S]*?</thead>", body)
                rows = len(re.findall(r"<tr\b", body)) - (len(re.findall(r"<tr\b", head.group(0))) if head else 0)
            sec_id, _ = sw_section_of(page, m.start())
            tables.append({"page": page.name, "id": attr(m.group(0), "id"), "title": sw_short(title or "", 120) or None, "rows": rows, "section": sec_id})
        # ---- equations (A1): div.eq[id] numbered in page order (E2), .math5 blocks by their section
        n_eq = n_eq_box = 0
        for m in re.finditer(r'<div\b[^>]*\bclass="(?:[^"]*\s)?(eq|math5)(?:\s[^"]*)?"[^>]*>', main):
            kind, tag = m.group(1), m.group(0)
            eid = attr(tag, "id")
            if kind == "eq" and not eid:
                continue
            s, e = sw_block(main, m.start(), "div")
            tex = re.search(r"\$\$([\s\S]*?)\$\$", main[s:e])
            sec_id, sec_txt = sw_section_of(page, m.start())
            n_eq += 1
            if kind == "eq":
                n_eq_box += 1
                label = attr(tag, "data-label") or f"({n_eq_box})"
            else:
                label = sec_txt or "Five-step block"
            equations.append({"page": page.name, "id": eid or sec_id, "label": label, "kind": kind,
                              "tex": sw_short(tex.group(1), 120) if tex else None, "section": sec_id})
        # ---- code listings (A1)
        n_code = 0
        for m in re.finditer(r"<pre\b([^>]*)>\s*<code\b([^>]*)>([\s\S]*?)</code>", main):
            n_code += 1
            lm = re.search(r"lang(?:uage)?-([\w+-]+)", m.group(2))
            lang = lm.group(1) if lm else attr(m.group(1), "data-lang")
            first = next((l.strip() for l in html_mod.unescape(TAG_RE.sub("", m.group(3))).splitlines() if l.strip()), "")
            sec_id, _ = sw_section_of(page, m.start())
            code.append({"page": page.name, "id": attr(m.group(1), "id"), "lang": lang, "firstLine": first[:100], "section": sec_id})
        # ---- concepts (A1): every <dfn> on the page (glossary entries are added after the loop)
        terms = []
        for m in re.finditer(r"<dfn\b[^>]*>([\s\S]*?)</dfn>", main):
            t = strip_tags(m.group(1))
            if t:
                terms.append(t)
                sec_id, _ = sw_section_of(page, m.start())
                concepts.append({"term": t, "page": page.name, "anchor": sec_id, "source": "dfn"})
        # ---- backlinks (A3): every internal link, keyed by its target `page.html#id` / `page.html`
        for m in re.finditer(r'<a\b[^>]*\shref="([^"]*)"[^>]*>([\s\S]*?)</a>', main):
            tag = m.group(0)[:m.group(0).find(">") + 1]
            cls = sw_classes(tag)
            if "cite" in cls or "anchor-link" in cls:
                continue
            target, anc = sw_resolve(by_rp, page, m.group(1))
            if target is None:
                continue
            if target is page and (not ctx.single or not anc or anc.startswith(("ref-", "gl-"))):
                continue   # same-page links are navigation, not backlinks (single mode: parts link one another)
            sec_id, sec_txt = sw_section_of(page, m.start())
            entry = {"page": page.name, "id": sec_id, "text": sw_short(m.group(2), 80) or sec_txt or page.title}
            lst = backlinks.setdefault(target.name + ("#" + anc if anc else ""), [])
            if len(lst) < 50 and not any(x["page"] == entry["page"] and x["id"] == entry["id"] for x in lst):
                lst.append(entry)
        # ---- evidence (E5): span.claim[data-src] plus every a.cite outside a claim
        claims, refs = [], {}
        claim_spans = []

        def add_claim(pos: int, text_html: str, src):
            sec_id, _ = sw_section_of(page, pos)
            target, anc = sw_resolve(by_rp, page, src) if src else (None, None)
            key = verified = label = None
            if target is not None and anc:
                key = anc if target is page else target.name + "#" + anc
                body = sw_ref(target, anc)
                verified = sw_verified(body) if body is not None else False
                label = sw_ref_label(body, anc) if body is not None else anc
            claims.append({"text": sw_short(text_html, 200), "src": src or None, "section": sec_id, "verified": bool(verified), "ref": key})
            if key:
                r = refs.setdefault(key, {"cited": 0, "verified": bool(verified), "label": label})
                r["cited"] += 1
                sr = ev_refs.setdefault(target.name + "#" + anc, {"cited": 0, "pages": [], "verified": bool(verified), "label": label})
                sr["cited"] += 1
                if page.name not in sr["pages"]:
                    sr["pages"].append(page.name)

        for m in re.finditer(sw_cls_re("claim"), main):
            if not m.group(0).startswith("<span"):
                continue
            s, e = sw_block(main, m.start(), "span")
            claim_spans.append((m.start(), e))
            add_claim(m.start(), main[s:e], attr(m.group(0), "data-src"))
        for m in re.finditer(r"<a\b[^>]*>", main):
            if "cite" not in sw_classes(m.group(0)) or any(s <= m.start() < e for s, e in claim_spans):
                continue
            k = bisect.bisect_right(starts, m.start()) - 1
            before = strip_tags(main[starts[k]:m.start()]) if k >= 0 else ""
            sentence = re.split(r"[.!?]\s+", before)[-1].strip() if before else ""
            add_claim(m.start(), sentence or "(citation)", attr(m.group(0), "href"))
        ev_pages[page.name] = {"claims": claims, "refs": refs}
        # ---- manifest entry (G4)
        plain = strip_tags(SW_SVG_STYLE_RE.sub(" ", main))
        words = len(plain.split())
        bloom = {k: 0 for k in SW_BLOOM}
        for bm in re.finditer(r'\sdata-bloom="([^"]*)"', main):
            for tok in re.split(r"[\s,;]+", bm.group(1).strip().lower()):
                if tok in bloom:
                    bloom[tok] += 1
        n_refs = n_ver = 0
        for rm in re.finditer(r'<ol\b[^>]*\bclass="(?:[^"]*\s)?refs(?:\s[^"]*)?"[^>]*>', main):
            s, e = sw_block(main, rm.start(), "ol")
            ol = main[s:e]
            for lm in re.finditer(r"<li\b[^>]*>", ol):
                n_refs += 1
                ls, le = sw_block(ol, lm.start(), "li")
                n_ver += 1 if sw_verified(ol[ls:le]) else 0
        gl = re.search(sw_cls_re("trust-gaps") + r"([\s\S]*?)</details>", main)
        gaps = max(len(re.findall(r"<!--\s*GAP:", page.raw)), len(re.findall(r"<li\b", gl.group(1))) if gl else 0)
        tm = next((x for x in re.finditer(r"<section\b[^>]*>", main) if "trust" in sw_classes(x.group(0))), None)
        objectives = []
        om = re.search(r'<ol\b[^>]*\bclass="(?:[^"]*\s)?objectives(?:\s[^"]*)?"[^>]*>', main)
        if om:
            s, e = sw_block(main, om.start(), "ol")
            objectives = [strip_tags(x) for x in re.findall(r"<li\b[^>]*>([\s\S]*?)</li>", main[s:e])]
        h1 = next((txt for lv, _, txt, _ in page.headings if lv == 1), page.title)
        h2s = [(hid, txt, hpos - pos0) for lv, hid, txt, hpos in page.headings if lv == 2]
        bounds = [0] + [p for _, _, p in h2s] + [len(main)]
        sections = []
        for i, (hid, txt) in enumerate([(None, h1)] + [(a, b) for a, b, _ in h2s]):
            chunk = strip_tags(SW_SVG_STYLE_RE.sub(" ", main[bounds[i]:bounds[i + 1]]))
            if i and chunk.startswith(txt):
                chunk = chunk[len(txt):].strip()
            if chunk:
                sections.append({"id": hid, "heading": txt, "text": chunk[:4000]})
        man_pages.append({
            "file": page.name, "path": page.rp, "num": regp.get("num"), "title": regp.get("title") or page.title, "group": regp.get("group"),
            "level": regp.get("level"), "desc": regp.get("desc"), "words": words, "readingMin": max(1, -(-words // 220)) if words else 0,
            "headings": [{"level": lv, "id": hid, "text": txt} for lv, hid, txt, _ in page.headings if 2 <= lv <= 4],
            "objectives": objectives, "bloom": bloom,
            "counts": {"figures": n_fig, "tables": n_tab, "equations": n_eq, "code": n_code, "demos": len(re.findall(sw_cls_re("demo"), main)),
                       "quizzes": len(re.findall(sw_cls_re("quiz"), main)), "exercises": len(re.findall(sw_cls_re("exercise"), main)),
                       "refs": n_refs, "verified": n_ver, "gaps": gaps, "claims": len(claims)},
            "terms": terms, "reviewed": attr(tm.group(0), "data-reviewed") if tm else None, "sections": sections,
        })
    # ---- concepts A–Z: glossary entries first, then dfn's; one entry per (term, page)
    glossary = [g for g in ctx.glossary if isinstance(g, dict) and g.get("term")]
    for g in glossary:
        concepts.append({"term": str(g["term"]), "page": g.get("page"), "anchor": g.get("anchor"), "source": "glossary"})
    seen, uniq = set(), []
    for c in sorted(concepts, key=lambda c: (c["term"].casefold(), c["source"] != "glossary")):
        k = (c["term"].casefold(), c["page"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    ctx.data["indexes"] = {"figures": figures, "tables": tables, "equations": equations, "code": code, "concepts": uniq}
    ctx.data["backlinks"] = backlinks
    ctx.data["evidence"] = {"pages": ev_pages, "refs": ev_refs, "claims": sum(len(v["claims"]) for v in ev_pages.values()), "sources": len(ev_refs)}
    manifest = {"generated": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
                "title": ctx.reg.get("title"), "subtitle": ctx.reg.get("subtitle"), "storagePrefix": ctx.reg.get("storagePrefix")}
    for k in ("version", "licence"):
        if ctx.reg.get(k):
            manifest[k] = ctx.reg[k]
    manifest["pages"] = man_pages
    manifest["glossary"] = len(glossary)
    ctx.write("assets/manifest.json", json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    ctx.data["manifest"] = dict(manifest, pages=[{k: v for k, v in p.items() if k != "sections"} for p in man_pages])
    ctx.write("assets/media.json", json.dumps(media, indent=1, ensure_ascii=False) + "\n")
# ==== END sitewide ====



# ==== BLOCK pages — C12 data["concepts"] · E6 data["changelog"] (from assets/changelog.json) · F4 data["planner"] (hours per page) ====
PG_SLUG_RE = re.compile(r"[^a-z0-9]+")
PG_STUDY_RE = re.compile(r"<dt>\s*Study time\s*</dt>\s*<dd[^>]*>([\s\S]*?)</dd>", re.I)
PG_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
PG_MENTION_MIN = 4       # a term shorter than this is never a "mention" (too many false hits: "map", "SI" …)
PG_MENTION_MAX = 8       # mentions recorded per term


def pg_slug(s: str) -> str:
    """The id rule of app.js slug(): lower-case, tags out, runs of non-alphanumerics -> '-', one leading (else one trailing)
    '-' dropped, 60 chars — so concept ids equal the ids of the inline glossary widget (`gl-<slug>`)."""
    s = PG_SLUG_RE.sub("-", TAG_RE.sub("", str(s).lower()))
    if s.startswith("-"):
        s = s[1:]
    elif s.endswith("-"):
        s = s[:-1]
    return s[:60]


def pg_hours_from_text(text: str):
    """'≈ 20–30 h' -> 25; '8 h' -> 8; '90 min' -> 1.5; None when there is no number. A range gives its midpoint."""
    plain = strip_tags(text)
    nums = [float(n.replace(",", ".")) for n in PG_NUM_RE.findall(plain)]
    if not nums:
        return None
    v = (nums[0] + nums[1]) / 2 if len(nums) >= 2 else nums[0]
    if re.search(r"\bmin", plain, re.I) and not re.search(r"\bh\b|hour", plain, re.I):
        v = v / 60
    v = round(v, 2)
    return (int(v) if float(v).is_integer() else v) if v > 0 else None


@builder
def pages_concepts(ctx):
    """C12: data["concepts"] = { nodes: [{ id, term, page, anchor, group }], edges: [{ a, b, kind: related|mentions }] }.
    Nodes are the glossary entries (A–Z); `related` edges come from an entry's `related: ["Term", …]` list (names resolve
    against terms and akas, unknown names warn); `mentions` edges when another term's name (>= 4 chars, plural allowed)
    occurs in the definition, at most 8 per term. Every pair is listed once; a curated link wins over a mention."""
    gl_file = ctx.site / "assets" / "glossary.json"
    groups = {p["file"]: p.get("group") for p in ctx.reg.get("pages", []) if isinstance(p, dict) and p.get("file")}
    entries = [g for g in ctx.glossary if isinstance(g, dict) and isinstance(g.get("term"), str) and g["term"].strip()]
    entries.sort(key=lambda g: g["term"].strip().casefold())
    nodes, seen, by_name = [], set(), {}
    for g in entries:
        base = "gl-" + (pg_slug(g["term"]) or "term")
        nid, n = base, 2
        while nid in seen:
            nid, n = f"{base}-{n}", n + 1
        seen.add(nid)
        node = {"id": nid, "term": g["term"].strip(), "page": g.get("page") or "", "anchor": g.get("anchor") or "",
                "group": groups.get(g.get("page")) or "—"}
        nodes.append(node)
        by_name.setdefault(node["term"].casefold(), nid)
        for aka in re.split(r"\s*[,;]\s*", str(g.get("aka") or "")):
            if aka.strip():
                by_name.setdefault(aka.strip().casefold(), nid)
    edges, pairs = [], set()

    def add(a: str, b: str, kind: str) -> bool:
        key = (a, b) if a < b else (b, a)
        if a == b or key in pairs:
            return False
        pairs.add(key)
        edges.append({"a": a, "b": b, "kind": kind})
        return True

    for g, node in zip(entries, nodes):
        rel = g.get("related")
        if rel is None:
            continue
        if not isinstance(rel, list) or not all(isinstance(r, str) for r in rel):
            ctx.warn(gl_file, 1, f'glossary term "{node["term"]}": related must be a list of term names')
            continue
        for name in rel:
            tid = by_name.get(name.strip().casefold())
            if not tid:
                ctx.warn(gl_file, 1, f'glossary term "{node["term"]}": related "{name}" is not a glossary term')
            else:
                add(node["id"], tid, "related")
    names = sorted(((n["term"].casefold(), n["id"]) for n in nodes if len(n["term"]) >= PG_MENTION_MIN), key=lambda x: -len(x[0]))
    for g, node in zip(entries, nodes):
        low = str(g.get("def") or "").casefold()
        if not low:
            continue
        count = 0
        for term, tid in names:
            if tid == node["id"] or term not in low:
                continue
            if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?:s|es)?(?![a-z0-9])", low) and add(node["id"], tid, "mentions"):
                count += 1
                if count >= PG_MENTION_MAX:
                    break
    ctx.data["concepts"] = {"nodes": nodes, "edges": edges}


@builder
def pages_changelog(ctx):
    """E6: data["changelog"] = { version, entries: [{ date, version, note, pages }] sorted by date desc } from the optional
    assets/changelog.json; `version` is site.json's, else the newest entry's, else "". A missing file gives entries: []."""
    cl_file = ctx.site / "assets" / "changelog.json"
    raw = ctx.load_optional_json("assets/changelog.json", [])
    if not isinstance(raw, list):
        ctx.warn(cl_file, 1, "changelog.json must be a JSON array")
        raw = []
    entries = []
    for e in raw:
        if not isinstance(e, dict):
            continue
        pages = e.get("pages")
        entries.append({"date": str(e.get("date") or ""), "version": str(e.get("version") or ""), "note": str(e.get("note") or ""),
                        "pages": [str(p) for p in pages] if isinstance(pages, list) else []})
    entries.sort(key=lambda e: e["date"], reverse=True)   # stable: same-day entries keep the file order
    version = ctx.reg.get("version")
    version = str(version) if version is not None and str(version).strip() else (entries[0]["version"] if entries else "")
    ctx.data["changelog"] = {"version": version, "entries": entries}


@builder
def pages_planner(ctx):
    """F4: data["planner"] = { pages: [{ file, title, num, hours }] } — every registry page with a level (a module) and any
    other page with `hours`; hours from the registry (`Hours` column of the site plan), else the midpoint of the module
    hero's "Study time ≈ 20–30 h", else null (listed, not scheduled)."""
    out = []
    for rp in ctx.reg.get("pages", []):
        if not isinstance(rp, dict) or not rp.get("file"):
            continue
        hours = rp.get("hours")
        if isinstance(hours, bool) or not isinstance(hours, (int, float)) or hours <= 0:
            hours = None
        if hours is None:
            page = ctx.by_name.get(rp["file"])
            m = PG_STUDY_RE.search(page.main) if page else None
            if m:
                hours = pg_hours_from_text(m.group(1))
        if hours is None and not rp.get("level"):
            continue
        if isinstance(hours, float) and hours.is_integer():
            hours = int(hours)
        out.append({"file": rp["file"], "title": rp.get("title") or rp["file"], "num": str(rp.get("num") or ""), "hours": hours})
    ctx.data["planner"] = {"pages": out}
# ==== END pages ====



# ==== BLOCK pipeline — (no builder expected) ====

# ==== END pipeline ====



# --------------------------------------------------------------------- main
def load_pages(site: Path, reg: dict, rep: Report):
    """(pages, pages_dir, home, single) with the layout rules of validate.py."""
    pages_dir = reg.get("pagesDir", "") if isinstance(reg.get("pagesDir", ""), str) else ""
    home = reg.get("home") or "index.html"
    single = reg.get("mode") == "single"
    reg_pages = [p for p in reg.get("pages", []) if isinstance(p, dict) and "file" in p]
    rels: list[str] = []
    for f in sorted(site.glob("*.html")):
        if f.is_file() and not f.name.startswith("_") and (not pages_dir or f.name == home):
            rels.append(f.name)
    if pages_dir and (site / pages_dir).is_dir():
        rels += sorted(pages_dir + f.name for f in (site / pages_dir).glob("*.html") if not f.name.startswith("_"))
    pages = []
    for rp in rels:
        try:
            raw = (site / rp).read_text(encoding="utf-8-sig")
        except OSError as e:
            rep.warn(site / rp, 1, f"unreadable page skipped: {e}")
            continue
        regp = next((p for p in reg_pages if p["file"] == posixpath.basename(rp)), None)
        pages.append(Page(rp, raw, regp))
    return pages, pages_dir, home, single


def build(site: Path, rep: Report) -> dict:
    """Run every builder and write assets/data.js. Returns the RESULT pairs (status comes from rep)."""
    reg, err = load_json(site / "assets" / "site.json")
    if err or not isinstance(reg, dict):
        rep.error(site / "assets" / "site.json", 1, err or "site.json must be a JSON object")
        reg = {}
    glossary, gerr = load_json(site / "assets" / "glossary.json")
    if gerr or not isinstance(glossary, list):
        if gerr:
            rep.warn(site / "assets" / "glossary.json", 1, gerr)
        glossary = []
    pages, pages_dir, home, single = load_pages(site, reg, rep)
    ctx = Ctx(site, reg, glossary, pages, pages_dir, home, single, rep)
    for fn in BUILDERS:
        try:
            fn(ctx)
        except Exception as e:  # noqa: BLE001 — a builder bug must be visible, not fatal for the others
            tb = traceback.extract_tb(e.__traceback__)[-1]
            rep.error(Path(__file__), tb.lineno, f"builder {fn.__name__} failed: {type(e).__name__}: {e}")
    data = {"generated": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()}
    data.update(ctx.data)
    (site / "assets").mkdir(parents=True, exist_ok=True)
    (site / "assets" / "data.js").write_text(data_js(data), encoding="utf-8")
    written = ["assets/data.js"] + ctx.written
    return {"pages": len(pages), "keys": sorted(ctx.data) or ["none"], "written": written}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siteDir")
    ap.add_argument("--quiet", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    site = Path(args.siteDir).resolve()
    if not site.is_dir():
        return usage_error(f"no such directory: {site}")
    if not (site / "assets").is_dir():
        return usage_error(f"no assets/ folder in {site} — run scaffold.py first")
    rep = Report("tool", "build_site_data")
    extra = build(site, rep)
    if not args.quiet:
        for w in extra["written"]:
            print(f"wrote          {w}")
    return rep.finish(extra, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
