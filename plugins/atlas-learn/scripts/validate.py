#!/usr/bin/env python
"""Lectern site validator — run after every writing pass and before hand-off.

Usage: python validate.py <siteDir> [--pages a.html,b.html] [--quiet]

Layout: the site root is the topic folder (topics/<slug>/); site.json `pagesDir` ("pages/" by default from
scaffold.py; "" = flat). index.html and assets/ sit at the site root; every other page under <pagesDir>.
Registry `file` and `data-page` are bare file names. The topic's PLAN.md, topic.json and tmp/ are not part of
the site and are ignored; so is any non-html file at the root.

Site-level: assets/site.json and assets/glossary.json parse and have the right shape (incl. the optional `theme`
hex colours); assets/site.js and assets/glossary.js equal their generated form (else run scaffold.py --sync);
registry <-> files; pages outside <pagesDir>; duplicate page nums; glossary entries and page targets;
assets/style.css and assets/app.js exist; app.js syntax (node).
Page-level (every page, or only --pages): required includes (../assets/… under pagesDir, assets/… at the root),
<title>, <main>, data-page, inline-script syntax (node), tag balance, duplicate ids, $$ parity, \\( \\) parity,
hard-coded SVG colours, internal links and anchors (resolved from the page's own folder), quiz answer ranges,
table-tool targets, output[for] bindings, photo attribution, embed data-src, the trust footer (every page except the
home page and glossary.html: section.trust with a real data-reviewed date, h2#trust, last section of <main>), exercises
(id, a details.solution that is closed by default, data-difficulty 1..3), step-through diagrams (>= 2 g[data-step] layers,
caption count = step count), module-page required ids, quizzes and ol.refs on module pages. HTML comments are ignored
everywhere (writers may leave <!-- GAP: … --> markers; the runtime counts them in the trust footer).
Single mode (site.json `"mode": "single"`, the source of a one-page guide, usually topics/<slug>/tmp/site/): the
registry lists exactly one page, the home; no other page may exist; the home page needs #summary, #checkpoints,
#glossary, #references, an ol.refs, a [data-glossary] widget, >= 1 section.part (data-part="M01"/"S01", an h2 with
an id), and the trust footer like any other page; glossary entries point to the home page; a page over
`budgetKb` (default 250) is a warning, not an error.
Problems print as `<file>:<line> <message>` (line 0 when the check has no position). Ends with
  RESULT: gate=site status=PASS|FAIL pages=n bad_pages=n site_issues=n bytes=n js_syntax=checked|skipped mode=single|site
"""
from __future__ import annotations

import argparse
import datetime
import json
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, glossary_js, load_json, result_line, site_js, usage_error, validate_theme  # noqa: E402
from _common import notation_rows  # noqa: E402  (E3 scholar: the shared notation-table reader)

ASSET_INCLUDES = ["assets/style.css", "assets/site.js", "assets/app.js"]
CDN_INCLUDES = ["katex.min.css", "auto-render"]
BALANCED_TAGS = ["main", "section", "div", "details", "summary", "figure", "svg", "g", "text", "a", "table", "thead",
                 "tbody", "tr", "ol", "ul", "pre", "label", "button", "span", "p"]
MODULE_IDS = ["objectives", "mistakes", "reading", "checkpoints", "deliverable"]
SINGLE_IDS = ["summary", "checkpoints", "glossary", "references"]
DEFAULT_BUDGET_KB = 250
NODE_PROG = ("const vm=require('vm'),fs=require('fs');for(const f of process.argv.slice(1)){"
             "try{new vm.Script(fs.readFileSync(f,'utf8'))}catch(e){console.log(f+'\\t'+e.message)}}")


def is_date(value: str) -> bool:
    """YYYY-MM-DD and a real calendar date."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        return False
    try:
        datetime.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def line_of(s: str, pos: int) -> int:
    return s.count("\n", 0, pos) + 1


def blank_keep_lines(m) -> str:
    return "\n" * m.group(0).count("\n")


JS_SCRIPT_TYPES = {"", "text/javascript", "application/javascript", "module", "text/ecmascript", "application/ecmascript"}   # other types are data


def node_check(snippets: list[tuple[str, str]]) -> dict[str, str] | None:
    """snippets: [(key, code)] -> {key: error}; None when node is unavailable."""
    node = shutil.which("node")
    if not node:
        return None
    if not snippets:
        return {}
    errors: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="atlas-learn-validate-") as td:
        paths = {}
        for i, (key, code) in enumerate(snippets):
            p = Path(td) / f"s{i}.js"
            p.write_text(code, encoding="utf-8")
            paths[str(p)] = key
        files = list(paths)
        for start in range(0, len(files), 80):
            batch = files[start:start + 80]
            try:
                out = subprocess.run([node, "-e", NODE_PROG, *batch], capture_output=True, text=True, timeout=120)
            except (subprocess.SubprocessError, OSError) as e:
                return {"__node__": f"node failed: {e}"}
            for line in (out.stdout or "").splitlines():
                if "\t" in line:
                    f, msg = line.split("\t", 1)
                    errors[paths.get(f, f)] = msg
    return errors


# ------------------------------------------------------------- feature checks
# The feature blocks below register checks here. A page check runs once per selected page with a PageCtx; a site check
# runs once, after every page was read, with a SiteCtx. Checks report through the context (never print), so routing
# per page, the counts and the RESULT line stay in main(). Messages are short, lower-case, and name the id involved.
PAGE_CHECKS: list = []
SITE_CHECKS: list = []


def page_check(fn):
    PAGE_CHECKS.append(fn)
    return fn


def site_check(fn):
    SITE_CHECKS.append(fn)
    return fn


class SiteCtx:
    """Everything a site-level check may read; errors count as site issues, warnings never fail the gate."""

    def __init__(self, site: Path, reg, glossary, pages: dict, ids: dict, pages_dir: str, home: str, single: bool, selected: list, rep: Report, site_issue):
        self.site, self.reg, self.glossary = site, reg, glossary
        self.pages, self.ids = pages, ids                 # rel path -> page text (comments blanked); rel path -> set of ids
        self.pages_dir, self.home, self.single, self.selected = pages_dir, home, single, selected
        self.extra: dict = {}                             # extra key=value pairs appended to the RESULT line
        self._rep, self._site_issue = rep, site_issue

    def error(self, file, line: int, msg: str) -> None:
        self._site_issue(file, line, msg)

    def warn(self, file, line: int, msg: str) -> None:
        self._rep.warn(file, line, msg)

    def asset(self, name: str) -> Path:
        return self.site / "assets" / name


class PageCtx:
    """Everything a page-level check may read; errors go to the page's issue list (routed to its writer)."""

    def __init__(self, sctx: SiteCtx, rp: str, s: str, no_script: str, issues: list, regp):
        self.site_ctx, self.site, self.reg, self.glossary = sctx, sctx.site, sctx.reg, sctx.glossary
        self.rp, self.name, self.folder = rp, posixpath.basename(rp), posixpath.dirname(rp)
        self.depth = len([x for x in self.folder.split("/") if x]) if self.folder else 0
        self.s, self.no_script = s, no_script             # page text with comments blanked; the same with <script> bodies blanked
        self.ids, self.own_ids = sctx.ids, sctx.ids.get(rp, set())
        self.regp = regp                                  # the page's registry entry, or None
        self.pages_dir, self.home, self.single = sctx.pages_dir, sctx.home, sctx.single
        self.is_home = self.name == sctx.home
        self._issues = issues

    def line(self, pos: int) -> int:
        return line_of(self.no_script, pos)

    def error(self, line: int, msg: str) -> None:
        self._issues.append((line, msg))

    def warn(self, line: int, msg: str) -> None:
        self.site_ctx.warn(self.site / self.rp, line, msg)

    def resolve(self, link: str):
        """`page.html#id`, `#id` or `page.html`, relative to this page -> (target rel path or None, anchor or None, exists)."""
        link = (link or "").strip()
        if link.startswith("#"):
            anc = link[1:]
            return self.rp, (anc or None), (not anc or anc in self.own_ids)
        page, _, anc = link.partition("#")
        page = page.replace("\\", "/")
        target = posixpath.normpath(posixpath.join(self.folder, page)) if self.folder else posixpath.normpath(page)
        if target.startswith("./"):
            target = target[2:]
        known = target in self.ids
        ok = known and (not anc or anc in self.ids[target])
        return (target if known else None), (anc or None), ok


# ==== BLOCK nav — A2 section metadata · A4 breadcrumb and keyboard shortcuts · F2 reading settings · F3 bilingual glossary · H3 automatic glossary links ====
# A4, F2 and H3 are runtime-only (no markup contract to check). F2's site.json `a11y` values are checked by the pipeline block.
NAV_H2_RE = re.compile(r"<h2\b([^>]*)>")
NAV_H3_META_RE = re.compile(r"<h3\b[^>]*\s(data-prereq|data-related)=")


@page_check
def nav_a2_section_meta(p: PageCtx) -> None:
    """A2: every data-prereq / data-related target on an h2 resolves like a link; data-reviewed on an h2 is a date."""
    for m in NAV_H2_RE.finditer(p.no_script):
        tag, ln = m.group(1), p.line(m.start())
        for name, label in (("data-prereq", "prerequisite"), ("data-related", "related")):
            am = re.search(r"\s" + name + r'="([^"]*)"', tag)
            if not am:
                continue
            targets = [x.strip() for x in am.group(1).split(",") if x.strip()]
            if not targets:
                p.warn(ln, f"section meta: {name} is empty")
            for link in targets:
                if not p.resolve(link)[2]:
                    p.error(ln, f"section meta: {label} {link} not found")
        rm = re.search(r'\sdata-reviewed="([^"]*)"', tag)
        if rm and not is_date(rm.group(1)):
            p.error(ln, f'section meta: data-reviewed "{rm.group(1)}" is not a date')
    for m in NAV_H3_META_RE.finditer(p.no_script):
        p.warn(p.line(m.start()), f"section meta: {m.group(1)} on <h3> is ignored (h2 only)")


@site_check
def nav_f3_bilingual_glossary(s: SiteCtx) -> None:
    """F3: term_local / def_local are strings; secondLanguage and term_local come together (warnings when one is missing)."""
    sj_p, gl_p = s.asset("site.json"), s.asset("glossary.json")
    second = s.reg.get("secondLanguage") if isinstance(s.reg, dict) else None
    if second is not None and (not isinstance(second, str) or not second.strip()):
        s.error(sj_p, 1, "site.json secondLanguage must be a non-empty string")
        second = None
    n_local = 0
    for g in s.glossary:
        if not isinstance(g, dict) or not g.get("term"):
            continue
        for key in ("term_local", "def_local"):
            if key in g and not isinstance(g[key], str):
                s.error(gl_p, 1, f'glossary term "{g["term"]}": {key} must be a string')
        if isinstance(g.get("term_local"), str) and g["term_local"].strip():
            n_local += 1
    if second and not n_local:
        s.warn(gl_p, 1, f'secondLanguage "{second}" is set but no glossary entry has term_local')
    if n_local and not second:
        s.warn(sj_p, 1, f"{n_local} glossary entr{'y has' if n_local == 1 else 'ies have'} term_local but site.json has no secondLanguage")
    if n_local:
        s.extra["bilingual"] = n_local

# ==== END nav ====



# ==== BLOCK learn — B3 instructor and handout modes · B5 Bloom tags and outcome matrix · B6 predict-then-reveal · B7 lab template ====
import html as _learn_html  # noqa: E402 — the learn block decodes entities when it tests a block for text

LEARN_BLOOM = ("remember", "understand", "apply", "analyze", "evaluate", "create")


def _learn_cls(tag: str, cls: str) -> bool:
    """True when the opening tag's class list contains `cls` (any attribute order, any other classes)."""
    return re.search(r'\bclass="(?:[^"]*\s)?' + re.escape(cls) + r'(?:\s[^"]*)?"', tag) is not None


def _learn_attr(tag: str, name: str):
    m = re.search(r'\s' + re.escape(name) + r'="([^"]*)"', tag)
    return m.group(1) if m else None


def _learn_body(s: str, m, tag: str) -> str:
    """Inner HTML of the element whose opening tag is match `m`, balanced on `tag` (nested same-name tags counted)."""
    pat = re.compile(r"<(/?)" + tag + r"\b[^>]*>")
    depth, pos = 1, m.end()
    while depth:
        mm = pat.search(s, pos)
        if not mm:
            return s[m.end():]
        pos = mm.end()
        depth += -1 if mm.group(1) else 1
    return s[m.end():mm.start()]


def _learn_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _learn_html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


@page_check
def learn_instructor(p: PageCtx) -> None:
    """B3: an instructor block (div/details.instructor) carries text beyond its title; table.rubric has a thead."""
    s = p.no_script
    for m in re.finditer(r"<(div|details)\b[^>]*>", s):
        if not _learn_cls(m.group(0), "instructor"):
            continue
        body = _learn_body(s, m, m.group(1))
        body = re.sub(r"<summary\b[^>]*>[\s\S]*?</summary>", " ", body)
        body = re.sub(r'<span\b[^>]*\bclass="(?:[^"]*\s)?callout-title(?:\s[^"]*)?"[^>]*>[\s\S]*?</span>', " ", body)
        if not _learn_text(body):
            p.error(p.line(m.start()), "instructor block is empty")
    for m in re.finditer(r"<table\b[^>]*>", s):
        if _learn_cls(m.group(0), "rubric") and not re.search(r"<thead\b", _learn_body(s, m, "table")):
            p.error(p.line(m.start()), "table.rubric has no thead")


@page_check
def learn_bloom(p: PageCtx) -> None:
    """B5: data-bloom values, data-objective indexes against the page's objectives list, the outcome matrix's list."""
    s = p.no_script
    for m in re.finditer(r'\sdata-bloom="([^"]*)"', s):
        if m.group(1).strip().lower() not in LEARN_BLOOM:
            p.error(p.line(m.start()), f'data-bloom "{m.group(1)}" is not a Bloom level')
    lists = [m for m in re.finditer(r"<ol\b[^>]*>", s) if _learn_cls(m.group(0), "objectives")]
    target = lists[0] if lists else None       # data-objective counts against the first list, or the one the matrix names
    for m in re.finditer(r'<\w+\b[^>]*\sdata-outcomes(?:="([^"]*)")?[^>]*>', s):
        v = (m.group(1) or "").strip()
        if v == "site":
            continue
        if v.startswith("#"):
            named = next((x for x in lists if _learn_attr(x.group(0), "id") == v[1:]), None)
            if named is None:
                p.error(p.line(m.start()), f"outcome matrix names missing list {v}")
            else:
                target = named
        elif not lists:
            p.error(p.line(m.start()), "outcome matrix but the page has no ol.objectives")
    n = len(re.findall(r"<li[\s>]", _learn_body(s, target, "ol"))) if target else 0
    for m in re.finditer(r'\sdata-objective="([^"]*)"', s):
        for tok in m.group(1).split(","):
            tok = tok.strip()
            if not tok:
                continue
            if not tok.isdigit() or int(tok) < 1:
                p.error(p.line(m.start()), f'data-objective "{m.group(1)}" is not a list of objective numbers')
                break
            if int(tok) > n:
                p.error(p.line(m.start()), f"data-objective {tok} but the page has {n} objectives")


