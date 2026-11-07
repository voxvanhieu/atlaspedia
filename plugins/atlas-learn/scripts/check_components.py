#!/usr/bin/env python
"""Component catalog gate — checks skills/compose/components/ and (re)generates the template's style guide.

Usage: python check_components.py [--styleguide] [--quiet]

Checks:
  1. every module folder under components/ has README.md and at least one snippet (*.html); INDEX.md lists every module
     and every snippet, and names no snippet that is missing; a .js sidecar has a snippet of the same name
  2. every snippet starts with the one-line header comment
       <!-- atlas-learn component: <module>/<file> · use when: … · replace: … · runtime: … · validator: … -->
     whose module/file match its path
  3. every class a snippet uses exists as `.class` in template/assets/style.css or as a quoted token in
     template/assets/app.js, or starts with d- / lg- / hljs- / language-, or is one of the runtime hook classes
  4. ids are unique across the whole catalog
  5. the style guide assembled from the catalog validates: validate.py runs over a temp site built from template/
     (index.html, glossary.html, the assembled styleguide.html, assets/) — its problems are this gate's problems
--styleguide writes the assembled page to template/styleguide.html when the gate passes (never by hand: the page is
generated from the READMEs and snippets; the trust snippet is used once as the page's own footer).
Problems print as `<file>:<line> <message>`. Ends with
  RESULT: gate=components status=PASS|FAIL errors=n warnings=n modules=n snippets=n classes_missing=n styleguide=written|unchanged|skipped
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, col_index, find_table, glossary_js, load_json, read_lines, site_js, usage_error  # noqa: E402

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
CATALOG = PLUGIN / "skills" / "compose" / "components"
TEMPLATE = PLUGIN / "skills" / "compose" / "template"
MODULE_ORDER = ["core", "math", "diagrams", "media", "demos", "plots", "assessment", "overview", "single", "trust"]   # plots (C5–C7) after demos
MODULE_ORDER += ["sitewide"]  # sitewide: A1 A3 E5 G4 H6 — the catalog module of the sitewide workstream
MODULE_ORDER += ["circuit"]  # circuit: C8 schematic symbols, pinouts and register maps
MODULE_ORDER += ["study"]  # study: B4 flashcards, F1 notes — the catalog module of the study workstream
MODULE_ORDER += ["protocol"]  # protocol: C2 C3 C4 — timing, bit-field, sequence and state diagrams as data
MODULE_ORDER += ["runner"]  # runner: D5 in-browser code runners
HEADER_RE = re.compile(r"^<!-- atlas-learn component: ([a-z]+)/([a-z0-9-]+\.html) · use when: (.+?) · replace: (.+?) · runtime: (.+?) · validator: (.+?) -->\s*$")
CLASS_PREFIXES = ("d-", "lg-", "hljs-", "language-")
# Hook classes defined by the template's trust / exercise / step-through blocks in style.css and app.js (spec §1);
# listed here so the catalog gate does not depend on the order in which those blocks land in the template.
HOOK_CLASSES = {
    "trust", "trust-stats", "trust-stat", "trust-assumptions", "trust-gaps", "trust-issue",
    "exercise", "exercise-head", "exercise-label", "exercise-diff", "exercise-done", "hint", "solution", "locked",
    "step-hidden", "diagram-steps", "step-tools", "step-count",
    "good", "warn", "bad", "done", "active",
}
QUOTED_RE = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|`[^`]*`")
CLASS_ATTR_RE = re.compile(r'\sclass="([^"]*)"')
ID_RE = re.compile(r'\sid="([^"]+)"')


def md_inline(text: str) -> str:
    """Escape, then `code` and **bold** — enough for a README's intro paragraph."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    return out


def readme_title_and_intro(path: Path) -> tuple[str, str]:
    lines = read_lines(path)
    title, intro, i = path.parent.name.title(), [], 0
    while i < len(lines) and not lines[i].startswith("# "):
        i += 1
    if i < len(lines):
        title = lines[i][2:].strip()
        i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines) and lines[i].strip() and not lines[i].startswith("#"):
        intro.append(lines[i].strip())
        i += 1
    return title, " ".join(intro)


