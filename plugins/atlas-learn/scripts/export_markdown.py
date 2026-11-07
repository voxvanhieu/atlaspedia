#!/usr/bin/env python
"""Markdown / LMS export of an atlas-learn site (contracts §9, feature G3).

Usage: python export_markdown.py <siteDir> --out <dir> [--pages a.html,b.html] [--no-solutions] [--lms] [--quiet]

Reads assets/site.json (the registry), assets/glossary.json, index.html and every page under <pagesDir> (the `_*.html`
skeletons are skipped; single mode: the one page), converts each page's <main> with the standard library html.parser and
writes, under --out:
  <page>.md          one Markdown file per page (the overview page becomes home.md, since index.md is the outline):
                     YAML front matter (title, file, num, group, level, desc, reviewed, verified n/m); the hero as a
                     title, standfirst and meta list; headings with their ids as `{#id}` suffixes; paragraphs, lists
                     (objectives, steps, timelines, checklists), definition lists; <details> as a bold summary followed
                     by its body; callouts as blockquotes with the title in bold; tables as pipe tables (cell text, no
                     colspans); code as fenced blocks with the language (executed examples keep their date, environment
                     and output); maths kept ($$ display, \\( \\) inline becomes $…$); photos as ![alt](src) with caption
                     and credit; diagrams as SVG files in figures/ (with the template's d-* styles and arrow markers
                     embedded, so they render on their own) linked from the page; embeds as links; demos as a note
                     ("Interactive demo: … — see the site" + the model note); quizzes as question + options with the
                     answer in <details>; exercises as statement, hints and the solution in <details>; the trust footer
                     as a final "## Trust" with its stats; links to other pages rewritten to .md.
  figures/           one <page>-<figure id>.svg per diagram
  index.md           the outline: the reading order with links, grouped as the sidebar
  imsmanifest.xml    with --lms: a thin IMS Common Cartridge-style manifest (schema 1.1.0) listing every HTML page as a
                     web-content resource, with the assets as a shared dependency — not SCORM, no quiz/grade mapping.
                     Its hrefs are relative to the site root: copy the file into the site folder (next to index.html)
                     and zip that folder, or point the LMS at the folder, to import the site as web content.
--no-solutions omits exercise solutions and quiz answers (a handout export); hints stay.
--pages limits the page files to the named basenames (index.md still lists every page).
Prose is not escaped for Markdown: a literal asterisk or underscore in prose may be read as emphasis by a renderer.
Problems print as `<file>:<line> <message>`. Ends with
  RESULT: tool=export_markdown status=PASS|FAIL errors=n warnings=n pages=n figures=n out=<path> lms=yes|no
"""
from __future__ import annotations

import argparse
import datetime
import json
import posixpath
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, load_json, usage_error  # noqa: E402

TEMPLATE_CSS = Path(__file__).resolve().parent.parent / "skills" / "compose" / "template" / "assets" / "style.css"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
INLINE = {"a", "abbr", "b", "bdi", "bdo", "br", "cite", "code", "data", "del", "dfn", "em", "i", "img", "ins", "kbd", "mark",
          "q", "s", "samp", "small", "span", "strong", "sub", "sup", "time", "u", "var", "wbr", "label", "output"}
SKIP = {"script", "style", "template", "button", "input", "select", "canvas", "nav", "noscript", "iframe", "video", "audio", "textarea"}
BR, NL = "\x00BR\x00", "\x00NL\x00"
MARKERS = (("arr", "d-fill-ink"), ("arr-data", "d-fill-data"), ("arr-ctrl", "d-fill-ctrl"), ("arr-power", "d-fill-power"),
           ("arr-muted", "d-fill-muted"), ("arr-accent", "d-fill-accent"))


# ------------------------------------------------------------------ tree ---
class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "start", "end")

    def __init__(self, tag: str, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or ()), [], parent
        self.start = self.end = None

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def has(self, *cls: str) -> bool:
        return all(c in self.classes for c in cls)

    @property
    def elements(self) -> list["Node"]:
        return [c for c in self.children if isinstance(c, Node)]

    def find(self, pred, depth: int = 50):
        for c in self.children:
            if isinstance(c, Node):
                if pred(c):
                    return c
                if depth > 0:
                    r = c.find(pred, depth - 1)
                    if r is not None:
                        return r
        return None

    def findall(self, pred, out=None, depth: int = 50) -> list["Node"]:
        out = [] if out is None else out
        for c in self.children:
            if isinstance(c, Node):
                if pred(c):
                    out.append(c)
                if depth > 0:
                    c.findall(pred, out, depth - 1)
        return out

    def text(self) -> str:
        """Plain text, whitespace collapsed."""
        parts = []
        for c in self.children:
            parts.append(c if isinstance(c, str) else c.text())
        return " ".join("".join(parts).split())

    def raw_text(self) -> str:
        return "".join(c if isinstance(c, str) else c.raw_text() for c in self.children)