@page_check
def learn_predict(p: PageCtx) -> None:
    """B6: a predict block names an existing .demo on the page and a data-answer within its options."""
    s = p.no_script
    demo_ids = {_learn_attr(m.group(0), "id") for m in re.finditer(r"<\w+\b[^>]*>", s)
                if "demo" in m.group(0) and _learn_cls(m.group(0), "demo") and _learn_attr(m.group(0), "id")}
    for m in re.finditer(r"<div\b[^>]*>", s):
        tag = m.group(0)
        if not _learn_cls(tag, "predict"):
            continue
        ln = p.line(m.start())
        body = _learn_body(s, m, "div")
        om = next((x for x in re.finditer(r"<ol\b[^>]*>", body) if _learn_cls(x.group(0), "opts")), None)
        n = len(re.findall(r"<li[\s>]", _learn_body(body, om, "ol"))) if om else 0
        ans = _learn_attr(tag, "data-answer")
        if ans is None:
            p.error(ln, "predict block without data-answer")
        elif not ans.strip().isdigit() or int(ans) >= n:
            p.error(ln, f"predict data-answer={ans} out of range ({n} options)")
        demo = _learn_attr(tag, "data-demo")
        if not (demo or "").strip():
            p.error(ln, "predict block without data-demo")
        elif demo not in demo_ids:
            p.error(ln, f"predict block targets missing demo {demo}")


@page_check
def learn_lab(p: PageCtx) -> None:
    """B7: a lab section has an id, an ol.steps, a checklist with data-key, and a closed details.lab-answer."""
    s = p.no_script
    for m in re.finditer(r"<(section|div)\b[^>]*>", s):
        tag = m.group(0)
        if not _learn_cls(tag, "lab"):
            continue
        ln = p.line(m.start())
        lid = _learn_attr(tag, "id")
        label = lid or f"at line {ln}"
        if not lid:
            p.error(ln, "lab section without id")
        body = _learn_body(s, m, m.group(1))
        if not any(_learn_cls(x.group(0), "steps") for x in re.finditer(r"<ol\b[^>]*>", body)):
            p.error(ln, f"lab {label} has no steps")
        cls = [x for x in re.finditer(r"<[uo]l\b[^>]*>", body) if _learn_cls(x.group(0), "checklist")]
        if not cls:
            p.error(ln, f"lab {label} has no checklist")
        elif not any((_learn_attr(x.group(0), "data-key") or "").strip() for x in cls):
            p.error(ln, f"lab {label}: checklist without data-key")
        for x in re.finditer(r"<details\b[^>]*>", body):
            if _learn_cls(x.group(0), "lab-answer") and re.search(r"\sopen(?=[\s>=/])", x.group(0)):
                p.error(p.line(m.end() + x.start()), f"lab {label}: answer open by default")
# ==== END learn ====



# ==== BLOCK scholar — B2 theorem blocks · E2 numbered equations · E3 notation tables · E1 citation export · C9 copy as LaTeX ====
# B2 theorem blocks · E2 numbered equations · E3 notation tables (page + site) · E1 citation fields. Messages are listed in
# components/math/README.md and the "References" section of components/core/README.md.
THM_KINDS = ("theorem", "lemma", "proposition", "corollary", "definition", "example", "remark", "proof")
REF_TYPES = ("article", "book", "web", "dataset", "standard", "thesis", "report", "software")
DOI_RE = re.compile(r"10\.\d{4,}/\S+")


def _cls(name: str) -> str:
    """Regex for `class="…"` containing the class `name` (any position in the list)."""
    return r'\bclass="(?:[^"]*\s)?' + name + r'(?:\s[^"]*)?"'


def _div_end(s: str, start: int) -> int:
    """Position just after the </div> that closes the <div …> opening at `start` (nesting-aware; len(s) when unbalanced)."""
    depth = 0
    for m in re.finditer(r"<div\b|</div>", s[start:]):
        depth += 1 if m.group(0) == "<div" else -1
        if depth == 0:
            return start + m.end()
    return len(s)


@page_check
def scholar_theorems(p: PageCtx) -> None:
    """B2: .thm data-kind in the known set; a proof never holds another block; a numbered block without id cannot be referenced."""
    s = p.no_script
    starts = list(re.finditer(r"<div\b[^>]*" + _cls("thm") + r"[^>]*>", s))
    for k, m in enumerate(starts):
        tag = m.group(0)
        idm = re.search(r'\sid="([^"]+)"', tag)
        label = idm.group(1) if idm else f"#{k + 1}"
        ln = p.line(m.start())
        km = re.search(r'\sdata-kind="([^"]*)"', tag)
        kind = (km.group(1) if km else "").strip().lower()
        if kind not in THM_KINDS:
            p.error(ln, f'thm {label} data-kind "{km.group(1) if km else ""}" unknown ({"|".join(THM_KINDS)})')
            continue
        if kind == "proof":
            if re.search(r"<div\b[^>]*" + _cls("thm"), s[m.end():_div_end(s, m.start())]):
                p.error(ln, f"thm {label} proof contains another thm block")
        elif not idm:
            p.warn(ln, f"thm {label} ({kind}) has no id — it cannot be referenced")


@page_check
def scholar_equations(p: PageCtx) -> None:
    """E2: a numbered equation is div.eq[id]; the id starts with eq- (the convention eqrefs and the indexes rely on)."""
    for m in re.finditer(r"<div\b[^>]*" + _cls("eq") + r"[^>]*>", p.no_script):
        idm = re.search(r'\sid="([^"]+)"', m.group(0))
        if idm and not idm.group(1).startswith("eq-"):
            p.warn(p.line(m.start()), f'eq id "{idm.group(1)}" should start with eq-')


