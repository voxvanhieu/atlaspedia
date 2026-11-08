"""Exercises every atlaspedia script against tests/fixtures. Run from anywhere: python <plugin>/tests/run_tests.py

Work files go to <system temp>/atlaspedia-tests-work (recreated on every run). Network checks are tolerant: they
report what the network allowed instead of failing when a host is blocked.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
SCRIPTS = PLUGIN / "scripts"
TEMPLATE = PLUGIN / "skills" / "compose" / "template"
REPO = PLUGIN.parent.parent  # <repo>/plugins/atlaspedia
PY = sys.executable
FIX = HERE / "fixtures"
FIX_REPO = FIX / "repo"
TOPIC = FIX_REPO / "topics" / "map-projections"
PLAN = TOPIC / "PLAN.md"
TMP = TOPIC / "tmp"
WORK = Path(tempfile.gettempdir()) / "atlaspedia-tests-work"
# reference pages the template ships (scaffold.py AUTO_PAGES): copied and registered automatically on a site scaffold
AUTO_PAGES = [f for f in ("indexes.html", "notation.html", "concepts.html", "changelog.html") if (TEMPLATE / f).exists()]
results: list[tuple[str, bool, str]] = []

# ---- feature tests ---------------------------------------------------------------
# The feature blocks at the end of this file register tests with @feature_test; main() calls each with a namespace `t`
# holding the helpers (run, check, mutate, line_no, result_of), the folders (WORK, PLUGIN, SCRIPTS, TEMPLATE, FIX), the
# scaffolded pages/ topic (t.topic, t.tmp, t.sj + t.reg registry, t.sync(), t.m02 text + t.page_m02 path, t.kind =
# _module.html text) and the single site (t.s_site, t.spage text, t.sj_single + t.sreg). A test restores what it changes.
FEATURE_TESTS: list = []


def feature_test(fn):
    FEATURE_TESTS.append(fn)
    return fn


def run(script: str, *args: str, cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run([PY, str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True,
                       cwd=str(cwd or HERE), encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not detail else "\n      " + detail.strip().replace("\n", "\n      ")[:900]))


def result_of(out: str) -> dict:
    line = [l for l in out.splitlines() if l.startswith("RESULT:")]
    if not line:
        return {}
    return dict(kv.split("=", 1) for kv in line[-1][len("RESULT: "):].split(" ") if "=" in kv)


def local_refs(text: str) -> str:
    """Catalog snippets cite the style guide's #ref-atlaspedia-docs / #ref-placeholder; on a test page they cite #ref-key."""
    return text.replace('"#ref-atlaspedia-docs"', '"#ref-key"').replace('"#ref-placeholder"', '"#ref-key"')


def mutate(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new)


def line_no(text: str, needle: str) -> int:
    for i, l in enumerate(text.splitlines(), 1):
        if needle in l:
            return i
    raise AssertionError(needle)