class Tree(HTMLParser):
    """Builds Node objects; records comments and the raw-text span of every element (for SVG extraction)."""

    def __init__(self, raw: str):
        super().__init__(convert_charrefs=True)
        self.raw, self.root = raw, Node("#root")
        self.cur = self.root
        self.comments: list[str] = []
        self._lines = [0] + [i + 1 for i, ch in enumerate(raw) if ch == "\n"]
        self.feed(raw)
        self.close()

    def _pos(self) -> int:
        line, off = self.getpos()
        return self._lines[line - 1] + off if line - 1 < len(self._lines) else len(self.raw)

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        n.start = self._pos()
        self.cur.children.append(n)
        if tag in VOID:
            n.end = n.start + len(self.get_starttag_text() or "")
        else:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        n.start = self._pos()
        n.end = n.start + len(self.get_starttag_text() or "")
        self.cur.children.append(n)

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is None or n.tag == "#root":
            return  # stray end tag
        n.end = self._pos() + len(tag) + 3
        self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)

    def handle_comment(self, data):
        self.comments.append(data)


# --------------------------------------------------------------- helpers ---
def collapse(s: str) -> str:
    s = " ".join(s.split())
    return s.replace(BR, "  \n").replace(NL, "\n")


def math_inline(s: str) -> str:
    """Inline delimiters \\( \\) -> $ $ and \\[ \\] -> $$ $$; $$ stays."""
    s = re.sub(r"\\\(\s*(.*?)\s*\\\)", lambda m: "$" + m.group(1) + "$", s, flags=re.S)
    s = re.sub(r"\\\[\s*(.*?)\s*\\\]", lambda m: "$$" + m.group(1) + "$$", s, flags=re.S)
    return s


def fence_for(code: str) -> str:
    n = 3
    for m in re.finditer(r"`{3,}", code):
        n = max(n, len(m.group(0)) + 1)
    return "`" * n


def indent(block: str, pad: str) -> str:
    return "\n".join((pad + ln) if ln.strip() else ln for ln in block.split("\n"))


def yaml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    return s if re.fullmatch(r"[A-Za-z][A-Za-z0-9 _-]*", s) and s.lower() not in ("yes", "no", "null", "true", "false", "on", "off") else json.dumps(s, ensure_ascii=False)


def svg_style(css_text: str) -> str:
    """The template's light variables plus every `svg .d-*` rule, so a diagram renders outside the page."""
    root = re.search(r":root\s*\{([^}]*)\}", css_text)
    rules = re.findall(r"(svg(?:\s+a(?::hover)?)?\s+\.d-[^{]*)\{([^}]*)\}", css_text)
    out = ["svg { background: var(--surface); }"]
    if root:
        out.insert(0, ":root {" + " ".join(root.group(1).split()) + "}")
    out += [sel.strip() + " {" + " ".join(body.split()) + "}" for sel, body in rules]
    return "\n".join(out)


def svg_markers() -> str:
    mk = lambda i, c: f'<marker id="{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="{c}"/></marker>'
    return "<defs>" + "".join(mk(i, c) for i, c in MARKERS) + "</defs>"


def embed_url(kind: str, src: str) -> str:
    """Open-in-browser URL for figure.embed (same rules as app.js embedTarget)."""
    src = (src or "").strip()
    if kind == "youtube":
        m = re.search(r"(?:youtu\.be/|[?&]v=|/embed/|/shorts/|/live/)([A-Za-z0-9_-]{6,})", src)
        return "https://www.youtube.com/watch?v=" + (m.group(1) if m else src)
    if kind == "vimeo":
        m = re.search(r"vimeo\.com/(?:video/)?(\d+)", src)
        return "https://vimeo.com/" + (m.group(1) if m else src)
    if kind == "sketchfab":
        m = re.search(r"(?:^|[/-])([a-f0-9]{32})(?:[/?#]|$)", src)
        return "https://sketchfab.com/models/" + (m.group(1) if m else src)
    return src