@page_check
def scholar_notation_tables(p: PageCtx) -> None:
    """E3: table.notation has a thead and every data row a td.sym — the cell build_site_data.py harvests the symbol from."""
    s = p.no_script
    for m in re.finditer(r"<table\b[^>]*" + _cls("notation") + r"[^>]*>", s):
        end = s.find("</table>", m.end())
        body = s[m.end():end if end >= 0 else len(s)]
        ln = p.line(m.start())
        if "<thead" not in body:
            p.error(ln, "notation table without thead")
        tb = re.search(r"<tbody\b[^>]*>([\s\S]*?)</tbody>", body)
        rows = [r for r in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>", tb.group(1) if tb else body) if "<th" not in r]
        for i, row in enumerate(rows):
            if not re.search(r"<td\b[^>]*" + _cls("sym"), row):
                p.error(ln, f"notation table row {i + 1} without td.sym")
                break


@page_check
def scholar_refs(p: PageCtx) -> None:
    """E1: the citation fields on ol.refs entries — data-year 4 digits, data-doi a DOI, data-type a known type."""
    s = p.no_script
    for om in re.finditer(r"<ol\b[^>]*" + _cls("refs") + r"[^>]*>", s):
        end = s.find("</ol>", om.end())
        body = s[om.end():end if end >= 0 else len(s)]
        for k, lm in enumerate(re.finditer(r"<li\b[^>]*>", body)):
            tag = lm.group(0)
            idm = re.search(r'\sid="([^"]+)"', tag)
            label = idm.group(1) if idm else f"#{k + 1}"
            ln = p.line(om.end() + lm.start())
            ym = re.search(r'\sdata-year="([^"]*)"', tag)
            if ym and not re.fullmatch(r"\d{4}", ym.group(1).strip()):
                p.error(ln, f'ref {label}: data-year "{ym.group(1)}" is not a 4-digit year')
            dm = re.search(r'\sdata-doi="([^"]*)"', tag)
            if dm and not DOI_RE.fullmatch(dm.group(1).strip()):
                p.error(ln, f'ref {label}: data-doi "{dm.group(1)}" is not a DOI (10.NNNN/…)')
            tm = re.search(r'\sdata-type="([^"]*)"', tag)
            if tm and tm.group(1).strip().lower() not in REF_TYPES:
                p.error(ln, f'ref {label}: data-type "{tm.group(1)}" is not one of {"|".join(REF_TYPES)}')


@site_check
def scholar_notation_site(s: SiteCtx) -> None:
    """E3: assets/notation.json shape (symbol + meaning required, kind symbol|constant, page must exist) and one meaning per symbol
    across the site — the json entries and every table.notation / table.constants row are compared; a differing meaning is a warning."""
    seen: dict[str, tuple[str, str]] = {}   # symbol -> (normalised meaning, where it was first seen)
    warned: set[str] = set()

    def see(symbol: str, meaning: str, where: str, file, line: int) -> None:
        key = symbol.strip()
        mean = re.sub(r"\s+", " ", meaning).strip().rstrip(".").lower()
        if not key or not mean:
            return
        if key not in seen:
            seen[key] = (mean, where)
        elif seen[key][0] != mean and key not in warned:
            warned.add(key)
            s.warn(file, line, f'notation: symbol "{key}" means "{seen[key][0]}" ({seen[key][1]}) and "{mean}" ({where})')

    nj = s.asset("notation.json")
    if nj.exists():
        obj, err = load_json(nj)
        names = {posixpath.basename(rp) for rp in s.pages}
        if err:
            s.error(nj, 1, err)
        elif not isinstance(obj, list):
            s.error(nj, 1, "assets/notation.json must be a JSON array")
        else:
            for i, e in enumerate(obj):
                if not isinstance(e, dict) or not isinstance(e.get("symbol"), str) or not e["symbol"].strip() \
                        or not isinstance(e.get("meaning"), str) or not e["meaning"].strip():
                    s.error(nj, 1, f"notation entry {i + 1} needs symbol and meaning: {json.dumps(e, ensure_ascii=False)[:60]}")
                    continue
                if e.get("kind") not in (None, "symbol", "constant"):
                    s.error(nj, 1, f'notation entry "{e["symbol"]}": kind must be symbol or constant (got {json.dumps(e.get("kind"))})')
                if e.get("page") and posixpath.basename(str(e["page"])) not in names:
                    s.error(nj, 1, f'notation entry "{e["symbol"]}" points to missing page {e["page"]}')
                see(e["symbol"], e["meaning"], "notation.json", nj, 1)
    for rp, text in s.pages.items():
        page_text = re.sub(r"<script[\s\S]*?</script>", blank_keep_lines, text)
        stem = posixpath.basename(rp).rsplit(".", 1)[0]
        for row in notation_rows(page_text):
            see(row["symbol"], row["meaning"], stem, s.site / rp, line_of(page_text, row["pos"]))
# ==== END scholar ====



# ==== BLOCK visual — C9 download SVG/PNG · C10 photo hotspots and lightbox · C11 compare slider and exploded-view layers ====
_VISUAL_FIG_RE = re.compile(r"<figure\b[^>]*>")
_VISUAL_VOID = {"img", "br", "hr", "input", "source", "track", "wbr", "meta", "link", "area", "col", "embed", "param", "use"}


def _visual_has_class(tag: str, cls: str) -> bool:
    return re.search(r'\bclass="(?:[^"]*\s)?' + re.escape(cls) + r'(?:\s[^"]*)?"', tag) is not None


def _visual_panes(body: str) -> int:
    """Direct children of a figure body that are neither the caption nor the legend (a small tag walker, void tags aware)."""
    depth, n = 0, 0
    for t in re.finditer(r"<(/?)([A-Za-z][\w-]*)[^>]*?(/?)>", body):
        closing, name, selfclose = t.group(1), t.group(2).lower(), t.group(3)
        if closing:
            depth = max(0, depth - 1)
            continue
        if depth == 0 and name != "figcaption" and not _visual_has_class(t.group(0), "legend"):
            n += 1
        if not selfclose and name not in _VISUAL_VOID:
            depth += 1
    return n


@page_check
def visual_checks(p: PageCtx) -> None:
    """C10: figure.photo[data-hotspots] has a ul.hotspots whose li carry numeric data-x/data-y in 0..100.
    C11: figure.compare has exactly two panes; figure.diagram[data-layers] has >= 2 named g[data-layer] layers with unique names
    (g[data-layer] without data-layers on the figure is advice only). C9 adds no markup and needs no check."""
    ns = p.no_script
    for m in _VISUAL_FIG_RE.finditer(ns):
        tag = m.group(0)
        ln = p.line(m.start())
        endf = ns.find("</figure>", m.end())
        body = ns[m.end():endf if endf >= 0 else len(ns)]
        idm = re.search(r'\sid="([^"]+)"', tag)
        fid = idm.group(1) if idm else f"at line {ln}"
        if _visual_has_class(tag, "photo") and re.search(r"\sdata-hotspots(?=[\s>=/])", tag):
            ul = re.search(r'<ul\b[^>]*\bclass="(?:[^"]*\s)?hotspots(?:\s[^"]*)?"[^>]*>([\s\S]*?)</ul>', body)
            if not ul:
                p.error(ln, f"photo {fid} has data-hotspots but no ul.hotspots")
            else:
                for li in re.finditer(r"<li\b([^>]*)>", ul.group(1)):
                    lln = p.line(m.end() + ul.start(1) + li.start())
                    attrs = li.group(1)
                    vals = {k: re.search(r'\sdata-' + k + r'="([^"]*)"', attrs) for k in ("x", "y")}
                    if not vals["x"] or not vals["y"]:
                        p.error(lln, "hotspot without data-x/data-y")
                        continue
                    for k, vm in vals.items():
                        raw = vm.group(1).strip()
                        try:
                            v = float(raw)
                        except ValueError:
                            p.error(lln, f'hotspot data-{k} "{raw}" is not a number')
                            continue
                        if not 0 <= v <= 100:
                            p.error(lln, f"hotspot data-{k} {raw} outside 0..100")
        if _visual_has_class(tag, "compare"):
            n = _visual_panes(body)
            if n != 2:
                p.error(ln, f"compare figure {fid} has {n} pane{'' if n == 1 else 's'}, needs 2")
        if _visual_has_class(tag, "diagram"):
            names = re.findall(r'<g\b[^>]*\bdata-layer="([^"]*)"', body)
            if re.search(r"\sdata-layers(?=[\s>=/])", tag):
                named = [x.strip() for x in names if x.strip()]
                if len(set(named)) < 2:
                    p.error(ln, f"exploded view {fid} has fewer than 2 layers")
                for nm in sorted({x for x in named if named.count(x) > 1}):
                    c = named.count(nm)
                    p.error(ln, f'layer "{nm}" used {"twice" if c == 2 else str(c) + " times"} in {fid}')
                if len(named) != len(names):
                    p.error(ln, f"layer without a name in {fid}")
            elif names:
                p.warn(ln, f"figure {fid} has g[data-layer] groups but no data-layers (no layer toggles)")
# ==== END visual ====



# ==== BLOCK plots — C5 plot upgrades · C6 declarative function plotter · C7 vector fields and parameter sweeps ====
# C5 plot upgrades are called from page scripts (node checks their syntax); C6 fnplot and C7 field / sweep are declarative
# figures whose attributes and expressions are checked here. EXPR_FUNCS must equal EXPR_FN in template/assets/app.js: the
# runtime's parser is the final judge, this is the same token check in Python (characters, parentheses, names).
EXPR_FUNCS = {"sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh", "exp", "ln", "log", "log10", "log2",
              "sqrt", "cbrt", "abs", "floor", "ceil", "round", "sign", "min", "max", "pow", "hypot", "clamp", "step"}
EXPR_CONSTS = {"pi", "e"}
PLOT_SCALES = {"linear", "log", "logx", "loglog"}
_EXPR_NUM = re.compile(r"(?<![A-Za-z_\d.])(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_EXPR_IDENT = re.compile(r"[A-Za-z_]\w*")
_NUM = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
_VAR_RE = re.compile(rf"^([A-Za-z_]\w*)\s*=\s*({_NUM}):({_NUM})(?::({_NUM}))?(?::({_NUM}))?$")
_SWEEP_RE = re.compile(rf"^([A-Za-z_]\w*)\s*=\s*({_NUM}):({_NUM}):({_NUM})$")
_FIG_RE = re.compile(r"<figure\b[^>]*>")


def expr_problem(src: str, names) -> str | None:
    """None when the expression passes the token check, else the short message the runtime would also give."""
    src = (src or "").strip()
    if not src:
        return "empty expression"
    bad = re.search(r"[^\w\s.+\-*/^%(),]", src)
    if bad:
        return f'unexpected character "{bad.group(0)}"'
    depth = 0
    for ch in src:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return "unbalanced parentheses"
    if depth:
        return "unbalanced parentheses"
    stripped = _EXPR_NUM.sub(" ", src)
    for m in _EXPR_IDENT.finditer(stripped):
        name = m.group(0)
        if stripped[m.end():].lstrip().startswith("("):
            if name not in EXPR_FUNCS:
                return f'unknown function "{name}"'
        elif name not in names and name not in EXPR_CONSTS:
            return f'unknown variable "{name}"'
    return None


def _fig_is(tag: str, cls: str) -> bool:
    return re.search(r'\bclass="(?:[^"]*\s)?' + cls + r'(?:\s[^"]*)?"', tag) is not None


def _attr(tag: str, name: str):
    m = re.search(r"\s" + re.escape(name) + r'="([^"]*)"', tag)
    return m.group(1) if m else None


def _pair(val):
    """`min,max[,label]` -> (min, max) or None; `,,label` (automatic range with a label) -> (None, None)."""
    parts = [x.strip() for x in (val or "").split(",")]
    if len(parts) >= 3 and parts[0] == "" and parts[1] == "":
        return (None, None)
    if len(parts) < 2 or not re.fullmatch(_NUM, parts[0]) or not re.fullmatch(_NUM, parts[1]):
        return None
    return (float(parts[0]), float(parts[1]))


@page_check
def check_plot_figures(p: PageCtx) -> None:
    text = p.no_script
    for m in _FIG_RE.finditer(text):
        tag = m.group(0)
        kind = "fnplot" if _fig_is(tag, "fnplot") else "field" if _fig_is(tag, "field") else "sweep" if _fig_is(tag, "sweep") else None
        if not kind:
            continue
        ln = p.line(m.start())
        endf = text.find("</figure>", m.end())
        body = text[m.end():endf if endf >= 0 else len(text)]
        if "<figcaption" not in body:
            p.warn(ln, f"{kind} figure without figcaption")
        scale = _attr(tag, "data-scale")
        if kind != "field" and scale is not None and scale not in PLOT_SCALES:
            p.error(ln, f'{kind} data-scale "{scale}" is not linear, log, logx or loglog')
        if kind == "fnplot":
            fn = _attr(tag, "data-fn")
            if not (fn or "").strip():
                p.error(ln, "fnplot without data-fn")
            xr = _pair(_attr(tag, "data-x"))
            if xr is None or xr[0] is None:
                p.error(ln, "fnplot data-x must be two numbers")
            elif scale in ("logx", "loglog") and (xr[0] <= 0 or xr[1] <= 0):
                p.error(ln, "fnplot data-x must be positive on a log axis")
            if _attr(tag, "data-y") is not None and _pair(_attr(tag, "data-y")) is None:
                p.error(ln, "fnplot data-y must be two numbers")
            names = {"x"}
            for ent in [x.strip() for x in (_attr(tag, "data-vars") or "").split(",") if x.strip()]:
                vm = _VAR_RE.match(ent)
                if not vm:
                    p.error(ln, f'fnplot var "{ent}" needs min:max')
                    continue
                names.add(vm.group(1))
                if float(vm.group(2)) >= float(vm.group(3)):
                    p.error(ln, f'fnplot var "{ent}" needs min < max')
                elif vm.group(4) is not None and float(vm.group(4)) <= 0:
                    p.error(ln, f'fnplot var "{ent}" needs a positive step')
            fns = [x.strip() for x in (fn or "").split(";") if x.strip()]
            for src in fns:
                msg = expr_problem(src, names)
                if msg:
                    p.error(ln, f"fnplot expression: {msg}")
            labels = [x.strip() for x in (_attr(tag, "data-labels") or "").split(",") if x.strip()]
            if labels and fns and len(labels) != len(fns):
                p.warn(ln, f"fnplot has {len(labels)} labels for {len(fns)} functions")
        elif kind == "field":
            fx, fy = _attr(tag, "data-fx"), _attr(tag, "data-fy")
            if not (fx or "").strip() or not (fy or "").strip():
                p.error(ln, "field figure needs data-fx and data-fy")
            else:
                for src in (fx, fy):
                    msg = expr_problem(src, {"x", "y"})
                    if msg:
                        p.error(ln, f"field expression: {msg}")
            for axis in ("data-x", "data-y"):
                val = _attr(tag, axis)
                if val is not None and (_pair(val) is None or _pair(val)[0] is None):
                    p.error(ln, f"field {axis} must be two numbers")
            for tr in [x.strip() for x in (_attr(tag, "data-trajectories") or "").split(";") if x.strip()]:
                xy = [x.strip() for x in tr.split(",")]
                if len(xy) != 2 or not all(re.fullmatch(_NUM, x) for x in xy):
                    p.error(ln, f'field trajectory "{tr}" needs x, y')
            grid = _attr(tag, "data-grid")
            if grid is not None and not re.fullmatch(r"\d+", grid.strip()):
                p.error(ln, f'field data-grid "{grid}" is not a whole number')
        else:
            fn = _attr(tag, "data-fn")
            if not (fn or "").strip():
                p.error(ln, "sweep without data-fn")
            xr = _pair(_attr(tag, "data-x"))
            if xr is None or xr[0] is None:
                p.error(ln, "sweep data-x must be two numbers")
            elif scale in ("logx", "loglog") and (xr[0] <= 0 or xr[1] <= 0):
                p.error(ln, "sweep data-x must be positive on a log axis")
            if _attr(tag, "data-y") is not None and _pair(_attr(tag, "data-y")) is None:
                p.error(ln, "sweep data-y must be two numbers")
            sw = _attr(tag, "data-sweep")
            names = {"x"}
            if sw is None:
                p.error(ln, "sweep without data-sweep")
            else:
                sm = _SWEEP_RE.match(sw.strip())
                if not sm:
                    p.error(ln, f'sweep data-sweep "{sw}" must be name=min:max:step')
                else:
                    names.add(sm.group(1))
                    lo, hi, step = float(sm.group(2)), float(sm.group(3)), float(sm.group(4))
                    if step <= 0 or hi < lo:
                        p.error(ln, f'sweep data-sweep "{sw}" needs min < max and a positive step')
                    else:
                        members = int((hi - lo) / step + 1e-9) + 1
                        if members > 24:
                            p.error(ln, f"sweep has {members} members, max 24")
            if (fn or "").strip():
                msg = expr_problem(fn, names)
                if msg:
                    p.error(ln, f"sweep expression: {msg}")
# ==== END plots ====



# ==== BLOCK compute — D1 demo state and presets · D2 export results · D3 unit-aware inputs · D4 uncertainty helpers · D6 sensitivity view ====
import html as _html  # noqa: E402

# the unit groups app.js knows (QC.units); keep the two tables in sync
UNIT_GROUPS = {
    "length": ["m", "cm", "mm", "km", "in", "ft", "mi"],
    "mass": ["kg", "g", "lb", "oz"],
    "time": ["s", "ms", "min", "h"],
    "temperature": ["K", "°C", "°F"],
    "speed": ["m/s", "km/h", "mph", "kn"],
    "pressure": ["Pa", "kPa", "bar", "psi", "atm"],
    "energy": ["J", "kJ", "Wh", "kWh", "cal"],
    "power": ["W", "kW", "hp"],
    "angle": ["rad", "deg"],
    "frequency": ["Hz", "kHz", "MHz", "rpm"],
    "voltage": ["V", "mV", "kV"],
    "current": ["A", "mA"],
    "data": ["B", "KB", "MB", "GB"],
}
_DEMO_START = re.compile(r'<div\b[^>]*\bclass="(?:[^"]*\s)?demo(?:\s[^"]*)?"[^>]*>')


def _attr(tag: str, name: str):
    m = re.search(r"\s" + re.escape(name) + r'="([^"]*)"', tag)
    return m.group(1) if m else None


def _demo_blocks(p: PageCtx):
    """[(start pos, id or None, body offset, body)] — one per .demo (they do not nest)."""
    starts = list(_DEMO_START.finditer(p.no_script))
    out = []
    for k, m in enumerate(starts):
        end = starts[k + 1].start() if k + 1 < len(starts) else len(p.no_script)
        out.append((m.start(), _attr(m.group(0), "id"), m.end(), p.no_script[m.end():end]))
    return out


@page_check
def compute_presets(p: PageCtx) -> None:
    """D1: every .demo should have an id; preset buttons name inputs of their demo, carry data-state and have unique names."""
    for pos, did, off, body in _demo_blocks(p):
        label = did or f"at line {p.line(pos)}"
        if not did:
            p.warn(p.line(pos), "demo without id (no URL state, presets, link or export)")
        inputs = set(re.findall(r'<(?:input|select)\b[^>]*\sid="([^"]+)"', body))
        seen: set = set()
        for m in re.finditer(r'<button\b[^>]*\bdata-preset="([^"]*)"[^>]*>', body):
            name, ln = m.group(1), p.line(off + m.start())
            if name in seen:
                p.error(ln, f'preset "{name}" defined twice in {label}')
            seen.add(name)
            state = _attr(m.group(0), "data-state")
            if state is None:
                p.error(ln, f'preset "{name}" has no data-state')
                continue
            for pair in _html.unescape(state).split("&"):
                if not pair.strip():
                    continue
                key = pair.split("=", 1)[0].strip()
                if key not in inputs:
                    p.error(ln, f'preset "{name}" names unknown input "{key}"')


@page_check
def compute_inputs(p: PageCtx) -> None:
    """D3/D4: data-unit-group ∈ groups with a data-unit of that group on a range/number input; data-si on text inputs; data-tol 0..100."""
    for m in re.finditer(r"<input\b[^>]*>", p.no_script):
        tag, ln = m.group(0), p.line(m.start())
        iid = _attr(tag, "id") or "?"
        group = _attr(tag, "data-unit-group")
        if group is not None:
            if group not in UNIT_GROUPS:
                p.error(ln, f'unit group "{group}" unknown')
            else:
                unit = _attr(tag, "data-unit")
                if unit is None:
                    p.error(ln, f'unit input "{iid}" has no data-unit')
                elif unit not in UNIT_GROUPS[group]:
                    p.error(ln, f'unit "{unit}" is not in group {group}')
            if not re.search(r'\stype="(?:range|number)"', tag):
                p.error(ln, f'unit input "{iid}" must be type range or number')
            if not re.search(r'<output\b[^>]*\sfor="' + re.escape(iid) + '"', p.no_script):
                p.warn(ln, f'unit input "{iid}" has no output[for] (the unit menu sits beside it)')
        if re.search(r"\sdata-si(?=[\s>=/])", tag) and re.search(r'\stype="number"', tag):   # data-si is usually a bare attribute
            p.warn(ln, f'data-si input "{iid}" should be type text so a prefix like 2.2µ can be typed')
        tol = _attr(tag, "data-tol")
        if tol is not None:
            try:
                ok = 0 <= float(tol) <= 100
            except ValueError:
                ok = False
            if not ok:
                p.error(ln, f'data-tol "{tol}" must be a number 0..100')
# ==== END compute ====



# ==== BLOCK evidence — references/evidence-policy.md §5–§8 ====
# Every figure that shows information and every demo cites its evidence; every data-cite resolves; the `illustrative`
# badge marks computed output only (inside a demo or a computed figure), never a stated number; every GAP marker has a
# visible gap badge beside it. Messages name the evidence policy section that the writer reads.
EV_FIGURE_KINDS = ("diagram", "plot", "fnplot", "field", "sweep", "timing", "bitfield", "seq", "fsm", "schematic", "pinout", "regmap")
EV_FIGURE_RE = re.compile(r'<figure\b[^>]*\bclass="([^"]*)"[^>]*>')
EV_EVIDENCE_RE = re.compile(_cls("cite") + "|" + _cls("claim") + r'|\sdata-cite="[^"]*\S')
EV_CLASS_RE = re.compile(r'\bclass="([^"]*)"')
EV_GAP_BADGES = ("unavailable", "insufficient", "not-specified")
EV_GAP_RE = re.compile(r"<!--\s*GAP:")


def _ev_figures(p: PageCtx):
    """[(start, end, tag, kind)] for every information figure (generated maps — the registry site map, the glossary concept map — excluded)."""
    out = []
    for m in EV_FIGURE_RE.finditer(p.no_script):
        kind = next((k for k in m.group(1).split() if k in EV_FIGURE_KINDS), None)
        if not kind:
            continue
        end = p.no_script.find("</figure>", m.end())
        end = len(p.no_script) if end < 0 else end + len("</figure>")
        body = p.no_script[m.end():end]
        if kind == "diagram" and ("data-sitemap" in body or "data-concept-map" in body):
            continue
        out.append((m.start(), end, m.group(0), kind))
    return out


def _ev_demos(p: PageCtx):
    """[(start, end, tag)] for every .demo, bounded by its own closing </div>."""
    return [(m.start(), _div_end(p.no_script, m.start()), m.group(0)) for m in _DEMO_START.finditer(p.no_script)]


def _ev_has_evidence(tag: str, body: str, home: bool) -> bool:
    if re.search(r'\sdata-cite="[^"]*\S', tag) or EV_EVIDENCE_RE.search(body):
        return True
    return home and re.search(r'<a\b[^>]*\shref="pages/[^"#]+\.html#[^"]+"', body) is not None   # the overview's evidence lives on the pages


@page_check
def evidence_figures_and_demos(p: PageCtx) -> None:
    """§5, §7: a figure that shows information, and every demo, names the source it rests on."""
    for start, end, tag, kind in _ev_figures(p):
        if not _ev_has_evidence(tag, p.no_script[start + len(tag):end], p.is_home):
            label = _attr(tag, "id") or f"{kind} at line {p.line(start)}"
            p.error(p.line(start), f"figure {label} cites no source — add data-cite=\"#ref-…\" to the figure or its elements, "
                                   "or a cite in its caption (evidence policy §7)")
    for start, end, tag in _ev_demos(p):
        if not _ev_has_evidence(tag, p.no_script[start + len(tag):end], False):
            label = _attr(tag, "id") or f"at line {p.line(start)}"
            p.error(p.line(start), f"demo {label} cites no source for its model — cite the documented calculation in its .demo-note (evidence policy §5)")


@page_check
def evidence_data_cite(p: PageCtx) -> None:
    """§4.6, §7: every data-cite token resolves to an id (`#ref-key` on this page or `other.html#ref-key`)."""
    for m in re.finditer(r'\sdata-cite="([^"]*)"', p.no_script):
        ln, toks = p.line(m.start()), [t for t in re.split(r"[\s,]+", m.group(1)) if t]
        if not toks:
            p.error(ln, "empty data-cite")
        for tok in toks:
            _, anc, ok = p.resolve(tok)
            if not ok or not anc:
                p.error(ln, f"data-cite {tok} does not resolve")


@page_check
def evidence_badges(p: PageCtx) -> None:
    """§5: `illustrative` marks computed output only; §8: every GAP marker has a visible gap badge."""
    allowed = [(a, b) for a, b, _t in _ev_demos(p)] + [(a, b) for a, b, _t, _k in _ev_figures(p)]
    gap_badges = 0
    for m in EV_CLASS_RE.finditer(p.no_script):
        cls = m.group(1).split()
        if "badge" not in cls:
            continue
        if any(c in cls for c in EV_GAP_BADGES):
            gap_badges += 1
        if "illustrative" in cls and not any(a <= m.start() < b for a, b in allowed):
            p.error(p.line(m.start()), "illustrative badge outside a demo or computed figure — a stated number needs a cited source, "
                                       "a missing one a gap badge (evidence policy §5, §8)")
    try:
        raw = (p.site / p.rp).read_text(encoding="utf-8")
    except OSError:
        return
    gaps = list(EV_GAP_RE.finditer(raw))
    if len(gaps) > gap_badges:
        p.error(line_of(raw, gaps[0].start()), f"{len(gaps)} GAP marker(s) but {gap_badges} visible gap badge(s) — put "
                                               "<span class=\"badge unavailable|insufficient|not-specified\"> beside each gap (evidence policy §8)")


# §10: the reader sees the subject and its sources, never how or why the page was produced. Two lists over the visible
# text (tags, comments and scripts removed): self-reference and decision narration (always), and the workflow's own
# vocabulary (skipped only on a page whose subject is the atlas-learn workflow itself: <body data-subject="atlas-learn">, which the
# template home and the style guide carry; outside the atlas-learn site itself that marker is a warning).
EV_PROCESS_RE = re.compile(
    r"\bas an AI\b|\b(?:AI|LLM|language[- ]model)[- ](?:generated|written|assistant)\b"
    r"|\b(?:generated|written|created|produced|compiled|drafted) (?:by|with|using) (?:an? )?(?:AI|LLM|language model|agents?|Claude|ChatGPT|GPT)\b"
    r"|\b(?:I|we)(?:'ve| have)? (?:chose|chosen|decided|added|omitted|included|selected|picked|left out|could not|couldn't|was unable|were unable|did not find|didn't find|opted)\b"
    r"|\b(?:this|the) (?:page|section|diagram|figure|demo|table|chart|plot|visuali[sz]ation|module|example) (?:was|is|has been) "
    r"(?:added|chosen|included|omitted|selected|generated|written|created|built|left out|kept) (?:because|since|so that|to show why)\b"
    r"|\bthere is no (?:diagram|figure|demo|visuali[sz]ation|chart|plot|table)(?: here)? because\b", re.I)
EV_WORKFLOW_RE = re.compile(
    r"\b(?:the dossier|dossier (?:rows?|entr(?:y|ies)|files?)|subagents?|page writers?|site reviewers?|module researchers?|source verifiers?"
    r"|dossier consolidator|brief author|main agent|page block|build notes?)\b|SITE_PLAN", re.I)


@page_check
def evidence_no_process_text(p: PageCtx) -> None:
    """§10: no text about the agents, the tools or the reasons behind the page — only the subject and what the sources state."""
    text = re.sub(r"<style\b[\s\S]*?</style>|<template\b[\s\S]*?</template>", " ", p.no_script, flags=re.I)
    text = re.sub(r"<[^>]+>", lambda m: " " * len(m.group(0)), text)   # keep offsets, so line numbers stay right
    for m in EV_PROCESS_RE.finditer(text):
        p.error(p.line(m.start()), f"process text \"{m.group(0)}\" — state what the sources say about the subject, not how or why "
                                   "the page was made; a missing visual or fact is a gap badge about the sources (evidence policy §10)")
    atlas_learn = re.search(r'<body\b[^>]*\sdata-subject="atlas-learn"', p.s) is not None
    title = (p.reg.get("title") if isinstance(p.reg, dict) else "") or ""
    if atlas_learn and title.strip().lower() != "atlas-learn":
        p.warn(1, "page still carries data-subject=\"atlas-learn\" (template text about the atlas-learn workflow) — rewrite it for this "
                  "topic and drop the marker; the workflow-vocabulary check is skipped while it is there (evidence policy §10)")
    if not atlas_learn:
        for m in EV_WORKFLOW_RE.finditer(text):
            p.error(p.line(m.start()), f"workflow text \"{m.group(0)}\" — the reader never sees the dossier, the agents or the "
                                       "plan; cite the source itself (evidence policy §10)")
# ==== END evidence ====


# ==== BLOCK sitewide — A1 indexes · A3 backlinks · E5 claim → evidence trace · G4 site manifest · H6 media manifest ====
# sitewide: E5 claims (page check) · H6 media licence, stale assets/data.js and the claims count (site check).
SW_CLAIM_RE = re.compile(r'<span\b[^>]*\bclass="(?:[^"]*\s)?claim(?:\s[^"]*)?"[^>]*>')
SW_MEDIA_PLATFORMS = ("youtube", "vimeo", "sketchfab", "pdf", "iframe")   # shown through the host's own viewer: no licence warning
# The same licence expression lives in the sitewide block of build_site_data.py (assets/media.json) — keep the two in step.
SW_LICENCE_RE = re.compile(r"(CC[ -]?BY(?:[ -](?:NC|ND|SA))*(?:[ -]\d\.\d)?|CC0(?:[ -]1\.0)?|Public domain|©[^,;<]*|\(c\)[^,;<]*|"
                           r"All rights reserved|MIT licen[cs]e|GPL[^,;<]*|Apache[^,;<]*|OGL[^,;<]*|Unsplash licen[cs]e|Pexels licen[cs]e)", re.I)


@page_check
def sitewide_claims(p: PageCtx) -> None:
    """E5: every span.claim carries a data-src that resolves to an id (`#ref-key` on this page or `other.html#ref-key`)."""
    for m in SW_CLAIM_RE.finditer(p.no_script):
        ln = p.line(m.start())
        sm = re.search(r'\sdata-src="([^"]*)"', m.group(0))
        src = sm.group(1).strip() if sm else ""
        if not src:
            p.error(ln, "claim without data-src")
            continue
        _, anc, ok = p.resolve(src)
        if not ok or not anc:
            p.error(ln, f"claim cites missing source {src}")


@site_check
def sitewide_site(s: SiteCtx) -> None:
    """claims=n on the RESULT line · H6 `media without a licence` (warning) · stale assets/data.js (warning)."""
    s.extra["claims"] = sum(len(SW_CLAIM_RE.findall(txt)) for txt in s.pages.values())
    for rp, txt in s.pages.items():
        ns = re.sub(r"<script[\s\S]*?</script>", blank_keep_lines, txt)
        n = 0
        for m in re.finditer(r"<figure\b[^>]*>", ns):
            n += 1
            tag = m.group(0)
            cm = re.search(r'\bclass="([^"]*)"', tag)
            cls = cm.group(1).split() if cm else []
            kind = next((k for k in ("photo", "embed", "compare") if k in cls), None)
            if not kind:
                continue
            km = re.search(r'\sdata-kind="([^"]*)"', tag)
            if kind == "embed" and (km.group(1) if km else "iframe") in SW_MEDIA_PLATFORMS:
                continue
            end = ns.find("</figure>", m.end())
            body = ns[m.end():end if end >= 0 else len(ns)]
            if kind == "compare" and "<img" not in body:
                continue   # two self-drawn SVG panes carry no third-party rights (integration: C11 × H6)
            crm = re.search(r'class="(?:[^"]*\s)?credit(?:\s[^"]*)?"[^>]*>([\s\S]*?)</span>', body)
            if not SW_LICENCE_RE.search(crm.group(1) if crm else ""):
                idm = re.search(r'\sid="([^"]+)"', tag)
                s.warn(s.site / rp, line_of(ns, m.start()), f"media without a licence: {posixpath.basename(rp)} {idm.group(1) if idm else f'figure #{n}'}")
    dj = s.asset("data.js")
    if dj.exists() and s.pages:
        try:
            newest = max(s.pages, key=lambda rp: (s.site / rp).stat().st_mtime)
            if (s.site / newest).stat().st_mtime - dj.stat().st_mtime > 1.0:
                s.warn(dj, 1, f"assets/data.js is older than {newest} — run build_site_data.py")
        except OSError:
            pass
# ==== END sitewide ====



# ==== BLOCK pages — C12 concept map · E6 changelog and version stamp · F4 study planner ====
@site_check
def pages_site_data(s: SiteCtx):
    """E6: site.json `version`/`licence` are strings, assets/changelog.json has the documented shape (errors; unknown page
    names warn); F4: pages[].hours is a number > 0 (error); C12: glossary `related` names resolve to terms (warnings).
    The RESULT line gains version=<site version|none>."""
    sj = s.asset("site.json")
    reg = s.reg if isinstance(s.reg, dict) else {}
    version = reg.get("version")
    if version is not None and not isinstance(version, str):
        s.error(sj, 1, "site.json version must be a string")
    s.extra["version"] = version.strip() if isinstance(version, str) and version.strip() else "none"
    reg_pages = [p for p in reg.get("pages", []) if isinstance(p, dict)] if isinstance(reg.get("pages"), list) else []
    for p in reg_pages:
        if "hours" in p:
            h = p["hours"]
            if isinstance(h, bool) or not isinstance(h, (int, float)) or h <= 0:
                s.error(sj, 1, f"{p.get('file', '?')}: hours must be a number > 0")
    # C12: `related` names must be glossary terms (or akas); a wrong type or an unknown name is advice, never a failure
    gj = s.asset("glossary.json")
    names: set[str] = set()
    for g in s.glossary:
        if isinstance(g, dict) and isinstance(g.get("term"), str):
            names.add(g["term"].strip().casefold())
            names.update(a.strip().casefold() for a in re.split(r"\s*[,;]\s*", str(g.get("aka") or "")) if a.strip())
    for g in s.glossary:
        if not isinstance(g, dict) or "related" not in g or not isinstance(g.get("term"), str):
            continue
        rel = g["related"]
        if not isinstance(rel, list) or not all(isinstance(r, str) for r in rel):
            s.warn(gj, 1, f'glossary term "{g["term"]}": related must be a list of term names')
            continue
        for name in rel:
            if name.strip().casefold() not in names:
                s.warn(gj, 1, f'glossary term "{g["term"]}": related "{name}" is not a glossary term')
    # E6: changelog.json shape
    cj = s.asset("changelog.json")
    if not cj.exists():
        return
    obj, err = load_json(cj)
    if err:
        s.error(cj, 1, err)
        return
    if not isinstance(obj, list):
        s.error(cj, 1, "changelog.json must be a JSON array")
        return
    known = {p["file"] for p in reg_pages if isinstance(p.get("file"), str)}
    for i, e in enumerate(obj, 1):
        if not isinstance(e, dict):
            s.error(cj, 1, f"changelog entry #{i} must be an object")
            continue
        if not is_date(str(e.get("date") or "")):
            s.error(cj, 1, f'changelog entry #{i}: date "{e.get("date")}" is not a date')
        if not isinstance(e.get("version"), str) or not e["version"].strip():
            s.error(cj, 1, f"changelog entry #{i}: version must be a string")
        pages = e.get("pages")
        if pages is None:
            continue
        if not isinstance(pages, list) or not all(isinstance(x, str) for x in pages):
            s.error(cj, 1, f"changelog entry #{i}: pages must be a list of file names")
            continue
        for x in pages:
            if x not in known:
                s.warn(cj, 1, f"changelog entry #{i}: unknown page {x}")
# ==== END pages ====



# ==== BLOCK pipeline — H1 consistency linter · H4 executed examples ====
import html as _html_mod  # noqa: E402 — pipeline block only

from _common import validate_a11y  # noqa: E402 — I4 derived policies

# ---- H4 executed examples (page checks) --------------------------------------------------------------------------
# pre[data-executed="YYYY-MM-DD"][data-env="…"] must be followed directly by pre.output (the pasted real output).
# Errors route to the page's writer; an output block that follows nothing is advice (the badge will not appear).
EXEC_PRE_RE = re.compile(r'<pre\b[^>]*\bdata-executed="([^"]*)"[^>]*>')
OUT_PRE_RE = re.compile(r'<pre\b[^>]*\bclass="(?:[^"]*\s)?output(?:\s[^"]*)?"[^>]*>')


@page_check
def check_executed_examples(p: PageCtx) -> None:
    s = p.no_script
    paired: set[int] = set()
    for m in EXEC_PRE_RE.finditer(s):
        ln = p.line(m.start())
        if not is_date(m.group(1)):
            p.error(ln, f'data-executed "{m.group(1)}" is not a date')
        if not re.search(r'\bdata-env="[^"]+"', m.group(0)):
            p.warn(ln, "executed example without data-env")
        end = s.find("</pre>", m.end())
        rest = s[end + 6:] if end >= 0 else ""
        nm = re.match(r"\s*<pre\b[^>]*>", rest)
        if not nm or not OUT_PRE_RE.match(nm.group(0).lstrip()):
            p.error(ln, "executed example without an output block")
        else:
            paired.add(end + 6 + (len(nm.group(0)) - len(nm.group(0).lstrip())))
    for om in OUT_PRE_RE.finditer(s):
        if om.start() not in paired:
            p.warn(p.line(om.start()), "output block without an executed example")


# ---- H1 consistency linter (site check, warnings only; s.extra["lint"] = count) ----------------------------------
# (1) <dfn> terms missing from glossary.json · (2) a multi-word glossary term written in two spellings across pages
# (case or hyphenation; the first letter is ignored so sentence starts do not count) · (3) unit spellings from a small
# variant table · (4) td.sym symbols that assets/notation.json does not list (only when that file exists).
# Checks 1–2 wait until glossary.json has entries (the glossary owner writes it late in the writer wave).
UNIT_VARIANTS = [("ms", "msec"), ("s", "sec"), ("km/h", "kph"), ("°C", "deg C", "degC"), ("Hz", "hz"), ("kg", "KG"),
                 ("min", "mins"), ("h", "hr", "hrs")]
LINT_SKIP_RE = re.compile(r"<(script|style|pre|code|svg|kbd|samp)\b[\s\S]*?</\1>", re.I)
LINT_TAG_RE = re.compile(r"<[^>]+>")
LINT_MAX_TERMS = 400


def lint_label(rp: str) -> str:
    """Short page label for lint messages: m02 for m02-kinds.html, otherwise the file stem."""
    stem = posixpath.basename(rp)[:-5] if rp.endswith(".html") else posixpath.basename(rp)
    m = re.match(r"^([ms]\d\d)(?=-|$)", stem)
    return m.group(1) if m else stem


def lint_text(s: str) -> str:
    """Prose of a page: code, scripts, SVG and keys removed, tags stripped, entities decoded, whitespace kept line-wise."""
    return _html_mod.unescape(LINT_TAG_RE.sub(" ", LINT_SKIP_RE.sub(" ", s)))


def lint_norm_symbol(x: str) -> str:
    return re.sub(r"\s+|\\\(|\\\)|\\\[|\\\]|\$", "", x or "")


@site_check
def check_consistency_lint(s: SiteCtx) -> None:
    n = 0
    pages = {rp: s.pages[rp] for rp in s.selected if rp in s.pages}
    texts = {rp: lint_text(t) for rp, t in pages.items()}
    glossary = [g for g in (s.glossary or []) if isinstance(g, dict) and g.get("term")]
    known: set[str] = set()
    for g in glossary:
        known.add(g["term"].strip().lower())
        for aka in re.split(r"\s*[,;·/]\s*", str(g.get("aka") or "")):
            if aka.strip():
                known.add(aka.strip().lower())
    # (1) dfn terms not in the glossary
    if glossary:
        for rp, text in pages.items():
            if posixpath.basename(rp) == "glossary.html":
                continue
            for m in re.finditer(r"<dfn\b[^>]*>([\s\S]*?)</dfn>", text):
                term = " ".join(_html_mod.unescape(LINT_TAG_RE.sub(" ", m.group(1))).split())
                low = term.lower()
                if not term or low in known or low.rstrip("s") in known or low + "s" in known:
                    continue
                s.warn(s.site / rp, line_of(text, m.start()), f'dfn "{term}" ({lint_label(rp)}) is not in glossary.json')
                n += 1
    # (2) one glossary term, two spellings
    if glossary:
        seen_terms: set[str] = set()
        for g in glossary[:LINT_MAX_TERMS]:
            names = [g["term"]] + [a for a in re.split(r"\s*[,;·/]\s*", str(g.get("aka") or "")) if a.strip()]
            for name in names:
                words = [w for w in re.split(r"[\s-]+", name.strip()) if w]
                if len(words) < 2 or name.lower() in seen_terms:
                    continue
                seen_terms.add(name.lower())
                pat = re.compile(r"(?<![\w-])" + r"[\s-]+".join(re.escape(w) for w in words) + r"(?![\w-])", re.I)
                forms: dict[str, tuple[str, list[str]]] = {}   # normalised form -> (first surface form, page labels)
                for rp, text in texts.items():
                    for m in pat.finditer(text):
                        form = " ".join(m.group(0).split())
                        # a hyphenated form used as a compound adjective ("running-example instance") or as a file
                        # name ("trust-footer.html") is correct English / a path, not a spelling variant
                        if "-" in form and re.match(r"[ \t]+\w|\.\w", text[m.end():m.end() + 3]):
                            continue
                        norm = form[:1].lower() + form[1:]
                        lab = lint_label(rp)
                        entry = forms.setdefault(norm, (form, []))
                        if lab not in entry[1]:
                            entry[1].append(lab)
                if len(forms) > 1:
                    listed = " and ".join(f'"{f}" ({", ".join(labs)})' for f, labs in forms.values())
                    s.warn(s.asset("glossary.json"), 0, f'term "{name}" is written as {listed}')
                    n += 1
    # (3) unit spellings
    for group in UNIT_VARIANTS:
        found: dict[str, list[str]] = {}
        for rp, text in texts.items():
            for v in group:
                pat = re.compile(r"(?<![\w.,])\d[\d.,]*\s*" + re.escape(v) + r"(?![\w/])")
                if pat.search(text):
                    lab = lint_label(rp)
                    if lab not in found.setdefault(v, []):
                        found[v].append(lab)
        if len(found) > 1:
            listed = " and ".join(f'"{v}" ({", ".join(found[v])})' for v in group if v in found)
            s.warn(s.site, 0, f"unit written as {listed}")
            n += 1
    # (4) notation symbols the site-wide notation file does not list
    npath = s.asset("notation.json")
    if npath.exists():
        notation, nerr = load_json(npath)
        if not nerr and isinstance(notation, list):
            listed_syms = set()
            for e in notation:
                if isinstance(e, dict):
                    for k in ("symbol", "tex"):
                        if e.get(k):
                            listed_syms.add(lint_norm_symbol(str(e[k])))
            for rp, text in pages.items():
                for m in re.finditer(r'<td\b[^>]*\bclass="(?:[^"]*\s)?sym(?:\s[^"]*)?"[^>]*>([\s\S]*?)</td>', text):
                    sym = " ".join(_html_mod.unescape(LINT_TAG_RE.sub(" ", m.group(1))).split())
                    if sym and lint_norm_symbol(sym) not in listed_syms:
                        s.warn(s.site / rp, line_of(text, m.start()), f'notation symbol "{sym}" ({lint_label(rp)}) is not in assets/notation.json')
                        n += 1
    s.extra["lint"] = n


# ---- I4 derived policies: site.json licence / a11y (site check, errors) -------------------------------------------
class _SiteRep:
    """Report-like adapter so _common.validate_a11y reports through the SiteCtx (errors count as site issues)."""

    def __init__(self, s: SiteCtx):
        self.s = s

    def error(self, file, line, msg):
        self.s.error(file, line, msg)

    def warn(self, file, line, msg):
        self.s.warn(file, line, msg)


@site_check
def check_site_policies(s: SiteCtx) -> None:
    reg = s.reg if isinstance(s.reg, dict) else {}
    f = s.asset("site.json")
    if "licence" in reg and (not isinstance(reg["licence"], str) or not reg["licence"].strip()):
        s.error(f, 1, f"site.json licence must be a non-empty string (got {json.dumps(reg['licence'])})")
    if "a11y" in reg:
        validate_a11y(reg["a11y"], f, _SiteRep(s))
# ==== END pipeline ====


# ==== BLOCK protocol — C2 timing/waveform diagrams · C3 bit-field/packet diagrams · C4 sequence diagrams and state machines ====
# figure.timing / figure.bitfield hold JSON in <script type="application/json">; figure.seq / figure.fsm hold text in
# <script type="text/plain"> (or a <pre>). The checks below mirror the parsers between `protocol:begin` and `protocol:end`
# in template/assets/app.js (same grammar, same messages) and report the line inside the page. Data scripts are not
# JavaScript, so the inline-script syntax check (node) skips every inline script whose type is not a JavaScript type.
import html as _proto_html  # noqa: E402

_PROTO_FIG_RE = re.compile(r"<figure\b[^>]*>")
_PROTO_SCRIPT_RE = re.compile(r"<script\b([^>]*)>")
_PROTO_WAVE_RE = re.compile(r"^[01xz.=2-9pnPN|]*$")
_PROTO_SEQ_PART = re.compile(r"^(participant|actor)\s+([\w.]+)(?:\s+as\s+(.+))?$")
_PROTO_SEQ_MSG = re.compile(r"^([\w.]+)\s*(-->>|->>|--x|-x|--\)|-\)|-->|->)\s*([\w.]+)\s*:(.*)$")
_PROTO_SEQ_NOTE = re.compile(r"^note\s+(over|left of|right of)\s+([\w.]+)(?:\s*,\s*([\w.]+))?\s*:(.*)$", re.I)
_PROTO_SEQ_OPEN = re.compile(r"^(loop|alt|opt)(?:\s+(.*))?$")
_PROTO_SEQ_ELSE = re.compile(r"^else(?:\s+(.*))?$")
_PROTO_FSM_TR = re.compile(r"^(\[\*\]|[\w.]+)\s*-->\s*(\[\*\]|[\w.]+)\s*(?::(.*))?$")
_PROTO_FSM_DESC = re.compile(r"^(?:state\s+)?([\w.]+)\s*:(.*)$")
_PROTO_FSM_ALIAS = re.compile(r'^state\s+"([^"]+)"\s+as\s+([\w.]+)$')
_PROTO_FSM_DECL = re.compile(r"^state\s+([\w.]+)$")
_PROTO_FSM_DIR = re.compile(r"^direction\s+(LR|RL|TB|TD|BT)$")


def _proto_num(v):
    """JavaScript Number(v) for JSON values: NaN (None here) for objects, lists and null."""
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        t = v.strip()
        if not t:
            return 0.0
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _proto_whole(v) -> bool:
    n = _proto_num(v)
    return n is not None and n == n and n not in (float("inf"), float("-inf")) and n == int(n)


def proto_timing_issues(cfg) -> list:
    """[(item index or None, level, message)]; item index = position among the rows that have a wave (in document order)."""
    out: list = []
    if not isinstance(cfg, dict) or not isinstance(cfg.get("signal"), list):
        return [(None, "error", 'JSON needs a "signal" array')]
    rows: list = []

    def walk(items):
        for it in items:
            if isinstance(it, list):
                walk(it[1:] if it and isinstance(it[0], str) else it)
            elif isinstance(it, dict):
                if it.get("wave") is not None:
                    rows.append(it)
            else:
                out.append((None, "error", "every signal entry must be an object or a group array"))

    walk(cfg["signal"])
    nodes = set()
    longest = max([len(str(r["wave"])) for r in rows] or [0])
    for k, r in enumerate(rows):
        wave, name = str(r["wave"]), "" if r.get("name") is None else str(r.get("name"))
        bad = next((ch for ch in wave if not _PROTO_WAVE_RE.match(ch)), None)
        if bad is not None:
            out.append((k, "error", f'signal "{name}": unknown wave character "{bad}"'))
            continue
        d = r.get("data")
        nd = len(d) if isinstance(d, list) else len(d.split()) if isinstance(d, str) else 0
        nb = sum(1 for ch in wave if ch == "=" or ch in "23456789")
        if nd < nb:
            out.append((k, "error", f'signal "{name}": {nd} data label{"" if nd == 1 else "s"} for {nb} bus cells'))
        if len(wave) != longest:
            out.append((k, "warn", f'signal "{name}" has {len(wave)} cycles, the longest has {longest}'))
        if isinstance(r.get("node"), str):
            nodes.update(ch for ch in r["node"] if ch != "." and re.match(r"\w", ch))
    conf = cfg.get("config")
    if isinstance(conf, dict) and conf.get("hscale") is not None:
        hs = _proto_num(conf.get("hscale"))
        if hs is None or not hs > 0:
            out.append((None, "error", "config.hscale must be a number > 0"))
    for e in cfg.get("edge") or [] if isinstance(cfg.get("edge"), list) else []:
        em = re.match(r"^\s*(\w)\s*(<?)[-~|]+(>?)\s*(\w)\s*(.*)$", str(e))
        if not em:
            out.append((None, "warn", f'edge "{e}" is not "a->b label"'))
        elif em.group(1) not in nodes or em.group(4) not in nodes:
            out.append((None, "warn", f'edge "{e}" names a node no signal defines'))
    return out


def proto_bitfield_issues(cfg) -> list:
    """[(field index or None, level, message)]."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("fields"), list) or not cfg["fields"]:
        return [(None, "error", 'JSON needs a non-empty "fields" array')]
    out: list = []
    unit = "bit" if cfg.get("unit") is None else str(cfg.get("unit"))
    if unit not in ("bit", "byte"):
        out.append((None, "error", f'unit "{unit}" must be bit or byte'))
    total, ok = 0, True
    for k, f in enumerate(cfg["fields"]):
        f = f if isinstance(f, dict) else {}
        name = "" if f.get("name") is None else str(f.get("name"))
        n = _proto_num(f.get("bits"))
        if not _proto_whole(f.get("bits")) or n <= 0:
            out.append((k, "error", f'field {k + 1}{f" {chr(34)}{name}{chr(34)}" if name else ""}: bits must be a whole number > 0'))
            ok = False
        else:
            total += int(n)
        ty = f.get("type")
        if ty is not None and str(ty) != "reserved" and not re.fullmatch(r"[2-9]", str(ty)):
            out.append((k, "warn", f'field {k + 1}: type "{ty}" is not reserved or 2–9 (drawn plain)'))
    lanes = cfg.get("lanes")
    if lanes is not None and (not _proto_whole(lanes) or _proto_num(lanes) <= 0):
        out.append((None, "error", "lanes must be a whole number > 0"))
    elif ok and lanes is not None and total % int(_proto_num(lanes)):
        ln_ = int(_proto_num(lanes))
        out.append((None, "warn", f"{total} {unit}s do not fill rows of {ln_} (last row {total % ln_})"))
    return out


def proto_parse_seq(src: str):
    """(errors, warnings) as [(line in the source, 1-based, message)] — the mirror of parseSeq in app.js."""
    errors, warnings, stack, declared, uses, parts = [], [], [], set(), [], set()
    for i, raw in enumerate(src.split("\n")):
        ln, s = i + 1, raw.strip()
        if not s or s.startswith("%%") or s == "sequenceDiagram" or s == "autonumber":
            continue
        m = _PROTO_SEQ_PART.match(s)
        if m:
            declared.add(m.group(2)); parts.add(m.group(2))
            continue
        m = _PROTO_SEQ_MSG.match(s)
        if m:
            uses += [(m.group(1), ln), (m.group(3), ln)]; parts.update((m.group(1), m.group(3)))
            continue
        m = _PROTO_SEQ_NOTE.match(s)
        if m:
            uses.append((m.group(2), ln)); parts.add(m.group(2))
            if m.group(3):
                uses.append((m.group(3), ln)); parts.add(m.group(3))
            continue
        m = _PROTO_SEQ_OPEN.match(s)
        if m:
            stack.append((m.group(1), ln))
            continue
        if _PROTO_SEQ_ELSE.match(s):
            if not stack or stack[-1][0] != "alt":
                errors.append((ln, '"else" outside an alt block'))
            continue
        if s == "end":
            if not stack:
                errors.append((ln, '"end" without loop, alt or opt'))
            else:
                stack.pop()
            continue
        errors.append((ln, f"line does not parse: {s}"))
    errors += [(ln, f'"{kind}" is never closed with "end"') for kind, ln in stack]
    if declared:
        seen = set()
        for u, ln in uses:
            if u not in declared and u not in seen:
                seen.add(u)
                warnings.append((ln, f'message to undeclared participant "{u}"'))
    if not errors and not parts:
        errors.append((1, "no participants and no messages"))
    return errors, warnings


def proto_parse_fsm(src: str):
    """(errors, warnings) as [(line in the source, 1-based, message)] — the mirror of parseFsm in app.js."""
    errors, warnings, states, initial = [], [], set(), False
    for i, raw in enumerate(src.split("\n")):
        ln, s = i + 1, raw.strip()
        if not s or s.startswith("%%") or re.fullmatch(r"stateDiagram(-v2)?", s) or _PROTO_FSM_DIR.match(s):
            continue
        m = _PROTO_FSM_TR.match(s)
        if m:
            if m.group(1) == "[*]":
                initial = True
                if m.group(2) == "[*]":
                    errors.append((ln, "a transition from [*] to [*]"))
                    continue
            states.update(x for x in (m.group(1), m.group(2)) if x != "[*]")
            continue
        m = _PROTO_FSM_ALIAS.match(s) or _PROTO_FSM_DECL.match(s)
        if m:
            states.add(m.group(m.lastindex))
            continue
        m = _PROTO_FSM_DESC.match(s)
        if m:
            if m.group(2).strip():
                states.add(m.group(1))
            continue
        errors.append((ln, f"line does not parse: {s}"))
    if not errors and not states:
        errors.append((1, "no states"))
    if not initial and not errors:
        warnings.append((1, "no initial [*] transition"))
    return errors, warnings


def _proto_kind(tag: str):
    cm = re.search(r'\sclass="([^"]*)"', tag)
    cls = cm.group(1).split() if cm else []
    return next((k for k in ("timing", "bitfield", "seq", "fsm") if k in cls), None)


@page_check
def protocol_checks(p: PageCtx) -> None:
    """C2 timing, C3 bit field (JSON) and C4 sequence / state machine (text) figures parse (the core node check skips data scripts)."""
    s = p.s
    for fm in _PROTO_FIG_RE.finditer(s):
        kind = _proto_kind(fm.group(0))
        if not kind:
            continue
        ln = line_of(s, fm.start())
        idm = re.search(r'\sid="([^"]+)"', fm.group(0))
        fid = idm.group(1) if idm else f"at line {ln}"
        label = {"seq": "sequence"}.get(kind, kind)
        endf = s.find("</figure>", fm.end())
        body = s[fm.end():endf if endf >= 0 else len(s)]
        if "<figcaption" not in body:
            p.warn(ln, f"{label} {fid} has no figcaption")
        json_kind = kind in ("timing", "bitfield")
        sm = re.search(r'<script\b[^>]*\btype="' + ("application/json" if json_kind else "text/plain") + r'"[^>]*>([\s\S]*?)</script>', body)
        pre = None if json_kind or sm else re.search(r"<pre\b[^>]*>([\s\S]*?)</pre>", body)
        src_m = sm or pre
        if not src_m:
            p.error(ln, f'{label} {fid} has no <script type="{"application/json" if json_kind else "text/plain"}">{"" if json_kind else " or <pre>"} source')
            continue
        text = src_m.group(1).replace("\r\n", "\n")
        if pre:
            text = _proto_html.unescape(re.sub(r"<[^>]+>", "", text))
        base = line_of(s, fm.end() + src_m.start(1))
        first = base + text[:len(text) - len(text.lstrip())].count("\n")   # the first line that holds content
        whole = {"no states", "no participants and no messages", "no initial [*] transition"}

        def report(level, line, msg):
            (p.error if level == "error" else p.warn)(line, f"{label} {fid}: {msg}")

        if json_kind:
            try:
                cfg = json.loads(text)
            except json.JSONDecodeError as e:
                report("error", base + e.lineno - 1, f"invalid JSON: {e.msg}")
                continue
            key = r'"wave"\s*:' if kind == "timing" else r'"bits"\s*:'
            spots = [base + text.count("\n", 0, km.start()) for km in re.finditer(key, text)]
            issues = proto_timing_issues(cfg) if kind == "timing" else proto_bitfield_issues(cfg)
            for k, level, msg in issues:
                report(level, spots[k] if k is not None and k < len(spots) else first, msg)
        else:
            errs, warns = proto_parse_seq(text) if kind == "seq" else proto_parse_fsm(text)
            for i, msg in errs:
                report("error", first if msg in whole else base + i - 1, msg)
            for i, msg in warns:
                report("warn", first if msg in whole else base + i - 1, msg)
# ==== END protocol ====


# ==== BLOCK circuit — C8 schematic symbols, pinouts and register maps ====
# C8: figure.schematic / figure.pinout / figure.regmap hold their JSON in a <template> child (a <script type="application/json"> would
# be fed to node's syntax check as JavaScript); the checks below mirror pinoutParts / regmapParts / schematicSvg in app.js.
# CIRCUIT_SYMS must equal Object.keys(SYM) in app.js (a feature test compares them).
# The core link check skips same-page "#sym-…" anchors (the sprite is injected at view time); circuit_checks reports unknown symbols.
import html as _circ_html  # noqa: E402 — circuit block

CIRCUIT_SYMS = ["resistor", "capacitor", "cap-polar", "inductor", "diode", "led", "zener", "npn", "pnp", "nmos", "pmos", "opamp",
                "ground", "vcc", "battery", "switch", "crystal", "fuse", "port"]
CIRCUIT_PIN_TYPES = ["power", "ground", "io", "input", "output", "analog", "clock", "control", "nc"]
CIRCUIT_ACCESS = ["RW", "RO", "WO", "W1C", "RSVD"]
_CIRC_FIG_RE = re.compile(r'<figure\b[^>]*\bclass="(?:[^"]*\s)?(schematic|pinout|regmap)(?:\s[^"]*)?"[^>]*>')
_CIRC_USE_RE = re.compile(r'<use\b[^>]*?\s(?:xlink:)?href="#(sym-[^"]*)"')


def _circ_num(v):
    """An integer from 12, "12", "0x1C", "0b1010" or "1_000"; None otherwise (mirrors cNum in app.js)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v.is_integer() else None
    if not isinstance(v, str):
        return None
    s = v.strip().replace("_", "").lower()
    if re.fullmatch(r"0x[0-9a-f]+", s):
        return int(s[2:], 16)
    if re.fullmatch(r"0b[01]+", s):
        return int(s[2:], 2)
    if re.fullmatch(r"\d+", s):
        return int(s)
    return None


def _circ_sym(v) -> bool:
    return isinstance(v, str) and re.sub(r"^#?sym-", "", v.strip().lower()) in CIRCUIT_SYMS


def _circ_bits(msb: int, lsb: int) -> str:
    return str(msb) if msb == lsb else f"{msb}:{lsb}"


def _circ_schematic(spec, err) -> None:
    parts = spec.get("parts")
    if not isinstance(parts, list) or not parts:
        err("has no parts")
        parts = []
    for k, part in enumerate(parts, 1):
        part = part if isinstance(part, dict) else {}
        if not _circ_sym(part.get("sym")):
            err(f'part {k} has unknown symbol "{part.get("sym")}"')
        if any(isinstance(part.get(a), bool) or not isinstance(part.get(a), (int, float)) for a in ("x", "y")):
            err(f"part {k} needs numeric x and y")
        if part.get("rot", 0) not in (0, 90, 180, 270) or isinstance(part.get("rot"), bool):
            err(f"part {k} rot must be 0, 90, 180 or 270")
    for k, w in enumerate(spec.get("wires") or [], 1):
        if not isinstance(w, list) or len(w) < 4 or len(w) % 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in w):
            err(f"wire {k} needs an even list of at least 4 numbers")
    for k, d in enumerate(spec.get("dots") or [], 1):
        if not isinstance(d, list) or len(d) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in d):
            err(f"dot {k} needs [x, y]")