def find_reference_page() -> Path | None:
    """A large real module page from a topic built in this repository before the trust footer existed (read only).

    Copied alone into a test site, such a page has broken cross-links and no trust footer, which the validate checks
    below expect. Any `m01-introduction.html` under topics/ without a `class="trust"` section qualifies."""
    cands = [REPO / "src" / "m01-introduction.html"]
    cands += sorted((REPO / "topics").glob("*/m01-introduction.html")) + sorted((REPO / "topics").glob("*/pages/m01-introduction.html"))
    for cand in cands:
        if cand.exists() and 'class="trust"' not in cand.read_text(encoding="utf-8", errors="replace"):
            return cand
    return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("python:", sys.version.split()[0], PY)
    print("work:", WORK)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()
    # a writable copy of the fixture repo (the hash test rewrites BRIEF.md's header)
    repo = WORK / "repo"
    shutil.copytree(FIX_REPO, repo)
    topic = repo / "topics" / "map-projections"
    plan = topic / "PLAN.md"
    tmp = topic / "tmp"
    plan_text = plan.read_text(encoding="utf-8")

    # ---- hash + BRIEF fixture -------------------------------------------------------
    code, out = run("check_plan.py", plan, "--hash")
    h = re.search(r"^HASH: ([0-9a-f]{12})$", out, re.M)
    check("check_plan --hash prints a 12-hex hash", code == 0 and bool(h), out)
    brief = tmp / "BRIEF.md"
    brief.write_text(re.sub(r"\*\*Insight hash\*\*: \S+", f"**Insight hash**: {h.group(1) if h else 'none'}", brief.read_text(encoding="utf-8")), encoding="utf-8")

    # ---- plan passes ----------------------------------------------------------------
    code, out = run("check_plan.py", plan)
    r = result_of(out)
    check("example plan PASS", code == 0 and r.get("status") == "PASS" and r.get("stage") == "research" and r.get("warnings") == "0", out)
    code, out = run("check_plan.py", plan, "--before", "research")
    check("example plan --before research PASS", code == 0 and result_of(out).get("status") == "PASS", out)
    code, out = run("check_plan.py", plan, "--before", "compose")
    check("example plan --before compose FAIL (research still open)", code == 1 and "before `compose`" in out, out)

    # ---- mutations ------------------------------------------------------------------
    mut_dir = WORK / "mut" / "topics" / "map-projections"
    shutil.copytree(topic, mut_dir)
    mplan = mut_dir / "PLAN.md"

    def expect_fail(name: str, text: str, needle_line: str, needle_msg: str, *extra: str, path: Path = mplan) -> None:
        path.write_text(text, encoding="utf-8")
        code, out = run("check_plan.py", path, *extra)
        ln = line_no(text, needle_line)
        ok = code == 1 and re.search(rf":{ln} .*{re.escape(needle_msg)}", out) is not None
        check(name + f" (line {ln})", ok, out)

    expect_fail("wrong marker FAIL", mutate(plan_text, "| M01 | From the globe to the plane | [x] | [x] | [ ] |", "| M01 | From the globe to the plane | [y] | [x] | [ ] |"),
                "| M01 |", "marker `[y]`")
    expect_fail("missing key FAIL", mutate(plan_text, "- **Why**: My world maps make Greenland look as big as Africa and I want to understand why, not just pick a preset.\n", ""),
                "## What I want", "exactly these bullets")
    expect_fail("placeholder FAIL", mutate(plan_text, "- **Goal**: Understand and choose map projections for my own maps, and implement the forward equations.", "- **Goal**: {goal}"),
                "- **Goal**:", "placeholder")
    expect_fail("[x] after [ ] FAIL", mutate(plan_text, "| [ ] | compose | index.html |", "| [x] | compose | index.html |"),
                "| compose |", "sequential")
    expect_fail("SKIP without note FAIL", mutate(plan_text, "- Changed 1 (research, 2026-11-05): M06 skipped — tile-server internals have no citable source at standard level; folded into M04 as an overview.\n", ""),
                "| M06 |", "no `Changed` note names M06")
    expect_fail("wrong Folder FAIL", mutate(plan_text, "**Folder**: topics/map-projections/", "**Folder**: .claude/tmp/map-projections/"),
                "**Folder**:", "Folder must be `topics/map-projections/`")
    expect_fail("old Files header FAIL", mutate(plan_text, "**Folder**: topics/map-projections/", "**Folder**: topics/map-projections/\n**Files**: .claude/tmp/map-projections/"),
                "**Files**:", "no longer a plan header line")
    expect_fail("wrong Progress output FAIL", mutate(plan_text, "| [ ] | research | tmp/dossier/ |", "| [ ] | research | .claude/tmp/map-projections/dossier/ |"),
                "| research |", "must be `tmp/dossier/`")
    # slug ≠ folder name
    other = WORK / "mut" / "topics" / "other-name"
    shutil.copytree(topic, other)
    expect_fail("slug ≠ folder name FAIL", plan_text, "**Slug**:", "must equal the plan's folder name `other-name`", path=other / "PLAN.md")
    # hash mismatch: edit INSIGHTS.md in the mutation copy
    mplan.write_text(plan_text, encoding="utf-8")
    ins = mut_dir / "tmp" / "INSIGHTS.md"
    ins.write_text(ins.read_text(encoding="utf-8").replace("replace the default projection", "replace the vendor projection"), encoding="utf-8")
    code, out = run("check_plan.py", mplan, "--before", "research")
    bl = line_no((mut_dir / "tmp" / "BRIEF.md").read_text(encoding="utf-8"), "**Insight hash**")
    check(f"hash mismatch FAIL (BRIEF.md line {bl})", code == 1 and re.search(rf"BRIEF\.md:{bl} Insight hash", out) is not None, out)

    # ---- next_stage -----------------------------------------------------------------
    code, out = run("next_stage.py", plan)
    want = ["Stage: research", "Open researched: M04,M05,S01", "Open checked: M03,M04,M05",
            "Open pages: index.html,m01-introduction.html,glossary.html", "Next: /atlaspedia:research map-projections"]
    check("next_stage output", code == 0 and all(w in out for w in want) and result_of(out).get("command") == "/atlaspedia:research" and result_of(out).get("slug") == "map-projections", out)

    # ---- Format header + estimate_size (single page) --------------------------------
    fmt_dir = WORK / "fmt" / "topics" / "map-projections"
    shutil.copytree(topic, fmt_dir)
    fplan = fmt_dir / "PLAN.md"
    single_text = mutate(plan_text, "**Stage**:", "**Format**: single\n**Stage**:")
    fplan.write_text(single_text, encoding="utf-8")
    code, out = run("check_plan.py", fplan)
    check("check_plan accepts **Format**: single", code == 0 and result_of(out).get("status") == "PASS", out)
    code, out = run("next_stage.py", fplan)
    check("next_stage prints Format: single and format=single", code == 0 and "Format: single" in out and result_of(out).get("format") == "single", out)
    code, out = run("next_stage.py", plan)
    check("next_stage: format=site when the plan has no Format line", code == 0 and result_of(out).get("format") == "site", out)
    bad_fmt = single_text.replace("**Format**: single", "**Format**: pdf")
    fplan.write_text(bad_fmt, encoding="utf-8")
    code, out = run("check_plan.py", fplan)
    ln = line_no(bad_fmt, "**Format**:")
    check(f"check_plan rejects **Format**: pdf (line {ln})", code == 1 and f":{ln} Format must be single or site (got `pdf`)" in out, out)
    fplan.write_text(single_text, encoding="utf-8")
    shutil.copyfile(FIX / "single" / "BRIEF-small.md", fmt_dir / "tmp" / "BRIEF.md")
    code, out = run("estimate_size.py", fplan)
    r = result_of(out)
    check("estimate_size small brief: 3 parts, 14 topics, 107 KB, fits=yes",
          code == 0 and r.get("status") == "PASS" and r.get("format") == "single" and r.get("parts") == "3" and r.get("topics") == "14"
          and r.get("est_kb") == "107" and r.get("budget_kb") == "250" and r.get("fits") == "yes" and re.search(r"BRIEF\.md:\d+ M01 topics=7 est=38KB", out) is not None, out)
    shutil.copyfile(FIX / "single" / "BRIEF-large.md", fmt_dir / "tmp" / "BRIEF.md")
    code, out = run("estimate_size.py", fplan)
    r = result_of(out)
    check("estimate_size large brief: 5 parts, 100 topics, 370 KB, fits=no",
          code == 0 and r.get("parts") == "5" and r.get("topics") == "100" and r.get("est_kb") == "370" and r.get("fits") == "no", out)
    code, out = run("estimate_size.py", fplan, "--budget", "400")
    check("estimate_size --budget 400: the large brief fits", code == 0 and result_of(out).get("fits") == "yes" and result_of(out).get("budget_kb") == "400", out)
    (fmt_dir / "tmp" / "BRIEF.md").unlink()
    code, out = run("estimate_size.py", fplan)
    check("estimate_size without BRIEF.md FAIL", code == 1 and result_of(out).get("status") == "FAIL" and "BRIEF.md not found" in out, out)

    # ---- dossier --------------------------------------------------------------------
    code, out = run("check_dossier.py", tmp / "dossier" / "m01-globe-to-plane.md")
    r = result_of(out)
    check("dossier m01 PASS", code == 0 and r.get("status") == "PASS" and r.get("sources") == "8" and r.get("t1") == "4" and r.get("unverified") == "1" and r.get("media") == "1" and r.get("demos") == "2", out)
    bad = tmp / "dossier" / "m02-bad.md"
    btext = bad.read_text(encoding="utf-8")
    code, out = run("check_dossier.py", bad)
    checks = [
        (line_no(btext, "| 2 | 1 | established | Snyder and Voxland"), "Verified cell is blank"),
        (line_no(btext, "| 3 | 4 | classic"), "Tier `4`"),
        (line_no(btext, "| 3 | 4 | classic"), "Status `classic`"),
        (line_no(btext, "| 3 | 4 | classic"), "without an http(s) link"),
        (line_no(btext, "Typical Web Mercator area exaggeration"), "no source (write a source #"),
        (line_no(btext, "Rhumb lines are straight on Mercator"), "source #9 does not exist"),
        (line_no(btext, "| video | https://www.youtube.com/watch?v=kIID5FDi2JQ"), "without a licence"),
        (1, "section `## Could not verify` missing"),
    ]
    missing = [f"{ln}:{msg}" for ln, msg in checks if re.search(rf":{ln} .*{re.escape(msg)}", out) is None]
    check("dossier m02 FAIL with the right lines", code == 1 and not missing, out + "\nMISSING: " + ", ".join(missing))
    code, out = run("check_dossier.py", tmp / "dossier" / "00-overview.md", "--overview")
    r = result_of(out)
    check("overview PASS", code == 0 and r.get("status") == "PASS" and r.get("pages") == "2" and r.get("sources") == "2" and r.get("unverified") == "2", out)
    ov_bad = WORK / "00-overview-bad.md"
    ov_bad.write_text((tmp / "dossier" / "00-overview.md").read_text(encoding="utf-8").replace("- Demos: latitude slider (m02 C1)\n", "").replace("**Priority module**: M04\n", ""), encoding="utf-8")
    code, out = run("check_dossier.py", ov_bad, "--overview")
    check("overview FAIL (missing Priority module + Demos line)", code == 1 and "Priority module" in out and "lacks the `- Demos:` line" in out, out)

    # ---- links ----------------------------------------------------------------------
    links_dir = WORK / "links"
    shutil.copytree(FIX / "links", links_dir)
    code, out = run("check_links.py", links_dir / "links.md", "--timeout", "20")
    r = result_of(out)
    report = links_dir / "links.links.md"
    check("check_links runs and writes the report", code == 0 and report.exists() and r.get("checked") == "7", out)
    print("      " + "\n      ".join(l for l in report.read_text(encoding="utf-8").splitlines() if l.startswith("| ") and not l.startswith("| #")))
    print("      " + out.strip().splitlines()[-1] + ("" if int(r.get("ok", "0")) >= 3 else "   (network limited: fewer than 3 ok)"))

    # ---- scaffold + validate, flat layout (parity with validate.js) -----------------
    ref_page = find_reference_page()
    site_plan = (tmp / "SITE_PLAN.md").read_text(encoding="utf-8")
    flat_plan = WORK / "SITE_PLAN_flat.md"
    flat_plan.write_text(site_plan.replace("**Status**: Draft", "**Pages dir**: flat\n**Status**: Draft"), encoding="utf-8")
    site_flat = WORK / "site-flat"
    code, out = run("scaffold.py", site_flat, "--plan", flat_plan)
    r = result_of(out)
    check("scaffold flat", code == 0 and r.get("status") == "PASS" and r.get("pages") == str(3 + len(AUTO_PAGES)) and (site_flat / "glossary.html").exists()
          and (site_flat / "assets" / "site.js").exists() and (site_flat / "assets" / "data.js").exists() and all((site_flat / f).exists() for f in AUTO_PAGES), out)
    if ref_page:
        shutil.copyfile(ref_page, site_flat / "m01-introduction.html")
    else:
        # No real topic page lives in this repo any more (topics may live in a sibling workspace):
        # synthesize one from a generated reference page, keeping the two defects the real page
        # used to contribute — a broken cross-link and no trust footer — and nothing else.
        text = (site_flat / "notation.html").read_text(encoding="utf-8")
        text = re.sub(r'<section class="trust"[\s\S]*?</section>',
                      '<p>See also: <a href="m99-synthetic-missing.html">the missing module</a>.</p>', text, count=1)
        (site_flat / "m01-introduction.html").write_text(text, encoding="utf-8")
        print("      (reference page m01-introduction.html not found in the repo: synthesized a minimal one)")
    code, out_py = run("validate.py", site_flat)
    r = result_of(out_py)
    check("validate.py flat: index + glossary clean, m01 broken links + missing trust footer only",
          r.get("js_syntax") == "checked" and r.get("bad_pages") == "1" and r.get("site_issues") == "0" and "broken links" in out_py
          and "page has no trust footer" in out_py and "m01-introduction.html:" in out_py, out_py)
    # --pages filter
    code, out = run("validate.py", site_flat, "--pages", "index.html,glossary.html", "--quiet")
    check("validate.py --pages filter PASS", code == 0 and result_of(out).get("pages") == "2", out)
    # out-of-sync detection
    (site_flat / "assets" / "site.js").write_text("window.SITE = {};\n", encoding="utf-8")
    code, out = run("validate.py", site_flat, "--quiet")
    check("validate.py detects site.js out of sync", code == 1 and result_of(out).get("site_issues") == "1", out)
    code, out = run("scaffold.py", site_flat, "--sync")
    check("scaffold --sync regenerates", code == 0 and "generated=site.js,glossary.js" in out, out)

    # ---- scaffold + validate on the topic folder (pages/ layout, theme) --------------
    code, out = run("scaffold.py", topic, "--plan", tmp / "SITE_PLAN.md", "--with-styleguide")
    r = result_of(out)
    gl = topic / "pages" / "glossary.html"
    kinds = [topic / "pages" / k for k in ("_skeleton.html", "_module.html", "_synthesis.html", "_reference.html")]
    ok_layout = (topic / "index.html").exists() and gl.exists() and all(k.exists() for k in kinds) and (topic / "pages" / "styleguide.html").exists() \
        and all('../assets/style.css' in k.read_text(encoding="utf-8") and 'src="../assets/app.js"' in k.read_text(encoding="utf-8") for k in kinds if k.exists())
    gtext = gl.read_text(encoding="utf-8") if gl.exists() else ""
    itext = (topic / "index.html").read_text(encoding="utf-8")
    sj = topic / "assets" / "site.json"
    reg = json.loads(sj.read_text(encoding="utf-8"))
    check("scaffold pages/: files placed, includes rewritten",
          code == 0 and ok_layout and '../assets/style.css' in gtext and 'src="../assets/app.js"' in gtext and 'href="pages/glossary.html"' in itext
          and reg.get("pagesDir") == "pages/", out)
    check("scaffold leaves PLAN.md, topic.json and tmp/ alone",
          (topic / "PLAN.md").read_text(encoding="utf-8") == plan_text and (topic / "topic.json").read_text(encoding="utf-8") == (TOPIC / "topic.json").read_text(encoding="utf-8")
          and sorted(p.name for p in tmp.iterdir()) == sorted(p.name for p in TMP.iterdir()) and not (topic / "tmp" / "assets").exists())
    check("scaffold --plan writes site.json theme from the Theme line",
          reg.get("theme") == {"accent": "#0b7a5c", "accentSoft": "#dff3ec", "dark": {"accent": "#5ad1a8", "accentSoft": "#0f2b23"}}, json.dumps(reg.get("theme")))
    if ref_page:
        m01 = re.sub(r'(href|src)="assets/', r'\1="../assets/', ref_page.read_text(encoding="utf-8"))
        (topic / "pages" / "m01-introduction.html").write_text(m01, encoding="utf-8")
    reg["pages"].insert(2, {"file": "styleguide.html", "num": "SG", "title": "Component Style Guide", "group": "Reference", "desc": "Every component once."})
    if not ref_page:
        reg["pages"] = [p for p in reg["pages"] if p["file"] != "m01-introduction.html"]
    sj.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run("scaffold.py", topic, "--sync")
    code, out = run("validate.py", topic)
    r = result_of(out)
    print("      --- validate.py (topic folder, pages/) ---\n      " + out.strip().replace("\n", "\n      "))
    if ref_page:
        check("validate.py pages/: index, glossary, styleguide clean; m01 broken links + missing trust footer only",
              r.get("site_issues") == "0" and r.get("bad_pages") == "1" and "pages/m01-introduction.html:" in out and r.get("pages") == str(4 + len(AUTO_PAGES)), out)
    else:
        check("validate.py pages/: index, glossary, styleguide clean", code == 0 and r.get("site_issues") == "0" and r.get("pages") == str(3 + len(AUTO_PAGES)), out)

    # ---- page-kind skeleton + the first feature batch (trust footer, exercises, step-through diagrams) ----
    kind = (topic / "pages" / "_module.html").read_text(encoding="utf-8")
    step_fig = '''<figure class="diagram" id="fig-steps" data-steps data-cite="#ref-key">
      <svg viewBox="0 0 600 200" role="img" aria-labelledby="fig-steps-t"><title id="fig-steps-t">Predict–update cycle</title>
        <rect class="d-box" x="20" y="60" width="160" height="80" rx="8"/><text class="d-text b" x="100" y="105" text-anchor="middle">Predict</text>
        <g data-step="1"><path class="d-data" d="M180 100 H300" marker-end="url(#arr-data)"/></g>
        <g data-step="2"><rect class="d-box accent" x="300" y="60" width="160" height="80" rx="8"/><text class="d-text b" x="380" y="105" text-anchor="middle">Update</text></g>
        <g data-step="3"><path class="d-ctrl d-dash" d="M380 140 V180 H100 V140" marker-end="url(#arr-ctrl)"/></g>
      </svg>
      <ol class="diagram-steps"><li>Prediction propagates the state.</li><li>The measurement update corrects it.</li><li>The loop repeats every sample.</li></ol>
      <figcaption><b>Figure 2.1 — Predict–update cycle.</b> Step through it.</figcaption>
    </figure>'''
    m02 = mutate(kind, 'data-page="mNN-slug.html"', 'data-page="m02-kinds.html"')
    m02 = mutate(m02, '<a href="m01-slug.html">M01</a>', '<a href="glossary.html">Glossary</a>')
    m02 = mutate(m02, '<h2 id="introduction">Conceptual introduction</h2>\n    <p>…</p>', '<h2 id="introduction">Conceptual introduction</h2>\n    <p>…</p>\n    ' + step_fig)
    page_m02 = topic / "pages" / "m02-kinds.html"
    page_m02.write_text(m02, encoding="utf-8")
    reg["pages"].append({"file": "m02-kinds.html", "num": "02", "title": "Kind skeleton test", "group": "Foundations", "level": 1, "desc": "A module page built from _module.html."})
    sj.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run("scaffold.py", topic, "--sync")
    code, out = run("validate.py", topic, "--pages", "m02-kinds.html")
    check("validate.py: _module.html page with trust footer + exercise + step diagram PASS", code == 0 and result_of(out).get("bad_pages") == "0", out)

    def expect_fail(name: str, text: str, msg: str) -> None:
        page_m02.write_text(text, encoding="utf-8")
        c, o = run("validate.py", topic, "--pages", "m02-kinds.html")
        check(name, c == 1 and msg in o, o)

    expect_fail("validate.py: missing trust footer FAIL", mutate(m02, '<section class="trust"', '<section class="provenance"'), "page has no trust footer (components/trust/trust-footer.html)")
    expect_fail("validate.py: trust data-reviewed not a date FAIL", mutate(m02, 'data-reviewed="2026-11-07"', 'data-reviewed="2026-13-40"'), "trust footer data-reviewed is not a date")
    expect_fail("validate.py: trust footer not last FAIL", mutate(m02, '</section>\n</main>', '</section>\n  <section><h2 id="after">After</h2><p>x</p></section>\n</main>'), "trust footer must be the last section")
    expect_fail("validate.py: solution open by default FAIL", mutate(m02, '<details class="solution">', '<details class="solution" open>'), "exercise ex-NN-1: solution open by default")
    expect_fail("validate.py: exercise without solution FAIL", mutate(m02, '<details class="solution">', '<details class="answer">'), "exercise ex-NN-1 has no solution")
    expect_fail("validate.py: step diagram with one layer FAIL", m02.replace('<g data-step="2">', '<g>').replace('<g data-step="3">', '<g>'), "step diagram fig-steps has fewer than 2 data-step layers")
    expect_fail("validate.py: step captions mismatch FAIL", mutate(m02, '<li>The loop repeats every sample.</li>', ''), "step diagram fig-steps: 2 captions for 3 steps")
    page_m02.write_text(m02, encoding="utf-8")
    # theme validation
    bad_reg = dict(reg)
    bad_reg["theme"] = {"accent": "blue", "dark": {"accentSoft": "#12"}}
    sj.write_text(json.dumps(bad_reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run("scaffold.py", topic, "--sync")
    code, out = run("validate.py", topic)
    check("validate.py rejects non-hex theme colours", code == 1 and "theme.accent must be a CSS hex colour" in out and "theme.dark.accentSoft must be a CSS hex colour" in out
          and result_of(out).get("site_issues") == "2", out)
    sj.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run("scaffold.py", topic, "--sync")
    # a page at the root of a pages/ site is an error; wrong include depth is reported
    stray = topic / "stray.html"
    stray.write_text(gtext.replace('data-page="glossary.html"', 'data-page="stray.html"'), encoding="utf-8")
    code, out = run("validate.py", topic)
    check("validate.py pages/: stray root page reported", code == 1 and "stray.html must live under pages/" in out and result_of(out).get("site_issues") == "1", out)
    stray.unlink()
    wrong = topic / "pages" / "glossary.html"
    wrong.write_text(gtext.replace("../assets/", "assets/"), encoding="utf-8")
    code, out = run("validate.py", topic, "--pages", "glossary.html")
    check("validate.py pages/: wrong include depth reported", code == 1 and "missing include ../assets/style.css" in out, out)
    wrong.write_text(gtext, encoding="utf-8")
    # app.js applies the theme (static check: the hook exists and node parses the file)
    app = (PLUGIN / "skills" / "compose" / "template" / "assets" / "app.js").read_text(encoding="utf-8")
    check("app.js has the theme hook", "applyTheme()" in app and "'--accent-soft'" in app and app.index("applyTheme();") < app.index("function toggleTheme"))
    check("app.js wires enhanceSteps, enhanceExercises and buildTrust in init()",
          all(f"function {fn}(main)" in app and f"{fn}(main);" in app for fn in ("enhanceSteps", "enhanceExercises", "buildTrust"))
          and app.index("enhanceDiagrams(main);") < app.index("enhanceSteps(main);") < app.index("enhanceChecklists(main);")
          < app.index("enhanceExercises(main);") < app.index("buildTrust(main);") < app.index("buildFooter(main);"))

    # ---- single format: scaffold into tmp/site, validate, bundle ---------------------
    tpl = WORK / "template"
    shutil.copytree(PLUGIN / "skills" / "compose" / "template", tpl)
    stub_note = ""
    if not (tpl / "_single.html").exists():
        (tpl / "_single.html").write_text("<!doctype html><title>stub</title>\n", encoding="utf-8")
        stub_note = " (stub _single.html: the template has none yet)"
    s_topic = WORK / "single" / "topics" / "map-one"
    s_site = s_topic / "tmp" / "site"
    code, out = run("scaffold.py", s_site, "--plan", FIX / "single" / "SITE_PLAN.md", "--template", tpl)
    sj_single = s_site / "assets" / "site.json"
    sreg = json.loads(sj_single.read_text(encoding="utf-8")) if sj_single.exists() else {}
    check("scaffold single into tmp/site: assets + _single.html only, site.json mode single" + stub_note,
          code == 0 and (s_site / "assets" / "style.css").exists() and (s_site / "assets" / "app.js").exists() and (s_site / "_single.html").exists()
          and not (s_site / "glossary.html").exists() and not (s_site / "index.html").exists() and not (s_site / "_module.html").exists()
          and not (s_site / "pages").exists() and sreg.get("mode") == "single" and sreg.get("pagesDir") == "" and sreg.get("budgetKb") == 250
          and len(sreg.get("pages", [])) == 1 and "write index.html from _single.html" in out, out)
    tpl_none = WORK / "template-none"
    shutil.copytree(tpl, tpl_none)
    (tpl_none / "_single.html").unlink()
    code, out = run("scaffold.py", WORK / "single-none", "--plan", FIX / "single" / "SITE_PLAN.md", "--template", tpl_none)
    check("scaffold single without _single.html in the template FAIL", code == 1 and "template has no _single.html" in out, out)
    spage = (FIX / "single" / "index.html").read_text(encoding="utf-8")
    (s_site / "index.html").write_text(spage, encoding="utf-8")
    (s_site / "assets" / "glossary.json").write_text(json.dumps([{"term": "Scale factor", "def": "How much a map stretches distances at a point.",
                                                                  "page": "index.html", "anchor": "m01-scale"}], indent=2) + "\n", encoding="utf-8")
    run("scaffold.py", s_site, "--sync")
    code, out = run("validate.py", s_site)
    r = result_of(out)
    check("validate single: the §1 page PASS with mode=single", code == 0 and r.get("mode") == "single" and r.get("pages") == "1" and r.get("bad_pages") == "0", out)
    code, out = run("validate.py", topic, "--pages", "index.html", "--quiet")
    check("validate site mode reports mode=site", result_of(out).get("mode") == "site", out)

    def single_fail(name: str, text: str, msg: str) -> None:
        (s_site / "index.html").write_text(text, encoding="utf-8")
        c, o = run("validate.py", s_site)
        check(name, c == 1 and msg in o, o)

    single_fail("validate single: missing #summary FAIL", mutate(spage, 'id="summary"', 'id="overview"'), "single page lacks #summary")
    single_fail("validate single: part without data-part FAIL", mutate(spage, '<section class="part" data-part="M02">', '<section class="part">'), "part section without a valid data-part")
    single_fail("validate single: part without h2 id FAIL", mutate(spage, '<h2 id="m02-choosing">', '<h2>'), "part M02 has no h2 id")
    single_fail("validate single: missing trust footer FAIL", mutate(spage, '<section class="trust"', '<section class="provenance"'), "page has no trust footer")
    single_fail("validate single: missing glossary widget FAIL", mutate(spage, ' data-glossary>', '>'), "single page has no data-glossary widget")
    (s_site / "index.html").write_text(spage, encoding="utf-8")
    (s_site / "other.html").write_text(spage.replace('data-page="index.html"', 'data-page="other.html"'), encoding="utf-8")
    code, out = run("validate.py", s_site)
    check("validate single: a second page FAIL", code == 1 and "single mode: other.html is not allowed (one page only)" in out, out)
    (s_site / "other.html").unlink()
    sreg_small = dict(sreg, budgetKb=1)
    sj_single.write_text(json.dumps(sreg_small, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run("scaffold.py", s_site, "--sync")
    code, out = run("validate.py", s_site)
    check("validate single: over-budget page is a warning, not a FAIL", code == 0 and re.search(r"warning: single page is \d+ KB, over the 1 KB budget", out) is not None, out)
    sj_single.write_text(json.dumps(sreg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run("scaffold.py", s_site, "--sync")
    bundle_out = s_topic / "index.html"
    code, out = run("bundle.py", s_site, "--out", bundle_out)
    r = result_of(out)
    btxt = bundle_out.read_text(encoding="utf-8") if bundle_out.exists() else ""
    bare = re.sub(r"<!--[\s\S]*?-->", "", btxt)
    check("bundle: one self-contained file (5 includes inlined, CDN kept, comments untouched)",
          code == 0 and r.get("status") == "PASS" and r.get("inlined") == "5" and "<style>" in btxt and "window.QC = " in btxt and "window.SITE = " in btxt
          and "window.QC_GLOSSARY = " in btxt and "window.QC_DATA = " in btxt and not re.search(r'(src|href)="(\./)?assets/', bare) and "atlaspedia single-page bundle" in btxt
          and "katex.min.js" in btxt and '<script src="assets/app.js"></script> -->' in btxt, out)
    node = shutil.which("node")
    if node:
        blocks = re.findall(r"<script>([\s\S]*?)</script>", bare)
        errs = []
        for i, b in enumerate(blocks):
            f = WORK / f"bundle-block-{i}.js"
            f.write_text(b, encoding="utf-8")
            p = subprocess.run([node, "--check", str(f)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if p.returncode:
                errs.append(f"block {i}: {(p.stderr or '')[:300]}")
        check(f"bundle: node --check passes on every inline script ({len(blocks)})", len(blocks) >= 4 and not errs, "\n".join(errs))
    else:
        print("      (bundle inline-script syntax check skipped: node not on PATH)")
    code, out = run("bundle.py", s_site, "--out", s_site / "bundle.html")
    check("bundle: --out inside the site folder refused", code == 1 and "--out is inside the site folder" in out and not (s_site / "bundle.html").exists(), out)

    # ---- build_index ----------------------------------------------------------------
    tj = repo / "topics" / "map-projections" / "topic.json"
    tjd = json.loads(tj.read_text(encoding="utf-8"))
    tjd["format"] = "single"
    tj.write_text(json.dumps(tjd, indent=2) + "\n", encoding="utf-8")
    code, out = run("build_index.py", repo, "--template", FIX / "template" / "root-index.html")
    r = result_of(out)
    html_text = (repo / "index.html").read_text(encoding="utf-8") if (repo / "index.html").exists() else ""
    dm = re.search(r'<script id="topics-data" type="application/json">([\s\S]*?)</script>', html_text)
    idx = json.loads(dm.group(1)) if dm else {}
    codes = [t["code"] for t in idx.get("topics", [])]
    check("build_index: valid topics listed, sorted by updated desc, bad topic reported and skipped",
          code == 0 and r.get("status") == "PASS" and r.get("topics") == "2" and codes == ["map-projections", "old-notes"] and r.get("skipped") == "bad-topic"
          and re.search(r"bad-topic[/\\]topic\.json:\d+ warning: status \"cooking\"", out) is not None, out)
    kd = next((t for t in idx.get("topics", []) if t.get("code") == "map-projections"), {})
    check("build_index carries topic.json fields into the dictionary data", kd.get("format") == "single" and "is not a topic.json field" not in out, out)
    check("build_index: one self-contained index.html (data inline, no sidecar files) and copied when absent",
          not (repo / "index.js").exists() and not (repo / "index.json").exists() and dm is not None
          and "Fixture dictionary" in html_text and r.get("written") == "index.html", out)
    (repo / "index.html").write_text("<!doctype html><title>custom</title>", encoding="utf-8")
    code, out = run("build_index.py", repo, "--template", FIX / "template" / "root-index.html")
    h2 = (repo / "index.html").read_text(encoding="utf-8")
    dm2 = re.search(r'<script id="topics-data" type="application/json">([\s\S]*?)</script>', h2)
    check("build_index: custom index.html keeps its markup, data block injected without --force",
          code == 0 and "custom" in h2 and dm2 is not None and json.loads(dm2.group(1)) == idx
          and result_of(out).get("written") == "index.html", out)
    code, out = run("build_index.py", repo, "--force", "--template", FIX / "template" / "root-index.html")
    check("build_index: --force replaces index.html", code == 0 and "Fixture dictionary" in (repo / "index.html").read_text(encoding="utf-8"), out)
    (repo / "index.html").unlink()
    code, out = run("build_index.py", repo, "--template", WORK / "no-such-template.html")
    check("build_index: missing template is a warning, nothing written", code == 0 and "dictionary template missing" in out and result_of(out).get("status") == "PASS"
          and result_of(out).get("written") == "none" and not (repo / "index.html").exists(), out)
    code, out = run("build_index.py", WORK / "links")
    check("build_index: no topics/ folder is a usage error", code == 2, out)

    # ---- component catalog ------------------------------------------------------------
    code, out = run("check_components.py")
    r = result_of(out)
    n_modules = len([d for d in (PLUGIN / "skills" / "compose" / "components").iterdir() if d.is_dir()])
    check(f"check_components PASS: {n_modules} modules (one per catalog folder), every snippet class known, style guide validates",
          code == 0 and r.get("status") == "PASS" and r.get("modules") == str(n_modules) and n_modules >= 9 and r.get("classes_missing") == "0", out)
    code, out = run("check_components.py", "--styleguide")
    check("check_components --styleguide: template/styleguide.html is in sync with the catalog (regenerate it after editing a snippet)",
          code == 0 and result_of(out).get("styleguide") == "unchanged", out)

    # ---- build_site_data: data.js from the pages/ topic ------------------------------
    code, out = run("build_site_data.py", topic)
    r = result_of(out)
    dj = topic / "assets" / "data.js"
    check("build_site_data: writes assets/data.js with a generated stamp, PASS, every builder ran",
          code == 0 and r.get("status") == "PASS" and r.get("pages") == str(4 + len(AUTO_PAGES) + (1 if ref_page else 0)) and dj.exists()
          and dj.read_text(encoding="utf-8").startswith("/* Site data") and '"generated"' in dj.read_text(encoding="utf-8"), out)

    # ---- feature tests (one block per workstream, registered with @feature_test) -------
    from types import SimpleNamespace
    t = SimpleNamespace(run=run, check=check, mutate=mutate, line_no=line_no, result_of=result_of, WORK=WORK, PLUGIN=PLUGIN, SCRIPTS=SCRIPTS,
                        TEMPLATE=TEMPLATE, FIX=FIX, repo=repo, topic=topic, tmp=tmp, plan=plan, sj=sj, reg=reg, kind=kind, m02=m02, page_m02=page_m02,
                        ref_page=ref_page, s_site=s_site, spage=spage, sj_single=sj_single, sreg=sreg, bundle_out=bundle_out, tpl=tpl, node=node,
                        AUTO_PAGES=AUTO_PAGES, sync=lambda: run("scaffold.py", topic, "--sync"))
    for fn in FEATURE_TESTS:
        print(f"---- {fn.__name__} ----")
        try:
            fn(t)
        except Exception as e:  # noqa: BLE001 — a broken feature test must show as a failure, not stop the run
            check(f"{fn.__name__} raised {type(e).__name__}", False, str(e))
        # every feature test leaves the shared sites as it found them
        page_m02.write_text(m02, encoding="utf-8")
        sj.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        run("scaffold.py", topic, "--sync")
        (s_site / "index.html").write_text(spage, encoding="utf-8")
        sj_single.write_text(json.dumps(sreg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        run("scaffold.py", s_site, "--sync")

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{len(results) - n_fail}/{len(results)} checks passed")
    return 1 if n_fail else 0


# ==== BLOCK nav — A2 section metadata · A4 breadcrumb and keyboard shortcuts · F2 reading settings · F3 bilingual glossary · H3 automatic glossary links ====
@feature_test
def nav_features(t) -> None:
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    # ---- static: the five features are registered, the markup names of the plan are in the runtime and the stylesheet
    for name in ("a2-section-meta", "a4-breadcrumb-shortcuts", "f2-reading-settings", "f3-bilingual-glossary", "h3-glossary-links"):
        t.check(f"nav: app.js registers feature {name}", f"feature({{ name: '{name}'" in app)
    t.check("nav: A4 help lists every shortcut and the breadcrumb/dialog markup names exist",
            all(x in app for x in ("['j', ", "['k', ", "['n', ", "['p', ", "['t', ", "['?', ", "['Esc'", "['/', ", "'Escape'"))
            and "class: 'breadcrumb'" in app and "class: 'kbd-help'" in app and "'aria-label': 'Breadcrumb'" in app)
    t.check("nav: F2 loads Atkinson Hyperlegible on demand, sets the root attributes, persists under nav:settings, reads SITE.a11y",
            "Atkinson+Hyperlegible" in app and all(a in app for a in ("'data-font-scale'", "'data-measure'", "'data-font'", "'data-motion'", "'data-contrast'"))
            and "'nav:settings'" in app and "SITE.a11y" in app and "settings-toggle" in app and "class: 'reading-settings'" in app and "prefers-reduced-motion" in app)
    t.check("nav: F3 augments .gl-row dt with span.gl-local and the search indexes term_local",
            "class: 'gl-local'" in app and "'.glossary-inline .gl-row > dt'" in app and "(g.term_local || '')" in app and "SITE.secondLanguage" in app)
    t.check("nav: H3 walks text nodes with a TreeWalker, caps terms and wraps, honours the opt-outs",
            "createTreeWalker" in app and "data-no-glossary-links" in app and ".no-gloss" in app and "H3_MAX_TERMS = 400" in app and "H3_MAX_WRAPS = 200" in app
            and "class: 'gloss'" in app and "class: 'gloss-tip'" in app and "innerHTML.replace" not in app.split("BLOCK nav")[1].split("END nav")[0])
    t.check("nav: style.css has the nav block classes and root attributes",
            all(c in css for c in (".section-meta", ".breadcrumb", ".kbd-help", ".reading-settings", ".settings-toggle", ".gl-local", "abbr.gloss", ".gloss-tip",
                                   '[data-font="dyslexic"]', '[data-contrast="high"]', '[data-motion="reduced"]', '[data-measure="narrow"]', "[data-font-scale]")))
    gh = (t.TEMPLATE / "glossary.html").read_text(encoding="utf-8")
    t.check("nav: template glossary.html renders the term_local column from site.json secondLanguage", "term_local" in gh and "secondLanguage" in gh and "def_local" in gh and "gl-local-col" in gh)
    snip = t.PLUGIN / "skills" / "compose" / "components" / "core" / "section-meta.html"
    t.check("nav: core/section-meta.html snippet exists with the header line and the four attributes",
            snip.exists() and snip.read_text(encoding="utf-8").startswith("<!-- atlaspedia component: core/section-meta.html ·")
            and all(a in snip.read_text(encoding="utf-8") for a in ("data-prereq=", "data-related=", "data-time=", "data-reviewed=")))

    # ---- A2 validator on the module page: resolvable targets PASS, each broken contract its message
    meta_h2 = '<h2 id="introduction" data-prereq="../index.html#deliverables, glossary.html#terms" data-related="#mistakes" data-time="8 min" data-reviewed="2026-11-07">Conceptual introduction</h2>'
    page = t.mutate(t.m02, '<h2 id="introduction">Conceptual introduction</h2>', meta_h2)
    t.page_m02.write_text(page, encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("nav: A2 h2 with resolvable data-prereq/data-related and a dated data-reviewed PASS", code == 0 and t.result_of(out).get("bad_pages") == "0" and "section meta" not in out, out)

    def fail(name: str, text: str, msg: str) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        ln = t.line_no(text, "Conceptual introduction</h2>")
        t.check(name + f" (line {ln})", c == 1 and f":{ln} {msg}" in o, o)

    fail("nav: A2 prerequisite page missing FAIL", t.mutate(page, "../index.html#deliverables", "m09-nope.html#x"), "section meta: prerequisite m09-nope.html#x not found")
    fail("nav: A2 prerequisite anchor missing FAIL", t.mutate(page, "glossary.html#terms", "glossary.html#nope"), "section meta: prerequisite glossary.html#nope not found")
    fail("nav: A2 related anchor missing FAIL", t.mutate(page, 'data-related="#mistakes"', 'data-related="#no-such-section"'), "section meta: related #no-such-section not found")
    fail("nav: A2 data-reviewed not a date FAIL", t.mutate(page, 'data-reviewed="2026-11-07">Conceptual', 'data-reviewed="2026-13-40">Conceptual'), 'section meta: data-reviewed "2026-13-40" is not a date')
    warn_page = t.mutate(page, '<h2 id="mistakes">Common engineering mistakes</h2>', '<h2 id="mistakes">Common engineering mistakes</h2>\n    <h3 data-prereq="#introduction">Sub-topic</h3>')
    t.page_m02.write_text(warn_page, encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("nav: A2 data-prereq on an h3 is a warning, not a FAIL", code == 0 and "warning: section meta: data-prereq on <h3> is ignored (h2 only)" in out, out)
    t.page_m02.write_text(page, encoding="utf-8")

    # ---- F3 validator (site check): shape errors and the secondLanguage ↔ term_local pairing warnings
    gj = t.topic / "assets" / "glossary.json"
    gj_orig = gj.read_text(encoding="utf-8")
    entries = [{"term": "Scale factor", "term_local": "Hệ số tỷ lệ", "def": "How much a map stretches distances at a point.",
                "def_local": "Mức độ bản đồ kéo giãn khoảng cách tại một điểm.", "page": "m02-kinds.html", "anchor": "introduction"},
               {"term": "Graticule", "def": "The grid of meridians and parallels drawn on a map.", "page": "m02-kinds.html"}]

    def site_case(name: str, glossary: list, second, want_code: int, needle: str, absent: str = "") -> None:
        reg2 = dict(t.reg)
        if second is not None:
            reg2["secondLanguage"] = second
        t.sj.write_text(json.dumps(reg2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        gj.write_text(json.dumps(glossary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        t.sync()
        c, o = t.run("validate.py", t.topic, "--pages", "glossary.html")
        t.check(name, c == want_code and (not needle or needle in o) and (not absent or absent not in o), o)

    try:
        site_case("nav: F3 term_local + secondLanguage PASS with no warning and bilingual=1 in RESULT", entries, "Vietnamese", 0, "bilingual=1", "warning: secondLanguage")
        bad = [dict(entries[0], term_local=3), dict(entries[1], def_local=["x"])]
        site_case("nav: F3 term_local / def_local not strings FAIL", bad, "Vietnamese", 1, 'glossary term "Scale factor": term_local must be a string')
        _, o = t.run("validate.py", t.topic, "--pages", "glossary.html")
        t.check("nav: F3 def_local not a string FAIL (second entry)", 'glossary term "Graticule": def_local must be a string' in o and t.result_of(o).get("site_issues") == "2", o)
        site_case("nav: F3 secondLanguage without any term_local is a warning", [entries[1]], "Vietnamese", 0, 'warning: secondLanguage "Vietnamese" is set but no glossary entry has term_local')
        site_case("nav: F3 term_local without secondLanguage is a warning", entries, None, 0, "warning: 1 glossary entry has term_local but site.json has no secondLanguage")
        site_case("nav: F3 secondLanguage not a string FAIL", entries, 7, 1, "site.json secondLanguage must be a non-empty string")
    finally:
        gj.write_text(gj_orig, encoding="utf-8")
        t.sj.write_text(json.dumps(t.reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        t.sync()

    # ---- scaffold: `**Second language**: <name>` in the SITE_PLAN header → site.json secondLanguage
    plan2 = t.WORK / "SITE_PLAN_nav.md"
    plan2.write_text(t.mutate((t.tmp / "SITE_PLAN.md").read_text(encoding="utf-8"), "**Status**: Draft", "**Second language**: Vietnamese\n**Status**: Draft"), encoding="utf-8")
    code, out = t.run("scaffold.py", t.WORK / "site-nav", "--plan", plan2)
    sj2 = t.WORK / "site-nav" / "assets" / "site.json"
    reg2 = json.loads(sj2.read_text(encoding="utf-8")) if sj2.exists() else {}
    t.check("nav: scaffold writes site.json secondLanguage from the Second language header line", code == 0 and reg2.get("secondLanguage") == "Vietnamese", out)

# ==== END nav ====



# ==== BLOCK learn — B3 instructor and handout modes · B5 Bloom tags and outcome matrix · B6 predict-then-reveal · B7 lab template ====
LEARN_OBJECTIVES = '''<ol class="objectives">
      <li data-bloom="remember">State the four atlaspedia stages.</li>
      <li data-bloom="understand">Explain why writers have no web tools.</li>
      <li data-bloom="apply">Compute the single-page budget.</li>
      <li data-bloom="analyze">Trace a number to its cited source.</li>
      <li data-bloom="create">Write a plan that passes check_plan.py.</li>
    </ol>'''
LEARN_SECTION = '''  <section>
    <h2 id="learning-features">Learning features</h2>
    <div class="instructor"><span class="callout-title">Instructor note</span><p>Run the budget demo before the formula.</p>
      <table class="rubric"><thead><tr><th>Criterion</th><th>2</th><th>1</th></tr></thead><tbody><tr><td>Arithmetic</td><td>Frame subtracted</td><td>One slip</td></tr></tbody></table></div>
    <details class="instructor"><summary>Instructor note — misconceptions</summary><p>Students read "verified" as "true".</p></details>
    <div class="outcomes" data-outcomes></div>
    <div class="outcomes" data-outcomes="site"></div>
    <div class="demo" id="demo-budget" data-cite="#ref-key"><div class="demo-head"><h4>Budget</h4><span class="badge illustrative">Illustrative</span></div>
      <div class="demo-body"><div class="demo-controls"><div class="ctl"><label for="t-parts">Parts</label><output for="t-parts"></output><input type="range" id="t-parts" min="1" max="16" value="7"></div></div>
      <div class="demo-output"><div class="readouts"><div class="readout"><div class="r-label">Size</div><div class="r-val" id="t-size">—</div></div></div></div></div></div>
    <div class="predict" data-demo="demo-budget" data-preset="over" data-answer="1" data-bloom="apply" data-objective="3">
      <p class="q">With 9 parts of 40 KB, does the page fit?</p>
      <ol class="opts"><li>Yes.</li><li>No — 150 KB over.</li><li>Only the allowance changes.</li></ol>
      <div class="explain">9 × 40 + 40 = 400 KB.</div>
    </div>
    <section class="lab" id="lab-budget" data-duration="45 min" data-bloom="apply" data-objective="3">
      <div class="lab-head"><h3>Measure a topic's size budget</h3><span class="badge neutral">Level 1</span></div>
      <p class="lab-aim">Estimate, build, compare.</p>
      <ol class="steps"><li>Run estimate_size.py.</li><li>Compose the page.</li></ol>
      <ul class="checklist" data-key="lab-budget-preflight"><li>Research row is [x].</li><li>node is on PATH.</li></ul>
      <table class="lab-record"><thead><tr><th>Quantity</th><th>Value</th></tr></thead><tbody><tr><td>Estimated size</td><td></td></tr></tbody></table>
      <div class="lab-report"><p>The filled table.</p></div>
      <details class="lab-answer"><summary>Expected results</summary><p>Within about a quarter of the estimate.</p></details>
    </section>
  </section>
'''


@feature_test
def learn_features(t):
    """B3 instructor/handout · B5 Bloom + outcome matrix · B6 predict · B7 lab: one valid page, then grouped broken variants."""
    page = t.mutate(t.m02, '<ol class="objectives">\n      <li>…</li>\n      <li>…</li>\n    </ol>', LEARN_OBJECTIVES)
    page = t.mutate(page, '<div class="quiz" data-answer="0">', '<div class="quiz" data-answer="0" data-bloom="understand" data-objective="1,2">')
    page = t.mutate(page, '<div class="exercise" id="ex-NN-1" data-difficulty="2">', '<div class="exercise" id="ex-NN-1" data-difficulty="2" data-bloom="analyze" data-objective="4">')
    page = t.mutate(page, '  <section>\n    <h2 id="mistakes">', LEARN_SECTION + '  <section>\n    <h2 id="mistakes">')
    t.page_m02.write_text(page, encoding="utf-8")
    c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("learn: module page with instructor notes, rubric, Bloom tags, outcome matrices, predict block and lab PASS",
            c == 0 and t.result_of(o).get("bad_pages") == "0" and t.result_of(o).get("js_syntax") == "checked", o)

    def fails(name: str, text: str, *msgs: str) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        cc, oo = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        for msg in msgs:
            t.check(f"learn: {name} FAIL → {msg}", cc == 1 and msg in oo, oo)

    # B3 + B5 in one variant (independent errors)
    v = t.mutate(page, '<thead><tr><th>Criterion</th><th>2</th><th>1</th></tr></thead>', '')
    v = t.mutate(v, 'data-bloom="create"', 'data-bloom="invent"')
    v = t.mutate(v, 'data-objective="1,2"', 'data-objective="1,9"')
    v = t.mutate(v, 'data-objective="4"', 'data-objective="four"')
    v = t.mutate(v, '<div class="outcomes" data-outcomes></div>', '<div class="outcomes" data-outcomes="#no-such-list"></div>')
    fails("rubric without thead, bad Bloom level, objective out of range, malformed objective, matrix naming a missing list", v,
          "table.rubric has no thead", 'data-bloom "invent" is not a Bloom level',
          "data-objective 9 but the page has 5 objectives", 'data-objective "four" is not a list of objective numbers', "outcome matrix names missing list #no-such-list")
    # an instructor div holding only its title, an instructor details holding only its summary, a matrix on a page without objectives
    div_start, div_end = page.index('<div class="instructor">'), page.index('</table></div>') + len('</table></div>')
    v = page[:div_start] + '<div class="instructor"><span class="callout-title">Instructor note</span></div>' + page[div_end:]
    v = t.mutate(v, '<p>Students read "verified" as "true".</p>', '')
    v = t.mutate(v, LEARN_OBJECTIVES, '<p>No objectives list.</p>')
    fails("empty instructor div and details, matrix without any objectives list", v, "instructor block is empty", "outcome matrix but the page has no ol.objectives", "data-objective 1 but the page has 0 objectives")
    t.check("learn: both empty instructor blocks are reported (div with only its title, details with only its summary)",
            v.count('class="instructor"') == 2 and t.run("validate.py", t.topic, "--pages", "m02-kinds.html")[1].count("instructor block is empty") == 2)
    # B6: four predict blocks, each broken differently
    bad_predicts = ('<div class="predict" data-demo="demo-budget" data-preset="over"><p class="q">No answer?</p><ol class="opts"><li>a</li><li>b</li></ol><div class="explain">x</div></div>\n'
                    '    <div class="predict" data-demo="demo-budget" data-answer="3"><p class="q">Out of range?</p><ol class="opts"><li>a</li><li>b</li></ol><div class="explain">x</div></div>\n'
                    '    <div class="predict" data-demo="demo-nowhere" data-answer="0"><p class="q">Missing demo?</p><ol class="opts"><li>a</li><li>b</li></ol><div class="explain">x</div></div>\n'
                    '    <div class="predict" data-answer="0"><p class="q">No demo?</p><ol class="opts"><li>a</li><li>b</li></ol><div class="explain">x</div></div>\n')
    v = t.mutate(page, '    <section class="lab" id="lab-budget"', '    ' + bad_predicts + '    <section class="lab" id="lab-budget"')
    fails("predict blocks without data-answer, out of range, missing demo, without data-demo", v,
          "predict block without data-answer", "predict data-answer=3 out of range (2 options)", "predict block targets missing demo demo-nowhere", "predict block without data-demo")
    # B7: five lab sections, each broken differently
    lab_ok = page[page.index('    <section class="lab" id="lab-budget"'):page.index('    </section>\n  </section>\n  <section>\n    <h2 id="mistakes">') + len('    </section>\n')]
    labs = [t.mutate(lab_ok, ' id="lab-budget"', '').replace('lab-budget-preflight', 'lab-noid-preflight'),
            t.mutate(lab_ok, 'id="lab-budget"', 'id="lab-nosteps"').replace('<ol class="steps">', '<ol class="procedure">').replace('lab-budget-preflight', 'lab-nosteps-preflight'),
            t.mutate(lab_ok, 'id="lab-budget"', 'id="lab-nolist"').replace('<ul class="checklist" data-key="lab-budget-preflight">', '<ul class="todo">'),
            t.mutate(lab_ok, 'id="lab-budget"', 'id="lab-nokey"').replace(' data-key="lab-budget-preflight"', ''),
            t.mutate(lab_ok, 'id="lab-budget"', 'id="lab-open"').replace('<details class="lab-answer">', '<details class="lab-answer" open>').replace('lab-budget-preflight', 'lab-open-preflight')]
    v = page.replace(lab_ok, "".join(labs))
    fails("labs without id, steps, checklist, data-key, with an open answer", v,
          "lab section without id", "lab lab-nosteps has no steps", "lab lab-nolist has no checklist", "lab lab-nokey: checklist without data-key", "lab lab-open: answer open by default")
    t.page_m02.write_text(page, encoding="utf-8")
    # the runtime and the stylesheet carry the four features; data.js builds on a tagged page (no learn key: the site matrix reads manifest.pages[].bloom)
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    t.check("learn: app.js registers learn-modes (shell), learn-bloom, learn-predict and learn-lab (enhance) and exposes QC.setMode/getMode/printHandout",
            all(f"name: '{n}', phase: '{ph}'" in app for n, ph in (("learn-modes", "shell"), ("learn-bloom", "enhance"), ("learn-predict", "enhance"), ("learn-lab", "enhance")))
            and "api: { getMode:" in app and "setMode:" in app and "printHandout }" in app)
    t.check("learn: app.js guards the optional contracts (QC.applyPreset may be missing, DATA.manifest may be missing, ?mode= forces one load)",
            "typeof fn !== 'function'" in app and "DATA.manifest && typeof DATA.manifest === 'object'" in app and "URLSearchParams(location.search).get('mode')" in app
            and "store.set('learn:mode', mode)" in app)
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    learn_css = re.search(r"BLOCK learn\b[^\n]*\n([\s\S]*?)/\* =+ END learn", css).group(1)   # the learn block of style.css, markers excluded
    t.check("learn: style.css block defines the mode rules and every learn class with variables only (no hex colours), plus print rules",
            all(x in learn_css for x in (':root:not([data-mode="instructor"]) .instructor', ':root[data-mode="handout"] details.solution', ".handout-head", ".mode-toggle",
                                         '.bloom[data-level="create"]', ".outcome-matrix", ".predict ol.opts button.correct", ".lab-head", "table.lab-record td:empty", "details.lab-answer", "@media print"))
            and not re.search(r"#[0-9a-fA-F]{3,8}\b", learn_css))
    c, o = t.run("build_site_data.py", t.topic)
    dj = (t.topic / "assets" / "data.js").read_text(encoding="utf-8") if (t.topic / "assets" / "data.js").exists() else ""
    t.check("learn: build_site_data PASS on the Bloom-tagged page and registers no learn key", c == 0 and t.result_of(o).get("status") == "PASS" and '"generated"' in dj and '"learn"' not in dj, o)
    sg = (t.TEMPLATE / "styleguide.html").read_text(encoding="utf-8") if (t.TEMPLATE / "styleguide.html").exists() else ""
    t.check("learn: the style guide renders instructor.html, bloom.html, predict.html and lab.html",
            all(x in sg for x in ('id="c-assessment-instructor"', 'id="c-assessment-bloom"', 'id="c-assessment-predict"', 'id="c-assessment-lab"', 'id="b7-lab-budget"', 'data-demo="demo-budget"')))
# ==== END learn ====



# ==== BLOCK scholar — B2 theorem blocks · E2 numbered equations · E3 notation tables · E1 citation export · C9 copy as LaTeX ====
@feature_test
def scholar(t) -> None:
    """B2 theorem blocks · E2 numbered equations · E3 notation tables, notation.json, the builder and the template page · E1 citation fields."""
    block = '''<div class="thm" data-kind="definition" id="thm-scale"><span class="thm-title">Scale factor</span><p>Ratio of a map distance to the globe distance.</p></div>
    <div class="thm" data-kind="theorem" id="thm-mercator"><p>On Mercator \\( k = \\sec\\varphi \\) in every direction.</p></div>
    <div class="thm" data-kind="proof"><p>Conformality forces equal stretch along the parallel and the meridian.</p></div>
    <div class="thm" data-kind="example" id="thm-greenland"><p>At 72° the factor is about 3.2.</p></div>
    <p>See <a class="thmref" href="#thm-mercator"></a> and <a class="eqref" href="#eq-forward"></a>.</p>
    <div class="eq" id="eq-forward">$$ x = R(\\lambda - \\lambda_0) $$</div>
    <div class="eq" id="eq-inverse" data-label="1a">$$ \\varphi = 2\\arctan e^{y/R} - \\pi/2 $$</div>
    <table class="notation" id="tbl-notation-m02"><thead><tr><th>Symbol</th><th>Meaning</th><th>Unit</th><th>Where defined</th></tr></thead>
    <tbody><tr><td class="sym">\\( \\lambda \\)</td><td>longitude</td><td>rad</td><td><a href="#eq-forward">eq. (1)</a></td></tr>
    <tr><td class="sym">\\( h \\)</td><td>scale factor along the meridian</td><td>—</td><td><a href="#thm-scale">Definition 1</a></td></tr></tbody></table>
    <table class="constants"><thead><tr><th>Constant</th><th>Symbol</th><th>Value</th><th>Unit</th><th>Source</th></tr></thead>
    <tbody><tr><td>Speed of light</td><td class="sym">\\( c \\)</td><td>299 792 458</td><td>m/s</td><td>CODATA 2018</td></tr></tbody></table>'''
    page = t.mutate(t.m02, '<h2 id="introduction">Conceptual introduction</h2>\n    <p>…</p>', '<h2 id="introduction">Conceptual introduction</h2>\n    <p>…</p>\n    ' + block)
    page = t.mutate(page, '<li id="ref-key">', '<li id="ref-key" data-type="article" data-authors="Snyder, J. P." data-year="1987" data-title="Map projections: a working manual" data-venue="USGS Professional Paper 1395" data-doi="10.3133/pp1395">')
    t.page_m02.write_text(page, encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("scholar: theorem blocks, numbered equations, notation tables and citation fields PASS", code == 0 and t.result_of(out).get("bad_pages") == "0", out)

    def expect(name: str, text: str, msg: str, warning: bool = False) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check(name, (c == 0 if warning else c == 1) and msg in o, o)

    expect("scholar: thm with an unknown data-kind FAIL", t.mutate(page, 'data-kind="example"', 'data-kind="exercise"'), 'thm thm-greenland data-kind "exercise" unknown')
    expect("scholar: proof containing another thm FAIL",
           t.mutate(page, '<p>Conformality forces equal stretch along the parallel and the meridian.</p></div>', '<p>Trivially,</p><div class="thm" data-kind="remark" id="thm-inside"><p>inside.</p></div></div>'),
           "thm #3 proof contains another thm block")
    expect("scholar: numbered thm without id is a warning", t.mutate(page, '<div class="thm" data-kind="example" id="thm-greenland">', '<div class="thm" data-kind="example">'), "thm #4 (example) has no id", warning=True)
    expect("scholar: eq id without the eq- prefix is a warning", t.mutate(page, 'id="eq-inverse"', 'id="inverse"'), 'eq id "inverse" should start with eq-', warning=True)
    expect("scholar: notation table without thead FAIL", t.mutate(page, '<thead><tr><th>Symbol</th><th>Meaning</th><th>Unit</th><th>Where defined</th></tr></thead>', ''), "notation table without thead")
    expect("scholar: notation row without td.sym FAIL", t.mutate(page, '<td class="sym">\\( h \\)</td>', '<td>\\( h \\)</td>'), "notation table row 2 without td.sym")
    expect("scholar: ref data-year not 4 digits FAIL", t.mutate(page, 'data-year="1987"', 'data-year="87"'), 'ref ref-key: data-year "87" is not a 4-digit year')
    expect("scholar: ref data-doi not a DOI FAIL", t.mutate(page, 'data-doi="10.3133/pp1395"', 'data-doi="pp1395"'), 'ref ref-key: data-doi "pp1395" is not a DOI')
    expect("scholar: ref data-type unknown FAIL", t.mutate(page, 'data-type="article"', 'data-type="blog"'), 'ref ref-key: data-type "blog" is not one of article|book|web')
    t.page_m02.write_text(page, encoding="utf-8")

    # site level: assets/notation.json shape, the conflicting-meaning warning, the builder's DATA.notation key
    nj = t.topic / "assets" / "notation.json"
    good = [{"symbol": "λ", "tex": "\\lambda", "meaning": "wavelength", "unit": "m", "kind": "symbol", "page": "m02-kinds.html", "anchor": "introduction"},
            {"symbol": "a", "meaning": "WGS 84 semi-major axis", "kind": "constant", "value": "6 378 137", "unit": "m"}]
    try:
        nj.write_text(json.dumps(good, ensure_ascii=False, indent=1), encoding="utf-8")
        code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check("scholar: one symbol with two meanings (notation.json vs a page table) is a warning, not a FAIL",
                code == 0 and 'notation: symbol "λ" means "wavelength" (notation.json) and "longitude" (m02-kinds)' in out, out)
        nj.write_text('[{"symbol": "λ"}, {"symbol": "k", "meaning": "x", "kind": "unit"}, {"symbol": "R", "meaning": "radius", "page": "m09-none.html"}]', encoding="utf-8")
        code, out = t.run("validate.py", t.topic, "--pages", "index.html")
        t.check("scholar: notation.json shape errors FAIL (3 site issues)",
                code == 1 and "notation entry 1 needs symbol and meaning" in out and 'notation entry "k": kind must be symbol or constant' in out
                and 'notation entry "R" points to missing page m09-none.html' in out and t.result_of(out).get("site_issues") == "3", out)
        nj.write_text('{"symbol": "λ"}', encoding="utf-8")
        code, out = t.run("validate.py", t.topic, "--pages", "index.html")
        t.check("scholar: notation.json that is not an array FAIL", code == 1 and "assets/notation.json must be a JSON array" in out, out)
        nj.write_text(json.dumps(good, ensure_ascii=False, indent=1), encoding="utf-8")
        code, out = t.run("build_site_data.py", t.topic)
        r = t.result_of(out)
        dj = (t.topic / "assets" / "data.js").read_text(encoding="utf-8")
        data = json.loads(dj.split("window.QC_DATA = ", 1)[1].rstrip().rstrip(";"))
        n = data.get("notation") or {}
        ents = n.get("entries", [])
        by = {(e.get("symbol"), e.get("meaning")): e for e in ents}
        m02 = [e for e in ents[len(good):] if e.get("page") == "m02-kinds.html"]   # harvested rows only (the json entries come first)
        lam, h, c = by.get(("λ", "longitude"), {}), by.get(("h", "scale factor along the meridian"), {}), by.get(("c", "Speed of light"), {})
        t.check("scholar: build_site_data writes DATA.notation (json entries first, harvested rows with tex, unit, value, kind, page, anchor)",
                code == 0 and "notation" in r.get("keys", "") and isinstance(n.get("pages"), int) and n["pages"] >= 1 and len(m02) == 3
                and ents[0]["symbol"] == "λ" and ents[0]["meaning"] == "wavelength" and ents[1]["kind"] == "constant" and ents[1]["value"] == "6 378 137"
                and lam.get("tex") == "\\lambda" and lam.get("unit") == "rad" and lam.get("anchor") == "tbl-notation-m02" and lam.get("kind") == "symbol"
                and h.get("where") == "Definition 1" and c.get("kind") == "constant" and c.get("value") == "299 792 458" and c.get("unit") == "m/s"
                and c.get("anchor") == "introduction" and c.get("where") == "CODATA 2018", out + "\n" + json.dumps(n, ensure_ascii=False)[:800])
    finally:
        if nj.exists():
            nj.unlink()

    # static: the runtime block, the stylesheet block, the template page and its registration
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    names = ("scholar-thm", "scholar-eq", "scholar-copy-tex", "scholar-notation", "scholar-refs")
    t.check("scholar: app.js registers the five scholar features inside the scholar block",
            all(f"feature({{ name: '{n}'" in app for n in names) and app.index("BLOCK scholar") < app.index("feature({ name: 'scholar-thm'") < app.index("END scholar")
            and 'annotation[encoding="application/x-tex"]' in app and "typeof window.QC.download === 'function'" in app)
    t.check("scholar: style.css defines the scholar classes", all(c in css for c in (".thm {", ".thm-label", ".eq-num", ".copy-tex", ".refs-tools", ".cite-card", ".notation-page", "table.notation td.sym")))
    np_ = t.TEMPLATE / "notation.html"
    nt = np_.read_text(encoding="utf-8") if np_.exists() else ""
    tsj = json.loads((t.TEMPLATE / "assets" / "site.json").read_text(encoding="utf-8"))
    ent = next((p for p in tsj.get("pages", []) if p.get("file") == "notation.html"), None)
    t.check("scholar: template notation.html carries the data-notation widget, a trust footer and data.js, and is registered as N / Reference",
            np_.exists() and 'data-page="notation.html"' in nt and 'class="notation-page" data-notation' in nt and 'class="trust"' in nt and "assets/data.js" in nt
            and ent is not None and ent.get("num") == "N" and ent.get("group") == "Reference")
    code, out = t.run("validate.py", t.topic, "--pages", "notation.html", "--quiet")
    t.check("scholar: the scaffolded pages/notation.html validates", code == 0 and t.result_of(out).get("bad_pages") == "0" and t.result_of(out).get("pages") == "1", out)
# ==== END scholar ====



# ==== BLOCK visual — C9 download SVG/PNG · C10 photo hotspots and lightbox · C11 compare slider and exploded-view layers ====
@feature_test
def visual_tests(t) -> None:
    """C10 hotspots, C11 compare + layers: a module page carrying all three validates; each validator message has a FAIL case;
    C9 and the runtime parts are checked statically (app.js registers the features and exposes QC.download / QC.svgToString)."""
    hot = '''<figure class="photo" id="fig-hot" data-hotspots>
      <img src="https://upload.wikimedia.org/wikipedia/commons/8/8e/Atlas_%28Farnese_Globe%29.jpg" alt="The Farnese Atlas" loading="lazy">
      <ul class="hotspots"><li data-x="52" data-y="22"><b>Globe</b> — the celestial sphere.</li><li data-x="48" data-y="60"><b>Atlas</b> — the Titan.</li></ul>
      <figcaption><b>Figure 2.2 — Pins.</b> <span class="credit">Source: <a href="https://commons.wikimedia.org/wiki/File:Atlas_(Farnese_Globe).jpg">Wikimedia Commons</a>, CC BY-SA 3.0</span></figcaption>
    </figure>'''
    cmp_ = '''<figure class="compare" id="fig-cmp" data-label-a="Mercator" data-label-b="Equal-area">
      <svg viewBox="0 0 300 200" role="img" aria-labelledby="fig-cmp-a"><title id="fig-cmp-a">Mercator graticule</title><rect class="d-box" x="10" y="10" width="280" height="180" rx="6"/><path class="d-line d-data" d="M10 60 H290 M10 140 H290"/></svg>
      <svg viewBox="0 0 300 200" role="img" aria-labelledby="fig-cmp-b"><title id="fig-cmp-b">Equal-area graticule</title><rect class="d-box alt" x="10" y="10" width="280" height="180" rx="6"/><path class="d-line d-ctrl" d="M10 80 H290 M10 120 H290"/></svg>
      <figcaption><b>Figure 2.3 — Two projections.</b> Drag the divider.</figcaption>
    </figure>'''
    lay = '''<figure class="diagram" id="fig-lay" data-layers data-cite="#ref-key">
      <svg viewBox="0 0 600 200" role="img" aria-labelledby="fig-lay-t"><title id="fig-lay-t">Site anatomy</title>
        <g data-layer="Frame"><rect class="d-box" x="20" y="20" width="560" height="40" rx="6"/></g>
        <g data-layer="Content"><rect class="d-box accent" x="20" y="80" width="560" height="100" rx="6"/></g>
        <g data-layer="Data" data-layer-off><path class="d-line d-dash" d="M300 180 V60"/></g>
      </svg>
      <figcaption><b>Figure 2.4 — Layers.</b> Toggle them.</figcaption>
    </figure>'''
    page = t.mutate(t.m02, '<h2 id="introduction">Conceptual introduction</h2>', '<h2 id="introduction">Conceptual introduction</h2>\n    ' + hot + '\n    ' + cmp_ + '\n    ' + lay)
    t.page_m02.write_text(page, encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("visual: module page with a hotspot photo, a compare figure and an exploded-view diagram PASS", code == 0 and t.result_of(out).get("bad_pages") == "0", out)

    def fail(name: str, text: str, msg: str) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check(name, c == 1 and msg in o, o)

    fail("visual: hotspot without data-x/data-y FAIL", t.mutate(page, '<li data-x="48" data-y="60">', '<li data-y="60">'), "hotspot without data-x/data-y")
    fail("visual: hotspot data-x outside 0..100 FAIL", t.mutate(page, 'data-x="52"', 'data-x="140"'), "hotspot data-x 140 outside 0..100")
    fail("visual: hotspot data-y not a number FAIL", t.mutate(page, 'data-y="22"', 'data-y="top"'), 'hotspot data-y "top" is not a number')
    fail("visual: data-hotspots without ul.hotspots FAIL", t.mutate(page, '<ul class="hotspots">', '<ul class="pins">'), "photo fig-hot has data-hotspots but no ul.hotspots")
    fail("visual: compare figure with 3 panes FAIL", t.mutate(page, '<figcaption><b>Figure 2.3', '<div class="card">a third pane</div>\n      <figcaption><b>Figure 2.3'), "compare figure fig-cmp has 3 panes, needs 2")
    fail("visual: compare figure with 1 pane FAIL", t.mutate(page, '<svg viewBox="0 0 300 200" role="img" aria-labelledby="fig-cmp-b"><title id="fig-cmp-b">Equal-area graticule</title><rect class="d-box alt" x="10" y="10" width="280" height="180" rx="6"/><path class="d-line d-ctrl" d="M10 80 H290 M10 120 H290"/></svg>', ''), "compare figure fig-cmp has 1 pane, needs 2")
    one = page.replace('<g data-layer="Content">', '<g>').replace('<g data-layer="Data" data-layer-off>', '<g>')
    fail("visual: exploded view with one layer FAIL", one, "exploded view fig-lay has fewer than 2 layers")
    fail("visual: duplicate layer name FAIL", t.mutate(page, 'data-layer="Content"', 'data-layer="Frame"'), 'layer "Frame" used twice in fig-lay')
    fail("visual: layer without a name FAIL", t.mutate(page, 'data-layer="Content"', 'data-layer=""'), "layer without a name in fig-lay")
    t.page_m02.write_text(t.mutate(page, '<figure class="diagram" id="fig-lay" data-layers data-cite="#ref-key">', '<figure class="diagram" id="fig-lay" data-cite="#ref-key">'), encoding="utf-8")
    c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("visual: g[data-layer] without data-layers is a warning, not a FAIL", c == 0 and "warning:" in o and "fig-lay has g[data-layer] groups but no data-layers" in o, o)
    # static: the runtime block (node --check of app.js is covered by validate's js_syntax=checked above)
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    t.check("visual: app.js registers c9-download, c10-photos and c11-compare-layers and exposes QC.download / QC.svgToString",
            all(f"feature({{ name: '{n}'" in app for n in ("c9-download", "c10-photos", "c11-compare-layers"))
            and "api: { download, svgToString }" in app and "function download(filename, data, mime)" in app and "function svgToString(svg, opts)" in app
            and all(tok in app for tok in ("'dl-menu'", "'hotspot-box'", "'hotspot-tip'", "'lightbox'", "'compare-range'", "'layer-tools'", "'layer-hidden'"))
            and app.index("function enhanceDownloads") < app.index("feature({ name: 'c9-download'") < app.index("feature({ name: 'c10-photos'") < app.index("feature({ name: 'c11-compare-layers'"))
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    t.check("visual: style.css has the download menu, hotspot, lightbox, compare and layer rules and hides the controls in print",
            all(sel in css for sel in (".dl-menu", ".hotspot-box", ".hotspot-tip", "ul.hotspots", ".lightbox[hidden]", ".compare-pane.b", ".compare-range", "svg g.layer-hidden", ".layer-chip"))
            and ".dl-menu, .lightbox, .lightbox-open, .compare-range, .layer-tools, .hotspot-tip { display: none !important; }" in css)
    cat = t.PLUGIN / "skills" / "compose" / "components"
    t.check("visual: catalog snippets media/photo-hotspots.html, media/compare.html, diagrams/diagram-layers.html exist and are listed in INDEX.md",
            all((cat / f).exists() for f in ("media/photo-hotspots.html", "media/compare.html", "diagrams/diagram-layers.html"))
            and all(n in (cat / "INDEX.md").read_text(encoding="utf-8") for n in ("photo-hotspots.html", "compare.html", "diagram-layers.html")))
# ==== END visual ====



# ==== BLOCK plots — C5 plot upgrades · C6 declarative function plotter · C7 vector fields and parameter sweeps ====
@feature_test
def plots_feature_tests(t) -> None:
    """C5 plot upgrades · C6 fnplot · C7 field and sweep: validator PASS/FAIL cases, the catalog module, static app.js checks
    and a node run of the extracted expression parser."""
    figs = '''<figure class="fnplot" id="c6-test" data-fn="a*sin(b*x)+c; cos(x)" data-x="-10,10,x" data-y="-4,4" data-vars="a=1:3:0.1:1.5, b=0.5:4:0.1:1, c=-2:2:0.5:0" data-labels="f, g" data-scale="linear" data-cite="#ref-key">
      <figcaption><b>Figure 2.2 — A function plotter.</b> Sliders for a, b and c.</figcaption>
    </figure>
    <figure class="field" id="c7-test-field" data-fx="y" data-fy="-x - 0.3*y" data-x="-3,3" data-y="-3,3" data-grid="16" data-trajectories="1,0; -2,1" data-cite="#ref-key">
      <figcaption><b>Figure 2.3 — A damped oscillator.</b> Phase portrait.</figcaption>
    </figure>
    <figure class="sweep" id="c7-test-sweep" data-fn="exp(-k*x)*cos(3*x)" data-x="0,10" data-sweep="k=0:1:0.2" data-cite="#ref-key">
      <figcaption><b>Figure 2.4 — A parameter sweep.</b> Six dampings.</figcaption>
    </figure>'''
    anchor = "Step through it.</figcaption>\n    </figure>"
    page = t.mutate(t.m02, anchor, anchor + "\n    " + figs)
    t.page_m02.write_text(page, encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("plots: fnplot + field + sweep figures PASS", code == 0 and t.result_of(out).get("bad_pages") == "0" and "warning:" not in out.replace("not checked", ""), out)

    def fail(name: str, text: str, msg: str) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        ln = t.line_no(text, 'id="c6-test"') if "fnplot" in msg else t.line_no(text, 'id="c7-test-field"') if "field" in msg else t.line_no(text, 'id="c7-test-sweep"')
        t.check(name, c == 1 and f":{ln} {msg}" in o, o)

    fail("plots: fnplot without data-fn FAIL", t.mutate(page, 'data-fn="a*sin(b*x)+c; cos(x)" ', ""), "fnplot without data-fn")
    fail("plots: fnplot data-x not two numbers FAIL", t.mutate(page, 'data-x="-10,10,x"', 'data-x="-10"'), "fnplot data-x must be two numbers")
    fail("plots: fnplot data-y not two numbers FAIL", t.mutate(page, 'data-y="-4,4"', 'data-y="wide"'), "fnplot data-y must be two numbers")
    fail("plots: fnplot log x with a negative range FAIL", t.mutate(page, 'data-scale="linear"', 'data-scale="logx"'), "fnplot data-x must be positive on a log axis")
    fail("plots: fnplot bad data-scale FAIL", t.mutate(page, 'data-scale="linear"', 'data-scale="semilog"'), 'fnplot data-scale "semilog" is not linear, log, logx or loglog')
    fail("plots: fnplot var without min:max FAIL", t.mutate(page, "a=1:3:0.1:1.5", "a=1"), 'fnplot var "a=1" needs min:max')
    fail("plots: fnplot var min above max FAIL", t.mutate(page, "a=1:3:0.1:1.5", "a=3:1"), 'fnplot var "a=3:1" needs min < max')
    fail("plots: fnplot var zero step FAIL", t.mutate(page, "a=1:3:0.1:1.5", "a=1:3:0"), 'fnplot var "a=1:3:0" needs a positive step')
    fail("plots: fnplot unknown function FAIL", t.mutate(page, "cos(x)", "foo(x)"), 'fnplot expression: unknown function "foo"')
    fail("plots: fnplot unknown variable FAIL", t.mutate(page, "+c;", "+q;"), 'fnplot expression: unknown variable "q"')
    fail("plots: fnplot unbalanced parentheses FAIL", t.mutate(page, "a*sin(b*x)+c", "a*sin(b*x+c"), "fnplot expression: unbalanced parentheses")
    fail("plots: fnplot unexpected character FAIL", t.mutate(page, "a*sin(b*x)+c", "a*sin(b*x)+$c"), 'fnplot expression: unexpected character "$"')
    fail("plots: field without data-fy FAIL", t.mutate(page, 'data-fy="-x - 0.3*y" ', ""), "field figure needs data-fx and data-fy")
    fail("plots: field unknown function FAIL", t.mutate(page, 'data-fx="y"', 'data-fx="sinn(y)"'), 'field expression: unknown function "sinn"')
    fail("plots: field unknown variable FAIL", t.mutate(page, 'data-fx="y"', 'data-fx="z"'), 'field expression: unknown variable "z"')
    fail("plots: field data-y not two numbers FAIL", t.mutate(page, 'data-y="-3,3"', 'data-y="3"'), "field data-y must be two numbers")
    fail("plots: field trajectory without y FAIL", t.mutate(page, 'data-trajectories="1,0; -2,1"', 'data-trajectories="1,0; 2"'), 'field trajectory "2" needs x, y')
    fail("plots: field data-grid not a number FAIL", t.mutate(page, 'data-grid="16"', 'data-grid="many"'), 'field data-grid "many" is not a whole number')
    fail("plots: sweep without data-fn FAIL", t.mutate(page, 'data-fn="exp(-k*x)*cos(3*x)" ', ""), "sweep without data-fn")
    fail("plots: sweep without data-sweep FAIL", t.mutate(page, ' data-sweep="k=0:1:0.2"', ""), "sweep without data-sweep")
    fail("plots: sweep data-sweep without step FAIL", t.mutate(page, 'data-sweep="k=0:1:0.2"', 'data-sweep="k=0:1"'), 'sweep data-sweep "k=0:1" must be name=min:max:step')
    fail("plots: sweep data-sweep min above max FAIL", t.mutate(page, 'data-sweep="k=0:1:0.2"', 'data-sweep="k=1:0:0.2"'), 'sweep data-sweep "k=1:0:0.2" needs min < max and a positive step')
    fail("plots: sweep with too many members FAIL", t.mutate(page, 'data-sweep="k=0:1:0.2"', 'data-sweep="k=0:1:0.01"'), "sweep has 101 members, max 24")
    fail("plots: sweep data-x not two numbers FAIL", t.mutate(page, 'data-x="0,10"', 'data-x="ten"'), "sweep data-x must be two numbers")
    fail("plots: sweep unknown variable FAIL", t.mutate(page, "exp(-k*x)", "exp(-z*x)"), 'sweep expression: unknown variable "z"')
    # warnings never fail the page
    t.page_m02.write_text(t.mutate(page, 'data-labels="f, g"', 'data-labels="f"'), encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("plots: label count mismatch is a warning, not a FAIL", code == 0 and "warning: fnplot has 1 labels for 2 functions" in out, out)
    t.page_m02.write_text(t.mutate(page, "<figcaption><b>Figure 2.4 — A parameter sweep.</b> Six dampings.</figcaption>\n", ""), encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("plots: figure without figcaption is a warning, not a FAIL", code == 0 and "warning: sweep figure without figcaption" in out, out)
    # catalog module and docs
    cat = t.PLUGIN / "skills" / "compose" / "components"
    snips = ["plot-log.html", "plot-log.js", "heatmap.html", "heatmap.js", "fnplot.html", "field.html", "field.js", "sweep.html", "sweep.js", "README.md"]
    index = (cat / "INDEX.md").read_text(encoding="utf-8")
    t.check("plots: catalog module plots/ complete and listed in INDEX.md", all((cat / "plots" / f).exists() for f in snips)
            and re.search(r"^\| `plots` \|", index, re.M) is not None and all(f in index for f in snips if f.endswith(".html")))
    readme = (cat / "plots" / "README.md").read_text(encoding="utf-8")
    t.check("plots: README documents every QC.plot option, the heatmap, the figures and the messages",
            all(k in readme for k in ("xScale", "yScale", "y2Label", "y2Range", "xTicks", "xFormat", "grid: false", "errors:", "yerr", "'scatter'", "'bar'", "'step'", "'area'",
                                      "QC.heatmap", "QC.parseExpr", "QC.field", "QC.sweep", "figure.fnplot", "figure.field", "figure.sweep",
                                      "fnplot expression: unknown function", "field figure needs data-fx and data-fy", "sweep has 101 members, max 24")))
    skill = (t.PLUGIN / "skills" / "compose" / "SKILL.md").read_text(encoding="utf-8")
    t.check("plots: compose SKILL.md derivation table names plots", "`plots`" in skill)
    # static app.js and style.css checks
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    block = app[app.index("==== BLOCK plots"):app.index("==== END plots")]
    t.check("plots: app.js registers the feature and exposes heatmap, parseExpr, field, sweep",
            "feature({\n    name: 'plots'" in app and "api: { heatmap, parseExpr, field, sweep" in block and "function heatmap(canvas, cfg)" in app
            and "function parseExpr(src)" in block and "function field(canvas, cfg)" in block and "function sweep(canvas, cfg)" in block)
    t.check("plots: QC.plot has log scales, series types, error bars, a second axis, title, ticks, formatters and grid",
            all(k in app for k in ("cfg.xScale === 'log'", "cfg.yScale === 'log'", "s.axis === 'y2'", "type === 'bar'", "type === 'scatter'", "type === 'step'", "type === 'area'",
                                   "s.errors", "s.yerr", "cfg.y2Label", "cfg.y2Range", "cfg.xTicks", "cfg.yTicks", "cfg.xFormat", "cfg.yFormat", "cfg.grid !== false", "cfg.title", "plotHooks")))
    t.check("plots: no eval or Function in the plots block; download tools fall back when QC.download is missing",
            "eval(" not in block and "Function(" not in block and "typeof window.QC.download === 'function'" in block and "URL.createObjectURL" in block and "'plot-tools'" in block)
    t.check("plots: style.css block defines the wrapper, tools, figure classes and controls",
            all(k in css for k in (".plot-wrap", ".plot-tools", "figure.plot", "figure.fnplot", "figure.field", "figure.sweep", ".fn-controls", ".fn-error")) and ".plot-tools { display: none !important; }" in css)
    # the expression parser, run by node outside the page (the same code the page uses, extracted between its markers)
    if t.node:
        m = re.search(r"/\* parseExpr:begin[\s\S]*?/\* parseExpr:end \*/", app)
        harness = (m.group(0) if m else "") + r"""
const f = parseExpr('a*sin(b*x)+c');
const out = [f({ x: 0, a: 2, b: 1, c: 1 }), parseExpr('2^3^2')({}), parseExpr('-2^2')({}), parseExpr('max(1, 2, 3) + min(4, 5)')({}), parseExpr('1e-3*1000')({}),
  parseExpr('step(-1) + step(2)')({}), parseExpr('clamp(5, 0, 1)')({}), parseExpr('10 % 3')({}), parseExpr('ln(e) + log10(100) + sqrt(16)')({}), parseExpr('q')({}), parseExpr('atan2(1, 1) / pi')({})];
const errs = [];
for (const s of ['foo(x)', '(1+2', '2x', '1 +', 'x $ 2', 'sin(1, 2)', '', 'constructor(1)']) { try { parseExpr(s); errs.push('no error for ' + s); } catch (e) { errs.push(e.message); } }
console.log(JSON.stringify({ out, errs, vars: parseExpr('a*x + b - pi').vars, proto: parseExpr('toString')({}) }));
"""
        hf = t.WORK / "plots-parse-expr.js"
        hf.write_text(harness, encoding="utf-8")
        pr = subprocess.run([t.node, str(hf)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            res = json.loads(pr.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            res = {}
        want_out = [1, 512, -4, 7, 1, 1, 1, 1, 7, None, 0.25]
        got = res.get("out", [])
        ok_out = len(got) == len(want_out) and all((w is None and g is None) or (w is not None and g is not None and abs(g - w) < 1e-9) for g, w in zip(got, want_out))
        errs = res.get("errs", [])
        ok_err = len(errs) == 8 and errs[0] == 'unknown function "foo"' and errs[1] == 'missing ")"' and "write * for multiplication" in errs[2] \
            and errs[3] == "unexpected end of expression" and errs[4] == 'unexpected character "$"' and errs[5] == "sin expects 1 argument" \
            and errs[6] == "empty expression" and errs[7] == 'unknown function "constructor"'
        t.check("plots: parseExpr evaluates, respects precedence and rejects bad input (node)",
                bool(m) and pr.returncode == 0 and ok_out and ok_err and res.get("vars") == ["a", "x", "b"] and res.get("proto") is None,
                (pr.stdout + pr.stderr)[:1200])
    else:
        print("      (parseExpr node check skipped: node not on PATH)")
# ==== END plots ====



# ==== BLOCK compute — D1 demo state and presets · D2 export results · D3 unit-aware inputs · D4 uncertainty helpers · D6 sensitivity view ====
COMPUTE_UNIT_GROUPS = ("length", "mass", "time", "temperature", "speed", "pressure", "energy", "power", "angle", "frequency", "voltage", "current", "data")
# runs app.js in node with a stub DOM (readyState 'loading', so init() never runs) and exercises the pure QC helpers
COMPUTE_HARNESS = r"""
const fs = require('fs');
const noop = () => {};
const fakeEl = () => ({ dataset: {}, style: { setProperty: noop, removeProperty: noop }, classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
  setAttribute: noop, getAttribute: () => null, removeAttribute: noop, appendChild: noop, prepend: noop, after: noop, before: noop, remove: noop, click: noop,
  querySelector: () => null, querySelectorAll: () => [], addEventListener: noop, removeEventListener: noop, insertAdjacentHTML: noop, closest: () => null,
  getBoundingClientRect: () => ({ top: 0, left: 0, width: 0, height: 0 }), contains: () => false, focus: noop, innerHTML: '', textContent: '' });
globalThis.window = globalThis;
globalThis.document = Object.assign(fakeEl(), { readyState: 'loading', body: fakeEl(), documentElement: fakeEl(), head: fakeEl(), createElement: () => fakeEl(),
  getElementById: () => null, dispatchEvent: noop, createTreeWalker: () => ({ nextNode: () => false }), fullscreenElement: null, activeElement: null, title: 't' });
globalThis.location = { pathname: '/site/pages/m02-kinds.html', search: '', hash: '', href: 'file:///site/pages/m02-kinds.html', protocol: 'file:' };
globalThis.history = { replaceState: noop, pushState: noop };
globalThis.navigator = { clipboard: { writeText: () => Promise.resolve() } };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => '' });
globalThis.addEventListener = noop; globalThis.removeEventListener = noop; globalThis.requestAnimationFrame = () => 0; globalThis.cancelAnimationFrame = noop;
globalThis.matchMedia = () => ({ matches: false, addEventListener: noop, removeEventListener: noop, addListener: noop });
globalThis.CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } }; globalThis.Event = class { constructor(t) { this.type = t; } };
globalThis.IntersectionObserver = class { observe() {} disconnect() {} }; globalThis.MutationObserver = class { observe() {} disconnect() {} }; globalThis.ResizeObserver = class { observe() {} disconnect() {} };
globalThis.Image = class {}; globalThis.HTMLElement = class {}; globalThis.Node = { DOCUMENT_POSITION_FOLLOWING: 4 }; globalThis.NodeFilter = { SHOW_COMMENT: 128 };
globalThis.devicePixelRatio = 1; globalThis.innerWidth = 1200; globalThis.innerHeight = 800; globalThis.scrollY = 0; globalThis.scrollTo = noop;
new Function(fs.readFileSync(process.argv[2], 'utf8'))();
const QC = globalThis.QC, out = {};
out.parse = [QC.parseSI('4.7k'), QC.parseSI('2.2µ'), QC.parseSI('2.2uF'), QC.parseSI('10 Hz'), QC.parseSI('-3.5M'), QC.parseSI('abc')];
out.fmt = [QC.fmtSI(4700, 'Ω'), QC.fmtSI(0.0000022, 'F'), QC.fmtSI(999.95, 'Hz'), QC.fmtSI(0, 'V'), QC.fmtSI(NaN, 'V'), QC.fmtSI(1e6, '')];
out.conv = [QC.convert(1, 'ft', 'm'), QC.convert(100, '°C', '°F'), QC.convert(32, '°F', 'K'), QC.convert(1, 'kWh', 'J'), QC.convert(1, 'm', 'kg')];
const model = v => v.a * v.b / v.c;
const inputs = { a: { nominal: 120, tol: 0.01 }, b: { nominal: 50000, tol: 0.02 }, c: { nominal: 1000, sigma: 5 } };
const r1 = QC.mc(model, inputs, { n: 500, seed: 7 }), r2 = QC.mc(model, inputs, { n: 500, seed: 7 }), r3 = QC.mc(model, inputs, { n: 500, seed: 8 });
out.mc = { n: r1.n, same: r1.mean === r2.mean && r1.sd === r2.sd && r1.p95 === r2.p95, differs: r1.mean !== r3.mean,
  order: r1.min <= r1.p5 && r1.p5 <= r1.p50 && r1.p50 <= r1.p95 && r1.p95 <= r1.max, nominal: r1.nominal,
  worstMin: r1.worst.min.value, worstMax: r1.worst.max.value, worstInputs: Object.keys(r1.worst.min.inputs).length,
  tornado: r1.tornado.map(x => x.name), cap: QC.mc(model, inputs, { n: 1e9, seed: 1 }).n <= 20000, bad: QC.mc(() => NaN, inputs, { n: 10 }).n };
out.csv = QC.export('t', { columns: ['x', 'y'], rows: [[1, 2], [3, 'a,b']] }, 'csv');
out.md = QC.export('t', [{ x: 1, y: 2 }, { x: 3, z: 4 }], 'md');
out.json = JSON.parse(QC.export('t', [[1, NaN]], 'json'));
out.api = ['applyPreset', 'setDemoState', 'getDemoState', 'demoLink', 'export', 'units', 'convert', 'fmtSI', 'parseSI', 'mc', 'tornado', 'tolerancesOf'].filter(k => typeof QC[k] !== (k === 'units' ? 'object' : 'function'));
out.presetMissing = QC.applyPreset('no-such-demo', 'over') === false && QC.getDemoState('no-such-demo') === null;
out.units = Object.keys(QC.units);
console.log(JSON.stringify(out));
"""


def _near(a, b, rel=1e-9) -> bool:
    return a is not None and b is not None and abs(a - b) <= rel * max(1.0, abs(b))


@feature_test
def compute_features(t) -> None:
    demos = t.PLUGIN / "skills" / "compose" / "components" / "demos"
    snip = lambda n: local_refs((demos / n).read_text(encoding="utf-8").split("\n", 1)[1])   # noqa: E731 — the body after the header comment
    markup = "\n".join(snip(n) for n in ("demo-calculator.html", "demo-units.html", "demo-uncertainty.html")).replace("#ref-claude-subagents", "#ref-key")
    js = "\n".join((demos / n).read_text(encoding="utf-8") for n in ("demo-calculator.js", "demo-units.js", "demo-uncertainty.js"))
    page = t.mutate(t.m02, '<p>…</p>\n    <figure class="diagram" id="fig-steps"', "<p>…</p>\n" + markup + '\n    <figure class="diagram" id="fig-steps"')
    page = t.mutate(page, "  // page-specific interactive code goes here (QC.plot, QC.bindControls, QC.fmt, QC.onTheme, QC.store …)", js)
    t.page_m02.write_text(page, encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("compute: module page with the calculator (presets), units and uncertainty demos PASS, no compute warnings",
            code == 0 and t.result_of(out).get("bad_pages") == "0" and not any(w in out for w in ("warning: demo without id", "warning: unit input", "warning: data-si"))
            and t.result_of(out).get("js_syntax") == "checked", out)

    def fail(name: str, text: str, msg: str) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check(name, c == 1 and msg in o, o)

    def warn(name: str, text: str, msg: str) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check(name, c == 0 and ("warning: " + msg) in o, o)

    fail("compute: preset naming an unknown input FAIL", t.mutate(page, 'data-state="parts=9&partkb=40&budget=250&frame=40"', 'data-state="parts=9&foo=40&budget=250&frame=40"'),
         'preset "over" names unknown input "foo"')
    fail("compute: preset name used twice FAIL", t.mutate(page, 'data-preset="fits"', 'data-preset="over"'), 'preset "over" defined twice in demo-budget')
    fail("compute: preset without data-state FAIL", t.mutate(page, 'data-preset="fits" data-state="parts=5&partkb=30&budget=250&frame=40"', 'data-preset="fits"'),
         'preset "fits" has no data-state')
    fail("compute: unknown unit group FAIL", t.mutate(page, 'data-unit-group="length" data-unit="km"', 'data-unit-group="volume" data-unit="km"'), 'unit group "volume" unknown')
    fail("compute: unit outside its group FAIL", t.mutate(page, 'data-unit-group="length" data-unit="km"', 'data-unit-group="length" data-unit="yd"'), 'unit "yd" is not in group length')
    fail("compute: unit input without data-unit FAIL", t.mutate(page, 'data-unit-group="length" data-unit="cm"', 'data-unit-group="length"'), 'unit input "d3-paper" has no data-unit')
    fail("compute: unit input that is not range/number FAIL", t.mutate(page, 'type="range" id="d3-paper"', 'type="text" id="d3-paper"'), 'unit input "d3-paper" must be type range or number')
    fail("compute: non-numeric data-tol FAIL", t.mutate(page, 'data-tol="2"', 'data-tol="abc"'), 'data-tol "abc" must be a number 0..100')
    fail("compute: data-tol over 100 FAIL", t.mutate(page, 'data-tol="2"', 'data-tol="150"'), 'data-tol "150" must be a number 0..100')
    warn("compute: demo without id is a warning", t.mutate(page, '<div class="demo" id="demo-units">', '<div class="demo">'), "demo without id (no URL state, presets, link or export)")
    warn("compute: unit input without an output is a warning", t.mutate(page, '<output for="d3-paper"></output>', ''), 'unit input "d3-paper" has no output[for]')
    warn("compute: data-si on a number input is a warning", t.mutate(page, 'type="text" id="d3-scale"', 'type="number" id="d3-scale"'), 'data-si input "d3-scale" should be type text')
    t.page_m02.write_text(page, encoding="utf-8")

    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    t.check("compute: app.js registers compute-state, compute-menu, compute-units, compute-uncertainty with the QC api",
            all(f"feature({{ name: '{n}'" in app for n in ("compute-state", "compute-menu", "compute-units", "compute-uncertainty"))
            and all(k in app for k in ("applyPreset, setDemoState, getDemoState, demoLink", "export: exportData", "units: UNITS, convert, fmtSI, parseSI", "mc, tornado, tolerancesOf")))
    t.check("compute: bindControls restores and writes the URL hash (demo controls section, before the blocks) and skips injected controls",
            app.index("function bindControls") < app.index("replaceHash(id, read())") < app.index("BLOCK compute") and "hashState()" in app and "INJECTED_CTL" in app)
    t.check("compute: app.js unit table has every validator unit group", all(f"{g}: {{ base:" in app for g in COMPUTE_UNIT_GROUPS))
    t.check("compute: app.js falls back to its own Blob download when QC.download is absent", "typeof window.QC.download === 'function'" in app and "URL.createObjectURL(new Blob(" in app)
    if not t.node:
        print("      (compute: node harness skipped — node not on PATH)")
        return
    harness = t.WORK / "compute-harness.js"
    harness.write_text(COMPUTE_HARNESS, encoding="utf-8")
    p = subprocess.run([t.node, str(harness), str(t.TEMPLATE / "assets" / "app.js")], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    try:
        r = json.loads((p.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        r = None
    t.check("compute: node harness runs app.js with a stub DOM", p.returncode == 0 and isinstance(r, dict), (p.stdout or "") + (p.stderr or ""))
    if not isinstance(r, dict):
        return
    t.check("compute: parseSI (4.7k, 2.2µ, 2.2uF, 10 Hz, -3.5M, abc)",
            _near(r["parse"][0], 4700) and _near(r["parse"][1], 2.2e-6) and _near(r["parse"][2], 2.2e-6) and _near(r["parse"][3], 10) and _near(r["parse"][4], -3.5e6) and r["parse"][5] is None, json.dumps(r["parse"]))
    t.check("compute: fmtSI → 4.7 kΩ · 2.2 µF · 1 kHz · 0 V · — · 1 M", r["fmt"] == ["4.7 kΩ", "2.2 µF", "1 kHz", "0 V", "—", "1 M"], json.dumps(r["fmt"], ensure_ascii=False))
    t.check("compute: convert ft→m, °C→°F, °F→K, kWh→J, m→kg is NaN",
            _near(r["conv"][0], 0.3048) and _near(r["conv"][1], 212) and _near(r["conv"][2], 273.15) and _near(r["conv"][3], 3.6e6) and r["conv"][4] is None, json.dumps(r["conv"]))
    m = r["mc"]
    t.check("compute: QC.mc is seeded and repeatable, quantiles ordered, n capped at 20000, NaN models give n=0",
            m["n"] == 500 and m["same"] and m["differs"] and m["order"] and m["cap"] and m["bad"] == 0, json.dumps(m))
    t.check("compute: QC.mc nominal 6000, corner worst case from 8 corners, tornado sorted by swing (b, c, a)",
            _near(m["nominal"], 6000) and _near(m["worstMin"], 120 * 0.99 * 50000 * 0.98 / 1015) and _near(m["worstMax"], 120 * 1.01 * 50000 * 1.02 / 985)
            and m["worstInputs"] == 3 and m["tornado"] == ["b", "c", "a"], json.dumps(m))
    t.check("compute: QC.export csv quotes commas, md unions object keys, json maps NaN to null",
            r["csv"] == "x,y\n1,2\n3,\"a,b\"\n" and "| x | y | z |" in r["md"] and "| 3 |  | 4 |" in r["md"] and r["json"]["rows"] == [[1, None]], json.dumps([r["csv"], r["md"], r["json"]]))
    t.check("compute: every QC key present; applyPreset/getDemoState on a missing demo return false/null; 13 unit groups",
            r["api"] == [] and r["presetMissing"] and r["units"] == list(COMPUTE_UNIT_GROUPS), json.dumps([r["api"], r["presetMissing"], r["units"]]))
# ==== END compute ====



# ==== BLOCK sitewide — A1 indexes · A3 backlinks · E5 claim → evidence trace · G4 site manifest · H6 media manifest ====
# sitewide: A1 indexes · A3 backlinks · E5 claims (PASS + both FAIL messages) · G4 manifest.json / DATA.manifest · H6 media.json + warning ·
# the stale data.js warning · static app.js / style.css / template checks.
SW_EXTRA = '''
    <p>A <dfn>projection</dfn> maps the sphere to the plane. <span class="claim" data-src="#ref-key">Web Mercator exaggerates Greenland about 14 times <a class="cite" href="#ref-key">[1]</a></span>. <span class="claim" data-src="glossary.html#terms">Every term is defined once in the glossary</span>. See the <a href="glossary.html#terms">term list</a> for the symbols; the proof is in Snyder <a class="cite" href="#ref-key">[1]</a>.</p>
    <figure class="photo" id="fig-globe"><img src="https://example.org/globe.jpg" alt="A globe" loading="lazy"><figcaption><b>Figure 2.2 — A globe.</b> Shapes stay true. <span class="credit">Source: <a href="https://commons.wikimedia.org/">Wikimedia Commons, Someone</a>, CC BY-SA 3.0</span></figcaption></figure>
    <figure class="photo" id="fig-nolic"><img src="https://example.org/map.jpg" alt="A map" loading="lazy"><figcaption><b>Figure 2.3 — A map.</b> Flat. <span class="credit">Source: <a href="https://example.org/">Example</a></span></figcaption></figure>
    <div class="table-wrap"><div class="table-tools"><span class="tt-title">Projection properties</span><input class="table-filter" data-target="tbl-proj" placeholder="Filter…"><span class="tt-count" data-target="tbl-proj"></span></div><table id="tbl-proj" class="sortable"><thead><tr><th>Projection</th><th>Property</th></tr></thead><tbody><tr><td>Mercator</td><td>conformal</td></tr><tr><td>Lambert</td><td>equal-area</td></tr></tbody></table></div>
    <div class="eq" id="eq-scale">$$ k = \\sec\\varphi $$</div>
    <pre><code class="language-python">k = 1 / math.cos(phi)  # scale factor</code></pre>'''


def sw_data(path):
    return json.loads(path.read_text(encoding="utf-8").split("window.QC_DATA = ", 1)[1].rstrip().rstrip(";"))


@feature_test
def sitewide(t):
    page = t.mutate(t.m02, "</figure>", "</figure>" + SW_EXTRA)
    page = t.mutate(page, '<ol class="objectives">\n      <li>…</li>', '<ol class="objectives">\n      <li data-bloom="apply">Compute the scale factor of Web Mercator at 60°.</li>')
    t.page_m02.write_text(page, encoding="utf-8")
    t.sync()
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    r = t.result_of(out)
    t.check("sitewide: claims, cites, photos, table, equation and code validate PASS; RESULT carries claims=n",
            code == 0 and r.get("bad_pages") == "0" and int(r.get("claims", "0")) >= 2, out)
    t.check("sitewide: media without a licence is a warning naming page and id (the licensed photo is not reported)",
            "warning: media without a licence: m02-kinds.html fig-nolic" in out and "fig-globe" not in out, out)

    def fail(name, text, msg):
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check(name, c == 1 and msg in o and "m02-kinds.html:" in o, o)

    fail("sitewide: claim cites missing source FAIL", t.mutate(page, 'data-src="#ref-key"', 'data-src="#ref-nope"'), "claim cites missing source #ref-nope")
    fail("sitewide: claim pointing at a page without an anchor FAIL", t.mutate(page, 'data-src="glossary.html#terms"', 'data-src="glossary.html"'), "claim cites missing source glossary.html")
    fail("sitewide: claim without data-src FAIL", t.mutate(page, '<span class="claim" data-src="glossary.html#terms">', '<span class="claim">'), "claim without data-src")
    # stale data.js: a warning that names the newer page; --sync clears it
    t.page_m02.write_text(page, encoding="utf-8")
    dj = t.topic / "assets" / "data.js"
    old = dj.stat().st_mtime - 120
    os.utime(dj, (old, old))
    c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("sitewide: stale assets/data.js is a warning naming the newer page", c == 0 and "warning: assets/data.js is older than pages/m02-kinds.html — run build_site_data.py" in o, o)
    t.sync()
    c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("sitewide: after --sync the stale warning is gone", c == 0 and "is older than" not in o, o)
    # build_site_data on the pages/ topic
    code, out = t.run("build_site_data.py", t.topic)
    r = t.result_of(out)
    data = sw_data(dj)
    ix, bl, ev, man = data.get("indexes", {}), data.get("backlinks", {}), data.get("evidence", {}), data.get("manifest", {})
    t.check("sitewide: build_site_data PASS, keys indexes,backlinks,evidence,manifest, writes manifest.json and media.json",
            code == 0 and r.get("status") == "PASS" and all(k in r.get("keys", "") for k in ("indexes", "backlinks", "evidence", "manifest"))
            and "assets/manifest.json" in r.get("written", "") and "assets/media.json" in r.get("written", ""), out)
    fig = next((f for f in ix.get("figures", []) if f.get("id") == "fig-globe"), {})
    tab = next((x for x in ix.get("tables", []) if x.get("id") == "tbl-proj"), {})
    eq = next((x for x in ix.get("equations", []) if x.get("id") == "eq-scale"), {})
    cd = next((x for x in ix.get("code", []) if x.get("page") == "m02-kinds.html"), {})
    t.check("sitewide: DATA.indexes lists the photo (kind, num, caption, section), the table (title, rows), the equation (label) and the code (lang, first line)",
            fig.get("kind") == "photo" and fig.get("num") == "Figure 2.2" and str(fig.get("caption", "")).startswith("Figure 2.2 — A globe.") and fig.get("section") == "introduction"
            and tab.get("title") == "Projection properties" and tab.get("rows") == 2 and eq.get("label") == "(1)" and eq.get("kind") == "eq" and "sec" in str(eq.get("tex"))
            and cd.get("lang") == "python" and str(cd.get("firstLine", "")).startswith("k = 1 / math.cos(phi)"), json.dumps([fig, tab, eq, cd], ensure_ascii=False))
    cons = ix.get("concepts", [])
    dfn = next((c for c in cons if c.get("term") == "projection" and c.get("source") == "dfn"), {})
    t.check("sitewide: DATA.indexes.concepts holds the dfn (page, section anchor) and the glossary terms, sorted A–Z",
            dfn.get("page") == "m02-kinds.html" and dfn.get("anchor") == "introduction" and any(c.get("source") == "glossary" for c in cons)
            and [c["term"].casefold() for c in cons] == sorted(c["term"].casefold() for c in cons), json.dumps(cons[:6], ensure_ascii=False))
    bl_terms, bl_page = bl.get("glossary.html#terms", []), bl.get("glossary.html", [])
    t.check("sitewide: DATA.backlinks records m02 → glossary.html#terms (section, link text) and the hero link → glossary.html (page-level, id null)",
            any(e.get("page") == "m02-kinds.html" and e.get("id") == "introduction" and e.get("text") == "term list" for e in bl_terms)
            and any(e.get("page") == "m02-kinds.html" and e.get("id") is None and e.get("text") == "Glossary" for e in bl_page)
            and not any("cite" in str(e) for e in bl_terms), json.dumps({"terms": bl_terms, "page": bl_page}, ensure_ascii=False))
    evp = ev.get("pages", {}).get("m02-kinds.html", {})
    cl, refs = evp.get("claims", []), evp.get("refs", {})
    t.check("sitewide: DATA.evidence for m02: 3 claims (2 spans + 1 bare cite), ref-key cited twice and verified, glossary.html#terms unverified, site totals",
            len(cl) == 3 and sum(1 for c in cl if c.get("verified")) == 2 and refs.get("ref-key", {}).get("cited") == 2 and refs["ref-key"].get("verified") is True
            and refs.get("glossary.html#terms", {}).get("verified") is False and all(c.get("section") == "introduction" for c in cl)
            and ev.get("refs", {}).get("m02-kinds.html#ref-key", {}).get("pages") == ["m02-kinds.html"] and ev.get("claims", 0) >= 3 and ev.get("sources", 0) >= 2,
            json.dumps(evp, ensure_ascii=False))
    mp = next((p for p in man.get("pages", []) if p.get("file") == "m02-kinds.html"), {})
    cnt = mp.get("counts", {})
    t.check("sitewide: DATA.manifest page entry — bloom.apply=1, counts, terms, reviewed, headings, reading time; no section text in data.js",
            mp.get("bloom", {}).get("apply") == 1 and sum(mp.get("bloom", {}).values()) == 1 and cnt.get("figures") == 3 and cnt.get("tables") == 1 and cnt.get("equations") == 1
            and cnt.get("code") == 1 and cnt.get("refs") == 1 and cnt.get("verified") == 1 and cnt.get("exercises") == 1 and cnt.get("quizzes") == 1 and cnt.get("gaps") == 1
            and cnt.get("claims") == 3 and "projection" in mp.get("terms", []) and mp.get("reviewed") == "2026-11-07" and any(h.get("id") == "introduction" for h in mp.get("headings", []))
            and "sections" not in mp and mp.get("words", 0) > 50 and mp.get("readingMin", 0) >= 1 and mp.get("level") == 1 and mp.get("num") == "02"
            and man.get("title") == "How map projections work" and man.get("storagePrefix") == "map-projections" and man.get("glossary", 0) > 0, json.dumps(mp, ensure_ascii=False))
    mj = json.loads((t.topic / "assets" / "manifest.json").read_text(encoding="utf-8"))
    mjp = next((p for p in mj.get("pages", []) if p.get("file") == "m02-kinds.html"), {})
    intro = next((s for s in mjp.get("sections", []) if s.get("id") == "introduction"), {})
    t.check("sitewide: assets/manifest.json carries plain-text sections (the introduction holds the claim text) and the same header as DATA.manifest",
            mj.get("title") == man.get("title") and mj.get("generated") == man.get("generated") and intro.get("heading") == "Conceptual introduction"
            and "Web Mercator exaggerates Greenland" in intro.get("text", "") and "<" not in intro.get("text", "") and len(intro.get("text", "")) <= 4000
            and mjp.get("sections", [{}])[0].get("id") is None, json.dumps(intro, ensure_ascii=False)[:400])
    media = json.loads((t.topic / "assets" / "media.json").read_text(encoding="utf-8"))
    m_ok = next((m for m in media if m.get("id") == "fig-globe"), {})
    m_no = next((m for m in media if m.get("id") == "fig-nolic"), {})
    t.check("sitewide: assets/media.json lists both photos with src, alt, caption, credit, creditUrl and the parsed licence (CC BY-SA 3.0 / null)",
            m_ok.get("kind") == "photo" and m_ok.get("src") == "https://example.org/globe.jpg" and m_ok.get("alt") == "A globe" and m_ok.get("licence") == "CC BY-SA 3.0"
            and m_ok.get("creditUrl") == "https://commons.wikimedia.org/" and str(m_ok.get("credit", "")).startswith("Source:") and str(m_ok.get("caption", "")).startswith("Figure 2.2")
            and m_no.get("licence") is None and m_no.get("page") == "m02-kinds.html", json.dumps([m_ok, m_no], ensure_ascii=False))
    # single site: one manifest page, bare cites traced
    code, out = t.run("build_site_data.py", t.s_site)
    sdata = sw_data(t.s_site / "assets" / "data.js")
    t.check("sitewide: single site builds — one manifest page (index.html), its cites traced as claims, media.json written",
            code == 0 and t.result_of(out).get("status") == "PASS" and [p.get("file") for p in sdata.get("manifest", {}).get("pages", [])] == ["index.html"]
            and len(sdata.get("evidence", {}).get("pages", {}).get("index.html", {}).get("claims", [])) >= 1 and (t.s_site / "assets" / "media.json").exists(), out)
    # the template page scaffolded into pages/ validates
    c, o = t.run("validate.py", t.topic, "--pages", "indexes.html")
    t.check("sitewide: the scaffolded pages/indexes.html validates (trust footer, includes, widget)",
            c == 0 and t.result_of(o).get("bad_pages") == "0" and "data-indexes" in (t.topic / "pages" / "indexes.html").read_text(encoding="utf-8"), o)
    # static checks
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    treg = json.loads((t.TEMPLATE / "assets" / "site.json").read_text(encoding="utf-8"))
    t.check("sitewide: app.js registers sitewide-search, sitewide-indexes, sitewide-backlinks, sitewide-evidence and sitewide-manifest; falls back when QC.download is missing",
            all(f"feature({{ name: '{n}'" in app for n in ("sitewide-search", "sitewide-indexes", "sitewide-backlinks", "sitewide-evidence", "sitewide-manifest"))
            and "typeof window.QC.download === 'function'" in app and "trust-evidence" in app and "SEARCH_EXTRA.push({ kind: 'Figure'" in app)
    t.check("sitewide: style.css defines the indexes, backlinks, claim and evidence classes with print rules",
            all(c in css for c in (".indexes {", ".ix-tabs", ".backlinks {", ".claim {", ".trust-evidence", ".evidence-table")) and ".ix-tools, .evidence-table .ev-up { display: none !important; }" in css)
    t.check("sitewide: template/indexes.html carries [data-indexes], a dated trust footer and is registered as IX under Reference in the template site.json",
            'data-page="indexes.html"' in (t.TEMPLATE / "indexes.html").read_text(encoding="utf-8") and 'data-reviewed="2026-11-07"' in (t.TEMPLATE / "indexes.html").read_text(encoding="utf-8")
            and any(p.get("file") == "indexes.html" and p.get("num") == "IX" and p.get("group") == "Reference" for p in treg.get("pages", [])))
# ==== END sitewide ====



# ==== BLOCK pages — C12 concept map · E6 changelog and version stamp · F4 study planner ====
@feature_test
def pages_features(t):
    """C12 concept map · E6 changelog + version stamp · F4 study planner: scaffold parsing, data.js keys, validator
    messages (PASS and FAIL per message), template pages, static app.js checks."""
    topic, sj, reg = t.topic, t.sj, t.reg
    gl_json = topic / "assets" / "glossary.json"
    cl_json = topic / "assets" / "changelog.json"
    gl_text = gl_json.read_text(encoding="utf-8")

    def write_reg(obj):
        sj.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def data_js():
        txt = (topic / "assets" / "data.js").read_text(encoding="utf-8")
        return json.loads(txt.split("window.QC_DATA = ", 1)[1].rstrip().rstrip(";"))

    def validate(*args):   # not --quiet: the problem lines are what the FAIL cases look for
        return t.run("validate.py", topic, "--pages", "index.html", *args)

    try:
        # ---- F4/E6 scaffold.py: `**Version**:` header -> site.json version; optional `Hours` column -> pages[].hours
        plan_text = (t.tmp / "SITE_PLAN.md").read_text(encoding="utf-8")
        hp = t.mutate(plan_text, "**Status**: Draft", "**Version**: 1.2\n**Status**: Draft")
        hp = t.mutate(hp, "| Writer | Size | Status |", "| Writer | Size | Hours | Status |")
        hp = t.mutate(hp, "|---|---|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|---|---|---|---|")
        hp = t.mutate(hp, "| W0 | 30–50 KB | [ ] |", "| W0 | 30–50 KB | | [ ] |")
        hp = t.mutate(hp, "| W1 | 90–140 KB | [ ] |", "| W1 | 90–140 KB | 20–30 | [ ] |")
        hp = t.mutate(hp, "| W9 | 20 KB | [ ] |", "| W9 | 20 KB | 2 | [ ] |")
        hplan = t.WORK / "SITE_PLAN_pages.md"
        hplan.write_text(hp, encoding="utf-8")
        hsite = t.WORK / "site-pages"
        code, out = t.run("scaffold.py", hsite, "--plan", hplan)
        hreg = json.loads((hsite / "assets" / "site.json").read_text(encoding="utf-8")) if (hsite / "assets" / "site.json").exists() else {}
        hours = {p["file"]: p.get("hours") for p in hreg.get("pages", [])}
        t.check("pages: scaffold --plan writes site.json version from **Version** and pages[].hours from the Hours column (range -> midpoint)",
                code == 0 and hreg.get("version") == "1.2" and hours.get("m01-introduction.html") == 25 and hours.get("glossary.html") == 2
                and "hours" not in next(p for p in hreg.get("pages", [{}]) if p.get("file") == "index.html"), out + json.dumps(hreg)[:400])
        t.check("pages: scaffold copies and registers concepts.html and changelog.html (Reference, CM/CL)",
                (hsite / "pages" / "concepts.html").exists() and (hsite / "pages" / "changelog.html").exists()
                and {(p["file"], p["num"], p["group"]) for p in hreg.get("pages", []) if p["file"] in ("concepts.html", "changelog.html")}
                == {("concepts.html", "CM", "Reference"), ("changelog.html", "CL", "Reference")}, json.dumps(hreg.get("pages"))[:600])
        bad = t.mutate(hp, "| 90–140 KB | 20–30 |", "| 90–140 KB | soon |")
        hplan.write_text(bad, encoding="utf-8")
        code, out = t.run("scaffold.py", t.WORK / "site-pages-bad", "--plan", hplan)
        ln = t.line_no(bad, "| soon |")
        t.check(f"pages: scaffold rejects a non-numeric Hours cell (line {ln})", code == 1 and f":{ln} Hours `soon` must be a number or a range like `20–30`" in out, out)

        # ---- builders: data.js keys concepts / changelog / planner on the pages/ topic
        gl = json.loads(gl_text)
        atlas_learn = next(g for g in gl if g["term"] == "atlaspedia")
        atlas_learn["related"] = ["Topic", "Nope"]
        gl_json.write_text(json.dumps(gl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        cl_json.write_text(json.dumps([
            {"date": "2026-11-01", "version": "1.0", "note": "first build", "pages": ["m02-kinds.html"]},
            {"date": "2026-11-07", "version": "1.1", "note": "fix round 1", "pages": ["index.html", "m02-kinds.html"]},
        ], indent=2) + "\n", encoding="utf-8")
        reg2 = json.loads(json.dumps(reg))
        reg2["version"] = "1.1"
        write_reg(reg2)
        code, out = t.run("build_site_data.py", topic)
        r = t.result_of(out)
        d = data_js()
        concepts, changelog, planner = d.get("concepts") or {}, d.get("changelog") or {}, d.get("planner") or {}
        node = next((n for n in concepts.get("nodes", []) if n.get("id") == "gl-atlaspedia"), None)
        edges = concepts.get("edges", [])
        t.check("pages: build_site_data PASS with keys concepts, changelog, planner",
                code == 0 and r.get("status") == "PASS" and all(k in r.get("keys", "").split(",") for k in ("concepts", "changelog", "planner")), out)
        t.check("pages: DATA.concepts nodes {id, term, page, anchor, group} (gl-atlaspedia in group Overview, A–Z)",
                node is not None and node.get("term") == "atlaspedia" and node.get("page") == "index.html" and node.get("anchor") == "executive-summary"
                and node.get("group") == "Overview" and set(node) == {"id", "term", "page", "anchor", "group"}
                and [n["term"].casefold() for n in concepts.get("nodes", [])] == sorted(n["term"].casefold() for n in concepts.get("nodes", [])), json.dumps(node))
        t.check("pages: DATA.concepts edges: `related` from glossary.json, `mentions` found in definitions, unknown name warned",
                {"a": "gl-atlaspedia", "b": "gl-topic", "kind": "related"} in edges and any(e.get("kind") == "mentions" for e in edges)
                and all(set(e) == {"a", "b", "kind"} for e in edges) and 'glossary term "atlaspedia": related "Nope" is not a glossary term' in out, out + json.dumps(edges)[:400])
        t.check("pages: DATA.changelog = {version, entries date desc}",
                changelog.get("version") == "1.1" and [e["date"] for e in changelog.get("entries", [])] == ["2026-11-07", "2026-11-01"]
                and changelog["entries"][0]["note"] == "fix round 1" and changelog["entries"][0]["pages"] == ["index.html", "m02-kinds.html"]
                and set(changelog["entries"][0]) == {"date", "version", "note", "pages"}, json.dumps(changelog))
        m02 = next((p for p in planner.get("pages", []) if p.get("file") == "m02-kinds.html"), None)
        t.check("pages: DATA.planner.pages {file, title, num, hours}: hours parsed from the module hero's Study time ≈ 20–30 h -> 25",
                m02 is not None and m02.get("hours") == 25 and m02.get("num") == "02" and set(m02) == {"file", "title", "num", "hours"}
                and not any(p["file"] == "glossary.html" for p in planner.get("pages", [])), json.dumps(planner))
        reg2["pages"] = [dict(p, hours=12) if p["file"] == "m02-kinds.html" else p for p in reg2["pages"]]
        write_reg(reg2)
        t.sync()
        m02 = next((p for p in data_js().get("planner", {}).get("pages", []) if p.get("file") == "m02-kinds.html"), {})
        t.check("pages: registry hours win over the hero (12) and scaffold --sync rebuilds data.js", m02.get("hours") == 12, json.dumps(m02))

        # ---- validator PASS: version, licence, hours, related, changelog all well-formed; RESULT carries version=
        reg2["licence"] = "CC BY-SA 4.0"
        write_reg(reg2)
        t.sync()
        code, out = validate()
        t.check("pages: validate PASS with version, licence, hours and changelog.json; RESULT version=1.1",
                code == 0 and t.result_of(out).get("version") == "1.1" and t.result_of(out).get("site_issues") == "0", out)
        code, out = t.run("validate.py", topic, "--pages", "concepts.html,changelog.html", "--quiet")
        t.check("pages: template pages concepts.html and changelog.html validate in the pages/ layout", code == 0 and t.result_of(out).get("bad_pages") == "0", out)

        # ---- validator FAIL / warning per message
        def expect(name, msg, code_want=1):
            c, o = validate()
            t.check(name, c == code_want and msg in o, o)

        cl_json.write_text('{"date": "2026-11-07"}\n', encoding="utf-8")
        expect("pages: changelog.json not an array FAIL", "changelog.json must be a JSON array")
        cl_json.write_text('["2026-11-07"]\n', encoding="utf-8")
        expect("pages: changelog entry not an object FAIL", "changelog entry #1 must be an object")
        cl_json.write_text(json.dumps([{"date": "2026-13-40", "version": "1.0", "note": "x"}]), encoding="utf-8")
        expect("pages: changelog bad date FAIL", 'changelog entry #1: date "2026-13-40" is not a date')
        cl_json.write_text(json.dumps([{"date": "2026-11-07", "version": 1.0, "note": "x"}]), encoding="utf-8")
        expect("pages: changelog version not a string FAIL", "changelog entry #1: version must be a string")
        cl_json.write_text(json.dumps([{"date": "2026-11-07", "version": "1.0", "pages": "m02-kinds.html"}]), encoding="utf-8")
        expect("pages: changelog pages not a list FAIL", "changelog entry #1: pages must be a list of file names")
        cl_json.write_text(json.dumps([{"date": "2026-11-07", "version": "1.0", "pages": ["m99-nope.html"]}]), encoding="utf-8")
        expect("pages: changelog unknown page is a warning, not a FAIL", "warning: changelog entry #1: unknown page m99-nope.html", 0)
        cl_json.unlink()
        reg3 = json.loads(json.dumps(reg2))
        reg3["version"] = 1.0
        write_reg(reg3)
        t.sync()
        expect("pages: site.json version not a string FAIL", "site.json version must be a string")
        reg3 = json.loads(json.dumps(reg2))
        reg3["licence"] = ["CC BY-SA 4.0"]
        write_reg(reg3)
        t.sync()
        expect("pages: site.json licence not a string FAIL", "site.json licence must be a non-empty string")
        reg3 = json.loads(json.dumps(reg2))
        reg3["pages"] = [dict(p, hours="abc") if p["file"] == "m02-kinds.html" else p for p in reg3["pages"]]
        write_reg(reg3)
        t.sync()
        expect("pages: pages[].hours not a number > 0 FAIL", "m02-kinds.html: hours must be a number > 0")
        write_reg(reg2)
        t.sync()
        expect("pages: unknown `related` name is a warning, not a FAIL", 'warning: glossary term "atlaspedia": related "Nope" is not a glossary term', 0)
        atlas_learn["related"] = "Topic"
        gl_json.write_text(json.dumps(gl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        t.sync()
        expect("pages: `related` not a list is a warning, not a FAIL", 'warning: glossary term "atlaspedia": related must be a list of term names', 0)

        # ---- static checks: app.js features, template pages registered, catalog snippets, styleguide carries them
        app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
        css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
        t.check("pages: app.js registers c12-concept-map (enhance), e6-changelog (post), f4-planner (enhance) and keeps QC.download optional",
                all(f"feature({{\n    name: '{n}'" in app for n in ("c12-concept-map", "e6-changelog", "f4-planner"))
                and "typeof window.QC.download === 'function'" in app and "store.set('pages:planner'" in app
                and app.index("name: 'c12-concept-map', phase: 'enhance'") > app.index("function enhanceDiagrams(main)"), "")
        t.check("pages: style.css pages block defines .site-stamp, .concept-info, .cm-node, .planner, .changelog",
                all(c in css for c in (".site-stamp", ".concept-info", "svg .cm-node", ".planner ", ".changelog ")), "")
        treg = json.loads((t.TEMPLATE / "assets" / "site.json").read_text(encoding="utf-8"))
        t.check("pages: template/assets/site.json registers concepts.html (CM) and changelog.html (CL) under Reference",
                {(p["file"], p["num"], p["group"]) for p in treg["pages"] if p["file"] in ("concepts.html", "changelog.html")}
                == {("concepts.html", "CM", "Reference"), ("changelog.html", "CL", "Reference")} and "concepts.html" in t.AUTO_PAGES and "changelog.html" in t.AUTO_PAGES, "")
        ov = t.PLUGIN / "skills" / "compose" / "components" / "overview"
        t.check("pages: overview snippets planner.html, concept-map.html, changelog.html exist with the header comment and are in INDEX.md",
                all((ov / f).exists() and (ov / f).read_text(encoding="utf-8").startswith(f"<!-- atlaspedia component: overview/{f} · use when:") for f in ("planner.html", "concept-map.html", "changelog.html"))
                and all(f in (t.PLUGIN / "skills" / "compose" / "components" / "INDEX.md").read_text(encoding="utf-8") for f in ("planner.html", "concept-map.html", "changelog.html")), "")
    finally:
        gl_json.write_text(gl_text, encoding="utf-8")
        if cl_json.exists():
            cl_json.unlink()
# ==== END pages ====



# ==== BLOCK pipeline — H1 consistency linter · H4 executed examples · G3 markdown export · I2 learning design · I4 derived policies ====
EXEC_SNIPPET = '''<pre data-executed="2026-11-07" data-env="Python 3.13.17"><code class="language-python">R = 6371.0088   # km
print(f"{R * 2:.1f} km")</code></pre>
<pre class="output"><samp>12742.0 km</samp></pre>'''


@feature_test
def pipeline_features(t):
    """H4 executed examples (snippet, CSS, JS, validator) · H1 consistency lint · G3 export_markdown.py · I4 Licence/A11y
    header lines → site.json (scaffold, validate_a11y) · I2 learning design (prompt files)."""
    run, check, mutate, R = t.run, t.check, t.mutate, t.result_of
    topic, m02, page_m02 = t.topic, t.m02, t.page_m02
    plugin = t.PLUGIN
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    catalog = plugin / "skills" / "compose" / "components"
    snippet_p = catalog / "core" / "code-executed.html"
    snippet = snippet_p.read_text(encoding="utf-8") if snippet_p.exists() else ""

    # ---- H4: static pieces --------------------------------------------------------------------------------------
    check("pipeline: app.js registers feature h4-executed (enhance) and style.css has the executed badge and output block",
          "feature({ name: 'h4-executed'" in app and "phase: 'enhance'" in app and "badge executed" in app
          and ".badge.executed" in css and "pre.output" in css and "pre[data-executed]" in css)
    check("pipeline: core/code-executed.html snippet has the header, a dated executed pre and a pre.output, and INDEX.md lists it",
          snippet.startswith("<!-- atlaspedia component: core/code-executed.html · use when:") and 'data-executed="2026-11-07"' in snippet
          and 'data-env="' in snippet and '<pre class="output"><samp>' in snippet
          and "code-executed.html" in (catalog / "INDEX.md").read_text(encoding="utf-8")
          and "H4 executed examples" in (catalog / "core" / "README.md").read_text(encoding="utf-8"))

    # ---- H4: validator ------------------------------------------------------------------------------------------
    intro = '<h2 id="introduction">Conceptual introduction</h2>\n    <p>…</p>'
    exec_page = mutate(m02, intro, intro + "\n    " + EXEC_SNIPPET)
    page_m02.write_text(exec_page, encoding="utf-8")
    code, out = run("validate.py", topic, "--pages", "m02-kinds.html")
    check("pipeline: executed example with output block PASS (no H4 warning)", code == 0 and R(out).get("bad_pages") == "0"
          and "executed example" not in out and "output block" not in out, out)

    def h4_fail(name, text, msg):
        page_m02.write_text(text, encoding="utf-8")
        c, o = run("validate.py", topic, "--pages", "m02-kinds.html")
        check(name, c == 1 and msg in o, o)

    h4_fail("pipeline: executed example without an output block FAIL",
            mutate(exec_page, '<pre class="output"><samp>12742.0 km</samp></pre>', '<p>12742.0 km</p>'), "executed example without an output block")
    h4_fail("pipeline: executed example with an output block that is not pre.output FAIL",
            mutate(exec_page, '<pre class="output"><samp>', '<pre class="result"><samp>'), "executed example without an output block")
    h4_fail("pipeline: data-executed not a date FAIL",
            mutate(exec_page, 'data-executed="2026-11-07"', 'data-executed="2026-13-40"'), 'data-executed "2026-13-40" is not a date')
    page_m02.write_text(mutate(exec_page, ' data-executed="2026-11-07" data-env="Python 3.13.17"', ''), encoding="utf-8")
    code, out = run("validate.py", topic, "--pages", "m02-kinds.html")
    check("pipeline: output block without an executed example is a warning, not a FAIL",
          code == 0 and "warning: output block without an executed example" in out, out)
    page_m02.write_text(mutate(exec_page, ' data-env="Python 3.13.17"', ''), encoding="utf-8")
    code, out = run("validate.py", topic, "--pages", "m02-kinds.html")
    check("pipeline: executed example without data-env is a warning, not a FAIL",
          code == 0 and "warning: executed example without data-env" in out, out)

    # ---- G3: export_markdown.py on the pages/ topic ------------------------------------------------------------
    rich = mutate(exec_page, '<h2 id="deliverable">Deliverable</h2>\n    <p>…</p>',
                  '<h2 id="deliverable">Deliverable</h2>\n    <p>Scale factor \\( k = \\sec\\varphi \\) at <dfn>Nuuk</dfn>; see <a class="xref" href="glossary.html#gl-gate">Glossary · gate</a>.</p>\n'
                  '    <div class="callout note"><span class="callout-title">Convention</span><p>Latitude φ in degrees.</p></div>\n'
                  '    <table class="compact"><thead><tr><th>City</th><th class="num">k</th></tr></thead><tbody><tr><td>Hanoi</td><td class="num">1.071</td></tr><tr><td>Nuuk | capital</td><td class="num">2.296</td></tr></tbody></table>')
    page_m02.write_text(rich, encoding="utf-8")
    exp = t.WORK / "pipeline-export"
    if exp.exists():
        shutil.rmtree(exp)
    code, out = run("export_markdown.py", topic, "--out", exp, "--lms")
    r = R(out)
    md = (exp / "m02-kinds.md").read_text(encoding="utf-8") if (exp / "m02-kinds.md").exists() else ""
    svg_p = exp / "figures" / "m02-kinds-fig-steps.svg"
    svg = svg_p.read_text(encoding="utf-8") if svg_p.exists() else ""
    n_pages = len([p for p in topic.glob("*.html") if not p.name.startswith("_")]) + len([p for p in (topic / "pages").glob("*.html") if not p.name.startswith("_")])
    check("pipeline: export_markdown PASS — one .md per page, home.md for the overview, index.md, figures/, imsmanifest.xml, RESULT keys",
          code == 0 and r.get("status") == "PASS" and r.get("pages") == str(n_pages) and int(r.get("figures", "0")) >= 1 and r.get("lms") == "yes"
          and "out=" in out and (exp / "index.md").exists() and (exp / "home.md").exists() and (exp / "glossary.md").exists()
          and not (exp / "index.html").exists() and svg_p.exists() and (exp / "imsmanifest.xml").exists(), out)
    check("pipeline: export — front matter, {#id} headings, objectives list, diagram figure link + caption + step captions",
          md.startswith("---\ntitle: Kind skeleton test\n") and "\nlevel: 1\n" in md and "\nreviewed: \"2026-11-07\"\n" in md and "\nverified: \"1/1\"\n" in md
          and "## Learning objectives {#objectives}" in md and "\n1. …\n2. …" in md
          and "![Figure 2.1 — Predict–update cycle. Step through it.](figures/m02-kinds-fig-steps.svg)" in md
          and "**Figure 2.1 — Predict–update cycle.** Step through it." in md and "1. Prediction propagates the state." in md, md[:1500])
    check("pipeline: export — executed code block with label and output, inline maths, callout blockquote, pipe table with escaped pipe, rewritten link",
          "*Executed 2026-11-07 · Python 3.13.17*\n\n```python\nR = 6371.0088   # km" in md and "Output:\n\n```text\n12742.0 km\n```" in md
          and "$k = \\sec\\varphi$" in md and "**Nuuk**" in md and "[Glossary · gate](glossary.md#gl-gate)" in md
          and "> **Convention**\n>\n> Latitude φ in degrees." in md
          and "| City | k |\n| --- | ---: |\n| Hanoi | 1.071 |\n| Nuuk \\| capital | 2.296 |" in md, md)
    check("pipeline: export — quiz with answer in details, exercise heading with hints and solution in details, trust section",
          "**Checkpoint.** Question?\n\n1. Correct option\n2. Distractor" in md and "<details><summary>Answer</summary>\n\n**1.** Correct option — Why the answer is correct." in md
          and "#### Exercise NN.1 {#ex-NN-1}" in md and "*difficulty 2 of 3 · ≈ 20 min*" in md and "<details><summary>Hint 1</summary>" in md
          and "<details><summary>Solution</summary>\n\nWorked solution" in md and "## Trust {#trust}\n\n- Sources verified: 1 / 1\n- Reviewed: 2026-11-07" in md
          and "- Open gaps: 1" in md and md.rstrip().endswith("delete this whole details block when there are none."), md)
    check("pipeline: export — standalone SVG carries xmlns, the template's d-* styles and the arrow markers",
          svg.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg"') and "<style>" in svg
          and "svg .d-box {" in svg and "--data: #2563eb" in svg and 'marker id="arr-data"' in svg and 'data-step="2"' in svg, svg[:400])
    idx = (exp / "index.md").read_text(encoding="utf-8")
    man = (exp / "imsmanifest.xml").read_text(encoding="utf-8")
    check("pipeline: export — index.md outline links every page in registry order; imsmanifest.xml lists the HTML pages as web content",
          "[02 · Kind skeleton test](m02-kinds.md)" in idx and "[00 · Research Overview](home.md)" in idx and "### Foundations" in idx
          and "<schema>IMS Common Cartridge</schema>" in man and 'type="webcontent" href="pages/m02-kinds.html"' in man
          and 'href="index.html"' in man and '<title>02 · Kind skeleton test</title>' in man and 'identifier="res_assets"' in man, idx + man[:600])
    code, out = run("export_markdown.py", topic, "--out", exp, "--pages", "m02-kinds.html", "--no-solutions", "--quiet")
    md2 = (exp / "m02-kinds.md").read_text(encoding="utf-8")
    check("pipeline: export --pages --no-solutions — one page, hints kept, solution and quiz answer omitted",
          code == 0 and R(out).get("pages") == "1" and "<summary>Hint 1</summary>" in md2 and "<summary>Solution</summary>" not in md2
          and "<summary>Answer</summary>" not in md2 and "solutions omitted" in (exp / "index.md").read_text(encoding="utf-8"), out)
    code, out = run("export_markdown.py", topic, "--out", exp, "--pages", "nope.html")
    check("pipeline: export --pages with an unknown page FAIL", code == 1 and "--pages names nope.html but it does not exist" in out, out)
    code, out = run("export_markdown.py", topic, "--out", topic / "assets")
    check("pipeline: export refuses --out inside assets/", code == 2, out)

    # ---- H1: consistency lint (site-level warnings, lint=n) -------------------------------------------------------
    page_m02.write_text(m02, encoding="utf-8")
    code, out = run("validate.py", topic, "--pages", "m02-kinds.html", "--quiet")
    check("pipeline: lint — the clean skeleton page reports lint=0", code == 0 and R(out).get("lint") == "0", out)
    gl_p = topic / "assets" / "glossary.json"
    gl_orig = gl_p.read_text(encoding="utf-8")
    gl = json.loads(gl_orig)
    gl.append({"term": "Web Mercator", "aka": "EPSG:3857", "def": "The spherical Mercator variant used by web map tiles.", "page": "m02-kinds.html", "anchor": "introduction"})
    gl.append({"term": "Scale factor", "def": "How much a map stretches distances at a point.", "page": "m02-kinds.html", "anchor": "introduction"})
    gl_p.write_text(json.dumps(gl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (topic / "assets" / "notation.json").write_text(json.dumps([{"symbol": "λ", "tex": "\\lambda", "meaning": "longitude", "unit": "rad"}]) + "\n", encoding="utf-8")
    lint_m02 = mutate(m02, intro, intro + '\n    <p>Web Mercator is conformal; a step takes 5 ms. A <dfn>Tissot indicatrix</dfn> shows the distortion, the <dfn>scale factors</dfn> grow polewards.</p>')
    lint_m03 = mutate(m02, 'data-page="m02-kinds.html"', 'data-page="m03-lint.html"')
    lint_m03 = mutate(lint_m03, intro, intro + '\n    <p>The web mercator projection stops at 85°; a step takes 7 msec and the loop runs at 50 Hz, 2 h in total.</p>'
                      '\n    <table class="notation"><thead><tr><th>Symbol</th><th>Meaning</th></tr></thead><tbody><tr><td class="sym">\\( \\lambda \\)</td><td>longitude</td></tr><tr><td class="sym">φ</td><td>latitude</td></tr></tbody></table>')
    page_m02.write_text(lint_m02, encoding="utf-8")
    page_m03 = topic / "pages" / "m03-lint.html"
    page_m03.write_text(lint_m03, encoding="utf-8")
    reg2 = json.loads(json.dumps(t.reg))
    reg2["pages"].append({"file": "m03-lint.html", "num": "03", "title": "Lint test", "group": "Foundations", "level": 1, "desc": "A second page for the consistency lint."})
    t.sj.write_text(json.dumps(reg2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run("scaffold.py", topic, "--sync")
    code, out = run("validate.py", topic, "--pages", "m02-kinds.html,m03-lint.html")
    r = R(out)
    want = ['warning: dfn "Tissot indicatrix" (m02) is not in glossary.json',
            'warning: term "Web Mercator" is written as "Web Mercator" (m02) and "web mercator" (m03)',
            'warning: unit written as "ms" (m02) and "msec" (m03)',
            'warning: notation symbol "φ" (m03) is not in assets/notation.json']
    missing = [w for w in want if w not in out]
    check("pipeline: lint — dfn missing, two spellings of a glossary term, unit variants, unlisted notation symbol (warnings, lint=4, still PASS)",
          code == 0 and r.get("lint") == "4" and not missing and 'dfn "scale factors"' not in out and 'symbol "\\( \\lambda \\)"' not in out
          and 'notation symbol "λ"' not in out and '"Hz"' not in out, out + "\nMISSING: " + " | ".join(missing))
    page_m03.unlink()
    (topic / "assets" / "notation.json").unlink()
    gl_p.write_text(gl_orig, encoding="utf-8")

    # ---- I4: Licence / A11y header lines → site.json, validate_a11y --------------------------------------------
    plan_text = (t.tmp / "SITE_PLAN.md").read_text(encoding="utf-8")
    plan_text = "\n".join(l for l in plan_text.splitlines() if not l.startswith("| m01-introduction.html")) + "\n"
    i4_plan = t.WORK / "SITE_PLAN_i4.md"
    i4_site = t.WORK / "pipeline-i4"
    i4_plan.write_text(mutate(plan_text, "**Status**: Draft", "**Licence**: CC BY-SA 4.0\n**A11y**: font dyslexic · scale 1.15 · motion reduced · contrast high\n**Status**: Draft"), encoding="utf-8")
    code, out = run("scaffold.py", i4_site, "--plan", i4_plan)
    sj4 = i4_site / "assets" / "site.json"
    reg4 = json.loads(sj4.read_text(encoding="utf-8")) if sj4.exists() else {}
    check("pipeline: scaffold writes site.json licence and a11y from the Licence / A11y header lines",
          code == 0 and reg4.get("licence") == "CC BY-SA 4.0" and reg4.get("a11y") == {"font": "dyslexic", "scale": 1.15, "motion": "reduced", "contrast": "high"}, out)
    code, out = run("validate.py", i4_site, "--quiet")
    check("pipeline: validate PASS with licence + a11y in site.json", code == 0 and R(out).get("site_issues") == "0", out)
    i4_plan.write_text(mutate(plan_text, "**Status**: Draft", "**A11y**: scale 2 · colour high\n**Status**: Draft"), encoding="utf-8")
    code, out = run("scaffold.py", i4_site, "--plan", i4_plan, "--force")
    check("pipeline: scaffold rejects an A11y line with a bad value and an unknown part",
          code == 1 and "A11y scale must be 1, 1.15 or 1.3 (got `2`)" in out and "A11y part `colour high` must be `font|scale|motion|contrast <value>`" in out, out)
    bad4 = dict(reg4, licence=5, a11y={"font": "comic", "scale": 1.3, "motion": "fast", "extra": 1})
    sj4.write_text(json.dumps(bad4, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    code, out = run("scaffold.py", i4_site, "--sync")
    check("pipeline: scaffold --sync reports bad a11y values", code == 1 and 'a11y.font must be default or dyslexic (got "comic")' in out, out)
    code, out = run("validate.py", i4_site)
    check("pipeline: validate FAIL on bad licence type and bad a11y values (unknown key is a warning)",
          code == 1 and "site.json licence must be a non-empty string (got 5)" in out and 'a11y.font must be default or dyslexic (got "comic")' in out
          and 'a11y.motion must be normal or reduced (got "fast")' in out and "warning: a11y.extra is not an a11y key" in out
          and R(out).get("site_issues") == "3", out)
    shutil.rmtree(i4_site, ignore_errors=True)

    # ---- I2 / I4: prompt files carry the learning design and the policy rows ----------------------------------
    rd = lambda *p: (plugin.joinpath(*p)).read_text(encoding="utf-8")
    brief_t = rd("skills", "research", "references", "brief-template.md")
    check("pipeline: brief template has §13 Learning design (outcomes, assessment, hours, prerequisites) and the five policy rows",
          "## 13. Learning design" in brief_t and "Outcomes:" in brief_t and "Assessment:" in brief_t and "Hours:" in brief_t and "Prerequisites:" in brief_t
          and all(f"| {row} |" in brief_t for row in ("Must cite", "Must avoid", "Citation style", "Licence", "Accessibility")) and "Must cite (searched first" in brief_t)
    check("pipeline: brief author writes §13 and the policy lines; brief reviewer checks observable outcomes with an assessment",
          "§13 learning design" in rd("agents", "brief-author.md") and "Must cite" in rd("agents", "brief-author.md")
          and "Learning design (I2)" in rd("agents", "brief-reviewer.md") and "every outcome has an assessment" in rd("agents", "brief-reviewer.md"))
    ins_t = rd("skills", "collect-insights", "references", "insights-template.md")
    guide = rd("skills", "collect-insights", "references", "interview-guide.md")
    check("pipeline: INSIGHTS template, interview guide §3 and the refiner carry Must cite / Must avoid / Citation style / Licence / Accessibility",
          all(f"| {row} |" in ins_t for row in ("Must cite", "Must avoid", "Citation style", "Licence", "Accessibility"))
          and all(f"| {row} |" in guide for row in ("Must cite", "Must avoid", "Citation style", "Licence", "Accessibility"))
          and "all rights reserved, personal use" in ins_t and all(k in rd("agents", "insight-refiner.md") for k in ("Must cite", "Must avoid", "Citation style", "Licence", "Accessibility")))
    sk = rd("skills", "compose", "SKILL.md")
    check("pipeline: compose skill derives **Licence** / **A11y** header lines, hands over Hours + outcomes (I2), names executed examples (H4) and the export (G3)",
          "**Licence**:" in sk and "**A11y**:" in sk and "**I2 learning design**" in sk and "`Hours` column" in sk and "**H4 executed examples**" in sk
          and "export_markdown.py" in sk and "**H1 consistency lint**" in sk)
    check("pipeline: authoring rules §7 executed examples + §8 lint, page-writer and site-reviewer bullets, research protocol paragraph, contracts rows",
          "## 7. Executed examples (H4)" in rd("skills", "compose", "references", "authoring-rules.md") and "## 8. Consistency lint (H1" in rd("skills", "compose", "references", "authoring-rules.md")
          and "**H4 executed examples**" in rd("agents", "page-writer.md") and "**I2 learning design**" in rd("agents", "page-writer.md")
          and "7d. **H1 consistency lint**" in rd("agents", "site-reviewer.md") and "7e. **H4 executed examples**" in rd("agents", "site-reviewer.md")
          and "**I4 must-cite, must-avoid and citation style.**" in rd("skills", "research", "references", "research-protocol.md")
          and "`export_markdown.py`" in rd("references", "contracts.md") and "## 13. Learning design" in rd("references", "contracts.md")
          and "`**A11y**:" in rd("references", "contracts.md") and "lint=n" in rd("references", "contracts.md"))
# ==== END pipeline ====


# ==== BLOCK protocol — C2 timing/waveform diagrams · C3 bit-field/packet diagrams · C4 sequence diagrams and state machines ====
@feature_test
def protocol_feature_tests(t) -> None:
    """C2 timing · C3 bit field · C4 sequence and state machine: the four catalog snippets validate (data scripts skip the
    node check), every error and warning names its line, a <pre> source works, and node runs the runtime's parsers and
    renderers (extracted between protocol:begin and protocol:end) against the Python mirror."""
    cat = t.PLUGIN / "skills" / "compose" / "components"
    snips = ["timing.html", "bitfield.html", "sequence.html", "fsm.html"]
    figs = local_refs("\n".join((cat / "protocol" / f).read_text(encoding="utf-8").split("\n", 1)[1].rstrip() for f in snips))
    anchor = "Step through it.</figcaption>\n    </figure>"
    page = t.mutate(t.m02, anchor, anchor + "\n" + figs)
    t.page_m02.write_text(page, encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    r = t.result_of(out)
    t.check("protocol: timing + bitfield + sequence + fsm snippets PASS without warnings", code == 0 and r.get("bad_pages") == "0" and "warning:" not in out.replace("not checked", ""), out)
    if t.node:
        t.check("protocol: JSON and text/plain scripts are not syntax-checked as JavaScript", r.get("js_syntax") == "checked" and "inline script" not in out, out)

    def run_page(text: str):
        t.page_m02.write_text(text, encoding="utf-8")
        return t.run("validate.py", t.topic, "--pages", "m02-kinds.html")

    def fail(name: str, old: str, new: str, needle: str, msg: str) -> None:
        text = t.mutate(page, old, new)
        c, o = run_page(text)
        ln = t.line_no(text, needle)
        t.check(name + f" (line {ln})", c == 1 and f":{ln} {msg}" in o, o)

    def warn(name: str, old: str, new: str, needle: str, msg: str) -> None:
        text = t.mutate(page, old, new)
        c, o = run_page(text)
        ln = t.line_no(text, needle)
        t.check(name + f" (line {ln})", c == 0 and f":{ln} warning: {msg}" in o, o)

    T, B, S, F = "timing fig-spi-mode1: ", "bitfield fig-ipv4-header: ", "sequence fig-tls13-handshake: ", "fsm fig-debounce-fsm: "
    fail("protocol: timing invalid JSON FAIL", '"config": { "hscale": 1.5 } }', '"config": { "hscale": 1.5 }, }', '"config"', T + "invalid JSON: ")
    fail("protocol: timing unknown wave character FAIL", '"0.ppp|ppp0."', '"0.ppq|ppp0."', '"SCLK"', T + 'signal "SCLK": unknown wave character "q"')
    fail("protocol: timing fewer data labels than bus cells FAIL", '"S2", "S1", "S0"]', '"S2", "S1"]', '"MISO"', T + 'signal "MISO": 5 data labels for 6 bus cells')
    fail("protocol: timing config.hscale 0 FAIL", '"hscale": 1.5', '"hscale": 0', '{ "signal": [', T + "config.hscale must be a number > 0")
    fail("protocol: timing without a signal array FAIL", '{ "signal": [', '{ "signals": [', '"signals"', T + 'JSON needs a "signal" array')
    fail("protocol: timing entry that is not an object FAIL", '{ "name": "nCS",  "wave": "10........1", "node": ".a" },', '"nCS", { "name": "nCS",  "wave": "10........1", "node": ".a" },', '{ "signal": [', T + "every signal entry must be an object or a group array")
    fail("protocol: timing without a JSON script FAIL", '<figure class="timing" id="fig-spi-mode1" data-cite="#ref-key">\n  <script type="application/json">', '<figure class="timing" id="fig-spi-mode1" data-cite="#ref-key">\n  <script type="application/x-json">',
         '<figure class="timing"', 'timing fig-spi-mode1 has no <script type="application/json"> source')
    fail("protocol: bitfield zero width FAIL", '{ "name": "ECN", "bits": 2 }', '{ "name": "ECN", "bits": 0 }', '"ECN"', B + 'field 4 "ECN": bits must be a whole number > 0')
    fail("protocol: bitfield negative width FAIL", '{ "name": "Identification", "bits": 16 }', '{ "name": "Identification", "bits": -16 }', '"Identification"', B + 'field 6 "Identification": bits must be a whole number > 0')
    fail("protocol: bitfield fractional width FAIL", '{ "name": "DSCP", "bits": 6 }', '{ "name": "DSCP", "bits": 5.5 }', '"DSCP"', B + 'field 3 "DSCP": bits must be a whole number > 0')
    fail("protocol: bitfield lanes 0 FAIL", '{ "lanes": 32, "msbFirst": true,', '{ "lanes": 0, "msbFirst": true,', '"lanes"', B + "lanes must be a whole number > 0")
    fail("protocol: bitfield unknown unit FAIL", '{ "lanes": 32, "msbFirst": true,', '{ "lanes": 32, "msbFirst": true, "unit": "word",', '"lanes"', B + 'unit "word" must be bit or byte')
    fail("protocol: bitfield empty fields FAIL", '"fields": [\n    { "name": "Version"', '"fields": [], "x": [\n    { "name": "Version"', '"lanes"', B + 'JSON needs a non-empty "fields" array')
    fail("protocol: bitfield invalid JSON FAIL", '{ "name": "IHL", "bits": 4, "attr": "5 words", "type": 3 },', '{ "name": "IHL", "bits": 4 "attr": "5 words", "type": 3 },', '"IHL"', B + "invalid JSON: ")
    fail("protocol: sequence line that does not parse FAIL", "C->>S: {Finished}", "C=>S: {Finished}", "C=>S", S + "line does not parse: C=>S: {Finished}")
    fail("protocol: sequence else outside alt FAIL", "alt status not stapled", "opt status not stapled", "else status stapled", S + '"else" outside an alt block')
    text = t.mutate(page, "C-xS: close_notify (lost when the link drops)", "C-xS: close_notify (lost when the link drops)\nend")
    c, o = run_page(text)
    t.check("protocol: sequence end without a block FAIL", c == 1 and f":{t.line_no(text, 'C-xS') + 1} {S}\"end\" without loop, alt or opt" in o, o)
    fail("protocol: sequence loop never closed FAIL", "  S-->>C: [application data]\nend\n", "  S-->>C: [application data]\n", "loop every request", S + '"loop" is never closed with "end"')
    fail("protocol: fsm line that does not parse FAIL", "MaybePressed --> Released : raw 0", "MaybePressed -> Released : raw 0", "MaybePressed -> Released", F + "line does not parse: MaybePressed -> Released : raw 0")
    fail("protocol: fsm transition from [*] to [*] FAIL", "[*] --> Released\n", "[*] --> Released\n[*] --> [*]\n", "[*] --> [*]", F + "a transition from [*] to [*]")
    fail("protocol: sequence without a source FAIL", '<figure class="seq" id="fig-tls13-handshake" data-cite="#ref-key">\n  <script type="text/plain">', '<figure class="seq" id="fig-tls13-handshake" data-cite="#ref-key">\n  <script type="text/x-seq">',
         '<figure class="seq"', 'sequence fig-tls13-handshake has no <script type="text/plain"> or <pre> source')
    warn("protocol: timing signals of unequal length WARN", '"wave": "z.===|===z."', '"wave": "z.===|===z"', '"MISO"', T + 'signal "MISO" has 10 cycles, the longest has 11')
    text = t.mutate(page, '"a->b t_lead', '"a->q t_lead')
    c, o = run_page(text)
    t.check("protocol: timing edge to an unknown node WARN", c == 0 and "warning: " + T + 'edge "a->q t_lead ≥ 50 ns" names a node no signal defines' in o, o)
    warn("protocol: bitfield widths not filling the rows WARN", '{ "name": "Destination Address", "bits": 32, "type": 5 }', '{ "name": "Destination Address", "bits": 30, "type": 5 }', '"lanes"', B + "158 bits do not fill rows of 32 (last row 30)")
    warn("protocol: sequence message to an undeclared participant WARN", "participant R as OCSP responder\n", "", "C->>R:", S + 'message to undeclared participant "R"')
    warn("protocol: fsm without an initial transition WARN", "[*] --> Released\n", "", "stateDiagram-v2", F + "no initial [*] transition")
    # a <pre> source (HTML-escaped) parses like a script source and reports its own lines
    pre = '<figure class="fsm" id="fsm-pre" data-cite="#ref-key">\n  <pre>\n[*] --&gt; Idle\nIdle --&gt; Run : start\nRun --&gt; Idle : stop &amp; reset\n  </pre>\n  <figcaption><b>Figure 9.9 — Pre.</b> x</figcaption>\n</figure>'
    c, o = run_page(page.replace(anchor, anchor + "\n" + pre))
    t.check("protocol: fsm in a <pre> PASS", c == 0 and "fsm-pre" not in o, o)
    bad = page.replace(anchor, anchor + "\n" + pre.replace("Idle --&gt; Run : start", "Idle =&gt; Run"))
    c, o = run_page(bad)
    t.check("protocol: fsm in a <pre> with a bad line FAIL", c == 1 and f":{t.line_no(bad, 'Idle =&gt; Run')} fsm fsm-pre: line does not parse: Idle => Run" in o, o)
    # catalog, docs, runtime and style
    index = (cat / "INDEX.md").read_text(encoding="utf-8")
    t.check("protocol: catalog module protocol/ complete and listed in INDEX.md", all((cat / "protocol" / f).exists() for f in snips + ["README.md"])
            and re.search(r"^\| `protocol` \|", index, re.M) is not None and all(f in index for f in snips))
    readme = (cat / "protocol" / "README.md").read_text(encoding="utf-8")
    t.check("protocol: README documents the four grammars and the messages",
            all(k in readme for k in ("figure.timing", "figure.bitfield", "figure.seq", "figure.fsm", "hscale", "msbFirst", '"byte"', "autonumber", "note over", "[*] -->",
                                      "unknown wave character", "data labels for", "bits must be a whole number > 0", "do not fill rows of", "line does not parse",
                                      '"else" outside an alt block', "never closed", "undeclared participant", "no initial [*] transition")))
    skill = (t.PLUGIN / "skills" / "compose" / "SKILL.md").read_text(encoding="utf-8")
    t.check("protocol: compose SKILL.md derivation table names protocol", "`protocol` when the page covers a protocol, bus, register layout or message exchange" in skill)
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    block = app[app.index("==== BLOCK protocol"):app.index("==== END protocol")]
    t.check("protocol: app.js renders in the shell phase, as figure.diagram, with title and desc, and exposes QC.protocol",
            "feature({ name: 'protocol', phase: 'shell'" in block and "fig.classList.add('diagram')" in block and "<desc id=" in block
            and "aria-labelledby" in block and "api: { protocol:" in block and "eval(" not in block and "Function(" not in block)
    t.check("protocol: style.css block defines the drawing classes, no hex colours",
            all(k in css for k in (".proto-error", "svg .tm-wave", "svg .tm-x", "svg .tm-gap", "svg .bf-box", "svg .bf-rsv", "svg .sq-life", "svg .sq-note", "svg .sq-frame", "svg .fsm-start", "svg .pr-c3"))
            and not re.search(r"#[0-9a-fA-F]{3,8}\b", css[css.index("==== BLOCK protocol"):css.index("==== END protocol")]))
    if not t.node:
        print("      (protocol node checks skipped: node not on PATH)")
        return
    m = re.search(r"/\* protocol:begin[\s\S]*?/\* protocol:end \*/", app)
    srcs = {f: re.search(r"<script[^>]*>([\s\S]*?)</script>", (cat / "protocol" / f).read_text(encoding="utf-8")).group(1) for f in snips}
    seq_cases = ["participant A\nA->>B: hi\nloop x\nfoo bar\nelse\nend\nend", "alt a\nA->>B: x\nelse b\nloop c\nend", "participant A as Alpha\nA-->>B: x\nnote right of C: y", ""]
    fsm_cases = ["A --> B\nA -> B", "stateDiagram\n[*] --> [*]", "state X\nX : idle", "%% nothing", "direction TB\n[*] --> A\nA --> [*]"]
    harness = (m.group(0) if m else "") + "\nconst SRC = " + json.dumps(srcs) + ", SEQ = " + json.dumps(seq_cases) + ", FSM = " + json.dumps(fsm_cases) + r""";
const res = {};
const t = PR.timing(JSON.parse(SRC['timing.html']), 'fig-t'), b = PR.bitfield(JSON.parse(SRC['bitfield.html'])), s = PR.seq(SRC['sequence.html']), f = PR.fsm(SRC['fsm.html']);
res.summaries = [t.summary, b.summary, s.summary, f.summary];
res.tparts = ['fill="url(#fig-t-hatch)"', 'class="tm-gap"', '>R/W<', 'marker-end="url(#arr-accent)"', 'class="tm-group"'].map(k => t.body.includes(k));
res.bparts = ['class="bf-field bf-rsv"', '>Destination Address<', '6 = TCP, 17 = UDP', '+16'].map(k => b.body.includes(k));
res.sparts = ['class="sq-frame"', 'class="sq-x"', 'class="sq-num"', 'd-line sq-msg d-dash', '>[status stapled]<', 'class="sq-note"'].map(k => s.body.includes(k));
res.fparts = ['fsm-back', 'class="fsm-start"', 'C', 'Maybe pressed'].map(k => f.body.includes(k));
const x = PR.seq('participant A as <img src=x onerror=alert(1)>\nA->>B: a & b <script>'), y = PR.fsm('[*] --> A\nA --> B : "q" <b>'), z = PR.timing({ signal: [{ name: '<i>', wave: '=', data: ['</text><script>'] }] }, 'z'), w = PR.bitfield({ fields: [{ name: '<svg onload=1>', bits: 8 }] });
res.escaped = [x.body, y.body, z.body, w.body].every(h => !/<(img|script|b|i|svg)[\s>]/.test(h)) && x.body.includes('&lt;img') && y.body.includes('&quot;q&quot;');
res.wide = PR.bitfield({ lanes: 8, unit: 'byte', fields: [{ name: 'Preamble', bits: 7 }, { name: 'SFD', bits: 1 }, { name: 'Destination MAC', bits: 6 }, { name: 'Source MAC', bits: 6 }, { name: 'EtherType', bits: 2 }] }).summary;
res.throws = [() => PR.timing({ signal: [{ name: 'a', wave: '01q' }] }), () => PR.timing({}), () => PR.timing({ signal: [], config: { hscale: -1 } }), () => PR.bitfield({ fields: [{ name: 'a', bits: 0 }] }),
  () => PR.bitfield({ fields: [{ bits: 2 }], lanes: 0 }), () => PR.seq('A=>B'), () => PR.fsm('A -> B')].map(fn => { try { fn(); return 'no error'; } catch (e) { return e.message; } });
res.seq = SEQ.map(src => { const p = PR.parseSeq(src); return [p.errors.map(e => [e.ln, e.msg]), p.warnings.map(e => [e.ln, e.msg])]; });
res.fsm = FSM.map(src => { const p = PR.parseFsm(src); return [p.errors.map(e => [e.ln, e.msg]), p.warnings.map(e => [e.ln, e.msg])]; });
console.log(JSON.stringify(res));
"""
    hf = t.WORK / "protocol-harness.js"
    hf.write_text(harness, encoding="utf-8")
    pr = subprocess.run([t.node, str(hf)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        res = json.loads(pr.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        res = {}
    t.check("protocol: renderers draw the four snippets with their summaries (node)",
            bool(m) and res.get("summaries") == ["timing diagram: 4 signals over 11 cycles", "bit-field diagram: 15 fields, 160 bits in 5 rows of 32",
                                                 "sequence diagram: 3 participants, 10 messages", "state machine: 4 states, 8 transitions"], (pr.stdout + pr.stderr)[:1500])
    t.check("protocol: hatching, gap, bus labels, edges, groups, reserved fields, frames, lost messages, numbering, notes, back edges are drawn (node)",
            all(res.get("tparts") or [False]) and all(res.get("bparts") or [False]) and all(res.get("sparts") or [False]) and all(res.get("fparts") or [False]), json.dumps(res)[:1500])
    t.check("protocol: every text is escaped; byte-unit packet frames work (node)", res.get("escaped") is True and res.get("wide") == "packet frame: 5 fields, 22 bytes in 3 rows of 8", json.dumps(res)[:800])
    t.check("protocol: renderers refuse bad sources with clear messages (node)", res.get("throws") == [
        'signal "a": unknown wave character "q"', 'timing JSON needs a "signal" array', "config.hscale must be a number > 0", 'field 1 "a": bits must be a whole number > 0',
        "lanes must be a whole number > 0", "line 1: line does not parse: A=>B", "line 1: line does not parse: A -> B"], json.dumps(res.get("throws")))
    import importlib.util
    spec = importlib.util.spec_from_file_location("atlas_validate_protocol", t.SCRIPTS / "validate.py")
    vmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vmod)
    py_seq = [[[list(e) for e in a], [list(e) for e in b2]] for a, b2 in (vmod.proto_parse_seq(x) for x in seq_cases)]
    py_fsm = [[[list(e) for e in a], [list(e) for e in b2]] for a, b2 in (vmod.proto_parse_fsm(x) for x in fsm_cases)]
    t.check("protocol: the Python validator mirrors the runtime's sequence and fsm parsers", res.get("seq") == py_seq and res.get("fsm") == py_fsm,
            json.dumps({"js": [res.get("seq"), res.get("fsm")], "py": [py_seq, py_fsm]})[:1500])
# ==== END protocol ====


# ==== BLOCK circuit — C8 schematic symbols, pinouts and register maps ====
@feature_test
def circuit_feature_tests(t) -> None:
    """C8 symbols, schematic, pinout and register map: validator PASS/FAIL/warning cases, the catalog module, static app.js checks and
    a node run of the pure renderers."""
    cat = t.PLUGIN / "skills" / "compose" / "components"
    snips = ["symbols.html", "schematic.html", "pinout.html", "regmap.html"]
    figs = local_refs("\n".join((cat / "circuit" / f).read_text(encoding="utf-8").split("\n", 1)[1] for f in snips))
    anchor = "Step through it.</figcaption>\n    </figure>"
    page = t.mutate(t.m02, anchor, anchor + "\n" + figs)
    t.page_m02.write_text(page, encoding="utf-8")
    code, out = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("circuit: the four catalog snippets PASS (no #sym-… broken links, no warnings)",
            code == 0 and t.result_of(out).get("bad_pages") == "0" and "warning:" not in out.replace("not checked", "") and "broken links" not in out, out)

    def fail(name: str, text: str, msg: str, needle: str) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check(name, c == 1 and f":{t.line_no(text, needle)} {msg}" in o, o)

    def warn(name: str, text: str, msg: str) -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check(name, c == 0 and "warning: " in o and msg in o, o)

    sch, pin, reg = 'id="fig-c8-led-driver"', 'id="fig-c8-atmega328p"', 'id="fig-c8-spi-regs"'
    # symbols
    fail("circuit: unknown symbol in use href FAIL", t.mutate(page, '<use href="#sym-fuse"', '<use href="#sym-fusee"'), 'unknown symbol "sym-fusee" in <use href>', 'href="#sym-fusee"')
    bad = t.mutate(page, '<use href="#sym-fuse"', '<a href="#no-such-anchor">x</a><use href="#sym-fuse"')
    t.page_m02.write_text(bad, encoding="utf-8")
    c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
    t.check("circuit: a real broken link next to #sym-… uses is still reported, without the symbols",
            c == 1 and f":{t.line_no(bad, 'no-such-anchor')} broken links: #no-such-anchor" in o and "#sym-" not in o.split("broken links:")[-1].split("\n")[0], o)
    # schematic
    fail("circuit: schematic invalid JSON FAIL (on the JSON line)", t.mutate(page, '"wires": [[80, 100, 100, 100]', '"wires": [[80, 100, 100, 100],'),
         "schematic fig-c8-led-driver: invalid JSON", '"wires": [[80, 100, 100, 100],,')
    fail("circuit: schematic unknown part symbol FAIL", t.mutate(page, '"sym": "npn"', '"sym": "triode"'), 'schematic fig-c8-led-driver: part 3 has unknown symbol "triode"', sch)
    fail("circuit: schematic part without numeric x FAIL", t.mutate(page, '"sym": "npn", "x": 100', '"sym": "npn", "x": "a"'), "schematic fig-c8-led-driver: part 3 needs numeric x and y", sch)
    fail("circuit: schematic bad rot FAIL", t.mutate(page, '"y": 20, "rot": 90', '"y": 20, "rot": 45'), "schematic fig-c8-led-driver: part 5 rot must be 0, 90, 180 or 270", sch)
    fail("circuit: schematic odd wire FAIL", t.mutate(page, "[120, 60, 120, 80]", "[120, 60, 120]"), "schematic fig-c8-led-driver: wire 2 needs an even list of at least 4 numbers", sch)
    fail("circuit: schematic without template FAIL", t.mutate(page, '<figure class="schematic" id="fig-c8-led-driver" data-cite="#ref-key">\n  <template>', '<figure class="schematic" id="fig-c8-led-driver" data-cite="#ref-key">\n  <div hidden>').replace(
        '"dots": []\n  }\n  </template>', '"dots": []\n  }\n  </div>'), "schematic fig-c8-led-driver has no <template> holding its JSON", sch)
    # pinout
    fail("circuit: pinout unknown package FAIL", t.mutate(page, '"package": "DIP-28"', '"package": "BGA"'), 'pinout fig-c8-atmega328p: package "BGA" is not DIP, SOIC, QFP or header', pin)
    fail("circuit: pinout duplicate pin number FAIL", t.mutate(page, '{"n": 22, "name": "GND"', '{"n": 8, "name": "GND"'), "pinout fig-c8-atmega328p: duplicate pin number 8", pin)
    fail("circuit: pinout missing pin number FAIL", t.mutate(page, '{"n": 22, "name": "GND"', '{"n": 29, "name": "GND"'), "pinout fig-c8-atmega328p: pin numbers must run 1..28 (missing 22)", pin)
    fail("circuit: pinout count does not match DIP-28 FAIL", t.mutate(page, '      {"n": 28, "name": "PC5 / ADC5 / SCL", "type": "analog", "note": "Also the I²C clock line"}', "").replace(
        '"note": "Also the I²C data line"},', '"note": "Also the I²C data line"}'), "pinout fig-c8-atmega328p: package DIP-28 but 27 pins", pin)
    odd = t.mutate(page, '      {"n": 28, "name": "PC5 / ADC5 / SCL", "type": "analog", "note": "Also the I²C clock line"}', "").replace(
        '"note": "Also the I²C data line"},', '"note": "Also the I²C data line"}')
    fail("circuit: pinout DIP with an odd pin count FAIL", t.mutate(odd, '"package": "DIP-28"', '"package": "DIP"'), "pinout fig-c8-atmega328p: DIP needs an even pin count (got 27)", pin)
    last = '      {"n": 28, "name": "PC5 / ADC5 / SCL", "type": "analog", "note": "Also the I²C clock line"}'
    qfp = t.mutate(t.mutate(page, last, last + ',' + chr(10) + '      {"n": 29, "name": "PB8"},' + chr(10) + '      {"n": 30, "name": "PB9"}'), '"package": "DIP-28"', '"package": "QFP"')
    fail("circuit: pinout QFP not divisible by 4 FAIL", qfp, "pinout fig-c8-atmega328p: QFP needs a pin count divisible by 4 (got 30)", pin)
    fail("circuit: pinout pin without name FAIL", t.mutate(page, '{"n": 8, "name": "GND"', '{"n": 8, "name": ""'), "pinout fig-c8-atmega328p: pin 8 has no name", pin)
    hdr = t.mutate(odd, '"package": "DIP-28"', '"package": "header", "rows": 2')
    fail("circuit: two-row header with an odd pin count FAIL", hdr, "pinout fig-c8-atmega328p: header with 2 rows needs an even pin count (got 27)", pin)
    warn("circuit: unknown pin type is a warning", t.mutate(page, '{"n": 8, "name": "GND", "type": "ground"}', '{"n": 8, "name": "GND", "type": "earth"}'), 'pinout fig-c8-atmega328p: pin 8 type "earth" is not one of')
    # register map
    fail("circuit: regmap bad width FAIL", t.mutate(page, '"width": 32', '"width": 12'), "regmap fig-c8-spi-regs: width must be 8, 16 or 32 (got 12)", reg)
    fail("circuit: regmap duplicate address FAIL", t.mutate(page, '"addr": "0x08"', '"addr": "0x04"'), "regmap fig-c8-spi-regs: duplicate register address 0x04 (STATUS, DATA)", reg)
    fail("circuit: regmap overlapping fields FAIL", t.mutate(page, '{"name": "CPHA", "msb": 4, "lsb": 4', '{"name": "CPHA", "msb": 5, "lsb": 4'), "regmap fig-c8-spi-regs: CTRL fields LSBF and CPHA overlap at bit 5", reg)
    fail("circuit: regmap field outside the width FAIL", t.mutate(page, '{"name": "RSVD", "msb": 31, "lsb": 16, "access": "RSVD"},\n        {"name": "DATA"', '{"name": "RSVD", "msb": 33, "lsb": 16, "access": "RSVD"},\n        {"name": "DATA"'),
         "regmap fig-c8-spi-regs: DATA.RSVD bits 33:16 outside a 32-bit register", reg)
    fail("circuit: regmap msb below lsb FAIL", t.mutate(page, '{"name": "BITS", "msb": 11, "lsb": 8', '{"name": "BITS", "msb": 8, "lsb": 11'), "regmap fig-c8-spi-regs: CTRL.BITS msb 8 is below lsb 11", reg)
    fail("circuit: regmap unknown access FAIL", t.mutate(page, '{"name": "RST", "msb": 1, "lsb": 1, "access": "WO"', '{"name": "RST", "msb": 1, "lsb": 1, "access": "WC"'), 'regmap fig-c8-spi-regs: CTRL.RST access "WC" is not RW, RO, WO, W1C or RSVD', reg)
    fail("circuit: regmap register reset too wide FAIL", t.mutate(page, '"reset": "0x00000004"', '"reset": "0x100000004"'), "regmap fig-c8-spi-regs: CLKDIV reset 0x100000004 does not fit 32 bits", reg)
    fail("circuit: regmap field reset too wide FAIL", t.mutate(page, '{"name": "BITS", "msb": 11, "lsb": 8, "access": "RW"', '{"name": "BITS", "msb": 11, "lsb": 8, "access": "RW", "reset": 16'), "regmap fig-c8-spi-regs: CTRL.BITS reset 0x10 does not fit 4 bits", reg)
    fail("circuit: regmap bad address FAIL", t.mutate(page, '"addr": "0x0C"', '"addr": "twelve"'), 'regmap fig-c8-spi-regs: CLKDIV addr "twelve" is not a number', reg)
    warn("circuit: an uncovered bit range is a warning (mark it RSVD)", t.mutate(page, '        {"name": "RSVD", "msb": 5, "lsb": 3, "access": "RSVD"},\n', ""),
         "regmap fig-c8-spi-regs: STATUS bits 5:3 are not covered by a field — mark them RSVD")
    t.page_m02.write_text(t.m02, encoding="utf-8")
    # catalog module, index, compose skill
    index = (cat / "INDEX.md").read_text(encoding="utf-8")
    t.check("circuit: catalog module circuit/ complete and listed in INDEX.md", all((cat / "circuit" / f).exists() for f in snips + ["README.md"])
            and re.search(r"^\| `circuit` \|", index, re.M) is not None and all(f in index for f in snips))
    readme = (cat / "circuit" / "README.md").read_text(encoding="utf-8")
    t.check("circuit: README documents the symbols, pins, the three figures and the messages",
            all(k in readme for k in ("sym-resistor", "sym-port", "rotate(90)", "figure.schematic", "figure.pinout", "figure.regmap", "<template>", "W1C", "QC.symbols()",
                                      "duplicate pin number", "overlap at bit", "mark them RSVD", 'unknown symbol "sym-x"')))
    skill = (t.PLUGIN / "skills" / "compose" / "SKILL.md").read_text(encoding="utf-8")
    t.check("circuit: compose SKILL.md derivation table names circuit", "`circuit` when" in skill)
    # static app.js / style.css / validate.py checks
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    val = (t.SCRIPTS / "validate.py").read_text(encoding="utf-8")
    block = app[app.index("==== BLOCK circuit"):app.index("==== END circuit")]
    js_syms = re.findall(r"^    '?([a-z-]+)'?: \['", block, re.M)
    py_syms = re.search(r"CIRCUIT_SYMS = \[([^\]]*)\]", val)
    t.check("circuit: 19 symbols, the same list in app.js and validate.py", len(js_syms) == 19 and py_syms is not None and js_syms == re.findall(r'"([a-z-]+)"', py_syms.group(1)), str(js_syms))
    t.check("circuit: app.js registers c8-circuit in the shell phase with its api; the sprite and the use expansion exist",
            "feature({ name: 'c8-circuit', phase: 'shell'" in block and "id: 'qc-symbols'" in block and "function expandUse(u)" in block
            and "api: { symbols:" in block and "fig.classList.add('diagram')" in block and "eval(" not in block)
    t.check("circuit: style.css block styles symbols, pinout and regmap with theme variables only",
            all(k in css for k in ("svg .sym-stroke", ".pinout-stub", ".regmap-bits", ".regmap-cell", ".pinout-table tr.is-hot")) and
            not re.search(r"#[0-9a-fA-F]{3,8}\b", css[css.index("==== BLOCK circuit"):css.index("==== END circuit")]))
    # the pure renderers, run by node outside the page
    if t.node:
        m = re.search(r"/\* circuit:pure:begin[\s\S]*?/\* circuit:pure:end \*/", app)
        harness = (m.group(0) if m else "") + r"""
const res = {};
const svg = schematicSvg({ parts: [{ sym: 'resistor', x: 40, y: 40, label: 'R1', value: '1 kΩ' }, { sym: 'sym-capacitor', x: 80, y: 40, rot: 90 }], wires: [[20, 40, 40, 40]], dots: [[80, 40]] }, 'f1', 'RC');
res.svg = [svg.includes('aria-labelledby="f1-t"'), svg.includes('<title id="f1-t">RC</title>'), svg.includes('class="sym sym-capacitor" transform="translate(80 40) rotate(90)"'), svg.includes('class="sym-wire"'), svg.includes('class="sym-dot"'), /viewBox="[-\d]+ [-\d]+ \d+ \d+"/.test(svg)];
const errs = [];
const tryIt = f => { try { f(); errs.push('no error'); } catch (e) { errs.push(e.message); } };
tryIt(() => schematicSvg({ parts: [{ sym: 'triode', x: 0, y: 0 }] }, 'f'));
tryIt(() => pinoutParts({ package: 'DIP', pins: [1, 2, 3].map(n => ({ n, name: 'P' + n })) }, 'p'));
tryIt(() => pinoutParts({ package: 'QFP', pins: [1, 2, 3, 4, 5, 6].map(n => ({ n, name: 'P' + n })) }, 'p'));
tryIt(() => regmapParts({ width: 12, registers: [] }, 'r'));
res.errs = errs;
const p = pinoutParts({ package: 'SOIC-8', title: 'LM358', pins: [1, 2, 3, 4, 5, 6, 7, 8].map(n => ({ n, name: 'P' + n, type: n === 4 ? 'ground' : n === 8 ? 'power' : 'analog' })) }, 'p8');
res.pin = [p.count, (p.svg.match(/class="pinout-pin"/g) || []).length, (p.table.match(/<tr data-pin=/g) || []).length, p.legend.includes('data-type="ground"'), p.svg.includes('tabindex="0"')];
const r = regmapParts({ width: 8, registers: [{ addr: '0x10', name: 'CTRL', reset: '0x81', fields: [{ name: 'EN', msb: 7, lsb: 7, access: 'RW' }, { name: 'MODE', msb: 2, lsb: 0, access: 'RO' }] }] }, 'r1');
res.reg = [r.html.includes('grid-column:2 / span 4'), r.html.includes('<code>0b001</code>'), r.html.includes('<code class="regmap-addr">0x10</code>'), r.legend.includes('RSVD'), r.tools === ''];
res.match = [regmapMatch('0x010', 16, 'ctrl'), regmapMatch('mode', 16, 'ctrl en mode'), regmapMatch('0x11', 16, 'ctrl'), regmapMatch('', 16, '')];
res.num = [cNum('0x1C'), cNum('0b101'), cNum('0x0000_0700'), cNum('x'), cNum(3.5)];
console.log(JSON.stringify(res));
"""
        hf = t.WORK / "circuit-pure.js"
        hf.write_text(harness, encoding="utf-8")
        pr = subprocess.run([t.node, str(hf)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            res = json.loads(pr.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            res = {}
        t.check("circuit: node — schematicSvg draws parts, rotation, wires, dots, title and a viewBox", res.get("svg") == [True] * 6, pr.stdout + pr.stderr)
        t.check("circuit: node — renderers throw on an unknown symbol, an odd DIP, a QFP not divisible by 4 and a bad width",
                res.get("errs") == ['part 1 has unknown symbol "triode"', "DIP needs an even pin count (got 3)", "QFP needs a pin count divisible by 4 (got 6)", "width must be 8, 16 or 32 (got 12)"], pr.stdout + pr.stderr)
        t.check("circuit: node — pinoutParts draws every pin focusable, one table row each and the legend", res.get("pin") == [8, 8, 8, True, True], pr.stdout + pr.stderr)
        t.check("circuit: node — regmapParts fills gaps as reserved, derives field resets, formats the address; find matches numerically",
                res.get("reg") == [True] * 5 and res.get("match") == [True, True, False, True] and res.get("num") == [28, 5, 1792, None, None], pr.stdout + pr.stderr)
# ==== END circuit ====


# ==== BLOCK study — B4 flashcards · F1 notes, highlights, bookmarks and resume position ====
# runs app.js in node with a stub DOM (readyState 'loading', so init() never runs) and exercises the pure B4 / F1 helpers
STUDY_HARNESS = r"""
const fs = require('fs');
const noop = () => {};
const fakeEl = () => ({ dataset: {}, style: { setProperty: noop, removeProperty: noop }, classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
  setAttribute: noop, getAttribute: () => null, removeAttribute: noop, appendChild: noop, prepend: noop, remove: noop, querySelector: () => null, querySelectorAll: () => [],
  addEventListener: noop, closest: () => null, innerHTML: '', textContent: '' });
globalThis.window = globalThis;
globalThis.document = Object.assign(fakeEl(), { readyState: 'loading', body: fakeEl(), documentElement: fakeEl(), head: fakeEl(), createElement: () => fakeEl(),
  getElementById: () => null, dispatchEvent: noop, title: 't' });
globalThis.location = { pathname: '/site/pages/glossary.html', search: '', hash: '', href: 'file:///site/pages/glossary.html', protocol: 'file:' };
globalThis.history = { replaceState: noop }; globalThis.navigator = {}; globalThis.addEventListener = noop;
globalThis.matchMedia = () => ({ matches: false, addEventListener: noop, addListener: noop });
globalThis.CustomEvent = class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } };
globalThis.QC_GLOSSARY = [
  { term: 'Scale factor', term_local: 'Hệ số tỷ lệ', def: 'Ratio of a <tiny> length on the map to the same length on the globe.', def_local: 'Tỷ số độ dài', tags: ['projection', 'distortion'], page: 'm02-kinds.html' },
  { term: 'Graticule', aka: 'grid', def: 'The grid of meridians and parallels, drawn\tas lines.', group: 'basics', page: 'm02-kinds.html' },
  { term: 'Conformal', def: 'Keeps angles, "locally".', tags: ['projection'], page: 'm02-kinds.html' },
  { term: 'Datum', def: 'A reference ellipsoid, plus an origin.', page: 'm02-kinds.html' },
  { def: 'no term: skipped' }
];
new Function(fs.readFileSync(process.argv[2], 'utf8'))();
const QC = globalThis.QC, out = {};
out.all = QC.flashDeck('all').map(c => c.term);
out.empty = QC.flashDeck('').length;
out.list = QC.flashDeck('graticule, Scale factor, Nope').map(c => c.term);
out.tagged = QC.flashDeck('all', 'Projection').map(c => c.term);
out.group = QC.flashDeck('all', 'basics, nothing').map(c => c.term);
out.card = QC.flashDeck('Scale factor')[0];
const t0 = 1e12, D = 864e5;
const r1 = QC.leitner(null, true, t0), r2 = QC.leitner(r1, true, t0), r3 = QC.leitner({ box: 5, due: 0, seen: 9 }, true, t0), r4 = QC.leitner(r2, false, t0);
out.leitner = [[r1.box, (r1.due - t0) / D, r1.seen], [r2.box, (r2.due - t0) / D, r2.seen], [r3.box, (r3.due - t0) / D], [r4.box, r4.due - t0, r4.seen]];
const deck = QC.flashDeck('all');
out.anki = QC.flashExport(deck, 'anki');
out.csv = QC.flashExport(deck, 'csv');
const text = 'The scale factor is one on the standard line. Far away, the scale factor is two on the edge of the map.';
const q = 'scale factor is';
out.locate = [QC.notesLocate(text, { quote: q, prefix: 'Far away, the ', suffix: ' two on' }), QC.notesLocate(text, { quote: q, prefix: 'The ', suffix: ' one on' }),
  QC.notesLocate(text, { quote: 'not there' }), QC.notesLocate(text, { quote: '' })];
out.textAt = out.locate[0] && text.slice(out.locate[0].start, out.locate[0].end);
const a = [{ id: 'n1', type: 'hl', page: 'a.html', quote: 'x', updated: 5 }, { id: 'bm:a.html#s', type: 'bm', page: 'a.html', updated: 1 }];
const b = [{ id: 'n1', type: 'hl', page: 'a.html', quote: 'newer', updated: 9 }, { id: 'n2', type: 'hl', page: 'b.html', quote: 'y', updated: 2 }, { id: 'bad', type: 'zz', page: 'a.html' }, null, { type: 'hl' }];
const m = QC.notesMerge(a, b);
out.merge = m.map(x => x.id + ':' + (x.quote || '')).sort();
out.mergeOld = QC.notesMerge(b, a).find(x => x.id === 'n1').quote;
out.api = ['flashDeck', 'flashExport', 'leitner', 'notesLocate', 'notesMerge', 'notesPanel', 'notesExport', 'notesImport'].filter(k => typeof QC[k] !== 'function');
console.log(JSON.stringify(out));
"""

STUDY_GLOSSARY = [
    {"term": "Scale factor", "def": "Ratio of a length on the map to the same length on the globe.", "page": "m02-kinds.html", "anchor": "introduction", "tags": ["projection", "distortion"]},
    {"term": "Graticule", "def": "The grid of meridians and parallels drawn on a map.", "page": "m02-kinds.html", "group": "basics"},
    {"term": "Conformal projection", "def": "A projection that keeps local angles.", "page": "m02-kinds.html", "tags": ["projection"]},
]
STUDY_DECK = '<div class="flashcards" id="fc-test" data-flashcards="Scale factor, graticule, Conformal projection" data-tags="projection, basics"></div>'


@feature_test
def study_features(t) -> None:
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    block = app[app.index("==== BLOCK study"):app.index("==== END study")]
    cat = t.PLUGIN / "skills" / "compose" / "components"
    # ---- static: features registered inside the block, markup names in the runtime and the stylesheet, catalog + docs wired
    t.check("study: app.js registers b4-flashcards (enhance) and f1-notes (post) inside the study block",
            "feature({ name: 'b4-flashcards', phase: 'enhance'" in block and "feature({ name: 'f1-notes', phase: 'post'" in block)
    t.check("study: B4 runtime reads QC_GLOSSARY, stores Leitner boxes under study:cards, has Space/1/2 keys and the Anki header",
            all(x in block for x in ("window.QC_GLOSSARY", "'study:cards'", "FC_DAYS = [0, 1, 3, 7, 14]", "e.key === '1'", "e.key === '2'", "'#separator:tab', '#html:true'", "term_local", "data-tags", "dataset.tags")))
    t.check("study: F1 runtime anchors by quote + prefix/suffix, wraps text nodes in mark.hl, keeps orphans, bookmarks h2, resumes, honours the opt-outs",
            all(x in block for x in ("createTreeWalker", "splitText", "el('mark', { class: 'hl hl-'", "it.orphan", "'nt-bm'", "y > 0.2", "> 60000", "prefers-reduced-motion",
                                     "data-no-notes", "SITE.notes === false", "'study:notes'", "'study:pos'", "e.key !== 'm'", "A4_KEYS", "FileReader", "data-notes-open"))
            and "innerHTML.replace" not in block and "localStorage.setItem(k, '1')" in block)
    t.check("study: style.css has the study classes, the three highlight colours, the handout and print rules",
            all(c in css for c in (".flashcards", ".fc-card", ".fc-boxes", "mark.hl", "--hl-1", "--hl-3", ".nt-pop", ".nt-panel", ".nt-toast", ".nt-bm", ".notes-toggle",
                                   ':root[data-mode="handout"] mark.hl', ".nt-toast { position: fixed")) and "@media print" in css.split("BLOCK study")[1].split("END study")[0])
    gh = (t.TEMPLATE / "glossary.html").read_text(encoding="utf-8")
    t.check("study: template glossary.html carries the flashcards deck below the terms table",
            'data-flashcards="all"' in gh and gh.index('id="tbl-glossary"') < gh.index('data-flashcards="all"') < gh.index("</main>"))
    snips = {n: (cat / "study" / n).read_text(encoding="utf-8") if (cat / "study" / n).exists() else "" for n in ("flashcards.html", "notes.html")}
    readme = (cat / "study" / "README.md").read_text(encoding="utf-8") if (cat / "study" / "README.md").exists() else ""
    t.check("study: catalog snippets with header lines, the deck and the data-notes-open button; README says .apkg is out of scope",
            snips["flashcards.html"].startswith("<!-- atlaspedia component: study/flashcards.html ·") and "data-flashcards=" in snips["flashcards.html"]
            and snips["notes.html"].startswith("<!-- atlaspedia component: study/notes.html ·") and "data-notes-open" in snips["notes.html"] and "data-no-notes" in snips["notes.html"]
            and ".apkg" in readme and "#separator:tab" in readme and "data-no-notes" in readme)
    idx = (cat / "INDEX.md").read_text(encoding="utf-8")
    skill = (t.PLUGIN / "skills" / "compose" / "SKILL.md").read_text(encoding="utf-8")
    t.check("study: INDEX.md row and the compose SKILL.md derivation line name the module",
            "| `study` |" in idx and "flashcards.html · notes.html" in idx and "| any page (study: B4 flashcards, F1 notes) |" in skill)

    # ---- the pure helpers, in node
    if t.node:
        harness = t.WORK / "study_harness.js"
        harness.write_text(STUDY_HARNESS, encoding="utf-8")
        p = subprocess.run([t.node, str(harness), str(t.TEMPLATE / "assets" / "app.js")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            o = json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
        t.check("study: QC exposes flashDeck, flashExport, leitner, notesLocate, notesMerge, notesPanel, notesExport, notesImport", o.get("api") == [], p.stdout + p.stderr)
        t.check("study: flashDeck — all (sorted), empty = all, a list keeps its order and drops unknown terms, data-tags matches tags and group",
                o.get("all") == ["Conformal", "Datum", "Graticule", "Scale factor"] and o.get("empty") == 4 and o.get("list") == ["Graticule", "Scale factor"]
                and o.get("tagged") == ["Conformal", "Scale factor"] and o.get("group") == ["Graticule"], json.dumps(o)[:600])
        card = o.get("card") or {}
        t.check("study: a card carries term_local / def_local and its tags", card.get("local") == "Hệ số tỷ lệ" and card.get("defLocal") == "Tỷ số độ dài"
                and card.get("tags") == ["projection", "distortion"] and card.get("id") == "scale-factor", json.dumps(card))
        t.check("study: leitner — Good moves a new card to box 2 (1 day), then box 3 (3 days), caps at 5 (14 days); Again → box 1, due now",
                o.get("leitner") == [[2, 1, 1], [3, 3, 2], [5, 14], [1, 0, 3]], json.dumps(o.get("leitner")))
        anki = (o.get("anki") or "").split("\n")
        t.check("study: Anki TSV — #separator:tab, #html:true, #tags column:3, one front/back/tags line per card, HTML escaped, tabs flattened",
                anki[:3] == ["#separator:tab", "#html:true", "#tags column:3"] and len(anki) == 3 + 4 + 1 and anki[-1] == ""
                and all(len(l.split("\t")) == 3 for l in anki[3:7])
                and "Scale factor<br><i>Hệ số tỷ lệ</i>\tRatio of a &lt;tiny&gt; length on the map to the same length on the globe.<br><i>Tỷ số độ dài</i>\tprojection distortion" in anki
                and any(l.startswith("Graticule\tThe grid of meridians and parallels, drawn as lines.\tbasics") for l in anki), "\n".join(anki))
        csv_lines = (o.get("csv") or "").split("\r\n")
        t.check("study: CSV — header, RFC 4180 quoting of commas and quotes",
                csv_lines[0] == "term,definition,term_local,definition_local,tags" and 'Conformal,"Keeps angles, ""locally"".",,,projection' in csv_lines
                and len(csv_lines) == 6, "\n".join(csv_lines))
        loc = o.get("locate") or [None] * 4
        t.check("study: notesLocate picks the occurrence whose prefix/suffix match, null when the quote is gone",
                loc[0] and loc[0].get("start") == 60 and o.get("textAt") == "scale factor is" and loc[1] and loc[1].get("start") == 4 and loc[2] is None and loc[3] is None, json.dumps(loc))
        t.check("study: notesMerge — union by id, the newer `updated` wins, invalid items dropped",
                o.get("merge") == ["bm:a.html#s:", "n1:newer", "n2:y"] and o.get("mergeOld") == "newer", json.dumps(o.get("merge")))
    else:
        print("      (study node harness skipped: node not on PATH)")

    # ---- validator: the deck on the module page, against a tagged glossary
    gj = t.topic / "assets" / "glossary.json"
    gj_orig = gj.read_text(encoding="utf-8")

    def set_glossary(entries) -> None:
        gj.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        t.sync()

    page = t.mutate(t.m02, '<h2 id="introduction">Conceptual introduction</h2>\n    <p>…</p>', '<h2 id="introduction">Conceptual introduction</h2>\n    <p>…</p>\n    ' + STUDY_DECK)

    def case(name: str, text: str, want: int, needle: str, absent: str = "") -> None:
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        hit = f":{t.line_no(text, 'id="fc-test"')} {needle}" if needle else ""   # file:line [warning: ]message
        t.check(name, c == want and (not hit or hit in o) and (not absent or absent not in o), o)

    try:
        set_glossary(STUDY_GLOSSARY)
        case("study: module page with a flashcards deck (term list in any case + tags) PASS, no study warnings", page, 0, "", "flashcards fc-test")
        case("study: deck term not in glossary.json FAIL", t.mutate(page, "graticule, Conformal", "graticule, Rhumb line, Conformal"), 1,
             'flashcards fc-test: term "Rhumb line" is not in glossary.json')
        case("study: deck with an empty item FAIL", t.mutate(page, "Scale factor, graticule", "Scale factor,, graticule"), 1,
             'flashcards fc-test: data-flashcards "Scale factor,, graticule, Conformal projection" has an empty item')
        case("study: malformed data-tags (empty item) FAIL", t.mutate(page, 'data-tags="projection, basics"', 'data-tags="projection,,basics"'), 1,
             'flashcards fc-test: data-tags "projection,,basics" is malformed')
        case("study: malformed data-tags (bad characters) FAIL", t.mutate(page, 'data-tags="projection, basics"', 'data-tags="projection; basics"'), 1,
             'flashcards fc-test: data-tags "projection; basics" is malformed')
        case("study: empty data-tags FAIL", t.mutate(page, 'data-tags="projection, basics"', 'data-tags=""'), 1, 'flashcards fc-test: data-tags "" is malformed')
        case("study: a tag no glossary entry carries is a warning", t.mutate(page, 'data-tags="projection, basics"', 'data-tags="projection, geodesy"'), 0,
             'warning: flashcards fc-test: tag "geodesy" matches no glossary entry')
        case("study: data-flashcards=\"all\" PASS", t.mutate(page, 'data-flashcards="Scale factor, graticule, Conformal projection"', 'data-flashcards="all"'), 0, "", "flashcards fc-test")
        case("study: data-no-notes on a div is a warning", t.mutate(page, "<p>…</p>\n    " + STUDY_DECK, '<p>…</p>\n    <div data-no-notes>' + STUDY_DECK + "</div>"), 0,
             "warning: data-no-notes on <div> is ignored (put it on <main>)")
        case("study: data-no-notes on main PASS without a warning", t.mutate(page, "<main>", "<main data-no-notes>"), 0, "", "data-no-notes on")
        set_glossary(STUDY_GLOSSARY[:2])
        case("study: a deck on a site whose glossary has 2 terms is a warning", t.mutate(page, ", Conformal projection", ""), 0,
             "warning: flashcards fc-test: the glossary has 2 terms — a deck needs at least 3")
        # site level: glossary tags / group shape, site.json notes flag
        bad = [dict(STUDY_GLOSSARY[0], tags="projection"), dict(STUDY_GLOSSARY[1], group=""), STUDY_GLOSSARY[2]]
        set_glossary(bad)
        c, o = t.run("validate.py", t.topic, "--pages", "glossary.html")
        t.check("study: glossary tags not a list FAIL and an empty group FAIL",
                c == 1 and 'glossary term "Scale factor": tags must be a list of strings' in o and 'glossary term "Graticule": group must be a non-empty string' in o, o)
        set_glossary(STUDY_GLOSSARY)
        reg2 = dict(t.reg, notes="off")
        t.sj.write_text(json.dumps(reg2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        t.sync()
        c, o = t.run("validate.py", t.topic, "--pages", "glossary.html")
        t.check("study: site.json notes not a boolean FAIL", c == 1 and 'site.json notes must be true or false (got "off")' in o, o)
        reg2["notes"] = False
        t.sj.write_text(json.dumps(reg2, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        t.sync()
        c, o = t.run("validate.py", t.topic, "--pages", "glossary.html")
        t.check("study: site.json notes: false and the template glossary page with its deck PASS", c == 0 and "notes must be" not in o and "flashcards" not in o, o)
    finally:
        gj.write_text(gj_orig, encoding="utf-8")
        t.sj.write_text(json.dumps(t.reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        t.page_m02.write_text(t.m02, encoding="utf-8")
        t.sync()
# ==== END study ====


# ==== BLOCK runner — D5 in-browser code runners (JS sandbox, Python via Pyodide) ====
# Pyodide never loads here: the tests cover the markup, the validator (incl. the opt-in node run) and the sandbox bootstrap,
# which runs in node's vm with a stub parent/addEventListener so the console capture and the error path are exercised.
RUNNER_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const noop = () => {};
const fakeEl = () => ({ dataset: {}, style: { setProperty: noop, removeProperty: noop }, classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
  setAttribute: noop, getAttribute: () => null, removeAttribute: noop, appendChild: noop, querySelector: () => null, querySelectorAll: () => [],
  addEventListener: noop, innerHTML: '', textContent: '' });
globalThis.window = globalThis;
globalThis.document = Object.assign(fakeEl(), { readyState: 'loading', body: fakeEl(), documentElement: fakeEl(), head: fakeEl(), createElement: () => fakeEl(),
  getElementById: () => null, dispatchEvent: noop });
globalThis.location = { pathname: '/site/pages/m02-kinds.html', search: '', hash: '', href: 'file:///site/pages/m02-kinds.html', protocol: 'file:' };
globalThis.navigator = {}; globalThis.addEventListener = noop; globalThis.matchMedia = () => ({ matches: false, addEventListener: noop });
new Function(fs.readFileSync(process.argv[2], 'utf8'))();
const QC = globalThis.QC, out = {};
// The frame: its one bootstrap script runs in a vm context with a stub parent, Blob/URL and (optionally) a fake Worker that runs
// the worker script in its own context; a forged message (wrong source) arrives first and must be ignored.
const lineOf = (e, fn) => { const m = new RegExp(fn + ':(\\d+)').exec(e.stack || ''); return m ? +m[1] : 0; };
function sandbox(code, offset, withWorker) {
  const doc = QC.runnerSrcdoc('tok-1', offset);
  const scripts = [...doc.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  const msgs = [], listeners = {}, blobs = new Map(), jobs = [];
  const parent = { postMessage: (d, o) => msgs.push([d.qcRunner, d.k, d.s, o]) };
  class FakeWorker {
    constructor(url) {
      const src = blobs.get(url), me = this, wl = {};
      const w = { console: {}, postMessage: d => me.onmessage && me.onmessage({ data: d }), addEventListener: (t, f) => { wl[t] = f; } };
      w.self = w; vm.createContext(w);
      jobs.push(() => {
        let sc;
        try { sc = new vm.Script(src, { filename: 'worker' }); } catch (e) { me.onerror({ message: 'Uncaught ' + e.name + ': ' + e.message, lineno: lineOf(e, 'worker'), preventDefault() {} }); return; }
        try { sc.runInContext(w); } catch (e) { wl.error({ error: e, message: String(e), lineno: lineOf(e, 'worker'), preventDefault() {} }); }
      });
    }
  }
  const ctx = { parent, console: {}, addEventListener: (t, f) => { listeners[t] = f; },
    Blob: class { constructor(parts) { this.s = parts.join(''); } }, URL: { createObjectURL: b => { const u = 'blob:null/' + blobs.size; blobs.set(u, b.s); return u; } },
    document: { createElement: () => ({}), body: { appendChild: sc => {
      try { new vm.Script(sc.textContent, { filename: 'inline' }).runInContext(ctx); } catch (e) { listeners.error({ error: e, message: String(e), lineno: lineOf(e, 'inline'), preventDefault() {} }); } } } } };
  if (withWorker) ctx.Worker = FakeWorker;
  ctx.window = ctx; vm.createContext(ctx);
  new vm.Script(scripts[0], { filename: 'srcdoc' }).runInContext(ctx);
  listeners.message({ source: {}, data: { qcRunner: 'tok-1', code: "console.log('forged')" } });
  listeners.message({ source: parent, data: { qcRunner: 'tok-2', code: "console.log('wrong token')" } });
  listeners.message({ source: parent, data: { qcRunner: 'tok-1', code } });
  jobs.forEach(j => j());
  return { doc, scripts, msgs, blobs: blobs.size };
}
const A = "const xs = [1, 2, 3];\nconsole.log('sum', xs.reduce((p, q) => p + q, 0), xs);\nconsole.warn('careful');\nconsole.log({ k: 1 }, null, undefined);";
const a = sandbox(A, 0, true), ai = sandbox(A, 0, false);
out.ok = a.msgs.map(m => m.slice(0, 3)); out.okInline = ai.msgs.map(m => m.slice(0, 3)); out.target = a.msgs.every(m => m[3] === '*');
out.nScripts = a.scripts.length; out.blobs = [a.blobs, ai.blobs];
const B = "console.log('before');\nnull.x;";
out.throws = sandbox(B, 0, true).msgs.map(m => m.slice(1, 3)); out.throwsInline = sandbox(B, 0, false).msgs.map(m => m.slice(1, 3));
out.throwsSetup = sandbox("const k = 1;\n" + B, 1, true).msgs.map(m => m.slice(1, 3));
out.syntaxErr = sandbox("console.log('x');\nlet = ;", 0, true).msgs.map(m => m.slice(1, 3));
const c = sandbox("console.log('</script><b>x</b>');", 0, true);
out.escaped = !c.doc.includes('<b>x</b>') && c.msgs.length === 2 && c.msgs[0][2] === '</script><b>x</b>';
out.syntax = [a, ai, c].every(r => r.scripts.every(s => { try { new vm.Script(s); return true; } catch (e) { return false; } }));
out.boot = a.doc.startsWith('<!doctype html>') && a.scripts.length === 1;
out.trace = QC.runnerPyTrace('Traceback (most recent call last):\n  File "/lib/python312.zip/_pyodide/_base.py", line 573, in eval_code_async\n    await CodeRunner(\n          ^^^^^^^^^^^\n  File "<exec>", line 3, in <module>\nZeroDivisionError: division by zero');
out.match = [QC.runnerMatches('a  \r\nb\n\n', 'a\nb'), QC.runnerMatches('a\nb', 'a\nc'), QC.runnerMatches('\n x\n', ' x'), QC.runnerNormalize('p \nq  \n')];
out.pyodide = QC.runnerPyodide;
console.log(JSON.stringify(out));
"""


def _runner_validate(t, site, page, env_extra=None, path=None):
    env = dict(os.environ)
    env.pop("ATLAS_RUN_RUNNERS", None)
    env.update(env_extra or {})
    if path is not None:
        env["PATH"] = path
    args = [sys.executable, str(t.SCRIPTS / "validate.py"), str(site)] + (["--pages", page] if page else [])
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(t.WORK))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


@feature_test
def runner_features(t):
    """D5 code runners: snippets, README, INDEX/SKILL/authoring rows, runtime block (static + sandbox bootstrap in node),
    CSS, every validator message, the single-format Python warning and the opt-in node run (ATLAS_RUN_RUNNERS)."""
    check, mutate, R = t.check, t.mutate, t.result_of
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    block = app[app.find("/* ==== BLOCK runner"):app.find("/* ==== END runner")]
    cat = t.PLUGIN / "skills" / "compose" / "components"
    js_snip = (cat / "runner" / "runner-js.html").read_text(encoding="utf-8")
    py_snip = (cat / "runner" / "runner-python.html").read_text(encoding="utf-8")
    readme = (cat / "runner" / "README.md").read_text(encoding="utf-8")
    index = (cat / "INDEX.md").read_text(encoding="utf-8")
    skill = (t.PLUGIN / "skills" / "compose" / "SKILL.md").read_text(encoding="utf-8")
    rules = (t.PLUGIN / "skills" / "compose" / "references" / "authoring-rules.md").read_text(encoding="utf-8")

    # ---- static pieces ----------------------------------------------------------------------------------------------
    check("runner: snippets start with the catalog header, use div.runner[data-lang][id], data-expected, data-setup on a text/plain script",
          js_snip.startswith("<!-- atlaspedia component: runner/runner-js.html · use when:") and py_snip.startswith("<!-- atlaspedia component: runner/runner-python.html · use when:")
          and js_snip.count('<div class="runner" id="') == 2 and 'data-lang="js"' in js_snip and 'data-lang="python"' in py_snip
          and '<script type="text/plain" id="d5-kalman-setup">' in js_snip and 'data-setup="d5-cities-setup"' in py_snip
          and "data-expected=" in js_snip and "data-expected=" in py_snip and "numpy" in py_snip)
    check("runner: README has the shape, a three-line security model, the network note; INDEX, SKILL and authoring rules carry the module",
          "## Security model" in readme and len(re.findall(r"^- ", readme.split("## Security model")[1].split("##")[0], re.M)) == 3
          and "cdn.jsdelivr.net" in readme and "about 10 MB" in readme and "## Validator messages this module can trigger" in readme
          and "| `runner` |" in index and "runner-js.html · runner-python.html" in index
          and "`runner` when" in skill and "edit and run" in skill and "Code runners (D5)" in rules and "must be real output" in rules)
    check("runner: app.js registers d5-runner in phase shell; sandbox is allow-scripts only, srcdoc, event.source + token check, timeout removes the frame",
          "name: 'd5-runner', phase: 'shell'" in app and "sandbox: 'allow-scripts'" in block and "allow-same-origin" not in block.replace("(no allow-same-origin", "")
          and "frame.srcdoc" in block and "e.source !== frame.contentWindow" in block and "e.source!==P" in block and "e.data.qcRunner !== token" in block
          and "frame.remove()" in block and "RUN_MAX_OUT" in block and re.search(r"\beval\(", block) is None)
    check("runner: Python is lazy (pinned jsdelivr Pyodide, one-time notice, Blob worker with importScripts, main-thread fallback, offline message)",
          "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/" in block and "runner:pyodide-ok" in block and "downloads about 10 MB from cdn.jsdelivr.net" in block
          and "new Worker(URL.createObjectURL(new Blob(" in block and "importScripts(" in block and "pyMain()" in block and "w.terminate()" in block
          and "Could not load Python" in block and "aria-live" in block and "Control+Enter" in block and "store.set(key" in block)
    check("runner: style.css styles the runner (bar, code, output stdout/stderr, chip pass/fail, notice, print)",
          all(c in css for c in (".runner {", ".runner-bar", ".runner-code", ".runner-line.err", ".runner-chip.pass", ".runner-chip.fail", ".runner-notice", ".runner-frame")))

    # ---- sandbox bootstrap and helpers in node ------------------------------------------------------------------------
    if t.node:
        hf = t.WORK / "runner-harness.js"
        hf.write_text(RUNNER_HARNESS, encoding="utf-8")
        pr = subprocess.run([t.node, str(hf), str(t.TEMPLATE / "assets" / "app.js")], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        m = re.search(r"^\{.*\}$", pr.stdout or "", re.M)
        res = json.loads(m.group(0)) if m else {}
        exp = [["tok-1", "out", "sum 6 [1,2,3]"], ["tok-1", "err", "careful"], ["tok-1", "out", '{"k":1} null undefined'], ["tok-1", "end", ""]]
        check("runner: sandbox captures console.log/warn (JSON for objects) and ends, in the frame's worker and in the no-worker fallback; forged messages ignored",
              res.get("ok") == exp and res.get("okInline") == exp and res.get("target") is True and res.get("nScripts") == 1
              and res.get("blobs") == [1, 0], (pr.stdout + pr.stderr)[:1200])
        thr = res.get("throws", [])
        check("runner: an uncaught error is reported on stderr with its name and the reader's line number, then end (worker, fallback, with setup lines)",
              len(thr) == 3 and thr[0] == ["out", "before"] and thr[1][0] == "err" and thr[1][1].startswith("TypeError: ") and thr[1][1].endswith("(line 2)")
              and thr[2] == ["end", ""] and res.get("throwsInline") == thr and res.get("throwsSetup") == thr, json.dumps([thr, res.get("throwsInline"), res.get("throwsSetup")]))
        se = res.get("syntaxErr", [])
        check("runner: a syntax error is reported on stderr, then end", len(se) == 2 and se[0][0] == "err" and se[0][1].startswith("SyntaxError") and se[1] == ["end", ""], json.dumps(se))
        check("runner: code reaches the frame by postMessage, never through HTML; the srcdoc parses; output comparison trims trailing spaces and blank lines",
              res.get("escaped") is True and res.get("syntax") is True and res.get("boot") is True
              and res.get("match") == [True, False, True, "p\nq"] and res.get("pyodide", "").startswith("https://cdn.jsdelivr.net/pyodide/v"), json.dumps(res))
        check("runner: Pyodide tracebacks drop the interpreter's own frames",
              res.get("trace") == 'Traceback (most recent call last):\n  File "<exec>", line 3, in <module>\nZeroDivisionError: division by zero', json.dumps(res.get("trace")))
    else:
        print("      (runner sandbox node check skipped: node not on PATH)")

    # ---- validator: both snippets on the module page PASS ------------------------------------------------------------
    body = lambda s: s.split("-->", 1)[1]
    intro = '<h2 id="introduction">Conceptual introduction</h2>\n    <p>…</p>'
    page = mutate(t.m02, intro, intro + "\n" + body(js_snip) + body(py_snip))
    t.page_m02.write_text(page, encoding="utf-8")
    code, out = _runner_validate(t, t.topic, "m02-kinds.html")
    check("runner: both snippets on a module page PASS (the Python setup script is not syntax-checked as JavaScript)",
          code == 0 and R(out).get("bad_pages") == "0" and "runner" not in out and "inline script" not in out, out)

    def fail(name, text, msg):
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = _runner_validate(t, t.topic, "m02-kinds.html")
        check(name, c == 1 and msg in o, o)

    fail("runner: runner without id FAIL", mutate(page, '<div class="runner" id="d5-quadkey" ', '<div class="runner" '), "runner without id")
    fail("runner: unknown data-lang FAIL", mutate(page, 'id="d5-quadkey" data-lang="js"', 'id="d5-quadkey" data-lang="ruby"'),
         'runner d5-quadkey: unknown data-lang "ruby" (js or python)')
    fail("runner: missing data-lang FAIL", mutate(page, 'id="d5-quadkey" data-lang="js"', 'id="d5-quadkey"'), 'runner d5-quadkey: unknown data-lang "" (js or python)')
    q0 = page.index('id="d5-quadkey"')
    q1, q2 = page.index("<pre>", q0), page.index("</pre>", q0) + len("</pre>")
    fail("runner: no starting code FAIL", page[:q1] + "<p>Edit me.</p>" + page[q2:], "runner d5-quadkey has no starting code (pre > code)")
    fail("runner: empty starting code FAIL", page[:q1] + '<pre><code class="language-javascript">  </code></pre>' + page[q2:], "runner d5-quadkey has no starting code")
    fail("runner: data-setup pointing at a missing id FAIL", mutate(page, 'data-setup="d5-kalman-setup"', 'data-setup="d5-nope"'),
         'runner d5-kalman-1d: data-setup "d5-nope" not found')
    fail("runner: data-setup pointing at a script that is not text/plain FAIL",
         mutate(page, '<script type="text/plain" id="d5-kalman-setup">', '<script id="d5-kalman-setup">'),
         'runner d5-kalman-1d: data-setup "d5-kalman-setup" must be a <script type="text/plain">')
    for bad in ("5s", "0", "-200", "2.5"):
        fail(f'runner: data-timeout "{bad}" FAIL', mutate(page, 'data-timeout="3000"', f'data-timeout="{bad}"'),
             f'runner d5-kalman-1d: data-timeout "{bad}" is not a positive integer')
    fail("runner: duplicate runner id FAIL", mutate(page, 'id="d5-quadkey"', 'id="d5-kalman-1d"'), "duplicate runner id d5-kalman-1d")
    t.page_m02.write_text(page, encoding="utf-8")

    # ---- single-format page: Python runner is a warning ----------------------------------------------------------------
    sp = t.spage.replace('<section class="trust"', body(py_snip) + '\n<section class="trust"', 1)
    (t.s_site / "index.html").write_text(sp, encoding="utf-8")
    code, out = _runner_validate(t, t.s_site, None)
    check("runner: Python runner on a single-format page is a warning, not a FAIL",
          code == 0 and "warning: runner d5-rhumb-vs-great-circle: Python runner on a single-format page — the bundle is offline-first" in out, out)
    sp_js = t.spage.replace('<section class="trust"', body(js_snip) + '\n<section class="trust"', 1)
    (t.s_site / "index.html").write_text(sp_js, encoding="utf-8")
    code, out = _runner_validate(t, t.s_site, None)
    check("runner: JavaScript runners on a single-format page PASS without the warning", code == 0 and "runner" not in out, out)
    (t.s_site / "index.html").write_text(t.spage, encoding="utf-8")

    # ---- opt-in node run (ATLAS_RUN_RUNNERS=1) --------------------------------------------------------------------------
    if t.node:
        on = {"ATLAS_RUN_RUNNERS": "1"}
        code, out = _runner_validate(t, t.topic, "m02-kinds.html", on)
        check("runner: ATLAS_RUN_RUNNERS=1 — both JS runners' node output equals data-expected (setup prepended), PASS",
              code == 0 and "runner" not in out, out)
        t.page_m02.write_text(mutate(page, "sigma=124 m", "sigma=125 m"), encoding="utf-8")
        c, o = _runner_validate(t, t.topic, "m02-kinds.html", on)
        check("runner: ATLAS_RUN_RUNNERS=1 — wrong data-expected FAIL with the first differing line",
              c == 1 and 'runner d5-kalman-1d: node output differs from data-expected at line 2: got "z=21.0331  K=0.495  x=21.0314  sigma=124 m", expected "z=21.0331  K=0.495  x=21.0314  sigma=125 m"' in o, o)
        t.page_m02.write_text(mutate(page, "// check: the parent tile", "undefinedFn(); // check: the parent tile"), encoding="utf-8")
        c, o = _runner_validate(t, t.topic, "m02-kinds.html", on)
        check("runner: ATLAS_RUN_RUNNERS=1 — code that throws FAIL with the error", c == 1 and "runner d5-quadkey: node run failed: ReferenceError: undefinedFn is not defined" in o, o)
        t.page_m02.write_text(mutate(page, "sigma=124 m", "sigma=125 m"), encoding="utf-8")
        code, out = _runner_validate(t, t.topic, "m02-kinds.html")
        check("runner: without ATLAS_RUN_RUNNERS a wrong data-expected is not checked", code == 0 and "node output differs" not in out, out)
        node_dir = str(Path(t.node).resolve().parent).lower()
        no_node = os.pathsep.join(d for d in os.environ.get("PATH", "").split(os.pathsep)
                                  if d and str(Path(d).resolve()).lower() != node_dir and not (Path(d) / "node.exe").exists() and not (Path(d) / "node").exists())
        code, out = _runner_validate(t, t.topic, "m02-kinds.html", on, path=no_node)
        check("runner: ATLAS_RUN_RUNNERS=1 without node on PATH — one warning, no FAIL",
              code == 0 and out.count("warning: runner node check skipped (node not on PATH)") == 1, out)
    else:
        print("      (runner node-run checks skipped: node not on PATH)")
    t.page_m02.write_text(t.m02, encoding="utf-8")
# ==== END runner ====


# ==== BLOCK export — G1 offline bundle · G2 PDF/print pipeline ====
# No test here touches the network: vendoring copies from a fake cache (--vendor-from), the offline error goes through
# a proxy on 127.0.0.1:9, and print_pdf.py drives a fake browser (a .py script that logs its argv and writes a PDF).
EXPORT_GF = ("/* cyrillic */\n@font-face {\n  font-family: 'IBM Plex Sans';\n  font-weight: 400;\n"
             "  src: url(https://fonts.gstatic.com/s/ibmplexsans/v19/cyr400.woff2) format('woff2');\n  unicode-range: U+0400-045F;\n}\n"
             "/* latin */\n@font-face {\n  font-family: 'IBM Plex Sans';\n  font-weight: 400;\n"
             "  src: url(https://fonts.gstatic.com/s/ibmplexsans/v19/lat400.woff2) format('woff2');\n  unicode-range: U+0000-00FF;\n}\n")
EXPORT_FAKE_BROWSER = r'''import json, sys
from pathlib import Path
args = sys.argv[1:]
with open(Path(__file__).with_suffix(".log"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\n")
out = next(a.split("=", 1)[1] for a in args if a.startswith("--print-to-pdf="))
objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> >>"]
pdf, offs = bytearray(b"%PDF-1.4\n"), []
for i, o in enumerate(objs, 1):
    offs.append(len(pdf))
    pdf += b"%d 0 obj\n" % i + o + b"\nendobj\n"
x = len(pdf)
pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
Path(out).write_bytes(bytes(pdf))
'''


def export_cache(root: Path) -> Path:
    """A fake vendor cache laid out like assets/vendor/ (raw Google css with gstatic urls, KaTeX css with woff2 + woff)."""
    files = {
        "katex/katex.min.css": '@font-face{font-family:KaTeX_Main;src:url(fonts/KaTeX_Main-Regular.woff2) format("woff2"),'
                               'url(fonts/KaTeX_Main-Regular.woff) format("woff")}.katex{font:normal 1.21em KaTeX_Main}',
        "katex/fonts/KaTeX_Main-Regular.woff2": "w2", "katex/fonts/KaTeX_Main-Regular.woff": "w1",
        "katex/katex.min.js": "window.katex = { render: function () {} };",
        "katex/contrib/auto-render.min.js": "window.renderMathInElement = function () {};",
        "highlight/highlight.min.js": "window.hljs = { highlightElement: function () {} };",
        "highlight/languages/verilog.min.js": "/* verilog */", "highlight/languages/matlab.min.js": "/* matlab */",
        "fonts/fonts.css": EXPORT_GF, "fonts/atkinson.css": EXPORT_GF.replace("ibmplexsans", "atkinsonhyperlegible"),
        "fonts/ibmplexsans-v19-cyr400.woff2": "c", "fonts/ibmplexsans-v19-lat400.woff2": "l",
        "fonts/atkinsonhyperlegible-v19-cyr400.woff2": "c", "fonts/atkinsonhyperlegible-v19-lat400.woff2": "l",
    }
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body, encoding="utf-8")
    return root


@feature_test
def export_features(t):
    """G1 scaffold.py --offline / vendor.py, validator, bundle.py offline inlining · G2 print CSS, runtime, print_pdf.py."""
    run, check, R = t.run, t.check, t.result_of
    plugin, work = t.PLUGIN, t.WORK / "export"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    cache = export_cache(work / "cache")
    site = work / "site"
    shutil.copytree(t.topic, site)
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    eblock = app[app.index("==== BLOCK export"):app.index("==== END export")]
    cblock = css[css.index("==== BLOCK export"):css.index("==== END export")]

    # ---- G1: runtime + template stay CDN-based -----------------------------------------------------------------
    check("export: app.js vendorUrl() lives in the export block; the highlight.js loader and the F2 font use it; hljs preloaded is reused",
          "function vendorUrl(cdn, local)" in eblock and "SITE.vendor === true" in eblock
          and "vendorUrl('https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/', 'highlight/')" in app
          and "F2_FONT_URL = vendorUrl(" in app and "(window.hljs ? Promise.resolve() :" in app)
    check("export: the template ships no vendor files and no PDFs",
          not (t.TEMPLATE / "assets" / "vendor").exists() and not list(t.TEMPLATE.rglob("*.pdf")))

    # ---- G1: scaffold --offline from a cache ---------------------------------------------------------------------
    code, out = run("scaffold.py", site, "--offline", "--vendor-from", cache)
    r = R(out)
    vdir = site / "assets" / "vendor"
    man_p = vdir / "manifest.json"
    man = json.loads(man_p.read_text(encoding="utf-8")) if man_p.exists() else {}
    files = man.get("files", {})
    pages = [site / "index.html"] + sorted((site / "pages").glob("*.html"))
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    cdn = [p.name for p, s in texts.items() if re.search(r'<(?:link|script)[^>]+(?:href|src)="https://(?:fonts\.googleapis|fonts\.gstatic|cdn\.jsdelivr|cdnjs)', s)]
    mod = texts.get(site / "pages" / "_module.html", "")
    sreg = json.loads((site / "assets" / "site.json").read_text(encoding="utf-8"))
    fonts_css = (vdir / "fonts" / "fonts.css").read_text(encoding="utf-8") if (vdir / "fonts" / "fonts.css").exists() else ""
    check("export: scaffold --offline --vendor-from copies the vendor set, writes the manifest, sets site.json vendor",
          code == 0 and r.get("status") == "PASS" and r.get("vendored") == str(len(files)) == "14" and r.get("fetched") == "14"
          and sreg.get("vendor") is True and '"vendor": true' in (site / "assets" / "site.js").read_text(encoding="utf-8")
          and all(set(e) == {"url", "bytes", "sha256"} and len(e["sha256"]) == 64 for e in files.values())
          and files.get("katex/katex.min.css", {}).get("url") == "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css"
          and files.get("fonts/ibmplexsans-v19-lat400.woff2", {}).get("url") == "https://fonts.gstatic.com/s/ibmplexsans/v19/lat400.woff2", out)
    check("export: every page (skeletons too) points at assets/vendor/ with the right ../ prefix; preconnect hints dropped",
          not cdn and '<link rel="stylesheet" href="../assets/vendor/katex/katex.min.css">' in mod
          and '<script defer src="../assets/vendor/katex/contrib/auto-render.min.js"></script>' in mod
          and '<link rel="stylesheet" href="assets/vendor/fonts/fonts.css">' in texts[site / "index.html"]
          and "preconnect" not in "".join(texts.values()) and int(r.get("rewritten", 0)) >= 8, ", ".join(cdn) + out)
    check("export: the Google Fonts css is rewritten to the local woff2 files (no gstatic url left)",
          "url(ibmplexsans-v19-lat400.woff2)" in fonts_css and "gstatic" not in fonts_css)
    before = {p: p.read_bytes() for p in [man_p] + pages}
    code, out = run("scaffold.py", site, "--offline", "--vendor-from", cache)
    check("export: --offline is idempotent (nothing fetched, manifest and pages byte-identical)",
          code == 0 and R(out).get("fetched") == "0" and R(out).get("rewritten") == "0" and all(p.read_bytes() == b for p, b in before.items()), out)
    shutil.rmtree(cache / "katex" / "fonts")
    (vdir / "katex" / "fonts" / "KaTeX_Main-Regular.woff").unlink()
    code, out = run("scaffold.py", site, "--offline", "--vendor-from", cache)
    check("export: a file missing from the cache FAIL names it", code == 1 and "katex/fonts/KaTeX_Main-Regular.woff is not in the vendor cache" in out, out)
    export_cache(cache)
    run("scaffold.py", site, "--offline", "--vendor-from", cache)
    code, out = run("scaffold.py", site, "--sync", "--vendor-from", cache)
    check("export: --vendor-from without --offline is a usage error", code == 2 and "--vendor-from needs --offline" in out, out)

    # offline without a cache: urllib goes through a dead proxy on localhost, so nothing reaches the network
    fresh = work / "fresh"
    shutil.copytree(t.topic, fresh)
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy", "http_proxy", "https_proxy", "all_proxy")}
    env.update(HTTPS_PROXY="http://127.0.0.1:9", HTTP_PROXY="http://127.0.0.1:9")
    p = subprocess.run([PY, str(t.SCRIPTS / "scaffold.py"), str(fresh), "--offline"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=120)
    out = p.stdout + p.stderr
    check("export: --offline with no network FAIL with a clear message; site.json keeps no vendor flag",
          p.returncode == 1 and "could not download https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" in out and "are you offline?" in out
          and "--vendor-from" in out and "vendor" not in json.loads((fresh / "assets" / "site.json").read_text(encoding="utf-8")), out)

    # ---- G1: validator -------------------------------------------------------------------------------------------
    sel = ("--pages", "index.html,glossary.html,m02-kinds.html")
    code, out = run("validate.py", site, *sel)
    check("export: validate on the vendored site PASS (vendored=14, no CDN error)",
          code == 0 and R(out).get("vendored") == "14" and "from a CDN" not in out, out)
    g = site / "pages" / "glossary.html"
    gtext = g.read_text(encoding="utf-8")
    g.write_text(gtext.replace("</head>", '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/mhchem.min.js"></script>\n</head>'), encoding="utf-8")
    code, out = run("validate.py", site, *sel)
    check("export: a vendored page still loading a CDN script FAIL",
          code == 1 and "vendored site: <script> still loads https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/mhchem.min.js from a CDN" in out, out)
    g.write_text(gtext, encoding="utf-8")
    js = vdir / "katex" / "katex.min.js"
    js.write_text("tampered", encoding="utf-8")
    code, out = run("validate.py", site, *sel)
    check("export: a vendor file whose sha256 differs from the manifest FAIL",
          code == 1 and re.search(r"manifest\.json:\d+ vendor file katex/katex\.min\.js does not match its manifest sha256", out) is not None, out)
    js.unlink()
    code, out = run("validate.py", site, *sel)
    check("export: a vendor file listed in the manifest but missing FAIL", code == 1 and "vendor file katex/katex.min.js is missing" in out, out)
    code, out = run("scaffold.py", site, "--offline", "--vendor-from", cache)
    check("export: --offline repairs a missing vendor file", code == 0 and R(out).get("fetched") == "1" and js.exists(), out)
    man_p.rename(man_p.with_suffix(".bak"))
    code, out = run("validate.py", site, *sel)
    check("export: vendor true without assets/vendor/manifest.json FAIL", code == 1 and "assets/vendor/manifest.json is missing" in out, out)
    man_p.with_suffix(".bak").rename(man_p)
    sj = site / "assets" / "site.json"
    sj.write_text(json.dumps(dict(sreg, vendor="yes"), indent=2) + "\n", encoding="utf-8")
    run("scaffold.py", site, "--sync")
    code, out = run("validate.py", site, *sel)
    check("export: site.json vendor other than true FAIL", code == 1 and 'site.json vendor must be true or absent (got "yes")' in out, out)
    sj.write_text(json.dumps(sreg, indent=2) + "\n", encoding="utf-8")
    run("scaffold.py", site, "--sync")

    # ---- G1: bundle.py inlines the vendored assets ----------------------------------------------------------------
    ssite = work / "single" / "site"
    shutil.copytree(t.s_site, ssite)
    spage = (ssite / "index.html").read_text(encoding="utf-8")
    (ssite / "index.html").write_text(spage.replace('<section class="trust"', '<pre><code class="language-python">print(1)</code></pre>\n<section class="trust"', 1), encoding="utf-8")
    code, out = run("scaffold.py", ssite, "--offline", "--vendor-from", cache)
    check("export: single site --offline PASS, index.html rewritten", code == 0 and 'href="assets/vendor/katex/katex.min.css"' in (ssite / "index.html").read_text(encoding="utf-8"), out)
    bout = work / "single" / "bundle.html"
    code, out = run("bundle.py", ssite, "--out", bout)
    b = bout.read_text(encoding="utf-8") if bout.exists() else ""
    bare = re.sub(r"<!--[\s\S]*?-->", "", b)
    check("export: bundle of a vendored single page inlines KaTeX css/js and fonts as data: URIs (woff2 only, latin subsets only)",
          code == 0 and "url(data:font/woff2;base64," in b and "KaTeX_Main-Regular.woff)" not in b and "format(\"woff\")" not in b
          and "cyr400" not in b and "unicode-range: U+0400" not in b and "window.katex = " in b and "window.renderMathInElement = " in b
          and not re.search(r'(src|href)="(\./)?assets/', bare) and "SITE.vendor = 'inline'" in b, out)
    check("export: bundle inlines highlight.js when the page has code", "window.hljs = " in b and "/* verilog */" in b and b.index("window.hljs = ") < b.rindex("</body>"), out)
    if t.node:
        errs = []
        for i, blk in enumerate(re.findall(r"<script>([\s\S]*?)</script>", bare)):
            f = work / f"bundle-{i}.js"
            f.write_text(blk, encoding="utf-8")
            pr = subprocess.run([t.node, "--check", str(f)], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if pr.returncode:
                errs.append(f"block {i}: {pr.stderr[:200]}")
        check("export: node --check passes on every inline script of the offline bundle", not errs, "\n".join(errs))
    ssj = ssite / "assets" / "site.json"
    ssj.write_text(json.dumps(dict(json.loads(ssj.read_text(encoding="utf-8")), budgetKb=1), indent=2) + "\n", encoding="utf-8")
    code, out = run("bundle.py", ssite, "--out", bout)
    check("export: an offline bundle over budgetKb is a warning naming the size, not a FAIL",
          code == 0 and re.search(r"warning: offline bundle is \d+ KB with the vendored assets inlined \(\d+ KB\), over the 1 KB budget", out) is not None, out)

    # ---- G2: print CSS + runtime ----------------------------------------------------------------------------------
    check("export: style.css print block — @page header/footer boxes, module h2 page breaks, link URLs, break-inside, canvas swap",
          "@page" in cblock and "@bottom-right { content: counter(page)" in cblock and 'body[data-print="module"] main.content > section' in cblock
          and "break-before: page" in cblock and 'attr(href)' in cblock and "break-inside: avoid" in cblock and "img.qc-print-canvas" in cblock
          and "canvas.qc-print-swapped" in cblock)
    check("export: app.js export-print feature — running header, beforeprint/afterprint canvas swap, QC.printPrepare/printRestore",
          "feature({\n    name: 'export-print', phase: 'shell'" in eblock and "addEventListener('beforeprint', printPrepare)" in eblock
          and "addEventListener('afterprint', printRestore)" in eblock and "toDataURL('image/png')" in eblock and "@top-left" in eblock
          and "api: { printPrepare, printRestore }" in eblock)

    # ---- G2: print_pdf.py with a fake browser -----------------------------------------------------------------------
    fake = work / "fake_browser.py"
    fake.write_text(EXPORT_FAKE_BROWSER, encoding="utf-8")
    log = fake.with_suffix(".log")
    pdf_dir = work / "pdf"
    order = [p["file"] for p in sreg["pages"]]
    code, out = run("print_pdf.py", site, "--browser", fake, "--out", pdf_dir)
    r = R(out)
    calls = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    urls = [c[-1] for c in calls]
    names = sorted(p.name for p in pdf_dir.glob("*.pdf"))
    want = [f"{i:02d}-{Path(f).stem}.pdf" for i, f in enumerate(order, 1)]
    try:
        import pypdf  # noqa: F401
        has_pypdf = True
    except ImportError:
        has_pypdf = False
    check("export: print_pdf.py prints every page in site.json order with the headless flags (fake browser)",
          code == 0 and r.get("status") == "PASS" and r.get("pdfs") == str(len(order)) and r.get("handout") == "no"
          and [u.rsplit("/", 1)[-1] for u in urls] == order and urls[0].startswith("file:") and "/pages/" in urls[1]
          and all("--headless=new" in c and "--no-pdf-header-footer" in c and any(a.startswith("--virtual-time-budget=") for a in c)
                  and any(a.startswith("--print-to-pdf=") for a in c) for c in calls)
          and all(n in names for n in want), out + "\n" + "\n".join(urls))
    check("export: print_pdf.py merges site.pdf only when pypdf is importable (optional dependency)",
          (r.get("combined") == "site.pdf" and (pdf_dir / "site.pdf").exists()) if has_pypdf
          else (r.get("combined") == "none" and "pypdf is not installed" in out), out)
    log.unlink()
    code, out = run("print_pdf.py", site, "--browser", fake, "--out", pdf_dir, "--handout", "--pages", "glossary.html,index.html")
    calls = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    gi = order.index("glossary.html") + 1
    check("export: print_pdf.py --handout --pages: ?mode=handout on every URL, reading order kept, NN from the whole order",
          code == 0 and R(out).get("pdfs") == "2" and R(out).get("handout") == "yes" and [c[-1].rsplit("/", 1)[-1] for c in calls] == ["index.html?mode=handout", "glossary.html?mode=handout"]
          and (pdf_dir / "01-index-handout.pdf").exists() and (pdf_dir / f"{gi:02d}-glossary-handout.pdf").exists(), out)
    code, out = run("print_pdf.py", site, "--browser", fake, "--pages", "nope.html")
    check("export: print_pdf.py --pages with an unknown page is a usage error", code == 2 and "not in site.json pages[]: nope.html" in out, out)
    broken = work / "broken_browser.py"
    broken.write_text("import sys\nsys.stderr.write('boom: no GPU\\n')\nsys.exit(3)\n", encoding="utf-8")
    code, out = run("print_pdf.py", site, "--browser", broken, "--out", work / "pdf2", "--pages", "index.html")
    check("export: a browser that writes no PDF FAIL with its exit code and stderr", code == 1 and "index.html: no PDF written (browser exit 3): boom: no GPU" in out, out)
    code, out = run("print_pdf.py", site, "--browser", work / "no-such-chrome.exe")
    check("export: no browser exits 2 with a clear message", code == 2 and "no headless browser found" in out and "--browser" in out, out)
    code, out = run("print_pdf.py", ssite, "--browser", fake, "--out", work / "pdf3")
    check("export: print_pdf.py on a single-format site prints its one page", code == 0 and R(out).get("pdfs") == "1" and (work / "pdf3" / "01-index.pdf").exists(), out)

    # ---- docs -----------------------------------------------------------------------------------------------------
    contracts = (plugin / "references" / "contracts.md").read_text(encoding="utf-8")
    skill = (plugin / "skills" / "compose" / "SKILL.md").read_text(encoding="utf-8")
    exp = plugin / "skills" / "compose" / "references" / "export.md"
    check("export: contracts.md, compose SKILL.md and references/export.md document --offline and print_pdf.py",
          "--offline" in contracts and "print_pdf.py" in contracts and '"vendor"' in contracts
          and "--offline" in skill and "print_pdf.py" in skill and exp.exists()
          and all(s in exp.read_text(encoding="utf-8") for s in ("--vendor-from", "manifest.json", "?mode=handout", "pypdf", "--browser")))
# ==== END export ====


# ==== BLOCK research — I1 reader emphasis from the Use answer · I5 discovery extensions ====
@feature_test
def research_features(t):
    """I1 Readers (derived, never asked) · I5 Discovery, dossier Kind column, enrich_openalex.py (fixture cache, no network)."""
    run, check, mutate, R, line_no = t.run, t.check, t.mutate, t.result_of, t.line_no
    plugin = t.PLUGIN
    rd = lambda *p: plugin.joinpath(*p).read_text(encoding="utf-8")  # noqa: E731

    # ---- prompt files carry the derivation ------------------------------------------------------------------------
    guide = rd("skills", "collect-insights", "references", "interview-guide.md")
    refiner = rd("agents", "insight-refiner.md")
    ins_t = rd("skills", "collect-insights", "references", "insights-template.md")
    check("research: interview guide derives Readers and Discovery and says personas are never asked (no persona dimension)",
          "| Readers | creative student |" in guide and "| Discovery | none (today's search budgets) |" in guide
          and "**Personas are derived, never asked (I1).**" in guide and "| Persona" not in guide.split("## 2.")[0])
    check("research: refiner derives Readers from Use/Goal with a quoted reason, default creative student, at most one you-decide gap; Discovery opt-in",
          "Readers (I1) ← Use and Goal, **derived, never asked**" in refiner and "**Default `creative student`**" in refiner
          and "**at most one** non-blocking direction gap" in refiner and "Discovery (I5) ← Use, Goal and Readers" in refiner
          and "Software developer → `code, standards`" in refiner and "researcher → `datasets`" in refiner)
    check("research: INSIGHTS template and plan template carry the Readers / Discovery rows and header lines",
          "| Readers |" in ins_t and "| Discovery |" in ins_t and "**Readers**: {" in rd("references", "plan-template.md")
          and "**Discovery**: {" in rd("references", "plan-template.md") and "`Readers` = the persona names" in rd("skills", "collect-insights", "SKILL.md"))
    ba, bt = rd("agents", "brief-author.md"), rd("skills", "research", "references", "brief-template.md")
    check("research: brief author leans modules on the persona (examples / tables / code / derivations) and copies Discovery; brief template has the lines and rows",
          "7c. **Reader emphasis (I1)**" in ba and "worked examples" in ba and "look-up tables" in ba and "runnable code" in ba and "derivations" in ba
          and "7d. **Discovery (I5)**" in ba and "Reader emphasis:" in bt and "Discovery (extra source classes, at most 2 searches per module per class" in bt
          and "| Readers | … | … |" in bt and "| Discovery | … | … |" in bt)
    sk = rd("skills", "compose", "SKILL.md")
    persona_rows = ("| creative student |", "| engineer |", "| software developer |", "| circuit designer |", "| researcher |", "| instructor |")
    check("research: compose SKILL.md has the persona → modules table naming protocol, runner, circuit, study and the print/offline offer",
          "**I1 reader emphasis**" in sk and all(r in sk for r in persona_rows) and all(f"`{m}`" in sk for m in ("protocol", "runner", "circuit", "study"))
          and "demo-uncertainty.html" in sk and "print/offline" in sk)
    proto = rd("skills", "research", "references", "research-protocol.md")
    check("research: protocol has the I5 source classes with tiers, the per-class cap and the OpenAlex step; scout, researcher, research skill and contracts follow",
          "**I5 source classes.**" in proto and "IEEE 754-2019" in proto and "at most 2 searches per module per class" in proto and "tune it after the first run" in proto
          and "**OpenAlex enrichment (I5)**" in proto and "**Other source classes (I5)**" in rd("agents", "field-scout.md")
          and "3a. **Discovery (I5)**" in rd("agents", "module-researcher.md") and "### B2a. OpenAlex enrichment (I5, opt-in)" in rd("skills", "research", "SKILL.md")
          and "**I1 reader emphasis / I5 discovery**" in rd("references", "contracts.md") and "**I5 source kind**" in rd("references", "contracts.md")
          and "| `enrich_openalex.py` |" in rd("references", "contracts.md") and "| Kind |" in rd("skills", "research", "references", "dossier-template.md"))

    # ---- check_plan: Readers / Discovery ---------------------------------------------------------------------------
    pdir = t.WORK / "research-plan" / "topics" / "map-projections"
    shutil.rmtree(pdir.parent.parent, ignore_errors=True)
    shutil.copytree(t.FIX / "repo" / "topics" / "map-projections", pdir)
    plan, ins = pdir / "PLAN.md", pdir / "tmp" / "INSIGHTS.md"
    plan0, ins0 = plan.read_text(encoding="utf-8"), ins.read_text(encoding="utf-8")

    def plan_run(header: str, ins_text: str = ins0):
        text = mutate(plan0, "**Stage**:", header + "\n**Stage**:")
        plan.write_text(text, encoding="utf-8")
        ins.write_text(ins_text, encoding="utf-8")
        code, out = run("check_plan.py", plan)
        return text, code, out

    text, code, out = plan_run('**Readers**: engineer, software developer — "reference while building"\n**Discovery**: code, standards')
    check("research: check_plan PASS with known Readers (reason after a dash) and Discovery header lines", code == 0 and R(out).get("warnings") == "0", out)
    text, code, out = plan_run("**Readers**: creative student\n**Discovery**: none")
    check("research: check_plan PASS with the default persona and Discovery none", code == 0 and R(out).get("warnings") == "0", out)
    text, code, out = plan_run("**Readers**: hacker")
    check("research: check_plan FAIL on an unknown persona, at the header line",
          code == 1 and re.search(rf":{line_no(text, '**Readers**')} Readers persona `hacker` is not one of: creative student", out) is not None, out)
    text, code, out = plan_run("**Readers**: ")
    check("research: check_plan FAIL on an empty Readers line", code == 1 and "Readers is empty" in out, out)
    text, code, out = plan_run("**Readers**: engineer, researcher, instructor")
    check("research: check_plan warns on three personas", code == 0 and "warning: Readers names 3 personas" in out, out)
    text, code, out = plan_run("**Discovery**: code, podcasts")
    check("research: check_plan FAIL on an unknown discovery class",
          code == 1 and re.search(rf":{line_no(text, '**Discovery**')} Discovery class `podcasts` is not one of: none, datasets", out) is not None, out)
    row_ok = ("| Region | skip regulation | not in scope |\n| Readers | creative student, engineer | \"self-study first, then a reference while making maps\" |\n"
              "| Discovery | none | no persona or words ask for more |")
    ins_ok = mutate(ins0, "| Region | skip regulation | not in scope |", row_ok)
    text, code, out = plan_run("**Readers**: creative student, engineer", ins_ok)
    check("research: check_plan PASS when the INSIGHTS.md Readers / Discovery rows match the header", code == 0 and R(out).get("warnings") == "0", out)
    text, code, out = plan_run("**Readers**: engineer", ins_ok)
    check("research: check_plan warns when the Readers header differs from the INSIGHTS.md row",
          code == 0 and "differs from the INSIGHTS.md Readers row `creative student, engineer`" in out, out)
    ins_bad = mutate(ins_ok, "| Readers | creative student, engineer |", "| Readers | designer |")
    text, code, out = plan_run("**Readers**: creative student", ins_bad)
    check("research: check_plan FAIL on an unknown persona in the INSIGHTS.md Readers row, at that row",
          code == 1 and re.search(rf"INSIGHTS\.md:{line_no(ins_bad, '| Readers | designer |')} INSIGHTS\.md Readers row persona `designer`", out) is not None, out)
    plan.write_text(plan0, encoding="utf-8")
    ins.write_text(ins0, encoding="utf-8")
    code, out = run("check_plan.py", plan)
    check("research: check_plan without Readers / Discovery lines is unchanged (both optional)", code == 0 and R(out).get("warnings") == "0", out)

    # ---- check_dossier: Kind column --------------------------------------------------------------------------------
    demo_fix = t.FIX / "research" / "discovery-demo"
    edir = t.WORK / "research-enrich" / "discovery-demo"
    shutil.rmtree(edir.parent, ignore_errors=True)
    shutil.copytree(demo_fix, edir)
    dfile = edir / "tmp" / "dossier" / "m01-equal-area.md"
    d0 = dfile.read_text(encoding="utf-8")
    code, out = run("check_dossier.py", dfile)
    check("research: dossier with a Kind column PASS and RESULT counts kinds",
          code == 0 and R(out).get("kinds") == "paper:3,dataset:1,code:1,standard:1,lecture:1,book:1" and R(out).get("warnings") == "0", out)
    bad = mutate(d0, "| 1 | 1 | foundational | book |", "| 1 | 1 | foundational | podcast |")
    dfile.write_text(bad, encoding="utf-8")
    code, out = run("check_dossier.py", dfile)
    check("research: dossier FAIL on an unknown Kind, at its row",
          code == 1 and re.search(rf":{line_no(bad, '| podcast |')} Kind `podcast` must be one of paper, dataset, code, standard, lecture, book, web", out) is not None, out)
    blank = mutate(d0, "| 7 | 2 | established | standard |", "| 7 | 2 | established |  |")
    dfile.write_text(blank, encoding="utf-8")
    code, out = run("check_dossier.py", dfile)
    check("research: dossier warns on a blank Kind cell", code == 0 and "warning: Kind cell is blank" in out, out)
    dfile.write_text(d0, encoding="utf-8")
    code, out = run("check_dossier.py", t.FIX / "repo" / "topics" / "map-projections" / "tmp" / "dossier" / "m01-globe-to-plane.md")
    check("research: a dossier without the Kind column is unchanged (no kinds key)", code == 0 and "kinds" not in R(out), out)
    ov = (t.FIX / "repo" / "topics" / "map-projections" / "tmp" / "dossier" / "00-overview.md").read_text(encoding="utf-8")
    ov = mutate(ov, "| # | Tier | Reference | Link | Topics |\n|---|---|---|---|---|", "| # | Tier | Kind | Reference | Link | Topics |\n|---|---|---|---|---|---|")
    ov = mutate(mutate(ov, "| 1 | 1 | Snyder (1987)", "| 1 | 1 | book | Snyder (1987)"), "| 2 | 2 | Gott et al. (2021)", "| 2 | 2 | video | Gott et al. (2021)")
    ovp = edir / "tmp" / "dossier" / "00-overview.md"
    ovp.write_text(ov, encoding="utf-8")
    code, out = run("check_dossier.py", ovp, "--overview")
    check("research: overview bibliography seed Kind column is checked too",
          code == 1 and re.search(rf":{line_no(ov, '| video |')} Kind `video` must be one of", out) is not None and R(out).get("kinds") == "book:1", out)
    ovp.unlink()

    # ---- enrich_openalex.py: fixture cache, never the network ------------------------------------------------------
    cache = edir / "tmp" / "openalex.json"
    cache0 = cache.read_text(encoding="utf-8")
    src = (t.SCRIPTS / "enrich_openalex.py").read_text(encoding="utf-8")
    check("research: enrich_openalex queries api.openalex.org/works/doi:, takes mailto only from ATLAS_OPENALEX_MAILTO and hardcodes no address",
          "https://api.openalex.org/works/" in src and '"/doi:"' in src and 'os.environ.get("ATLAS_OPENALEX_MAILTO"' in src
          and re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", src) is None)
    code, out = run("enrich_openalex.py", edir, "--offline")
    r = R(out)
    check("research: enrich --offline reads the cache, FAILs on the retracted work at its row and warns on the year mismatch",
          code == 1 and r.get("status") == "FAIL" and r.get("retracted") == "1" and r.get("errors") == "1" and r.get("cached") == "4"
          and r.get("missing") == "1" and r.get("ids") == "5" and r.get("enriched") == "3" and r.get("offline") == "yes" and r.get("fetched") == "0"
          and r.get("cache", "").endswith("discovery-demo/tmp/openalex.json")
          and re.search(rf":{line_no(d0, '| 4 | 1 |')} #4 10\.1016/s0140-6736\(97\)11096-0 is RETRACTED", out) is not None
          and re.search(rf":{line_no(d0, '| 2 | 1 |')} warning: #2 year mismatch: cited 2019, OpenAlex 2018", out) is not None
          and "not in OpenAlex" in out and "1 id(s) not looked up (offline" in out, out)
    d1 = dfile.read_text(encoding="utf-8")
    check("research: enrich writes one Enriched line per looked-up source under ## OpenAlex enrichment and leaves the cache untouched offline",
          d1.count("## OpenAlex enrichment") == 1 and d1.count("- Enriched: #") == 4 and "- Enriched: #4 — doi:10.1016/s0140-6736(97)11096-0 · 1998 · The Lancet" in d1
          and "· RETRACTED (OpenAlex" in d1 and "OA https://pubs.usgs.gov/pp/1395/report.pdf" in d1 and cache.read_text(encoding="utf-8") == cache0, d1[-900:])
    code, out = run("enrich_openalex.py", edir, "--offline")
    d2 = dfile.read_text(encoding="utf-8")
    check("research: enrich is idempotent (the section is rewritten, not appended) and the dossier still passes its gate",
          d2 == d1 and run("check_dossier.py", dfile)[0] == 0, out)
    cache.write_text(cache0.replace('"is_retracted": true', '"is_retracted": false'), encoding="utf-8")
    code, out = run("enrich_openalex.py", edir, "--offline", "--no-write")
    check("research: enrich PASS (exit 0) when nothing is retracted; --no-write leaves the dossier alone",
          code == 0 and R(out).get("status") == "PASS" and R(out).get("retracted") == "0" and dfile.read_text(encoding="utf-8") == d2, out)
    cache.write_text(cache0, encoding="utf-8")
    old_api = os.environ.get("ATLAS_OPENALEX_API")
    os.environ["ATLAS_OPENALEX_API"] = "http://127.0.0.1:9/works"   # a closed local port: no real network is touched
    try:
        code, out = run("enrich_openalex.py", edir, "--no-write", "--timeout", "5")
    finally:
        if old_api is None:
            os.environ.pop("ATLAS_OPENALEX_API", None)
        else:
            os.environ["ATLAS_OPENALEX_API"] = old_api
    check("research: a network error degrades to a warning and the cache (offline=yes), the retraction still fails, the cache is not rewritten",
          code == 1 and "OpenAlex lookup of 10.5281/zenodo.0000000 failed" in out and R(out).get("offline") == "yes"
          and R(out).get("retracted") == "1" and "Traceback" not in out and cache.read_text(encoding="utf-8") == cache0, out)
    cache.unlink()
    dfile.write_text(d0, encoding="utf-8")
    code, out = run("enrich_openalex.py", edir, "--offline")
    check("research: enrich --offline without a cache warns, passes, and writes no cache",
          code == 0 and R(out).get("missing") == "5" and R(out).get("enriched") == "0" and not cache.exists()
          and dfile.read_text(encoding="utf-8") == d0, out)
    code, out = run("enrich_openalex.py", t.WORK / "research-enrich" / "no-such-topic")
    check("research: enrich usage error on a missing topic (exit 2)", code == 2 and "RESULT: status=USAGE" in out, out)
    shutil.rmtree(t.WORK / "research-plan", ignore_errors=True)
    shutil.rmtree(t.WORK / "research-enrich", ignore_errors=True)
# ==== END research ====


# ==== BLOCK evidence — references/evidence-policy.md: the gates refuse unsupported content; no instruction file permits it ====
EV_FORBIDDEN = (   # phrases that granted a permission the evidence policy withdrew (policy §3, §5, §6)
    ("unverified — model knowledge", "a reference nobody retrieved used as a Verified value"),
    ("or says `estimate`", "`estimate` accepted as a source"),
    ('explicit "estimate"', "`estimate` accepted as a source"),
    ("typical range", "a remembered range filling a missing value"),
    ("illustrative when estimated", "an unsourced number allowed with a badge"),
    ("label estimated ones illustrative", "an unsourced number allowed with a badge"),
    ("Light: model knowledge", "model knowledge as a verification level"),
    ("what you already know", "model knowledge as field-map content"),
    ("or the `illustrative` badge", "an unsourced number allowed with a badge"),
    ("must carry the `illustrative` badge", "an unsourced number allowed with a badge"),
    ("say why there is no visual", "process text on the page (policy §10)"),
    ("say why in one sentence", "process text on the page (policy §10)"),
    ("say in one sentence why there is none", "process text on the page (policy §10)"),
    ("say why there is none", "process text on the page (policy §10)"),
)


@feature_test
def evidence_policy(t):
    """The scenarios of the evidence policy, at the gates that enforce them (dossier and page), plus a lint over every
    instruction file: no file may keep a permission the policy withdrew, and every skill and agent points at the policy."""
    R = t.result_of
    # ---- dossier gate (research) ------------------------------------------------------------------------------------
    good = (t.FIX / "repo" / "topics" / "map-projections" / "tmp" / "dossier" / "m01-globe-to-plane.md").read_text(encoding="utf-8")
    dfile = t.WORK / "ev-m01.md"

    def dossier(name, text, code_want, *needles, args=()):
        dfile.write_text(text, encoding="utf-8")
        c, o = t.run("check_dossier.py", dfile, *args)
        t.check(name, c == code_want and all(n in o for n in needles), o)
        return o

    out = dossier("evidence: complete documentation — the dossier with sources, locators, C and R ids PASS", good, 0)
    t.check("evidence: the dossier RESULT counts documented calculations and relationships", R(out).get("calcs") == "2" and R(out).get("relations") == "1", out)
    dossier("evidence: missing value — `estimate` in Key facts FAIL (no invented or estimated values)",
            t.mutate(good, "| Web Mercator is cut at about ±85.05° latitude so the map is square | 6 |", "| Web Mercator is cut at about ±85.05° latitude so the map is square | estimate |"),
            1, "`estimate` is not evidence")
    dossier("evidence: untraceable — a `model knowledge` Verified cell FAIL",
            t.mutate(good, "not confirmed automatically — tool home page, no citable description", "unverified — model knowledge"), 1, "Verified cell says `model knowledge`")
    dossier("evidence: a key fact without a locator FAIL",
            t.mutate(good, "| 1 | Mercator projection chapter, scale-factor formula | 1987 |", "| 1 |  | 1987 |"), 1, "Key facts: Locator is blank")
    dossier("evidence: undocumented formula — a demo candidate naming no C id FAIL",
            t.mutate(good, "model: C1 (source 1);", "model: k = sec φ (source 1);"), 1, "demo candidate names no documented calculation")
    dossier("evidence: a demo candidate naming an unknown C id FAIL",
            t.mutate(good, "model: C1 (source 1);", "model: C9 (source 1);"), 1, "names C9, which is not in `## Documented calculations`")
    dossier("evidence: a documented calculation citing no source FAIL",
            t.mutate(good, "| sphere; latitude below 90° in magnitude | 1 |", "| sphere; latitude below 90° in magnitude |  |"), 1, "Documented calculations: no source")
    dossier("evidence: missing relationship — a relationship row citing a source that does not exist FAIL",
            t.mutate(good, "| a developable surface (cylinder, cone or plane) | 3 |", "| a developable surface (cylinder, cone or plane) | 12 |"), 1, "source #12 does not exist")
    dossier("evidence: user assumption — `user` is accepted for a running-example parameter (labelled user-provided)", good, 0)
    dossier("evidence: user assumption — `user` is NOT accepted as the source of a key fact",
            t.mutate(good, "| Web Mercator is cut at about ±85.05° latitude so the map is square | 6 |", "| Web Mercator is cut at about ±85.05° latitude so the map is square | user |"),
            1, "Key facts: source cell `user` has no source #")
    ov = (t.FIX / "repo" / "topics" / "map-projections" / "tmp" / "dossier" / "00-overview.md").read_text(encoding="utf-8")
    dossier("evidence: overview — a parameter-sheet value without a source FAIL",
            t.mutate(ov, "| km | user (m01 running example) |", "| km | estimate |"), 1, "parameter `Earth radius (sphere)` has no source", args=("--overview",))
    dossier("evidence: overview — a page's Demos line naming no documented calculation FAIL",
            t.mutate(ov, "- Demos: latitude slider (m02 C1)", "- Demos: latitude slider"), 1, "`- Demos:` names no documented calculation", args=("--overview",))
    dossier("evidence: overview — a page's Diagrams line citing no relationship or source FAIL",
            t.mutate(ov, "- Diagrams: rhumb line vs great circle — m02 #1", "- Diagrams: rhumb line vs great circle"), 1, "`- Diagrams:` cites no documented relationship", args=("--overview",))
    dossier("evidence: no suitable visualization — `none — <why>` on Demos and Diagrams PASS",
            t.mutate(t.mutate(ov, "- Demos: latitude slider (m02 C1)", "- Demos: none — the sources give no formula with two inputs"),
                     "- Diagrams: rhumb line vs great circle — m02 #1", "- Diagrams: none — no documented relationships"), 0, args=("--overview",))
    dfile.unlink()

    # ---- page gate (compose) ------------------------------------------------------------------------------------------
    page = t.m02

    def pg(name, text, code_want, *needles):
        t.page_m02.write_text(text, encoding="utf-8")
        c, o = t.run("validate.py", t.topic, "--pages", "m02-kinds.html")
        t.check(name, c == code_want and all(n in o for n in needles), o)

    pg("evidence: interactive diagram with data-cite PASS", page, 0)
    pg("evidence: interactive diagram citing nothing FAIL", t.mutate(page, 'data-steps data-cite="#ref-key">', "data-steps>"), 1, "figure fig-steps cites no source")
    pg("evidence: a diagram whose elements carry data-cite (no figure-level cite) PASS",
       t.mutate(t.mutate(page, 'data-steps data-cite="#ref-key">', "data-steps>"), '<rect class="d-box" x="20" y="60"', '<rect class="d-box" data-cite="#ref-key" x="20" y="60"'), 0)
    pg("evidence: a diagram with a cite in its caption PASS",
       t.mutate(t.mutate(page, 'data-steps data-cite="#ref-key">', "data-steps>"), "Step through it.</figcaption>", 'Step through it <a class="cite" href="#ref-key">[1]</a>.</figcaption>'), 0)
    pg("evidence: a data-cite that does not resolve FAIL", t.mutate(page, 'data-steps data-cite="#ref-key">', 'data-steps data-cite="#ref-nope">'), 1, "data-cite #ref-nope does not resolve")
    pg("evidence: the generated site map needs no cite PASS",
       t.mutate(page, "</figure>", '</figure>\n    <figure class="diagram" id="ev-sitemap"><svg data-sitemap viewBox="0 0 10 10"></svg><figcaption>Site map.</figcaption></figure>'), 0)
    demo = ('<div class="demo" id="ev-demo"><div class="demo-head"><h4>k</h4><span class="badge illustrative">Model output</span></div>'
            '<div class="demo-body"><div class="demo-controls"><div class="ctl"><label for="ev-phi">φ</label><output for="ev-phi"></output>'
            '<input type="range" id="ev-phi" min="0" max="80" value="60"></div></div><div class="demo-output"><div class="readouts"><div class="readout">'
            '<div class="r-label">k</div><div class="r-val" id="ev-k">—</div></div></div></div></div>'
            '<div class="demo-note">Model: k = sec φ CITE.</div></div>')
    with_demo = lambda cite: t.mutate(page, "</figure>", "</figure>\n    " + demo.replace("CITE", cite))   # noqa: E731
    pg("evidence: a demo whose note cites its documented calculation PASS (illustrative = computed output, allowed inside the demo)",
       with_demo('<a class="cite" href="#ref-key">[1]</a>'), 0)
    pg("evidence: incomplete calculation inputs / undocumented formula — a demo citing nothing FAIL", with_demo(""), 1, "demo ev-demo cites no source for its model")
    pg("evidence: an `illustrative` badge on a stated number in prose FAIL",
       t.mutate(page, '<p>…</p>\n    <figure class="diagram" id="fig-steps"', '<p>Greenland looks 10 times too large <span class="badge illustrative">Illustrative</span>.</p>\n    <figure class="diagram" id="fig-steps"'),
       1, "illustrative badge outside a demo or computed figure")
    gap = '<p>The latitude limit of the tile scheme <!-- GAP: tile-scheme latitude limit --> BADGE.</p>\n    <figure class="diagram" id="fig-steps"'
    pg("evidence: missing information — a GAP marker without a visible badge FAIL (never filled silently)",
       t.mutate(page, '<p>…</p>\n    <figure class="diagram" id="fig-steps"', gap.replace("BADGE", "")), 1, "1 GAP marker(s) but 0 visible gap badge(s)")
    pg("evidence: a GAP marker with a visible 'Not available in sources' badge PASS",
       t.mutate(page, '<p>…</p>\n    <figure class="diagram" id="fig-steps"', gap.replace("BADGE", '<span class="badge unavailable">Not available in sources</span>')), 0)
    pg("evidence: conflicting sources shown with the conflict badge and both cites PASS",
       t.mutate(page, '<p>…</p>\n    <figure class="diagram" id="fig-steps"',
                '<p>The limit is 85.05° <a class="cite" href="#ref-key">[1]</a> or 85.06° <a class="cite" href="#ref-key">[1]</a> <span class="badge conflict">Sources conflict</span>.</p>\n    <figure class="diagram" id="fig-steps"'), 0)
    # §10: the page states the subject and its sources, never how or why it was made
    para = lambda txt: t.mutate(page, '<p>…</p>\n    <figure class="diagram" id="fig-steps"', f'<p>{txt}</p>\n    <figure class="diagram" id="fig-steps"')   # noqa: E731
    pg("evidence: process text — narrating why a diagram was added FAIL",
       para('This diagram was added because the projection families are easier to compare side by side.'), 1, 'process text "This diagram was added because"')
    pg("evidence: process text — first-person decision FAIL", para('We omitted the Robinson projection.'), 1, 'process text "We omitted"')
    pg("evidence: process text — explaining a missing visual FAIL", para('There is no demo here because no formula was documented.'), 1, 'process text "There is no demo here because"')
    pg("evidence: process text — AI self-reference FAIL", para('This summary was generated by an AI assistant.'), 1, 'process text "generated by an AI"')
    pg("evidence: workflow text — gap worded about the search FAIL",
       para('The tile limit is not in the dossier <span class="badge unavailable">Not available in sources</span>.'), 1, 'workflow text "the dossier"')
    pg("evidence: workflow text — naming an agent role FAIL", para('The page writer left this value open.'), 1, 'workflow text "page writer"')
    pg("evidence: gap worded about the sources PASS",
       para('The cited sources do not state the tile scheme\'s latitude limit <span class="badge not-specified">Not specified</span>.'), 0)
    atlas_page = t.mutate(page, "<body ", '<body data-subject="atlaspedia" ')
    pg("evidence: data-subject=\"atlaspedia\" outside the atlaspedia site skips the vocabulary list with a warning, still fails self-reference",
       t.mutate(atlas_page, '<p>…</p>\n    <figure class="diagram" id="fig-steps"', '<p>The page writer reads the dossier. We chose this layout.</p>\n    <figure class="diagram" id="fig-steps"'),
       1, 'process text "We chose"', 'page still carries data-subject="atlaspedia"')
    t.page_m02.write_text(page, encoding="utf-8")
    tmpl = {n: (t.TEMPLATE / n).read_text(encoding="utf-8") for n in ("index.html", "styleguide.html")}
    t.check("evidence: the template home and the style guide (subject: the atlaspedia workflow) carry data-subject=\"atlaspedia\"; no other template page does",
            all('data-subject="atlaspedia"' in s for s in tmpl.values())
            and not any('data-subject=' in p.read_text(encoding="utf-8") for p in t.TEMPLATE.glob("*.html") if p.name not in tmpl))

    # ---- runtime and stylesheet ------------------------------------------------------------------------------------
    app = (t.TEMPLATE / "assets" / "app.js").read_text(encoding="utf-8")
    css = (t.TEMPLATE / "assets" / "style.css").read_text(encoding="utf-8")
    t.check("evidence: app.js registers evidence-cite in the shell phase (before scholar-refs binds the hover cards) and no longer calls demos illustrative",
            "feature({ name: 'evidence-cite', phase: 'shell'" in app and "illustrative models" not in app and "Illustrative calculations" not in app)
    t.check("evidence: style.css has every evidence-status badge and the data-cite styles",
            all(f".badge.{b}" in css for b in ("documented", "not-specified", "insufficient", "unavailable", "conflict", "user-input")) and ".fig-sources" in css and ".cited" in css)

    # ---- instruction lint: no file keeps a withdrawn permission; every skill and agent points at the policy ----------
    texts = {f: f.read_text(encoding="utf-8") for f in t.PLUGIN.rglob("*") if f.suffix in (".md", ".html", ".js", ".py")
             and "tests" not in f.relative_to(t.PLUGIN).parts and f.name != "evidence-policy.md"}
    hits = [f"{f.relative_to(t.PLUGIN)}: “{ph}” ({why})" for f, s in texts.items() for ph, why in EV_FORBIDDEN if ph in s]
    t.check("evidence: no instruction, template, snippet or script keeps a withdrawn permission (estimate, model knowledge, typical ranges, illustrative numbers)",
            not hits, "\n".join(hits))
    roles = sorted((t.PLUGIN / "agents").glob("*.md")) + sorted((t.PLUGIN / "skills").glob("*/SKILL.md"))
    missing = [str(f.relative_to(t.PLUGIN)) for f in roles if "evidence-policy.md" not in texts[f] and "evidence policy" not in texts[f]]
    t.check("evidence: every agent and every skill points at references/evidence-policy.md", not missing, ", ".join(missing))
    t.check("evidence: contracts.md and the README name the evidence policy",
            "evidence-policy.md" in texts[t.PLUGIN / "references" / "contracts.md"] and "evidence-policy.md" in texts[t.PLUGIN / "README.md"])
# ==== END evidence ====



if __name__ == "__main__":
    sys.exit(main())