# -------------------------------------------------------------- exporter ---
class Exporter:
    def __init__(self, site: Path, out: Path, reg: dict, glossary: list, md_names: dict, home: str, no_solutions: bool, rep: Report):
        self.site, self.out, self.reg, self.glossary, self.md_names, self.home = site, out, reg, glossary, md_names, home
        self.no_solutions, self.rep = no_solutions, rep
        self.figures = 0
        css_p = site / "assets" / "style.css"
        css = css_p.read_text(encoding="utf-8-sig") if css_p.exists() else (TEMPLATE_CSS.read_text(encoding="utf-8-sig") if TEMPLATE_CSS.exists() else "")
        self.style = svg_style(css)
        # per page
        self.rp = self.stem = self.raw = ""
        self.fig_n = 0
        self.stats = {"refs": 0, "verified": 0, "demos": 0, "gaps": 0}

    # ---- links --------------------------------------------------------------
    def href(self, href: str) -> str:
        href = (href or "").strip()
        if not href or href.startswith("#") or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href):
            return href
        path, _, anc = href.partition("#")
        if path.lower().endswith(".html"):
            base = posixpath.basename(path.replace("\\", "/"))
            name = self.md_names.get(base) or (base[:-5] + ".md")
            return name + ("#" + anc if anc else "")
        return href

    # ---- inline -------------------------------------------------------------
    def inline(self, n: Node) -> str:
        return collapse(math_inline(self._inline(n)))

    def _inline(self, n: Node) -> str:
        parts = []
        for c in n.children:
            if isinstance(c, str):
                parts.append(c)
                continue
            t, cls = c.tag, c.classes
            if t in SKIP:
                continue
            if t == "br":
                parts.append(BR)
            elif t == "img":
                parts.append(f"![{c.attrs.get('alt', '')}]({c.attrs.get('src', '')})")
            elif t == "a":
                inner = self._inline(c).strip() or c.attrs.get("href", "")
                parts.append(f"[{inner}]({self.href(c.attrs.get('href', ''))})" if c.attrs.get("href") else inner)
            elif t in ("code", "kbd", "samp"):
                raw = c.raw_text().strip()
                parts.append(("`` " + raw + " ``") if "`" in raw else ("`" + raw + "`"))
            elif t in ("b", "strong", "dfn"):
                inner = self._inline(c).strip()
                parts.append(f"**{inner}**" if inner else "")
            elif t in ("i", "em", "var", "cite"):
                inner = self._inline(c).strip()
                parts.append(f"*{inner}*" if inner else "")
            elif t in ("sup", "sub"):
                parts.append(f"<{t}>{self._inline(c).strip()}</{t}>")
            elif t == "span" and "badge" in cls:
                parts.append(f" [{self._inline(c).strip()}]")
            elif t == "span" and "why" in cls:
                parts.append(f" — {self._inline(c).strip()}")
            elif t == "span" and "f-num" in cls:
                parts.append(f"**{self._inline(c).strip()}** ")
            elif t in INLINE or t in ("p", "div", "li", "h5"):
                parts.append(self._inline(c))
            else:  # a block inside inline context: flatten its text
                parts.append(" " + NL.join(self.blocks(c)) + " ")
        return "".join(parts)

    # ---- blocks -------------------------------------------------------------
    def blocks(self, n: Node) -> list[str]:
        """Render the children of a container as Markdown blocks."""
        out: list[str] = []
        run: list = []  # pending inline run (text + inline elements)

        def flush():
            if run:
                tmp = Node("#run")
                tmp.children = list(run)
                txt = self.inline(tmp)
                if txt.strip():
                    out.append(txt.strip())
                run.clear()

        for c in n.children:
            if isinstance(c, str) or c.tag in INLINE:
                if isinstance(c, Node) and c.tag in SKIP:
                    continue
                run.append(c)
            else:
                flush()
                out.extend(self.element(c))
        flush()
        return out

    def inline_only(self, n: Node) -> bool:
        return all(isinstance(c, str) or c.tag in INLINE or c.tag in SKIP for c in n.children)

    def element(self, n: Node) -> list[str]:
        t, cls = n.tag, n.classes
        if t in SKIP or t == "svg" and "data-sitemap" in n.attrs:
            return []
        if "data-glossary" in n.attrs or n.attrs.get("id") == "tbl-glossary":
            return self.glossary_list()
        if "data-curriculum" in n.attrs:
            return self.curriculum()
        if "data-stats" in n.attrs or "data-filters" in n.attrs:
            return []
        if t == "header" and "module-hero" in cls:
            return self.hero(n)
        if t == "section" and "trust" in cls:
            return self.trust(n)
        if t == "figure":
            return self.figure(n)
        if t == "svg":
            return self.svg_figure(n, None, "")
        if "demo" in cls and t == "div":
            return self.demo(n)
        if "quiz" in cls and t == "div":
            return self.quiz(n)
        if "exercise" in cls and t == "div":
            return self.exercise(n)
        if "callout" in cls:
            return self.callout(n)
        if "keywords" in cls:
            words = [c.text() for c in n.elements if c.text()]
            return ["*Keywords:* " + " · ".join(words)] if words else []
        if "card" in cls and "stat" in cls:
            v = n.find(lambda c: c.has("stat-value")); lab = n.find(lambda c: c.has("stat-label"))
            return [f"**{v.text() if v else ''}** — {lab.text() if lab else ''}".strip(" —")]
        if t == "details":
            return self.details(n)
        if "tabs" in cls and t == "div":
            return self.tabs(n)
        if "table-wrap" in cls:
            return self.table_wrap(n)
        if "table-tools" in cls:
            return []
        if t == "table":
            return self.table(n)
        if t == "pre":
            return self.pre(n)
        if t in ("ul", "ol"):
            return [self.list(n)]
        if t == "dl":
            return self.dl(n)
        if re.fullmatch(r"h[1-6]", t):
            return [self.heading(n)]
        if t == "blockquote":
            return ["\n".join("> " + ln for b in self.blocks(n) for ln in b.split("\n"))]
        if t == "hr":
            return ["---"]
        if t == "img":
            return [f"![{n.attrs.get('alt', '')}]({n.attrs.get('src', '')})"]
        if t == "p" or self.inline_only(n):
            txt = self.inline(n)
            return [txt] if txt.strip() else []
        return self.blocks(n)

    def heading(self, n: Node) -> str:
        lvl = int(n.tag[1])
        txt = self.inline(n).replace("#", "").strip() if lvl <= 2 else self.inline(n).strip()
        anchor = f" {{#{n.attrs['id']}}}" if n.attrs.get("id") else ""
        return "#" * lvl + " " + txt + anchor

    def list(self, n: Node, pad: str = "") -> str:
        ordered = n.tag == "ol"
        check = "checklist" in n.classes
        timeline = "timeline" in n.classes
        lines: list[str] = []
        k = 0
        for li in n.elements:
            if li.tag != "li":
                continue
            k += 1
            marker = f"{k}. " if ordered else ("- [ ] " if check else "- ")
            sub = " " * len(marker)
            head: list = []
            tail: list[Node] = []
            for c in li.children:
                if tail or (isinstance(c, Node) and c.tag not in INLINE and c.tag not in SKIP):
                    if isinstance(c, Node):
                        tail.append(c)
                    elif c.strip():
                        tail.append(c)
                else:
                    head.append(c)
            tmp = Node("#li"); tmp.children = head
            first = self.inline(tmp).strip()
            if timeline:
                when = li.find(lambda c: c.has("tl-when"), 1)
                if when:
                    first = re.sub(r"^\s*" + re.escape(when.text()) + r"\s*", "", first)
                    first = f"**{when.text()}** — {first}"
            if li.attrs.get("id"):
                first = f'<a id="{li.attrs["id"]}"></a>' + first
            item = pad + marker + first
            for c in tail:
                if isinstance(c, str):
                    item += "\n" + pad + sub + collapse(math_inline(c)).strip()
                elif c.tag in ("ul", "ol"):
                    item += "\n" + self.list(c, pad + sub)
                else:
                    for b in self.element(c):
                        item += "\n\n" + indent(b, pad + sub)
            lines.append(item)
        return "\n".join(lines)

    def dl(self, n: Node) -> list[str]:
        items = []
        dts = n.findall(lambda c: c.tag == "dt", depth=2)
        for dt in dts:
            sib = dt.parent.elements
            i = sib.index(dt)
            dd = sib[i + 1] if i + 1 < len(sib) and sib[i + 1].tag == "dd" else None
            val = ""
            if dd is not None:
                diff = dd.find(lambda c: c.has("diff"), 2)
                val = f"{diff.attrs.get('data-level', '?')} / 5" if diff else self.inline(dd).strip()
            items.append(f"- **{self.inline(dt).strip()}**: {val}".rstrip(": "))
        return ["\n".join(items)] if items else []

    def hero(self, n: Node) -> list[str]:
        out = []
        h1 = n.find(lambda c: c.tag == "h1", 2)
        eyebrow = n.find(lambda c: c.has("eyebrow"), 2)
        lede = n.find(lambda c: c.has("lede"), 2)
        if h1:
            out.append("# " + self.inline(h1).strip())
        if eyebrow and eyebrow.text():
            out.append("*" + self.inline(eyebrow).strip() + "*")
        if lede and lede.text():
            out.append(self.inline(lede).strip())
        for dl in n.findall(lambda c: c.tag == "dl", depth=2):
            out.extend(self.dl(dl))
        for c in n.elements:
            if c not in (h1, eyebrow, lede) and c.tag not in ("dl", "h1"):
                out.extend(self.element(c))
        return out

    def callout(self, n: Node) -> list[str]:
        title = n.find(lambda c: c.has("callout-title"), 1)
        body = Node("#body"); body.children = [c for c in n.children if c is not title]
        lines = []
        if title:
            lines.append("> **" + self.inline(title).strip() + "**")
            lines.append(">")
        for b in self.blocks(body):
            lines.extend("> " + ln if ln.strip() else ">" for ln in b.split("\n"))
            lines.append(">")
        while lines and lines[-1] == ">":
            lines.pop()
        return ["\n".join(lines)] if lines else []

    def details(self, n: Node, closed_html: bool = False) -> list[str]:
        summary = n.find(lambda c: c.tag == "summary", 1)
        body = Node("#body"); body.children = [c for c in n.children if c is not summary]
        title = self.inline(summary).strip() if summary else "Details"
        inner = self.blocks(body)
        if closed_html:
            return ["<details><summary>" + title + "</summary>\n\n" + "\n\n".join(inner) + "\n\n</details>"]
        return ["**" + title + "**"] + inner

    def tabs(self, n: Node) -> list[str]:
        labels = {b.attrs.get("data-tab"): b.text() for b in n.findall(lambda c: c.tag == "button", depth=2)}
        out = []
        for p in n.elements:
            if "tab-panel" in p.classes:
                out.append("**" + (labels.get(p.attrs.get("data-tab")) or p.attrs.get("data-tab") or "Tab") + "**")
                out.extend(self.blocks(p))
        return out

    def table_wrap(self, n: Node) -> list[str]:
        out = []
        title = n.find(lambda c: c.has("tt-title"), 2)
        if title and title.text():
            out.append("**" + self.inline(title).strip() + "**")
        for c in n.elements:
            if "table-tools" in c.classes:
                continue
            if "table-note" in c.classes:
                out.append("*" + self.inline(c).strip() + "*")
            else:
                out.extend(self.element(c))
        return out

    def table(self, n: Node) -> list[str]:
        rows = n.findall(lambda c: c.tag == "tr", depth=3)
        if not rows:
            return []
        thead = n.find(lambda c: c.tag == "thead", 1)
        head_rows = [r for r in rows if thead is not None and r.parent is thead]
        head = head_rows[0] if head_rows else rows[0]
        body_rows = [r for r in rows if r is not head and r not in head_rows]
        cell = lambda c: self.inline(c).replace("\n", " ").replace("|", "\\|").strip()
        hcells = [c for c in head.elements if c.tag in ("th", "td")]
        header = [cell(c) for c in hcells]
        width = max([len(header)] + [len([c for c in r.elements if c.tag in ("th", "td")]) for r in body_rows])
        header += [""] * (width - len(header))
        align = ["---:" if "num" in c.classes else "---" for c in hcells] + ["---"] * (width - len(hcells))
        lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(align) + " |"]
        for r in body_rows:
            cells = [cell(c) for c in r.elements if c.tag in ("th", "td")]
            cells += [""] * (width - len(cells))
            lines.append("| " + " | ".join(cells) + " |")
        cap = n.find(lambda c: c.tag == "caption", 1)
        return (["**" + self.inline(cap).strip() + "**"] if cap else []) + ["\n".join(lines)]

    def pre(self, n: Node) -> list[str]:
        code = n.find(lambda c: c.tag == "code", 1)
        samp = n.find(lambda c: c.tag == "samp", 1)
        src = (code or samp or n).raw_text().strip("\n")
        lang = ""
        if code:
            m = re.search(r"lang(?:uage)?-(\w+)", code.attrs.get("class") or "")
            lang = m.group(1) if m else ""
        f = fence_for(src)
        out = []
        if "output" in n.classes:
            out.append("Output:")
            lang = lang or "text"
        elif "data-executed" in n.attrs:
            env = n.attrs.get("data-env", "")
            out.append("*Executed " + n.attrs.get("data-executed", "") + (" · " + env if env else "") + "*")
        out.append(f + lang + "\n" + src + "\n" + f)
        return out

    def figure(self, n: Node) -> list[str]:
        cls = n.classes
        cap = n.find(lambda c: c.tag == "figcaption", 1)
        caption = self.inline(cap).strip() if cap else ""
        svg = n.find(lambda c: c.tag == "svg", 2)
        img = n.find(lambda c: c.tag == "img", 2)
        out: list[str] = []
        if "embed" in cls:
            kind = n.attrs.get("data-kind", "iframe")
            url = embed_url(kind, n.attrs.get("data-src", ""))
            title = n.attrs.get("data-title") or kind
            out.append(f"[▶ {title}]({url}) *(embedded {kind}; opens the source)*")
        elif svg is not None:
            out.extend(self.svg_figure(svg, n, caption))
        elif img is not None:
            out.append(f"![{img.attrs.get('alt', '')}]({img.attrs.get('src', '')})")
        else:
            out.append("*(interactive figure — see the site)*")
        if caption:
            out.append(caption)
        steps = n.find(lambda c: c.tag == "ol" and c.has("diagram-steps"), 1)
        if steps is not None:
            out.append(self.list(steps))
        legend = n.find(lambda c: c.has("legend"), 1)
        if legend is not None and legend.text():
            out.append("*Legend: " + " · ".join(c.text() for c in legend.elements if c.text()) + "*")
        return out

    def svg_figure(self, svg: Node, fig: Node | None, caption: str) -> list[str]:
        self.fig_n += 1
        fid = (fig.attrs.get("id") if fig is not None else None) or svg.attrs.get("id") or f"figure-{self.fig_n}"
        fid = re.sub(r"[^A-Za-z0-9_-]+", "-", fid)
        if svg.start is None or svg.end is None:
            self.rep.warn(self.site / self.rp, 0, f"figure {fid}: SVG could not be extracted")
            return []
        raw = self.raw[svg.start:svg.end]
        open_end = raw.find(">")
        open_tag = raw[:open_end + 1]
        if "xmlns=" not in open_tag:
            open_tag = open_tag[:4] + ' xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"' + open_tag[4:]
        body = raw[open_end + 1:]  # the drawing as written (d-* classes stay; the embedded style resolves them)
        doc = ('<?xml version="1.0" encoding="UTF-8"?>\n' + open_tag + "\n<style>" + self.style + "</style>\n" + svg_markers() + body)
        figdir = self.out / "figures"
        figdir.mkdir(parents=True, exist_ok=True)
        name = f"{self.stem}-{fid}.svg"
        (figdir / name).write_text(doc, encoding="utf-8")
        self.figures += 1
        alt = re.sub(r"[*_`\[\]]", "", caption)[:160] or fid
        return [f"![{alt}](figures/{name})"]

    def demo(self, n: Node) -> list[str]:
        h = n.find(lambda c: c.tag in ("h4", "h3", "h5"), 3)
        title = self.inline(h).strip() if h else n.attrs.get("id", "demo")
        note = n.find(lambda c: c.has("demo-note"), 2)
        lines = [f"> **Interactive demo: {title}** — see the site; the calculator runs only in the browser."]
        if note is not None:
            lines.append(">")
            lines.append("> " + self.inline(note).strip().replace("\n", "\n> "))
        return ["\n".join(lines)]

    def quiz(self, n: Node) -> list[str]:
        q = n.find(lambda c: c.has("q"), 1)
        opts = n.find(lambda c: c.tag == "ol" and c.has("opts"), 1)
        explain = n.find(lambda c: c.has("explain"), 1)
        out = ["**Checkpoint.** " + (self.inline(q).strip() if q else "")]
        items = [li for li in opts.elements if li.tag == "li"] if opts else []
        if items:
            out.append("\n".join(f"{i + 1}. {self.inline(li).strip()}" for i, li in enumerate(items)))
        if self.no_solutions:
            return out
        try:
            ans = int(n.attrs.get("data-answer", ""))
        except ValueError:
            ans = -1
        answer = f"**{ans + 1}.** {self.inline(items[ans]).strip()}" if 0 <= ans < len(items) else "*(no answer marked)*"
        expl = self.inline(explain).strip() if explain else ""
        out.append("<details><summary>Answer</summary>\n\n" + answer + ((" — " + expl) if expl else "") + "\n\n</details>")
        return out

    def exercise(self, n: Node) -> list[str]:
        head = n.find(lambda c: c.has("exercise-head"), 1)
        label = head.find(lambda c: c.has("exercise-label"), 1) if head else None
        title = label.text() if label else (n.attrs.get("id") or "Exercise")
        anchor = f" {{#{n.attrs['id']}}}" if n.attrs.get("id") else ""
        out = ["#### " + title + anchor]
        meta = []
        if n.attrs.get("data-difficulty"):
            meta.append(f"difficulty {n.attrs['data-difficulty']} of 3")
        if head:
            meta += [b.text() for b in head.findall(lambda c: c.has("badge"), depth=1) if b.text()]
        if meta:
            out.append("*" + " · ".join(meta) + "*")
        for c in n.children:
            if c is head:
                continue
            if isinstance(c, Node) and c.tag == "details":
                if "solution" in c.classes:
                    if not self.no_solutions:
                        out.extend(self.details(c, closed_html=True))
                elif "hint" in c.classes:
                    out.extend(self.details(c, closed_html=True))
                else:
                    out.extend(self.details(c))
            elif isinstance(c, Node):
                out.extend(self.element(c))
            elif c.strip():
                out.append(collapse(math_inline(c)).strip())
        return out

    def trust(self, n: Node) -> list[str]:
        st = self.stats
        out = ["## Trust {#trust}",
               "\n".join([f"- Sources verified: {st['verified']} / {st['refs']}", f"- Reviewed: {n.attrs.get('data-reviewed') or 'n/a'}",
                          f"- Interactive demos: {st['demos']} (documented models, reader inputs)", f"- Open gaps: {st['gaps']}"])]
        for d in n.findall(lambda c: c.tag == "details", depth=1):
            out.extend(self.details(d))
        return out

    def glossary_list(self) -> list[str]:
        items = []
        titles = {p["file"]: (f"{p.get('num', '')} · {p.get('title', '')}".strip(" ·")) for p in self.reg.get("pages", []) if isinstance(p, dict) and p.get("file")}
        for g in sorted((g for g in self.glossary if isinstance(g, dict) and g.get("term")), key=lambda g: g["term"].lower()):
            where = ""
            if g.get("page"):
                where = f" ([→ {titles.get(g['page']) or g['page']}]({self.md_names.get(g['page'], g['page'][:-5] + '.md')}{'#' + g['anchor'] if g.get('anchor') else ''}))"
            aka = f" ({g['aka']})" if g.get("aka") else ""
            items.append(f'- <a id="gl-{re.sub(r"[^a-z0-9]+", "-", g["term"].lower()).strip("-")}"></a>**{g["term"]}**{aka} — {g.get("def", "")}{where}')
        return ["\n".join(items)] if items else ["*(no glossary terms yet)*"]

    def curriculum(self) -> list[str]:
        items = []
        for p in self.reg.get("pages", []):
            if not isinstance(p, dict) or p.get("file") == self.home:
                continue
            lvl = f" (Level {p['level']})" if p.get("level") else ""
            items.append(f"- [{p.get('num', '')} · {p.get('title', p['file'])}]({self.md_names.get(p['file'], p['file'][:-5] + '.md')}) — {p.get('desc', '')}{lvl}".rstrip(" —"))
        return ["\n".join(items)] if items else []

    # ---- page ---------------------------------------------------------------
    def page(self, rp: str, raw: str, regp: dict | None) -> tuple[str, int]:
        self.rp, self.raw, self.fig_n = rp, raw, 0
        name = posixpath.basename(rp)
        self.stem = self.md_names[name][:-3]
        tree = Tree(raw)
        main = tree.root.find(lambda c: c.tag == "main") or tree.root
        title_n = tree.root.find(lambda c: c.tag == "title", 3)
        h1 = main.find(lambda c: c.tag == "h1", 3)
        title = (regp or {}).get("title") or (h1.text() if h1 else "") or (title_n.text() if title_n else name)
        refs = main.findall(lambda c: c.tag == "li" and c.parent is not None and c.parent.tag == "ol" and c.parent.has("refs"))
        trust = main.find(lambda c: c.tag == "section" and c.has("trust"), 2)
        gaps = sum(1 for cm in tree.comments if re.match(r"\s*GAP:", cm))
        if trust is not None:
            gl = trust.find(lambda c: c.has("trust-gaps"), 1)
            if gl is not None:
                gaps = max(gaps, len(gl.findall(lambda c: c.tag == "li", depth=3)))
        self.stats = {"refs": len(refs), "verified": sum(1 for li in refs if li.find(lambda c: c.has("badge", "verified"), 4) is not None),
                      "demos": len(main.findall(lambda c: c.tag == "div" and c.has("demo"))), "gaps": gaps}
        fm = {"title": title, "file": name, "num": (regp or {}).get("num", ""), "group": (regp or {}).get("group", "")}
        if (regp or {}).get("level"):
            fm["level"] = regp["level"]
        fm["desc"] = (regp or {}).get("desc", "")
        fm["reviewed"] = (trust.attrs.get("data-reviewed") if trust is not None else "") or ""
        fm["verified"] = f"{self.stats['verified']}/{self.stats['refs']}"
        front = "---\n" + "\n".join(f"{k}: {yaml_value(v)}" for k, v in fm.items() if v != "" or k == "title") + "\n---"
        body = self.blocks(main)
        text = front + "\n\n" + "\n\n".join(b for b in body if b.strip()) + "\n"
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text, self.fig_n