def _circ_pinout(spec, err, warn) -> None:
    pm = re.fullmatch(r"(DIP|SOIC|QFP|header)(?:-(\d+))?", str(spec.get("package", "")).strip(), re.I)
    if not pm:
        err(f'package "{spec.get("package")}" is not DIP, SOIC, QFP or header')
    pins = spec.get("pins")
    if not isinstance(pins, list) or not pins:
        err("has no pins")
        return
    nums: list[int] = []
    for k, p in enumerate(pins, 1):
        p = p if isinstance(p, dict) else {}
        n = _circ_num(p.get("n"))
        if n is None or n < 1:
            err(f"pin #{k} has no number n")
            continue
        if n in nums:
            err(f"duplicate pin number {n}")
        nums.append(n)
        if not str(p.get("name") or "").strip():
            err(f"pin {n} has no name")
        t = str(p.get("type") or "io").lower()
        if t not in CIRCUIT_PIN_TYPES:
            warn(f'pin {n} type "{p.get("type")}" is not one of {", ".join(CIRCUIT_PIN_TYPES)} (drawn in a neutral colour)')
    count = len(set(nums))
    missing = [i for i in range(1, count + 1) if i not in nums]
    if missing:
        err(f"pin numbers must run 1..{count} (missing {', '.join(map(str, missing[:5]))})")
    if not pm:
        return
    kind = "header" if pm.group(1).lower() == "header" else pm.group(1).upper()
    if pm.group(2) and int(pm.group(2)) != len(pins):
        err(f"package {spec.get('package')} but {len(pins)} pins")
    if kind in ("DIP", "SOIC") and len(pins) % 2:
        err(f"{kind} needs an even pin count (got {len(pins)})")
    if kind == "QFP" and len(pins) % 4:
        err(f"QFP needs a pin count divisible by 4 (got {len(pins)})")
    if kind == "header":
        rows = spec.get("rows", 1)
        if rows not in (1, 2):
            err(f"header rows must be 1 or 2 (got {rows})")
        elif rows == 2 and len(pins) % 2:
            err(f"header with 2 rows needs an even pin count (got {len(pins)})")


