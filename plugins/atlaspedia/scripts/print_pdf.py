#!/usr/bin/env python
"""G2 PDF/print pipeline: print a site's pages to PDF with headless Chrome / Edge / Chromium.

Usage:
  python print_pdf.py <siteDir> [--pages a.html,b.html] [--handout] [--out <dir>] [--browser <path>]
                      [--budget-ms 15000] [--timeout 120]

Pages print in reading order (site.json pages[]; index.html at the root, the others under pagesDir; a single-format
site prints its one page). --pages keeps that order and prints only the named files. Each page becomes
<out>/NN-<name>.pdf (NN = position in the reading order; `-handout` before .pdf with --handout); <out> defaults to
<siteDir>/tmp/pdf/ when the site has a tmp/ folder (a topic folder; tmp/ is git-ignored), else <siteDir>/pdf/.
--handout loads every page with ?mode=handout (B3 handout mode: no solutions, instructor notes or quiz explanations,
a Name / Date line). The stylesheet's print rules hide the shell, keep figures and tables whole, break
before each section of a module page and add a running header and page numbers.

The browser runs as
  <browser> --headless=new --disable-gpu --no-first-run --no-default-browser-check --user-data-dir=<temp>
            --run-all-compositor-stages-before-draw --virtual-time-budget=<budget-ms> --no-pdf-header-footer
            --print-to-pdf=<file> <file:///…/page.html[?mode=handout]>
The virtual-time budget lets KaTeX, highlight.js and the plots finish before the page is printed. A vendored site
(scaffold.py --offline) prints without network; otherwise the fonts and KaTeX come from the CDN.
Browser: --browser <path> (a `.py` path runs with this Python: test doubles and wrappers), else $ATLAS_BROWSER, else
chrome / msedge / chromium on PATH and the usual install paths on Windows, macOS and Linux. None found: exit 2.

Combined PDF: when the optional `pypdf` package is importable, the page PDFs are also merged into <out>/site.pdf
(site-handout.pdf with --handout). pypdf is not required (`pip install pypdf` to get the merged file).

Ends with
  RESULT: tool=print_pdf status=PASS|FAIL errors=n warnings=n pages=n pdfs=n combined=<file>|none handout=yes|no out=<dir>
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, display, load_json, usage_error  # noqa: E402

NAMES = ["chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge", "microsoft-edge",
         "microsoft-edge-stable"]


def browser_candidates() -> list[Path]:
    out: list[Path] = []
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            out += [Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
                    Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                    Path(base) / "Chromium" / "Application" / "chrome.exe"]
    out += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            Path("/usr/bin/google-chrome"), Path("/usr/bin/chromium"), Path("/usr/bin/chromium-browser"),
            Path("/usr/bin/microsoft-edge"), Path("/snap/bin/chromium")]
    return out


def find_browser(given: str | None) -> tuple[Path | None, str]:
    """(path, how) — path None when nothing was found; how explains what was tried."""
    if given:
        p = Path(given)
        return (p.resolve() if p.is_file() else None), f"--browser {given}"
    env = os.environ.get("ATLAS_BROWSER")
    if env:
        p = Path(env)
        return (p.resolve() if p.is_file() else None), f"$ATLAS_BROWSER={env}"
    for n in NAMES:
        w = shutil.which(n)
        if w:
            return Path(w), "PATH"
    for c in browser_candidates():
        if c.is_file():
            return c, "install path"
    return None, "PATH (" + ", ".join(NAMES[:5]) + " …) and the usual Chrome/Edge/Chromium install folders"


def reading_order(site: Path, reg: dict) -> list[tuple[str, Path]]:
    """[(file name, path)] in site.json order; the home page at the root, the rest under pagesDir."""
    home = reg.get("home") or "index.html"
    pages_dir = reg.get("pagesDir", "") if isinstance(reg.get("pagesDir", ""), str) else ""
    out = []
    for p in reg.get("pages") or []:
        if isinstance(p, dict) and isinstance(p.get("file"), str):
            f = p["file"]
            out.append((f, site / f if (f == home or not pages_dir) else site / pages_dir / f))
    if reg.get("mode") == "single":
        out = [x for x in out if x[0] == home][:1] or [(home, site / home)]
    return out


def command(browser: Path, url: str, pdf: Path, profile: Path, budget_ms: int) -> list[str]:
    head = [sys.executable, str(browser)] if browser.suffix.lower() == ".py" else [str(browser)]
    return head + ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                   f"--user-data-dir={profile}", "--run-all-compositor-stages-before-draw",
                   f"--virtual-time-budget={budget_ms}", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", url]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siteDir")
    ap.add_argument("--pages")
    ap.add_argument("--handout", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--browser")
    ap.add_argument("--budget-ms", type=int, default=15000, dest="budget_ms")
    ap.add_argument("--timeout", type=float, default=120)
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    site = Path(args.siteDir).resolve()
    reg, err = load_json(site / "assets" / "site.json")
    if err or not isinstance(reg, dict):
        return usage_error(f"{site}: no usable assets/site.json ({err or 'not an object'}) — scaffold the site first")
    order = reading_order(site, reg)
    if args.pages:
        want = [x.strip() for x in args.pages.split(",") if x.strip()]
        unknown = [w for w in want if w not in {f for f, _ in order}]
        if unknown:
            return usage_error(f"--pages: not in site.json pages[]: {', '.join(unknown)}")
    else:
        want = [f for f, _ in order]
    browser, how = find_browser(args.browser)
    if browser is None:
        return usage_error(f"no headless browser found (looked at {how}). Install Google Chrome, Microsoft Edge or Chromium, "
                           "or pass --browser <path to chrome/msedge/chromium>")
    out = Path(args.out).resolve() if args.out else (site / "tmp" / "pdf" if (site / "tmp").is_dir() else site / "pdf")
    out.mkdir(parents=True, exist_ok=True)
    rep = Report("tool", "print_pdf")
    suffix = "-handout" if args.handout else ""
    width = max(2, len(str(len(order))))
    selected = [(n, name, path) for n, (name, path) in enumerate(order, 1) if name in want]   # NN = place in the whole reading order
    pdfs: list[Path] = []
    print(f"browser        {browser} (from {how})")
    with tempfile.TemporaryDirectory(prefix="atlaspedia-print-") as profile:
        for n, name, path in selected:
            if not path.is_file():
                rep.error(path, 1, f"{name} is in site.json but the file is missing")
                continue
            pdf = out / f"{n:0{width}d}-{Path(name).stem}{suffix}.pdf"
            if pdf.exists():
                pdf.unlink()
            url = path.as_uri() + ("?mode=handout" if args.handout else "")
            cmd = command(browser, url, pdf, Path(profile), args.budget_ms)
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout, encoding="utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                rep.error(path, 1, f"{name}: the browser did not finish within {args.timeout:g} s")
                continue
            except OSError as e:
                rep.error(path, 1, f"{name}: could not start the browser: {e}")
                continue
            if not pdf.is_file() or pdf.stat().st_size == 0:
                tail = ((p.stderr or "") + (p.stdout or "")).strip().splitlines()[-3:]
                rep.error(path, 1, f"{name}: no PDF written (browser exit {p.returncode}){': ' + ' | '.join(tail) if tail else ''}")
                continue
            pdfs.append(pdf)
            print(f"printed        {display(pdf)} ({pdf.stat().st_size / 1024:.0f} KB)")
    combined = "none"
    if pdfs:
        try:
            from pypdf import PdfWriter  # optional dependency
        except ImportError:
            print("combined       skipped: pypdf is not installed (optional: pip install pypdf for one merged PDF)")
        else:
            target = out / f"site{suffix}.pdf"
            try:
                w = PdfWriter()
                for f in pdfs:
                    w.append(str(f))
                with open(target, "wb") as fh:
                    w.write(fh)
                combined = target.name
                print(f"combined       {display(target)} ({len(pdfs)} pages' PDFs merged in reading order)")
            except Exception as e:  # noqa: BLE001 — a merge failure leaves the per-page PDFs usable
                rep.warn(target, 1, f"could not merge the PDFs with pypdf: {e}")
    return rep.finish({"pages": len(selected), "pdfs": len(pdfs), "combined": combined,
                       "handout": "yes" if args.handout else "no", "out": display(out)})


if __name__ == "__main__":
    sys.exit(main())
