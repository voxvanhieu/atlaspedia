#!/usr/bin/env python
"""Bundle a single-page site into one self-contained HTML file (contracts section 9).

Usage: python bundle.py <siteDir> --out <file.html> [--quiet]

Reads <siteDir>/index.html (the source of a single-format topic, usually topics/<slug>/tmp/site/) and writes one
file: every `<link rel="stylesheet" href="assets/…">` becomes a `<style>` with the file's text; every
`<script src="assets/….js">` (site.js, glossary.js, app.js; `defer` or not) becomes an inline `<script>` with the
file's text, in the same place and order (`</script` inside the code is written `<\\/script`). CDN links (fonts,
KaTeX, highlight.js) stay. G1 vendored site (site.json `"vendor": true`, scaffold.py --offline): the page links
assets/vendor/…, so those files are inlined too and the page works with no network: every url() in a vendored
stylesheet becomes a data: URI (KaTeX keeps only its woff2 sources; Google Fonts keep only the latin and latin-ext
@font-face blocks), highlight.js is inlined when the page has code blocks, and the inlined site.js sets
SITE.vendor = "inline" (the dyslexia font, an opt-in reading setting, then loads from the CDN). Expect about 1 MB; a
warning names the size when the bundle is over site.json `budgetKb` (default 250, the budget validate.py warns about). A comment naming the source and the date is inserted after `<head>`. Tags inside HTML
comments are left alone. app.js finds its root from the page location and waits for DOMContentLoaded while the
document is loading, so the inlined copy at the end of <body> behaves like the included one.

Errors: <siteDir>/index.html missing; an `assets/` include whose file is missing; any `src="assets/` or
`href="assets/` left in the output; --out inside <siteDir> (refused). Nothing is written on an error.
Ends with
  RESULT: tool=bundle status=PASS|FAIL inlined=n bytes=n out=<path>
"""
from __future__ import annotations

import argparse
import base64
import datetime
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, display, load_json, result_line, usage_error  # noqa: E402

COMMENT_RE = re.compile(r"(<!--[\s\S]*?-->)")
LINK_RE = re.compile(r"<link\b[^>]*>", re.I)
SCRIPT_RE = re.compile(r"<script\b([^>]*)>\s*</script>", re.I)
ATTR_RE = r'\b{name}\s*=\s*"([^"]*)"'
LEFTOVER_RE = re.compile(r'\b(?:src|href)\s*=\s*"(?:\./)?assets/[^"]*"', re.I)
# G1 vendored inlining
DEFAULT_BUDGET_KB = 250
KEEP_SUBSETS = ("latin", "latin-ext")
MIME = {".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf", ".svg": "image/svg+xml", ".png": "image/png"}
SUBSET_FACE_RE = re.compile(r"/\*\s*([\w-]+)\s*\*/\s*@font-face\s*\{[^}]*\}\s*")
SRC_RE = re.compile(r"(\bsrc\s*:\s*)([^;}]+)")
URL_RE = re.compile(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)")
HLJS_FILES = ("highlight.min.js", "languages/verilog.min.js", "languages/matlab.min.js")


def inline_vendor_css(css: str, folder: Path, missing: list) -> str:
    """A vendored stylesheet with every url() as a data: URI (woff2 only where a src list offers it; latin subsets only)."""
    css = SUBSET_FACE_RE.sub(lambda m: m.group(0) if m.group(1) in KEEP_SUBSETS else "", css)

    def woff2_only(m):
        items = re.findall(r"url\([^)]*\)\s*(?:format\([^)]*\))?", m.group(2))
        keep = [i for i in items if ".woff2" in i]
        return m.group(1) + ",".join(keep) if keep and len(keep) < len(items) else m.group(0)

    def data_uri(m):
        u = m.group(2)
        if u.startswith(("data:", "http://", "https://", "#")):
            return m.group(0)
        f = folder / u.split("?")[0].split("#")[0]
        if not f.is_file():
            missing.append(f)
            return m.group(0)
        mime = MIME.get(f.suffix.lower(), "application/octet-stream")
        return f"url(data:{mime};base64,{base64.b64encode(f.read_bytes()).decode('ascii')})"
    return URL_RE.sub(data_uri, SRC_RE.sub(woff2_only, css))


def script_text(f: Path) -> str:
    return re.sub(r"</script", r"<\\/script", f.read_text(encoding="utf-8-sig"), flags=re.I)


def attr(tag: str, name: str) -> str | None:
    m = re.search(ATTR_RE.format(name=name), tag, re.I)
    return m.group(1) if m else None