# ------------------------------------------------------------- manifest ---
def manifest_xml(reg: dict, pages: list[dict], pages_dir: str, home: str) -> str:
    title = xml_escape(str(reg.get("title") or "atlas-learn site"))
    ident = re.sub(r"[^A-Za-z0-9_-]+", "-", str(reg.get("storagePrefix") or "atlas-learn")).strip("-") or "atlas-learn"
    assets = [a for a in ("assets/style.css", "assets/app.js", "assets/site.js", "assets/glossary.js", "assets/data.js")]
    groups: list[tuple[str, list[dict]]] = []
    for p in pages:
        g = p.get("group") or "Pages"
        if not groups or groups[-1][0] != g:
            groups.append((g, []))
        groups[-1][1].append(p)
    res_id = {p["file"]: f"res_{i + 1}" for i, p in enumerate(pages)}
    href = lambda f: f if (f == home or not pages_dir) else pages_dir + f
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             "<!-- Thin IMS Common Cartridge-style manifest written by atlas-learn export_markdown.py (--lms): every HTML page as",
             "     web content, the fixed assets as a shared dependency. Not SCORM: no runtime API, grades or quiz mapping.",
             "     Paths are relative to the site root: copy this file next to index.html and zip the site folder. -->",
             f'<manifest identifier="atlas-learn-{ident}" xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1"',
             '          xmlns:lomimscc="http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest"',
             '          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">',
             "  <metadata>", "    <schema>IMS Common Cartridge</schema>", "    <schemaversion>1.1.0</schemaversion>",
             f"    <lomimscc:lom><lomimscc:general><lomimscc:title><lomimscc:string>{title}</lomimscc:string></lomimscc:title></lomimscc:general></lomimscc:lom>",
             "  </metadata>", "  <organizations>", '    <organization identifier="org_1" structure="rooted-hierarchy">', '      <item identifier="root">']
    for gi, (g, ps) in enumerate(groups):
        lines.append(f'        <item identifier="group_{gi + 1}"><title>{xml_escape(g)}</title>')
        for p in ps:
            lines.append(f'          <item identifier="item_{res_id[p["file"]][4:]}" identifierref="{res_id[p["file"]]}"><title>{xml_escape((p.get("num", "") + " · " if p.get("num") else "") + str(p.get("title") or p["file"]))}</title></item>')
        lines.append("        </item>")
    lines += ["      </item>", "    </organization>", "  </organizations>", "  <resources>",
              '    <resource identifier="res_assets" type="webcontent" href="assets/style.css">' + "".join(f'<file href="{a}"/>' for a in assets) + "</resource>"]
    for p in pages:
        h = xml_escape(href(p["file"]))
        lines.append(f'    <resource identifier="{res_id[p["file"]]}" type="webcontent" href="{h}"><file href="{h}"/><dependency identifierref="res_assets"/></resource>')
    lines += ["  </resources>", "</manifest>", ""]
    return "\n".join(lines)