def _circ_regmap(spec, err, warn) -> None:
    width = spec.get("width")
    if width not in (8, 16, 32) or isinstance(width, bool):
        err(f"width must be 8, 16 or 32 (got {width})")
        return
    regs = spec.get("registers")
    if not isinstance(regs, list) or not regs:
        err("has no registers")
        return
    seen: dict[int, str] = {}
    for k, r in enumerate(regs, 1):
        r = r if isinstance(r, dict) else {}
        name = str(r.get("name") or f"register {k}")
        addr = _circ_num(r.get("addr"))
        if addr is None:
            err(f'{name} addr "{r.get("addr")}" is not a number')
        elif addr in seen:
            err(f"duplicate register address 0x{addr:02X} ({seen[addr]}, {name})")
        else:
            seen[addr] = name
        if r.get("reset") is not None:
            rv = _circ_num(r.get("reset"))
            if rv is None:
                err(f'{name} reset "{r.get("reset")}" is not a number')
            elif rv >= 2 ** width:
                err(f"{name} reset 0x{rv:X} does not fit {width} bits")
        owner: dict[int, str] = {}
        for f in r.get("fields") or []:
            f = f if isinstance(f, dict) else {}
            fname = str(f.get("name") or "?")
            label = f"{name}.{fname}"
            msb, lsb = f.get("msb"), f.get("lsb")
            if any(isinstance(v, bool) or not isinstance(v, int) for v in (msb, lsb)):
                err(f"{label} needs whole-number msb and lsb")
                continue
            if msb < lsb:
                err(f"{label} msb {msb} is below lsb {lsb}")
                continue
            if lsb < 0 or msb >= width:
                err(f"{label} bits {_circ_bits(msb, lsb)} outside a {width}-bit register")
                continue
            acc = str(f.get("access") or "").upper()
            if acc not in CIRCUIT_ACCESS:
                err(f'{label} access "{f.get("access")}" is not RW, RO, WO, W1C or RSVD')
            if f.get("reset") is not None:
                fv = _circ_num(f.get("reset"))
                if fv is None:
                    err(f'{label} reset "{f.get("reset")}" is not a number')
                elif fv >= 2 ** (msb - lsb + 1):
                    err(f"{label} reset 0x{fv:X} does not fit {msb - lsb + 1} bit{'s' if msb > lsb else ''}")
            clash = sorted({owner[b] for b in range(lsb, msb + 1) if b in owner})
            for other in clash:
                bit = max(b for b in range(lsb, msb + 1) if owner.get(b) == other)
                err(f"{name} fields {other} and {fname} overlap at bit {bit}")
            for b in range(lsb, msb + 1):
                owner.setdefault(b, fname)
        gaps, b = [], width - 1
        while b >= 0:
            if b in owner:
                b -= 1
                continue
            hi = b
            while b >= 0 and b not in owner:
                b -= 1
            gaps.append(_circ_bits(hi, b + 1))
        if gaps:
            warn(f"{name} bits {', '.join(gaps)} are not covered by a field — mark them RSVD")