def css_classes(css: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"\.([A-Za-z_][\w-]*)", css)}


def js_tokens(js: str) -> set[str]:
    out: set[str] = set()
    for m in QUOTED_RE.finditer(js):
        out.update(t for t in re.split(r"[^\w-]+", m.group(0)[1:-1]) if t)
    return out


def ordered_modules(names: list[str]) -> list[str]:
    known = [m for m in MODULE_ORDER if m in names]
    return known + sorted(n for n in names if n not in MODULE_ORDER)


# ------------------------------------------------------------- assembly ---
ABOUT_HTML = """  <section>
    <h2 id="about">How an atlas-learn site is put together</h2>
    <p>A site is <code>index.html</code> at the topic root, every other page under <code>pages/</code>, and <code>assets/</code>. Two asset files are fixed code copied from the template and never edited per site; two are data written per site. The runtime reads the <dfn>registry</dfn> (<code>assets/site.js</code>) to build the sidebar, search index, pager, progress and the overview widgets, so <strong>the registry is written first</strong> and page file names never change afterwards.</p>
    <table class="compact">
      <thead><tr><th>File</th><th>Fixed or per site</th><th>Role</th></tr></thead>
      <tbody>
        <tr><td><code>assets/style.css</code></td><td>Fixed</td><td>Design tokens, typography, layout, every component, light theme default with dark mode</td></tr>
        <tr><td><code>assets/app.js</code></td><td>Fixed</td><td>Shell, TOC, search, tables, quizzes, diagrams, step-through, code, embeds, tabs, checklists, exercises, plots, storage, overview widgets, trust footer</td></tr>
        <tr><td><code>assets/site.js</code></td><td>Per site (generated)</td><td>Title, subtitle, storage prefix, level names, footnote, theme, the page registry — from <code>assets/site.json</code></td></tr>
        <tr><td><code>assets/glossary.js</code></td><td>Per site (generated)</td><td>Glossary terms: searched site-wide, rendered by <code>glossary.html</code> — from <code>assets/glossary.json</code></td></tr>
        <tr><td><code>index.html</code></td><td>Per site</td><td>Overview: summary, scope, method, findings, system map, curriculum map, deliverables index</td></tr>
        <tr><td><code>pages/mNN-slug.html</code></td><td>Per site</td><td>One learning module each, from <code>_module.html</code>; synthesis parts from <code>_synthesis.html</code>; the bibliography from <code>_reference.html</code></td></tr>
      </tbody>
    </table>
    <div class="callout note"><span class="callout-title">What the runtime injects</span><p>The reading-progress bar, top bar with search (<kbd>/</kbd>) and theme toggle, the sidebar, the on-page table of contents (right rail on wide screens), the previous/next pager, the "mark module as completed" button, the trust-footer statistics and the footnote. A page only writes <code>&lt;main&gt;</code>.</p></div>
  </section>
"""