def outline_md(reg: dict, pages: list[dict], md_names: dict, exported: set, home: str, out_dir: Path, figures: int, no_solutions: bool, lms: bool) -> str:
    lines = ["# " + str(reg.get("title") or "atlas-learn site"), ""]
    sub = reg.get("subtitle") or ""
    lines.append(((sub + " · ") if sub else "") + f"exported {datetime.date.today().isoformat()} by atlas-learn export_markdown.py")
    lines += ["", "## Reading order", ""]
    group = None
    for i, p in enumerate(pages):
        if p.get("group") != group:
            group = p.get("group")
            lines += ([""] if lines[-1] else []) + [f"### {group or 'Pages'}", ""]
        name = md_names[p["file"]]
        link = f"[{p.get('num', '')} · {p.get('title') or p['file']}]({name})" if name in exported else f"{p.get('num', '')} · {p.get('title') or p['file']} (`{p['file']}`, not exported)"
        lvl = f" — Level {p['level']}" if p.get("level") else ""
        lines.append(f"{i + 1}. {link}{(' — ' + p['desc']) if p.get('desc') else ''}{lvl}")
        if p["file"] == home and name in exported:
            lines[-1] += " *(the overview page; this file is the outline)*"
    lines += ["", f"{len(exported)} of {len(pages)} pages exported · {figures} figure{'s' if figures != 1 else ''} in `figures/` · solutions {'omitted' if no_solutions else 'included'}"
              + (" · `imsmanifest.xml` for an LMS import" if lms else ""), ""]
    return "\n".join(lines)