def asset_rel(value: str | None) -> str | None:
    if not value:
        return None
    v = value[2:] if value.startswith("./") else value
    return v if v.startswith("assets/") else None


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siteDir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--quiet", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    site = Path(args.siteDir).resolve()
    out = Path(args.out).resolve()
    if not site.is_dir():
        return usage_error(f"no such directory: {site}")
    rep = Report("tool", "bundle")
    inlined = 0

    def finish(nbytes: int = 0) -> int:
        if not args.quiet:
            rep.print_problems()
        print(result_line(tool="bundle", status=rep.status, inlined=inlined, bytes=nbytes, out=display(out)))
        return 1 if rep.errors else 0

    try:
        out.relative_to(site)
        rep.error(out, 1, f"refusing to write {display(out)}: --out is inside the site folder {display(site)}")
        return finish()
    except ValueError:
        pass
    src = site / "index.html"
    if not src.exists():
        rep.error(src, 1, "index.html missing in the site folder")
        return finish()
    text = src.read_text(encoding="utf-8-sig")
    reg, _ = load_json(site / "assets" / "site.json") if (site / "assets" / "site.json").exists() else (None, None)
    vendored = isinstance(reg, dict) and reg.get("vendor") is True   # G1
    vendor_bytes = 0

    contents: list[str] = []

    def placeholder(block: str) -> str:
        contents.append(block)
        return f"\x00ATLAS{len(contents) - 1}\x00"

    def inline_link(m: re.Match) -> str:
        nonlocal inlined
        tag = m.group(0)
        rel = asset_rel(attr(tag, "href"))
        if not rel or "stylesheet" not in (attr(tag, "rel") or "").lower():
            return tag
        f = site / rel
        if not f.is_file():
            rep.error(src, line_of(text, m.start()), f"include {rel} is missing")
            return tag
        inlined += 1
        css = f.read_text(encoding="utf-8-sig")
        if rel.startswith("assets/vendor/"):  # G1: fonts as data: URIs
            nonlocal vendor_bytes
            missing: list = []
            css = inline_vendor_css(css, f.parent, missing)
            for mf in missing:
                rep.error(src, line_of(text, m.start()), f"{rel} references {display(mf)}, which is missing — run scaffold.py --offline")
            vendor_bytes += len(css.encode("utf-8"))
        return placeholder(f"<style>/* {rel} */\n{css}\n</style>")

    def inline_script(m: re.Match) -> str:
        nonlocal inlined, vendor_bytes
        tag = m.group(0)
        rel = asset_rel(attr(m.group(1), "src"))
        if not rel:
            return tag
        f = site / rel
        if not f.is_file():
            rep.error(src, line_of(text, m.start()), f"include {rel} is missing")
            return tag
        code = script_text(f)
        if vendored and rel == "assets/site.js":
            code += "\nif (window.SITE) window.SITE.vendor = 'inline';   /* bundle.py: the vendored assets are inlined in this file */"
        if rel.startswith("assets/vendor/"):
            vendor_bytes += len(code.encode("utf-8"))
        inlined += 1
        return placeholder(f"<script>/* {rel} */\n{code}\n</script>")

    pieces = COMMENT_RE.split(text)
    offset = 0
    for i, piece in enumerate(pieces):
        if i % 2 == 0:  # outside comments
            seg = LINK_RE.sub(inline_link, piece)
            seg = SCRIPT_RE.sub(inline_script, seg)
            for lm in LEFTOVER_RE.finditer(seg):
                rep.error(src, line_of(text, offset + min(lm.start(), len(piece))), f"output still references assets/: {lm.group(0)}")
            pieces[i] = seg
        offset += len(piece)
    html = "".join(pieces)
    html = re.sub("\x00ATLAS(\\d+)\x00", lambda m: contents[int(m.group(1))], html)
    hl = site / "assets" / "vendor" / "highlight"
    if vendored and re.search(r"<pre\b[^>]*>\s*<code", text) and (hl / HLJS_FILES[0]).is_file():
        # G1: app.js skips its highlight.js loader when window.hljs exists
        code = "\n".join(script_text(hl / n) for n in HLJS_FILES if (hl / n).is_file())
        block = f"<script>/* assets/vendor/highlight/ (highlight.js 11.9.0, inlined for offline use) */\n{code}\n</script>\n"
        vendor_bytes += len(block.encode("utf-8"))
        inlined += 1
        bm = list(re.finditer(r"</body\s*>", html, re.I))
        html = html[:bm[-1].start()] + block + html[bm[-1].start():] if bm else html + block

    rel_src = os.path.relpath(site, out.parent).replace("\\", "/")
    stamp = (f"<!-- atlaspedia single-page bundle · generated by bundle.py from {rel_src} on "
             f"{datetime.date.today().isoformat()} · edit the source and re-run -->")
    hm = re.search(r"<head\b[^>]*>", html, re.I)
    if hm:
        html = html[:hm.end()] + "\n" + stamp + html[hm.end():]
    else:
        rep.warn(src, 1, "no <head> tag; the bundle comment goes first")
        html = stamp + "\n" + html
    if rep.errors:
        return finish()
    out.parent.mkdir(parents=True, exist_ok=True)
    data = html.encode("utf-8")
    out.write_bytes(data)
    if not args.quiet:
        print(f"wrote          {display(out)} ({len(data) / 1024:.0f} KB, {inlined} include(s) inlined)")
    if vendored:
        bk = reg.get("budgetKb", DEFAULT_BUDGET_KB)
        budget = bk if isinstance(bk, (int, float)) and not isinstance(bk, bool) and bk > 0 else DEFAULT_BUDGET_KB
        if not args.quiet:
            print(f"offline        vendored KaTeX, fonts and highlight.js inlined ({vendor_bytes / 1024:.0f} KB of it)")
        if len(data) > budget * 1024:
            rep.warn(out, 1, f"offline bundle is {len(data) / 1024:.0f} KB with the vendored assets inlined ({vendor_bytes / 1024:.0f} KB), "
                             f"over the {budget:g} KB budget — it works with no network but is heavy to e-mail (a non-vendored bundle keeps KaTeX and the fonts on the CDN)")
    return finish(len(data))


if __name__ == "__main__":
    sys.exit(main())