@page_check
def circuit_checks(p: PageCtx) -> None:
    """C8: <use href="#sym-…"> names a library symbol; schematic, pinout and register-map JSON parse and make sense."""
    ns = p.no_script
    # the core link check skips "#sym-…" anchors (the sprite is injected at view time); unknown symbols are reported here
    for m in _CIRC_USE_RE.finditer(ns):
        if not _circ_sym(m.group(1)):
            p.error(p.line(m.start()), f'unknown symbol "{m.group(1)}" in <use href> (the library: {", ".join(CIRCUIT_SYMS)})')
    for m in _CIRC_FIG_RE.finditer(ns):
        kind, tag, ln = m.group(1), m.group(0), p.line(m.start())
        idm = re.search(r'\sid="([^"]+)"', tag)
        fid = idm.group(1) if idm else f"at line {ln}"
        endf = ns.find("</figure>", m.end())
        body = ns[m.end():endf if endf >= 0 else len(ns)]

        def err(msg, at=None, kind=kind, fid=fid, ln=ln):
            p.error(at or ln, f"{kind} {fid}: {msg}" if not msg.startswith("has ") else f"{kind} {fid} {msg}")

        def warn(msg, kind=kind, fid=fid, ln=ln):
            p.warn(ln, f"{kind} {fid}: {msg}")

        if not idm:
            p.warn(ln, f"{kind} figure without id (the download file and the title id need one)")
        if not re.search(r"<figcaption\b", body):
            p.warn(ln, f"{kind} {fid} has no figcaption")
        tm = re.search(r"<template\b[^>]*>([\s\S]*?)</template>", body)
        if not tm:
            err("has no <template> holding its JSON")
            continue
        try:
            spec = json.loads(_circ_html.unescape(tm.group(1)))
        except json.JSONDecodeError as e:
            err(f"invalid JSON ({e.msg})", p.line(m.end() + tm.start(1)) + e.lineno - 1)
            continue
        if not isinstance(spec, dict):
            err("JSON must be an object")
            continue
        if kind == "schematic":
            _circ_schematic(spec, err)
        elif kind == "pinout":
            _circ_pinout(spec, err, warn)
        else:
            _circ_regmap(spec, err, warn)
# ==== END circuit ====


# ==== BLOCK study — B4 flashcards · F1 notes, highlights, bookmarks and resume position ====
# B4: [data-flashcards] names real glossary terms (mirrors flashDeck in app.js: "all"/empty = every term, else a comma list
# matched case-insensitively against `term`); data-tags is a comma list of tag names; a deck needs at least 3 terms.
# F1 is runtime only: site.json `notes` must be a boolean; data-no-notes only works on <main> (warning).
STUDY_FC_RE = re.compile(r"<([a-zA-Z][\w-]*)\b([^>]*\sdata-flashcards(?![\w-])(?:=\"([^\"]*)\")?[^>]*)>")
STUDY_TAG_RE = re.compile(r"^[^\W_](?:[\w .:/+-]*[\w+])?$")
STUDY_NO_NOTES_RE = re.compile(r"<([a-zA-Z][\w-]*)\b[^>]*\sdata-no-notes\b[^>]*>")
STUDY_MIN_TERMS = 3


def _study_tags(g) -> list:
    t = g.get("tags")
    out = [x for x in t if isinstance(x, str)] if isinstance(t, list) else ([x for x in t.split(",")] if isinstance(t, str) else [])
    if isinstance(g.get("group"), str):
        out.append(g["group"])
    return [x.strip().lower() for x in out if x.strip()]


@page_check
def study_flashcards(p: PageCtx) -> None:
    """B4: every term a flashcards deck names is in glossary.json; data-tags is well formed; warn on small or empty decks."""
    gl = [g for g in p.glossary if isinstance(g, dict) and isinstance(g.get("term"), str) and g["term"].strip()]
    terms = {g["term"].strip().lower() for g in gl}
    tags = {t for g in gl for t in _study_tags(g)}
    for m in STUDY_FC_RE.finditer(p.no_script):
        attrs, ln = m.group(2), p.line(m.start())
        im = re.search(r'\sid="([^"]*)"', attrs)
        name = f"flashcards {im.group(1)}" if im else "flashcards"
        spec = (m.group(3) or "").strip()
        if 0 < len(terms) < STUDY_MIN_TERMS:   # an empty glossary is a fresh scaffold, not a mistake
            p.warn(ln, f"{name}: the glossary has {len(terms)} term{'' if len(terms) == 1 else 's'} — a deck needs at least {STUDY_MIN_TERMS}")
        if spec and spec.lower() != "all":
            for t in [x.strip() for x in spec.split(",")]:
                if not t:
                    p.error(ln, f'{name}: data-flashcards "{spec}" has an empty item (use "all" or a comma list of terms)')
                elif t.lower() not in terms:
                    p.error(ln, f'{name}: term "{t}" is not in glossary.json')
        tm = re.search(r'\sdata-tags(?![\w-])(?:="([^"]*)")?', attrs)
        if tm:
            raw = tm.group(1) or ""
            items = [x.strip() for x in raw.split(",")]
            if not raw.strip() or any(not x or not STUDY_TAG_RE.match(x) for x in items):
                p.error(ln, f'{name}: data-tags "{raw}" is malformed (a comma list of tag names: letters, digits, spaces, - _ . : / +)')
            else:
                for x in items:
                    if x.lower() not in tags:
                        p.warn(ln, f'{name}: tag "{x}" matches no glossary entry (glossary.json tags / group)')
    for m in STUDY_NO_NOTES_RE.finditer(p.no_script):
        if m.group(1).lower() != "main":
            p.warn(p.line(m.start()), f"data-no-notes on <{m.group(1)}> is ignored (put it on <main>)")


@site_check
def study_site(s: SiteCtx) -> None:
    """B4 glossary tags / group shape; F1 site.json notes flag."""
    gl_p, sj_p = s.asset("glossary.json"), s.asset("site.json")
    for g in s.glossary:
        if not isinstance(g, dict) or not g.get("term"):
            continue
        t = g.get("tags")
        if t is not None and not (isinstance(t, list) and all(isinstance(x, str) and x.strip() for x in t)):
            s.error(gl_p, 1, f'glossary term "{g["term"]}": tags must be a list of strings')
        if "group" in g and not (isinstance(g["group"], str) and g["group"].strip()):
            s.error(gl_p, 1, f'glossary term "{g["term"]}": group must be a non-empty string')
    if isinstance(s.reg, dict) and "notes" in s.reg and not isinstance(s.reg["notes"], bool):
        s.error(sj_p, 1, f"site.json notes must be true or false (got {json.dumps(s.reg['notes'])})")
# ==== END study ====