TAIL_HTML = """  <section>
    <h2 id="mistakes">Common authoring mistakes</h2>
    <div class="callout mistakes"><span class="callout-title">Mistakes to avoid</span><ul>
      <li>Writing CSS or a second script handler into a page — every style and behaviour lives in the fixed assets; a missing component is added to the template, never to a page.</li>
      <li>Hard-coding SVG colours instead of the <code>d-*</code> classes, so dark mode breaks.</li>
      <li>Citing a reference that is not in the dossier, or leaving the <code>verified</code> badge off a reference the dossier verified — the trust footer then under-reports.</li>
      <li>Hiding required content in a non-default tab or an open-by-default solution.</li>
      <li>Copying a snippet without renaming its ids when the page already uses them.</li>
    </ul></div>
  </section>

  <section>
    <h2 id="reading">Further reading</h2>
    <ol class="refs">
      <li id="ref-katex-autorender"><span class="ref-authors">KaTeX contributors</span> (2024). <a href="https://katex.org/docs/autorender">KaTeX auto-render extension</a>. <span class="ref-venue">katex.org documentation</span> <span class="badge established">Reference</span><span class="badge verified">Verified</span><span class="why">The delimiter rules the math module relies on.</span></li>
      <li id="ref-model-viewer"><span class="ref-authors">Google</span> (2024). <a href="https://modelviewer.dev/">&lt;model-viewer&gt; web component</a>. <span class="ref-venue">modelviewer.dev</span> <span class="badge established">Reference</span><span class="badge verified">Verified</span><span class="why">What the 3D embed loads on demand; attributes and poster behaviour.</span></li>
    </ol>
  </section>

  <section>
    <h2 id="checkpoints">Knowledge checkpoints</h2>
    <div class="quiz" data-answer="2">
      <p class="q">A writer needs a component that is not in its MODULES list. What does the catalog ask for?</p>
      <ol class="opts">
        <li>Write the markup from memory and mention it in the report.</li>
        <li>Add the missing CSS to the page so it renders.</li>
        <li>Find the module in INDEX.md, read its README, use the snippet, and report the extra load in a Friction line.</li>
      </ol>
      <div class="explain">Loading on demand is allowed and expected; what the main agent needs is the Friction line, so the derivation rule that builds the MODULES list can be corrected.</div>
    </div>
  </section>

  <section>
    <h2 id="deliverable">Deliverable</h2>
    <p>A page that uses only catalog components, passes <code>validate.py</code>, and ends with a trust footer whose numbers are honest.</p>
  </section>
"""