# ----------------------------------------------------------------- main ---
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siteDir")
    ap.add_argument("--out", required=False)
    ap.add_argument("--pages")
    ap.add_argument("--no-solutions", action="store_true", dest="no_solutions")
    ap.add_argument("--lms", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    if not args.out:
        return usage_error("give --out <dir>")
    site = Path(args.siteDir).resolve()
    if not site.is_dir():
        return usage_error(f"no such directory: {site}")
    out = Path(args.out).resolve()
    if out == site or out == site / "assets" or (site / "assets") in out.parents:
        return usage_error("--out must not be the site folder or its assets/ folder")
    rep = Report("tool", "export_markdown")
    reg, err = load_json(site / "assets" / "site.json")
    if err or not isinstance(reg, dict):
        rep.error(site / "assets" / "site.json", 1, err or "site.json must be a JSON object")
        return rep.finish({"pages": 0, "figures": 0, "out": str(out), "lms": "no"})
    glossary, gerr = load_json(site / "assets" / "glossary.json")
    if gerr or not isinstance(glossary, list):
        if gerr:
            rep.warn(site / "assets" / "glossary.json", 1, gerr)
        glossary = []
    pages_dir = reg.get("pagesDir", "") if isinstance(reg.get("pagesDir", ""), str) else ""
    home = reg.get("home") or "index.html"
    reg_pages = [p for p in reg.get("pages", []) if isinstance(p, dict) and p.get("file")]
    # files on disk (registry order first, then unregistered pages)
    on_disk: dict[str, Path] = {}
    for f in sorted(site.glob("*.html")):
        if f.is_file() and not f.name.startswith("_") and (not pages_dir or f.name == home):
            on_disk[f.name] = f
    if pages_dir and (site / pages_dir).is_dir():
        for f in sorted((site / pages_dir).glob("*.html")):
            if not f.name.startswith("_"):
                on_disk.setdefault(f.name, f)
    order = [p["file"] for p in reg_pages if p["file"] in on_disk] + [n for n in on_disk if n not in {p["file"] for p in reg_pages}]
    for p in reg_pages:
        if p["file"] not in on_disk:
            rep.warn(site / "assets" / "site.json", 1, f"registry lists {p['file']} but the file does not exist — skipped")
    # markdown names: <stem>.md, the home page -> home.md (index.md is the outline)
    md_names: dict[str, str] = {}
    for name in order:
        md = "home.md" if name == home else name[:-5] + ".md"
        if md == "home.md" and "home.html" in on_disk and name == home:
            md = "home-page.md"
        md_names[name] = md
    selected = list(order)
    if args.pages:
        wanted = [posixpath.basename(x.strip().replace("\\", "/")) for x in args.pages.split(",") if x.strip()]
        selected = []
        for w in wanted:
            if w not in on_disk:
                rep.error(site / w, 1, f"--pages names {w} but it does not exist")
            elif w not in selected:
                selected.append(w)
    out.mkdir(parents=True, exist_ok=True)
    ex = Exporter(site, out, reg, glossary, md_names, home, args.no_solutions, rep)
    exported: set[str] = set()
    for name in selected:
        regp = next((p for p in reg_pages if p["file"] == name), None)
        try:
            raw = on_disk[name].read_text(encoding="utf-8-sig")
            text, nfig = ex.page(str(on_disk[name].relative_to(site)).replace("\\", "/"), raw, regp)
        except Exception as e:  # noqa: BLE001 — one bad page must not stop the export
            rep.error(on_disk[name], 1, f"could not convert: {type(e).__name__}: {e}")
            continue
        (out / md_names[name]).write_text(text, encoding="utf-8")
        exported.add(md_names[name])
        if not args.quiet:
            print(f"wrote          {md_names[name]}" + (f"  ({nfig} figure{'s' if nfig != 1 else ''})" if nfig else ""))
    pages_for_index = [p for p in reg_pages if p["file"] in on_disk] + [{"file": n, "title": n, "num": "", "group": "Unregistered"} for n in order if n not in {p["file"] for p in reg_pages}]
    (out / "index.md").write_text(outline_md(reg, pages_for_index, md_names, exported, home, out, ex.figures, args.no_solutions, args.lms), encoding="utf-8")
    if not args.quiet:
        print("wrote          index.md")
    if args.lms:
        (out / "imsmanifest.xml").write_text(manifest_xml(reg, pages_for_index, pages_dir, home), encoding="utf-8")
        if not args.quiet:
            print("wrote          imsmanifest.xml (thin IMS CC manifest; paths relative to the site root)")
    return rep.finish({"pages": len(exported), "figures": ex.figures, "out": str(out), "lms": "yes" if args.lms else "no"}, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