# ==== BLOCK runner — D5 in-browser code runners (JS sandbox, Python via Pyodide) ====
# div.runner[id][data-lang="js|python"] > pre > code (starting code); optional data-expected (stdout), data-timeout (ms, a
# positive integer), data-setup (the id of a hidden <script type="text/plain">, prepended to the code at run time).
# Errors: runner without id · unknown data-lang · no starting code · data-setup missing or not a text/plain script ·
# bad data-timeout · duplicate runner id. Warning: a Python runner on a single-format page (the bundle is offline-first).
# Opt-in (environment ATLAS_RUN_RUNNERS=1): every JS runner with data-expected runs under node with the browser's console
# formatting, and its stdout must equal data-expected; skipped with one warning when node is not on PATH.
# A text/plain <script> holds setup code (Python, too), not page JavaScript: the core inline-script check skips non-JS types.
import html as _rn_html  # noqa: E402 — runner block only
import os as _rn_os  # noqa: E402

RUNNER_LANGS = ("js", "python")
_RN_DIV_RE = re.compile(r"<div\b[^>]*>")
_RN_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)</script>")
_RN_STATE = {"node_warned": False}
# the sandbox's console formatting (runSrcdoc in app.js), so node prints what the browser prints
_RN_NODE_SHIM = ('(function(){function f(v){if(typeof v==="string")return v;if(v instanceof Error)return v.name+": "+v.message;'
                 'try{var j=JSON.stringify(v);return j===undefined?String(v):j}catch(e){return String(v)}}'
                 'function w(o){return function(){o.write(Array.prototype.map.call(arguments,f).join(" ")+"\\n")}}'
                 'console.log=console.info=console.debug=w(process.stdout);console.warn=console.error=w(process.stderr)})();\n')