def assemble(modules: list[dict], skeleton: str) -> str:
    """The style guide page from the catalog. `modules`: [{name, title, intro, snippets:[{file, stem, use, replace, runtime, validator, body, js}]}]"""
    head = re.search(r"<head>[\s\S]*?</head>", skeleton)
    head_html = head.group(0) if head else "<head><meta charset=\"utf-8\"></head>"
    head_html = re.sub(r"<title>[^<]*</title>", "<title>Component style guide</title>", head_html)
    head_html = re.sub(r'<meta name="description" content="[^"]*">',
                       '<meta name="description" content="Every component of the atlas-learn compose template rendered once from its component catalog, with its source.">', head_html)
    scripts = re.findall(r'<script[^>]*\bsrc="[^"]+"[^>]*></script>', skeleton)
    n_snips = sum(len(m["snippets"]) for m in modules)
    out = ["<!doctype html>", '<html lang="en">', head_html, '<body data-page="styleguide.html" data-subject="atlas-learn">',
           "<!--\n  COMPONENT STYLE GUIDE — GENERATED from skills/compose/components/ by scripts/check_components.py --styleguide.\n"
           "  Do not edit by hand: change a snippet or README in the catalog and regenerate.\n-->",
           "<main>",
           '  <header class="module-hero">',
           '    <div class="eyebrow">atlas-learn · Template · Style guide</div>',
           "    <h1>Component style guide</h1>",
           '    <p class="lede">The building blocks atlas-learn page writers assemble every topic from, each rendered once from the component catalog with its source. Every example uses atlas-learn itself as the running example, so the page also reads as a tour of how the plugin works: its stages, agents, gates and size budget.</p>',
           '    <dl class="meta-strip">',
           f"      <div><dt>Modules</dt><dd>{len(modules)}</dd></div>",
           f"      <div><dt>Snippets</dt><dd>{n_snips}</dd></div>",
           "      <div><dt>Catalog</dt><dd><code>skills/compose/components/</code></dd></div>",
           "      <div><dt>Running example</dt><dd>atlas-learn and its <code>map-projections</code> topic</dd></div>",
           "    </dl>",
           "  </header>",
           "",
           "  <section>",
           '    <h2 id="objectives">What this page is for</h2>',
           '    <ol class="objectives">',
           "      <li>See every catalog component rendered in the fixed stylesheet and runtime, light and dark.</li>",
           "      <li>Copy a snippet's source from its <b>Source</b> block or from the catalog file it names.</li>",
           "      <li>Check that a new component (a template block plus its snippet) renders and validates before any topic uses it.</li>",
           "      <li>Read, per component, when it earns its place and what the validator will say when it is misused.</li>",
           "    </ol>",
           '    <div class="keywords"><span>catalog</span><span>snippet</span><span>runtime</span><span>validator</span></div>',
           '    <div class="callout note"><span class="callout-title">About the examples</span><p>Every snippet describes atlas-learn itself, and the <code>map-projections</code> sample topic from the plugin README stands in for a real run; where a component needs outside material (a photo, a 3D model), it comes from cartography, the field atlas-learn is named after. Figures and demos about atlas-learn cite its documentation <a class="cite" href="#ref-atlas-learn-docs">[4]</a>; the domain examples (map projections, SPI, TLS, an AVR pinout) cite a template placeholder <a class="cite" href="#ref-placeholder">[5]</a> instead of a source nobody retrieved — in a site, every cite names a dossier entry (<code>references/evidence-policy.md</code>). When a page writer copies a snippet, every word of it is replaced with the topic\'s own content; only the markup stays. The rules are in <code>references/authoring-rules.md</code>.</p></div>',
           "  </section>",
           "",
           ABOUT_HTML]
    js_parts: list[str] = []
    trust_body = None
    for m in modules:
        out.append("  <section>")
        out.append(f'    <h2 id="c-{m["name"]}">{html.escape(m["title"], quote=False)}</h2>')
        out.append(f"    <p>{md_inline(m['intro'])}</p>")
        for s in m["snippets"]:
            out.append(f'    <h3 id="c-{m["name"]}-{s["stem"]}">{m["name"]}/{s["file"]}</h3>')
            out.append(f"    <p><b>Use when:</b> {html.escape(s['use'])}. <b>Replace:</b> {html.escape(s['replace'])}. "
                       f"<b>Runtime:</b> {html.escape(s['runtime'])}. <b>Validator:</b> {html.escape(s['validator'])}.</p>")
            if m["name"] == "trust":
                trust_body = s["body"]
                out.append("    <p>Rendered once as this page's own footer — scroll to the bottom.</p>")
            else:
                out.append(s["body"].rstrip())
            src = s["body"].rstrip() + ("\n\n<script>\n// qc:ready handler body (" + s["file"][:-5] + ".js)\n" + s["js"].rstrip() + "\n</script>" if s["js"] else "")
            out.append("    <details><summary>Source</summary><pre><code class=\"language-html\">" + html.escape(src, quote=True) + "</code></pre></details>")
            if s["js"]:
                js_parts.append(f"  {{ /* {m['name']}/{s['file'][:-5]}.js */\n{s['js'].rstrip()}\n  }}")
        out.append("  </section>")
        out.append("")
    out.append(TAIL_HTML)
    if trust_body:
        out.append(trust_body.rstrip())
    out.append("</main>")
    out.append("")
    out.extend(scripts)
    out.append("<script>")
    out.append("document.addEventListener('qc:ready', () => {")
    out.extend(js_parts)
    out.append("});")
    out.append("</script>")
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------- main ---
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--styleguide", action="store_true", help="write template/styleguide.html when the gate passes")
    ap.add_argument("--quiet", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    if not CATALOG.is_dir():
        return usage_error(f"catalog folder missing: {CATALOG}")
    if not TEMPLATE.is_dir():
        return usage_error(f"template folder missing: {TEMPLATE}")
    rep = Report("gate", "components")
    index_p = CATALOG / "INDEX.md"
    classes_missing = 0
    styleguide = "skipped"

    # ---- 1. folders, INDEX.md -----------------------------------------------
    folders = [d for d in CATALOG.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]
    names = ordered_modules([d.name for d in folders])
    listed: dict[str, list[str]] = {}
    if not index_p.exists():
        rep.error(index_p, 1, "INDEX.md missing")
    else:
        lines = read_lines(index_p)
        t = find_table(lines, 0, len(lines))
        if not t:
            rep.error(index_p, 1, "INDEX.md has no module table")
        else:
            header, hidx, rows = t
            mi, si = col_index(header, "Module"), col_index(header, "Snippets")
            if mi < 0 or si < 0:
                rep.error(index_p, hidx + 1, "INDEX.md table needs `Module` and `Snippets` columns")
            else:
                for ridx, cells in rows:
                    if len(cells) <= max(mi, si):
                        continue
                    mod = cells[mi].strip().strip("`").strip()
                    snips = re.findall(r"[a-z0-9-]+\.html", cells[si])
                    if mod in listed:
                        rep.error(index_p, ridx + 1, f"module `{mod}` listed twice")
                    listed[mod] = snips
                    if mod not in names:
                        rep.error(index_p, ridx + 1, f"module `{mod}` has no folder under components/")
                    else:
                        for sn in snips:
                            if not (CATALOG / mod / sn).exists():
                                rep.error(index_p, ridx + 1, f"snippet {mod}/{sn} is listed but missing")
        for n in names:
            if n not in listed:
                rep.error(index_p, 1, f"module `{n}` is not listed in INDEX.md")

    # ---- 2.–4. modules, headers, classes, ids ---------------------------------
    css = (TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8-sig") if (TEMPLATE / "assets" / "style.css").exists() else ""
    app = (TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8-sig") if (TEMPLATE / "assets" / "app.js").exists() else ""
    if not css:
        rep.error(TEMPLATE / "assets" / "style.css", 1, "template style.css missing")
    if not app:
        rep.error(TEMPLATE / "assets" / "app.js", 1, "template app.js missing")
    known_css, known_js = css_classes(css), js_tokens(app)
    ids_seen: dict[str, Path] = {}
    modules: list[dict] = []
    n_snippets = 0
    for n in names:
        folder = CATALOG / n
        readme = folder / "README.md"
        htmls = sorted(p for p in folder.glob("*.html"))
        jss = sorted(p for p in folder.glob("*.js"))
        if not readme.exists():
            rep.error(readme, 1, f"module `{n}` has no README.md")
            title, intro = n.title(), ""
        else:
            title, intro = readme_title_and_intro(readme)
            if not intro:
                rep.error(readme, 1, "README.md needs a use-when paragraph right after its `# ` title")
        if not htmls:
            rep.error(folder, 1, f"module `{n}` has no snippet (*.html)")
        for js in jss:
            if not (folder / (js.stem + ".html")).exists():
                rep.error(js, 1, f"{js.name} has no snippet {js.stem}.html beside it")
        snippets = []
        for p in htmls:
            n_snippets += 1
            text = p.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
            first, _, rest = text.partition("\n")
            m = HEADER_RE.match(first)
            if not m:
                rep.error(p, 1, "first line must be `<!-- atlas-learn component: <module>/<file> · use when: … · replace: … · runtime: … · validator: … -->`")
                body, fields = text, ("", "", "", "")
            else:
                if m.group(1) != n or m.group(2) != p.name:
                    rep.error(p, 1, f"header names {m.group(1)}/{m.group(2)} but the file is {n}/{p.name}")
                body, fields = rest, (m.group(3), m.group(4), m.group(5), m.group(6))
            if n in listed and p.name not in listed[n]:
                rep.error(index_p, 1, f"snippet {n}/{p.name} is not listed in INDEX.md")
            no_comment = re.sub(r"<!--[\s\S]*?-->", "", body)
            for cm in CLASS_ATTR_RE.finditer(no_comment):
                for tok in cm.group(1).split():
                    if tok in known_css or tok in known_js or tok in HOOK_CLASSES or tok.startswith(CLASS_PREFIXES):
                        continue
                    classes_missing += 1
                    rep.error(p, body[:cm.start()].count("\n") + 2, f"class `{tok}` not in style.css/app.js")
            for im in ID_RE.finditer(no_comment):
                i = im.group(1)
                if i in ids_seen:
                    rep.error(p, body[:im.start()].count("\n") + 2, f"id `{i}` also used in {ids_seen[i].parent.name}/{ids_seen[i].name}")
                else:
                    ids_seen[i] = p
            jsp = folder / (p.stem + ".js")
            snippets.append({"file": p.name, "stem": p.stem, "use": fields[0], "replace": fields[1], "runtime": fields[2],
                             "validator": fields[3], "body": body,
                             "js": jsp.read_text(encoding="utf-8-sig").replace("\r\n", "\n") if jsp.exists() else None})
        modules.append({"name": n, "title": title, "intro": intro, "snippets": snippets})
    if "trust" not in names:
        rep.error(CATALOG / "trust", 1, "the `trust` module is required (the style guide uses its snippet as its own footer)")

    # ---- 5. assemble and validate ---------------------------------------------
    skeleton_p = TEMPLATE / "_skeleton.html"
    page = ""
    if not skeleton_p.exists():
        rep.error(skeleton_p, 1, "template _skeleton.html missing (the style guide takes its <head> and script tags from it)")
    else:
        page = assemble(modules, skeleton_p.read_text(encoding="utf-8-sig").replace("\r\n", "\n"))
        out_p = TEMPLATE / "styleguide.html"
        with tempfile.TemporaryDirectory(prefix="atlas-learn-components-") as td:
            site = Path(td) / "site"
            (site / "assets").mkdir(parents=True)
            ok = True
            # every template page except the skeletons and the generated style guide (reference pages such as
            # indexes.html, notation.html … are checked here too, so they must be registered in template/assets/site.json)
            tpl_pages = sorted(p.name for p in TEMPLATE.glob("*.html") if not p.name.startswith("_") and p.name != "styleguide.html")
            for f in ("index.html", "glossary.html"):
                if f not in tpl_pages:
                    rep.error(TEMPLATE / f, 1, f"template {f} missing")
                    ok = False
            for f in tpl_pages:
                shutil.copyfile(TEMPLATE / f, site / f)
            (site / "assets" / "data.js").write_text("window.QC_DATA = {};\n", encoding="utf-8")
            for f in ("style.css", "app.js", "site.json", "glossary.json"):
                if (TEMPLATE / "assets" / f).exists():
                    shutil.copyfile(TEMPLATE / "assets" / f, site / "assets" / f)
                else:
                    rep.error(TEMPLATE / "assets" / f, 1, f"template assets/{f} missing")
                    ok = False
            if ok:
                reg, err = load_json(site / "assets" / "site.json")
                gl, gerr = load_json(site / "assets" / "glossary.json")
                if err or gerr:
                    rep.error(TEMPLATE / "assets" / "site.json", 1, err or gerr)
                else:
                    (site / "assets" / "site.js").write_text(site_js(reg), encoding="utf-8")
                    (site / "assets" / "glossary.js").write_text(glossary_js(gl), encoding="utf-8")
                    (site / "styleguide.html").write_text(page, encoding="utf-8")
                    try:
                        proc = subprocess.run([sys.executable, str(HERE / "validate.py"), str(site)], capture_output=True,
                                              text=True, encoding="utf-8", errors="replace", cwd=str(site), timeout=300)
                        v_out = proc.stdout + proc.stderr
                    except (OSError, subprocess.TimeoutExpired) as e:
                        v_out, proc = f"validate.py failed to run: {e}", None
                        rep.error(HERE / "validate.py", 1, v_out)
                    if proc is not None:
                        for ln in v_out.splitlines():
                            lm = re.match(r"^(.*?):(\d+) (warning: )?(.*)$", ln.strip())
                            if not lm or ln.startswith("RESULT:"):
                                continue
                            f, line, warn, msg = lm.group(1).replace("\\", "/"), int(lm.group(2)), lm.group(3), lm.group(4)
                            target = out_p if f.endswith("styleguide.html") else (TEMPLATE / f if not Path(f).is_absolute() else Path(f))
                            (rep.warn if warn else rep.error)(target, line, f"[validate] {msg}")
                        if proc.returncode not in (0, 1):
                            rep.error(HERE / "validate.py", 1, f"[validate] exited {proc.returncode}: {v_out.strip().splitlines()[-1] if v_out.strip() else ''}")
        if args.styleguide:
            if rep.errors:
                rep.warn(out_p, 1, "style guide not written: fix the errors above and run again")
            else:
                old = out_p.read_text(encoding="utf-8-sig").replace("\r\n", "\n") if out_p.exists() else None
                if old == page:
                    styleguide = "unchanged"
                else:
                    out_p.write_text(page, encoding="utf-8")
                    styleguide = "written"
    return rep.finish({"modules": len(names), "snippets": n_snippets, "classes_missing": classes_missing, "styleguide": styleguide}, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