def _rn_norm(text: str) -> str:
    """Same as runNorm in app.js: CRLF -> LF, trailing spaces per line dropped, leading/trailing blank lines dropped."""
    lines = [ln.rstrip() for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n")


def _rn_attr(tag: str, name: str):
    m = re.search(r"\s" + re.escape(name) + r'="([^"]*)"', tag)
    return m.group(1) if m else None


def _rn_div_end(s: str, start: int) -> int:
    depth = 0
    for m in re.finditer(r"<div\b|</div>", s[start:]):
        depth += 1 if m.group(0) == "<div" else -1
        if depth == 0:
            return start + m.end()
    return len(s)


def _rn_text_plain(attrs: str) -> bool:
    t = _rn_attr(attrs, "type")
    return t is not None and t.strip().lower() == "text/plain"


def _rn_node_run(code: str, timeout_ms: int):
    """-> (stdout, error message or None), or None when node is not on PATH."""
    node = shutil.which("node")
    if not node:
        return None
    with tempfile.TemporaryDirectory(prefix="atlas-learn-runner-") as td:
        f = Path(td) / "runner.js"
        f.write_text(_RN_NODE_SHIM + code, encoding="utf-8")
        try:
            pr = subprocess.run([node, str(f)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=timeout_ms / 1000 + 5, cwd=td)
        except subprocess.TimeoutExpired:
            return "", f"timed out after {timeout_ms} ms"
        except OSError as e:
            return "", f"node failed: {e}"
    err = None
    if pr.returncode:
        tail = [ln for ln in (pr.stderr or "").splitlines() if re.match(r"\w*Error\b", ln)]
        err = (tail[0] if tail else f"exit code {pr.returncode}")[:160]
    return pr.stdout or "", err


@page_check
def runner_checks(p: PageCtx) -> None:
    s = p.s
    scripts: dict = {}
    for i, m in enumerate(_RN_SCRIPT_RE.finditer(s)):
        idm = re.search(r'\sid="([^"]+)"', m.group(1))
        if idm:
            scripts[idm.group(1)] = (m.group(1), m.group(2))
    ns = p.no_script
    seen: dict = {}
    run_node = _rn_os.environ.get("ATLAS_RUN_RUNNERS", "") not in ("", "0")
    boxes = [m for m in _RN_DIV_RE.finditer(ns) if re.search(r'\bclass="(?:[^"]*\s)?runner(?:\s[^"]*)?"', m.group(0))]
    for k, m in enumerate(boxes):
        tag, ln = m.group(0), p.line(m.start())
        rid = _rn_attr(tag, "id")
        label = rid or f"#{k + 1}"
        if not rid:
            p.error(ln, f"runner without id (runner {label} on this page; edits are saved per id)")
        elif rid in seen:
            p.error(ln, f"duplicate runner id {rid} (first at line {seen[rid]})")
        else:
            seen[rid] = ln
        lang = _rn_attr(tag, "data-lang")
        if lang not in RUNNER_LANGS:
            p.error(ln, f'runner {label}: unknown data-lang "{lang or ""}" (js or python)')
        body = ns[m.end():_rn_div_end(ns, m.start())]
        cm = re.search(r"<pre\b[^>]*>\s*<code\b[^>]*>([\s\S]*?)</code>", body)
        code = _rn_html.unescape(re.sub(r"<[^>]+>", "", cm.group(1))) if cm else ""
        if not code.strip():
            p.error(ln, f"runner {label} has no starting code (pre > code)")
        to = _rn_attr(tag, "data-timeout")
        timeout = 5000
        if to is not None:
            if re.fullmatch(r"\d+", to) and int(to) > 0:
                timeout = int(to)
            else:
                p.error(ln, f'runner {label}: data-timeout "{to}" is not a positive integer (milliseconds)')
        setup_id, setup = _rn_attr(tag, "data-setup"), ""
        if setup_id is not None:
            if setup_id not in scripts:
                p.error(ln, f'runner {label}: data-setup "{setup_id}" not found (needs <script type="text/plain" id="{setup_id}"> on this page)')
            elif not _rn_text_plain(scripts[setup_id][0]):
                p.error(ln, f'runner {label}: data-setup "{setup_id}" must be a <script type="text/plain">')
            else:
                setup = scripts[setup_id][1].strip("\n") + "\n"
        if lang == "python" and p.single:
            p.warn(ln, f"runner {label}: Python runner on a single-format page — the bundle is offline-first and Pyodide needs a network")
        expected = _rn_attr(tag, "data-expected")
        if not (run_node and lang == "js" and expected is not None and code.strip()):
            continue
        res = _rn_node_run(setup + code, timeout)
        if res is None:
            if not _RN_STATE["node_warned"]:
                _RN_STATE["node_warned"] = True
                p.warn(0, "runner node check skipped (node not on PATH)")
            continue
        out, err = res
        want = _rn_norm(_rn_html.unescape(expected))
        if err:
            p.error(ln, f"runner {label}: node run failed: {err}")
        elif _rn_norm(out) != want:
            g, w = _rn_norm(out).split("\n"), want.split("\n")
            j = next((i for i in range(max(len(g), len(w))) if (g[i] if i < len(g) else None) != (w[i] if i < len(w) else None)), 0)
            p.error(ln, f"runner {label}: node output differs from data-expected at line {j + 1}: "
                        f"got {json.dumps(g[j] if j < len(g) else '(nothing)', ensure_ascii=False)}, "
                        f"expected {json.dumps(w[j] if j < len(w) else '(nothing)', ensure_ascii=False)}")

# ==== END runner ====


# ==== BLOCK export — G1 offline bundle · G2 PDF/print pipeline ====
# G1: a site whose site.json says "vendor": true (scaffold.py --offline) must load nothing from a CDN, and every file
# assets/vendor/manifest.json lists must be on disk with its recorded sha256. G2 is CSS + runtime + print_pdf.py.
EXPORT_TAG_RE = re.compile(r"<(link|script)\b[^>]*>", re.I)


def _export_vendored(reg) -> bool:
    return isinstance(reg, dict) and reg.get("vendor") is True


@page_check
def export_cdn_refs(p: PageCtx) -> None:
    """G1: a vendored site's pages may not keep a CDN <link>/<script> (fonts, KaTeX, highlight.js)."""
    if not _export_vendored(p.reg):
        return
    from vendor import CDN_HOSTS  # noqa: E402 — same folder
    for m in EXPORT_TAG_RE.finditer(p.s):
        for am in re.finditer(r'\b(?:href|src)\s*=\s*"(https?://([^/"]+)[^"]*)"', m.group(0)):
            if am.group(2).lower() in CDN_HOSTS:
                p.error(line_of(p.s, m.start()), f"vendored site: <{m.group(1).lower()}> still loads {am.group(1)[:90]} from a CDN "
                        "— run scaffold.py --offline to point it at assets/vendor/")


@site_check
def export_vendor_manifest(s: SiteCtx) -> None:
    """G1: "vendor" is true or absent; a vendored site has assets/vendor/manifest.json and every file it lists matches."""
    if not isinstance(s.reg, dict) or "vendor" not in s.reg:
        return
    sj = s.asset("site.json")
    if not _export_vendored(s.reg):
        s.error(sj, 1, f'site.json vendor must be true or absent (got {json.dumps(s.reg["vendor"])})')
        return
    mp = s.asset("vendor") / "manifest.json"
    if not mp.is_file():
        s.error(sj, 1, 'site.json has "vendor": true but assets/vendor/manifest.json is missing — run scaffold.py --offline')
        return
    man, err = load_json(mp)
    files = man.get("files") if isinstance(man, dict) else None
    if err or not isinstance(files, dict):
        s.error(mp, 1, err or 'manifest.json must be {"files": {path: {url, bytes, sha256}}}')
        return
    import hashlib
    text = mp.read_text(encoding="utf-8-sig")
    for rel, e in files.items():
        pos = text.find(json.dumps(rel) + ":")
        ln = line_of(text, pos) if pos >= 0 else 1
        f = s.asset("vendor") / rel
        if not f.is_file():
            s.error(mp, ln, f"vendor file {rel} is missing — run scaffold.py --offline")
        elif not isinstance(e, dict) or hashlib.sha256(f.read_bytes()).hexdigest() != e.get("sha256"):
            s.error(mp, ln, f"vendor file {rel} does not match its manifest sha256 — run scaffold.py --offline")
    s.extra["vendored"] = len(files)

# ==== END export ====


# ==== BLOCK research — I1 reader emphasis from the Use answer · I5 discovery extensions ====
# ==== END research ====



def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siteDir")
    ap.add_argument("--pages")
    ap.add_argument("--quiet", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    site = Path(args.siteDir).resolve()
    if not site.is_dir():
        return usage_error(f"no such directory: {site}")
    rep = Report("gate", "site")
    site_issues = 0

    def site_issue(file, line, msg):
        nonlocal site_issues
        site_issues += 1
        rep.error(file, line, msg)

    # ---------------------------------------------------------------- registry
    site_json_p, site_js_p = site / "assets" / "site.json", site / "assets" / "site.js"
    gl_json_p, gl_js_p = site / "assets" / "glossary.json", site / "assets" / "glossary.js"
    reg, err = load_json(site_json_p)
    pages_reg: list[dict] = []
    pages_dir = ""
    home = "index.html"
    mode = "site"
    budget_kb = DEFAULT_BUDGET_KB
    if err:
        site_issue(site_json_p, 1, err)
    elif not isinstance(reg, dict):
        site_issue(site_json_p, 1, "site.json must be a JSON object")
    else:
        for key in ("title", "storagePrefix", "pages"):
            if key not in reg:
                site_issue(site_json_p, 1, f"site.json lacks `{key}`")
        pd = reg.get("pagesDir", "")
        if not isinstance(pd, str) or pd.startswith("/") or "\\" in pd or (pd and not pd.endswith("/")):
            site_issue(site_json_p, 1, f"pagesDir must be a relative folder ending with `/` or \"\" (got {json.dumps(pd)})")
        else:
            pages_dir = pd
        home = reg.get("home") or "index.html"
        mode = reg.get("mode") or "site"
        if mode not in ("single", "site"):
            site_issue(site_json_p, 1, f"site.json mode must be single or site (got {json.dumps(mode)})")
            mode = "site"
        bk = reg.get("budgetKb", DEFAULT_BUDGET_KB)
        budget_kb = bk if isinstance(bk, (int, float)) and not isinstance(bk, bool) and bk > 0 else DEFAULT_BUDGET_KB
        if "theme" in reg:
            before = len(rep.errors)
            validate_theme(reg["theme"], site_json_p, rep)
            site_issues += len(rep.errors) - before
        pages_reg = reg.get("pages") if isinstance(reg.get("pages"), list) else []
        levels = reg.get("levels") or {}
        for p in pages_reg:
            if not isinstance(p, dict) or not all(k in p for k in ("file", "num", "title", "group")):
                site_issue(site_json_p, 1, f"page entry needs file, num, title, group: {json.dumps(p)[:60]}")
                continue
            if "/" in p["file"] or "\\" in p["file"]:
                site_issue(site_json_p, 1, f"{p['file']}: registry `file` must be a bare file name")
            if "level" in p and (not isinstance(p["level"], int) or str(p["level"]) not in {str(k) for k in levels}):
                site_issue(site_json_p, 1, f"{p['file']}: level {p.get('level')} is not one of the named levels")
            if not p.get("desc"):
                rep.warn(site_json_p, 1, f"{p['file']}: no desc")
        if site_js_p.exists():
            if site_js_p.read_text(encoding="utf-8-sig").replace("\r\n", "\n") != site_js(reg):
                site_issue(site_js_p, 1, "assets/site.js is out of sync with site.json — run scaffold.py --sync")
        else:
            site_issue(site_js_p, 1, "assets/site.js missing — run scaffold.py --sync")
    glossary, gerr = load_json(gl_json_p)
    if gerr:
        site_issue(gl_json_p, 1, gerr)
        glossary = []
    elif not isinstance(glossary, list):
        site_issue(gl_json_p, 1, "glossary.json must be a JSON array")
        glossary = []
    else:
        if gl_js_p.exists():
            if gl_js_p.read_text(encoding="utf-8-sig").replace("\r\n", "\n") != glossary_js(glossary):
                site_issue(gl_js_p, 1, "assets/glossary.js is out of sync with glossary.json — run scaffold.py --sync")
        else:
            site_issue(gl_js_p, 1, "assets/glossary.js missing — run scaffold.py --sync")

    # ------------------------------------------------------------ page files
    # rel paths (posix) of every page; basename -> rel path for registry/glossary lookups
    rel_paths: list[str] = []
    root_html = sorted(f.name for f in site.glob("*.html") if not f.name.startswith("_") and f.is_file())
    if pages_dir and pages_dir.split("/")[0] == "tmp":
        site_issue(site_json_p, 1, "pagesDir must not be the topic's tmp/ folder")
        pages_dir = ""
    if pages_dir:
        for name in root_html:
            if name == home:
                rel_paths.append(name)
            else:
                site_issue(site / name, 1, f"{name} must live under {pages_dir} (only {home} sits at the site root)")
        pdir = site / pages_dir
        if pdir.is_dir():
            rel_paths += sorted(pages_dir + f.name for f in pdir.glob("*.html") if not f.name.startswith("_"))
        else:
            site_issue(pdir, 1, f"pages folder {pages_dir} missing")
    else:
        rel_paths = root_html
    single = mode == "single"
    if single:
        regs = [p for p in pages_reg if isinstance(p, dict)]
        if len(regs) != 1 or regs[0].get("file") != home:
            site_issue(site_json_p, 1, "single mode: site.json must list exactly one page (the home)")
        for rp in list(rel_paths):
            if rp != home:
                site_issue(site / rp, 1, f"single mode: {rp} is not allowed (one page only)")
                rel_paths.remove(rp)
    by_name: dict[str, str] = {}
    for rp in rel_paths:
        by_name.setdefault(posixpath.basename(rp), rp)
    pages_reg = [p for p in pages_reg if isinstance(p, dict) and "file" in p]
    for p in pages_reg:
        if p["file"] not in by_name:
            site_issue(site_json_p, 1, f"registry lists {p['file']} but the file does not exist" + (f" under {pages_dir}" if pages_dir and p["file"] != home else ""))
    reg_files = {p["file"] for p in pages_reg}
    for rp in rel_paths:
        if posixpath.basename(rp) not in reg_files:
            site_issue(site / rp, 1, f"{rp} is not in assets/site.json pages[] (sidebar/pager/search will not know it)")
    seen_num: dict[str, str] = {}
    for p in pages_reg:
        n = str(p.get("num"))
        if n in seen_num:
            site_issue(site_json_p, 1, f"duplicate page num \"{n}\" ({seen_num[n]}, {p['file']})")
        seen_num[n] = p["file"]
    for g in glossary:
        if not isinstance(g, dict) or not g.get("term") or not g.get("def"):
            site_issue(gl_json_p, 1, f"glossary entry without term/def: {json.dumps(g, ensure_ascii=False)[:60]}")
            continue
        if single and g.get("page") and g["page"] != home:
            site_issue(gl_json_p, 1, f"glossary term \"{g['term']}\" must point to {home} in single mode (got {g['page']})")
            continue
        if g.get("page") and g["page"] not in by_name:
            site_issue(gl_json_p, 1, f"glossary term \"{g['term']}\" points to missing page {g['page']}")
    for a in ("assets/style.css", "assets/app.js"):
        if not (site / a).exists():
            site_issue(site / a, 1, f"{a} missing")

    pages: dict[str, str] = {}
    ids: dict[str, set] = {}
    for rp in rel_paths:
        raw = (site / rp).read_text(encoding="utf-8-sig")
        s = re.sub(r"<!--[\s\S]*?-->", blank_keep_lines, raw)
        pages[rp] = s
        ids[rp] = {m.group(1) for m in re.finditer(r'\sid="([^"]+)"', s)}
    selected = list(rel_paths)
    if args.pages:
        wanted = [x.strip().replace("\\", "/") for x in args.pages.split(",") if x.strip()]
        selected = []
        for w in wanted:
            rp = w if w in pages else by_name.get(posixpath.basename(w))
            if rp is None:
                site_issue(site / w, 1, f"--pages names {w} but it does not exist")
            elif rp not in selected:
                selected.append(rp)

    snippets: list[tuple[str, str]] = []
    app_js = site / "assets" / "app.js"
    if app_js.exists():
        snippets.append(("assets/app.js", app_js.read_text(encoding="utf-8-sig")))
    page_issues: dict[str, list[tuple[int, str]]] = {rp: [] for rp in selected}
    total_bytes = 0
    sctx = SiteCtx(site, reg if isinstance(reg, dict) else {}, glossary, pages, ids, pages_dir, home, single, selected, rep, site_issue)
    for rp in selected:
        s = pages[rp]
        name = posixpath.basename(rp)
        folder = posixpath.dirname(rp)
        depth = len([x for x in folder.split("/") if x]) if folder else 0
        up = "../" * depth
        issues = page_issues[rp]
        total_bytes += len(s.encode("utf-8"))
        no_script = re.sub(r"<script[\s\S]*?</script>", blank_keep_lines, s)
        for inc in ASSET_INCLUDES:
            if (up + inc) not in s:
                hint = f" (a page under {pages_dir} includes `{up + inc}`)" if depth and inc in s else ""
                issues.append((0, f"missing include {up + inc}{hint}"))
        for inc in CDN_INCLUDES:
            if inc not in s:
                issues.append((0, f"missing include {inc}"))
        if not re.search(r"<title>[^<]+</title>", s):
            issues.append((0, "no <title>"))
        if not re.search(r"<main[\s>]", s):
            issues.append((0, "no <main>"))
        m = re.search(r'<body[^>]*data-page="([^"]+)"', s)
        dp = m.group(1) if m else None
        if dp != name:
            issues.append((line_of(s, m.start()) if m else 0, f'data-page="{dp}" ≠ {name}'))
        for i, m in enumerate(re.finditer(r"<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)</script>", s)):
            st = re.search(r'\btype\s*=\s*"([^"]*)"', m.group(1))
            if st and st.group(1).strip().lower() not in JS_SCRIPT_TYPES:
                continue   # data blocks (application/json, text/plain: protocol sources, runner setup code) are not JavaScript
            snippets.append((f"{rp}\t{i + 1}\t{line_of(s, m.start())}", m.group(2)))
        for t in BALANCED_TAGS:
            o = len(re.findall(r"<" + t + r"[\s>]", no_script))
            c = len(re.findall(r"</" + t + r">", no_script))
            if o != c:
                issues.append((0, f"<{t}> {o} open / {c} close"))
        seen, dup = set(), {}
        for m in re.finditer(r'\sid="([^"]+)"', s):
            i = m.group(1)
            if i in seen:
                dup.setdefault(i, line_of(s, m.start()))
            seen.add(i)
        if dup:
            issues.append((min(dup.values()), "duplicate ids: " + ", ".join(list(dup)[:6])))
        dd = len(re.findall(r"\$\$", no_script))
        if dd % 2:
            issues.append((0, f"odd number of $$ ({dd}) — a price like $$ or $$$ will be rendered as maths"))
        op, cl = len(re.findall(r"\\\(", no_script)), len(re.findall(r"\\\)", no_script))
        if op != cl:
            issues.append((0, f"\\( {op} vs \\) {cl}"))
        hc = list(re.finditer(r'<(rect|path|circle|text|line|polygon|polyline|ellipse)[^>]*\s(fill|stroke)="#[0-9a-fA-F]{3,8}"', no_script))
        if hc:
            issues.append((line_of(no_script, hc[0].start()), f"{len(hc)} hard-coded SVG colour(s) — use d-* classes so dark mode works"))
        bad_links: dict[str, int] = {}
        for m in re.finditer(r'href="([^"#:?]*\.html)?(#[^"]*)?"', no_script):
            if not m.group(1) and not m.group(2):
                continue
            anc = m.group(2)[1:] if m.group(2) else None
            if anc == "" or (not m.group(1) and anc and anc.startswith("sym-")):
                continue   # "#sym-…": the C8 symbol sprite is injected at view time; circuit_checks names unknown symbols
            if m.group(1):
                target = posixpath.normpath(posixpath.join(folder, m.group(1).replace("\\", "/"))) if folder else posixpath.normpath(m.group(1))
                target = target.lstrip("./") if target.startswith("./") else target
            else:
                target = rp
            if target not in pages and not (site / target).exists():
                bad_links.setdefault("missing " + m.group(1), line_of(no_script, m.start()))
                continue
            if anc and target in ids and anc not in ids[target]:
                bad_links.setdefault(f"{m.group(1) or ''}#{anc}", line_of(no_script, m.start()))
        if bad_links:
            keys = list(bad_links)
            issues.append((min(bad_links.values()), "broken links: " + ", ".join(keys[:10]) + (f" (+{len(keys) - 10})" if len(keys) > 10 else "")))
        for m in re.finditer(r'<div class="quiz"[^>]*data-answer="(\d+)"[^>]*>([\s\S]*?)</ol>', no_script):
            n = len(re.findall(r"<li[\s>]", m.group(2)))
            if int(m.group(1)) >= n:
                issues.append((line_of(no_script, m.start()), f"quiz data-answer={m.group(1)} out of range ({n} options)"))
        if re.search(r'class="quiz"', no_script) and not re.search(r'class="quiz"[^>]*data-answer', no_script):
            issues.append((0, "quiz without data-answer"))
        for m in re.finditer(r'data-target="([^"]+)"', no_script):
            if m.group(1) not in ids[rp]:
                issues.append((line_of(no_script, m.start()), f"table tool targets missing id {m.group(1)}"))
        for m in re.finditer(r'<output for="([^"]+)"', no_script):
            if m.group(1) not in ids[rp]:
                issues.append((line_of(no_script, m.start()), f'<output for="{m.group(1)}"> has no input'))
        for m in re.finditer(r'<figure class="photo"[\s\S]*?</figure>', no_script):
            if not re.search(r'<img[^>]*\salt="[^"]+"', m.group(0)):
                issues.append((line_of(no_script, m.start()), "photo without alt text"))
            if not re.search(r'class="credit"[\s\S]*<a ', m.group(0)):
                issues.append((line_of(no_script, m.start()), "photo without a source link in .credit"))
        for m in re.finditer(r'<figure class="embed"([^>]*)>', no_script):
            if "data-src=" not in m.group(1):
                issues.append((line_of(no_script, m.start()), "embed without data-src"))
        # trust footer: every page except the home page and glossary.html; dated; the last section of <main>
        if (name != home or single) and name != "glossary.html":
            tm = next((m for m in re.finditer(r"<section\b[^>]*>", no_script) if re.search(r'\bclass="trust(?:\s[^"]*)?"', m.group(0))), None)
            if not tm or not re.search(r'<h2\b[^>]*\sid="trust"', no_script):
                issues.append((line_of(no_script, tm.start()) if tm else 0, "page has no trust footer (components/trust/trust-footer.html)"))
            else:
                dm = re.search(r'data-reviewed="([^"]*)"', tm.group(0))
                if not dm or not is_date(dm.group(1)):
                    issues.append((line_of(no_script, tm.start()), "trust footer data-reviewed is not a date"))
                last = None
                for sm in re.finditer(r"<section\b[^>]*>", no_script):
                    last = sm
                if last is not None and last.start() != tm.start():
                    issues.append((line_of(no_script, tm.start()), "trust footer must be the last section"))
        # exercises: id, a closed details.solution, difficulty 1..3
        ex_starts = list(re.finditer(r'<div\b[^>]*\bclass="exercise(?:\s[^"]*)?"[^>]*>', no_script))
        for k, m in enumerate(ex_starts):
            tag = m.group(0)
            idm = re.search(r'\sid="([^"]+)"', tag)
            label = idm.group(1) if idm else f"#{k + 1}"
            ln = line_of(no_script, m.start())
            if not idm:
                issues.append((ln, "exercise without id"))
            end = ex_starts[k + 1].start() if k + 1 < len(ex_starts) else len(no_script)
            body = no_script[m.end():end]
            sol = re.search(r'<details\b[^>]*\bclass="solution(?:\s[^"]*)?"[^>]*>', body)
            if not sol:
                issues.append((ln, f"exercise {label} has no solution"))
            elif re.search(r"\sopen(?=[\s>=/])", sol.group(0)):
                issues.append((line_of(no_script, m.end() + sol.start()), f"exercise {label}: solution open by default"))
            dd = re.search(r'data-difficulty="([^"]*)"', tag)
            if dd and dd.group(1) not in ("1", "2", "3"):
                issues.append((ln, f"exercise {label}: data-difficulty must be 1, 2 or 3"))
        # step-through diagrams: >= 2 data-step layers; captions match the step count
        for m in re.finditer(r"<figure\b[^>]*>", no_script):
            tag = m.group(0)
            if "data-steps" not in tag or not re.search(r'\bclass="diagram(?:\s[^"]*)?"', tag):
                continue
            endf = no_script.find("</figure>", m.end())
            body = no_script[m.end():endf if endf >= 0 else len(no_script)]
            idm = re.search(r'\sid="([^"]+)"', tag)
            fid = idm.group(1) if idm else f"at line {line_of(no_script, m.start())}"
            steps = {s for s in re.findall(r'<g\b[^>]*\bdata-step="(\d+)"', body)}
            if len(steps) < 2:
                issues.append((line_of(no_script, m.start()), f"step diagram {fid} has fewer than 2 data-step layers"))
            cm = re.search(r'<ol\b[^>]*\bclass="diagram-steps"[^>]*>([\s\S]*?)</ol>', body)
            if cm:
                n = len(re.findall(r"<li[\s>]", cm.group(1)))
                if n != len(steps):
                    issues.append((line_of(no_script, m.end() + cm.start()), f"step diagram {fid}: {n} captions for {len(steps)} steps"))
        if single and name == home:
            for i in SINGLE_IDS:
                if i not in ids[rp]:
                    issues.append((0, f"single page lacks #{i}"))
            if not re.search(r'class="refs(?:\s[^"]*)?"', no_script):
                issues.append((0, "single page has no ol.refs"))
            if not re.search(r"\sdata-glossary(?=[\s>=/])", no_script):
                issues.append((0, "single page has no data-glossary widget"))
            parts = [m for m in re.finditer(r"<section\b[^>]*>", no_script) if re.search(r'\bclass="part(?:\s[^"]*)?"', m.group(0))]
            if not parts:
                issues.append((0, "single page has no section.part"))
            for m in parts:
                ln = line_of(no_script, m.start())
                dp = re.search(r'\sdata-part="([^"]*)"', m.group(0))
                pid = dp.group(1) if dp else ""
                if not re.fullmatch(r"[MS]\d\d", pid):
                    issues.append((ln, "part section without a valid data-part"))
                nxt = re.search(r"<section\b|</section>", no_script[m.end():])
                body = no_script[m.end():m.end() + nxt.start()] if nxt else no_script[m.end():]
                if not re.search(r'<h2\b[^>]*\sid="[^"]+"', body):
                    issues.append((ln, f"part {pid or '?'} has no h2 id"))
            nbytes = (site / rp).stat().st_size
            if nbytes > budget_kb * 1024:
                rep.warn(site / rp, 0, f"single page is {round(nbytes / 1024)} KB, over the {budget_kb} KB budget")
        regp = next((p for p in pages_reg if p["file"] == name), None)
        if regp and regp.get("level"):
            for i in MODULE_IDS:
                if i not in ids[rp]:
                    issues.append((0, f"module page lacks #{i}"))
            if not re.search(r'class="quiz"', no_script):
                issues.append((0, "module page has no knowledge checkpoints"))
            if not re.search(r'class="refs"', no_script):
                issues.append((0, "module page has no ol.refs"))
        pctx = PageCtx(sctx, rp, s, no_script, issues, regp)
        for chk in PAGE_CHECKS:
            chk(pctx)
    for chk in SITE_CHECKS:
        chk(sctx)

    # ------------------------------------------------------------- js syntax
    js_syntax = "skipped"
    js_errors = node_check(snippets)
    if js_errors is None:
        rep.warn(site, 0, "inline-script and app.js syntax not checked (node not on PATH)")
    elif "__node__" in js_errors:
        rep.warn(site, 0, js_errors["__node__"])
    else:
        js_syntax = "checked"
        for key, msg in js_errors.items():
            if key == "assets/app.js":
                site_issue(app_js, 1, "assets/app.js syntax: " + msg)
            else:
                f, n, line = key.split("\t")
                if f in page_issues:
                    page_issues[f].append((int(line), f"inline script #{n}: {msg}"))

    bad_pages = 0
    for rp in selected:
        issues = page_issues[rp]
        if issues:
            bad_pages += 1
        for line, msg in sorted(issues, key=lambda x: x[0]):
            rep.error(site / rp, line, msg)
    if not args.quiet:
        rep.print_problems()
        for rp in selected:
            kb = len(pages[rp].encode("utf-8")) / 1024
            print(f"{rp:<40}{kb:7.0f} KB  {'OK' if not page_issues[rp] else str(len(page_issues[rp])) + ' issue(s)'}")
        print(f"\n{len(selected)} page(s) checked of {len(rel_paths)}, {total_bytes / 1024 / 1024:.2f} MB, {len(glossary)} glossary terms, "
              f"{len(pages_reg)} registry entries, layout {'single page' if single else 'flat' if not pages_dir else pages_dir} — {bad_pages} page(s) with issues, {site_issues} site-level issue(s)")
    print(result_line(gate="site", status=rep.status, pages=len(selected), bad_pages=bad_pages, site_issues=site_issues,
                      bytes=total_bytes, js_syntax=js_syntax, mode=mode, **sctx.extra))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
