#!/usr/bin/env python
"""G1 offline bundle: vendor the CDN assets a site loads into <site>/assets/vendor/ and point every page at them.

Usage:
  python vendor.py <siteDir> [--vendor-from <dir>] [--force]
  (normally run through `scaffold.py <siteDir> --offline`, which also regenerates site.js)

Downloads (or, with --vendor-from, copies from a local cache laid out like assets/vendor/ — another site's
assets/vendor/ works, its manifest.json supplies the source URLs):
  katex/      KaTeX 0.16.9 katex.min.css, katex.min.js, contrib/auto-render.min.js and every font file the css
              references (the css keeps its relative url(fonts/…)); any other katex@0.16.9/dist/ file a page links
  highlight/  highlight.js 11.9.0 highlight.min.js, languages/verilog.min.js, languages/matlab.min.js (what app.js loads)
  fonts/      the Google Fonts css the pages link (fonts.css for the template's families, fonts-<hash>.css for any
              other css2 URL) and atkinson.css (the F2 dyslexia-friendly font), fetched with a modern User-Agent so
              Google serves woff2; every woff2 is downloaded beside the css and the css url()s are rewritten to it
Then every page (index.html, the pages folder, the `_*.html` skeletons) gets its CDN <link>/<script> rewritten to
assets/vendor/… (../ from pages/), the fonts preconnect hints are dropped, and site.json gets `"vendor": true`
(app.js then loads highlight.js and the F2 font from assets/vendor/ too).

Idempotent: a file whose manifest entry (same source URL, size and sha256) matches the file on disk is not fetched
again, so a re-run needs no network. assets/vendor/manifest.json lists every file: {url, bytes, sha256}. Files of an
older manifest that are no longer needed are deleted. --force refetches everything.
Network failures stop with a message naming the URL (exit 1) and nothing in site.json changes.

Ends with
  RESULT: tool=vendor status=PASS|FAIL files=n fetched=n kept=n bytes=n pages=n
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, load_json, usage_error  # noqa: E402

KATEX_CDN = "https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/"
HLJS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/"
FONTS_URL = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600"
             "&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap")
F2_FONT_URL = "https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400;1,700&display=swap"
PREFIXES = {KATEX_CDN: "katex/", HLJS_CDN: "highlight/"}
REQUIRED = [(KATEX_CDN + "katex.min.css", "katex/katex.min.css"), (KATEX_CDN + "katex.min.js", "katex/katex.min.js"),
            (KATEX_CDN + "contrib/auto-render.min.js", "katex/contrib/auto-render.min.js"),
            (HLJS_CDN + "highlight.min.js", "highlight/highlight.min.js"),
            (HLJS_CDN + "languages/verilog.min.js", "highlight/languages/verilog.min.js"),
            (HLJS_CDN + "languages/matlab.min.js", "highlight/languages/matlab.min.js")]
# Hosts whose <link>/<script> a vendored page must not use any more (validate.py imports this).
CDN_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "unpkg.com")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MANIFEST = "manifest.json"
GF_CSS_RE = re.compile(r"https://fonts\.googleapis\.com/css2?\?[^\"'\s>]+")
URL_RE = re.compile(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)")
TAG_RE = re.compile(r"<(?:link|script)\b[^>]*>", re.I)
PRECONNECT_RE = re.compile(r'[ \t]*<link\b[^>]*rel="(?:preconnect|dns-prefetch)"[^>]*href="https://fonts\.(?:googleapis|gstatic)\.com"[^>]*>[ \t]*\r?\n?', re.I)


class VendorError(Exception):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def font_css_name(url: str) -> str:
    """The Google Fonts css a page links -> its local file name under fonts/."""
    url = url.replace("&amp;", "&")
    if url == FONTS_URL:
        return "fonts.css"
    if url == F2_FONT_URL:
        return "atkinson.css"
    return f"fonts-{sha256(url.encode())[:8]}.css"


def gstatic_name(url: str) -> str:
    """https://fonts.gstatic.com/s/ibmplexmono/v20/abc.woff2 -> ibmplexmono-v20-abc.woff2"""
    path = url.split("://", 1)[-1].split("/", 1)[-1].split("?")[0]
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] == "s":
        parts = parts[1:]
    return re.sub(r"[^A-Za-z0-9._-]", "_", "-".join(parts))


class Fetcher:
    def __init__(self, cache: Path | None, timeout: float = 30):
        self.cache, self.timeout = cache, timeout
        self.cache_manifest = {}
        if cache is not None:
            obj, _ = load_json(cache / MANIFEST) if (cache / MANIFEST).exists() else ({}, None)
            self.cache_manifest = (obj or {}).get("files", {}) if isinstance(obj, dict) else {}

    def get(self, url: str | None, rel: str, ua: bool = False) -> bytes:
        if self.cache is not None:
            p = self.cache / rel
            if not p.is_file():
                raise VendorError(f"{rel} is not in the vendor cache {self.cache} (source {url or 'unknown'})")
            return p.read_bytes()
        if not url:
            raise VendorError(f"{rel}: source URL unknown (not in manifest.json) — re-run with --force")
        req = urllib.request.Request(url, headers={"User-Agent": UA if ua else "atlas-learn-vendor/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.read()
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise VendorError(f"could not download {url} ({reason}) — are you offline? Re-run with network access, "
                              f"or pass --vendor-from <dir> (a folder laid out like assets/vendor/, e.g. another site's)") from None


class Vendor:
    def __init__(self, site: Path, fetcher: Fetcher, force: bool = False):
        self.site, self.fetcher, self.force = site, fetcher, force
        self.vdir = site / "assets" / "vendor"
        old, _ = load_json(self.vdir / MANIFEST) if (self.vdir / MANIFEST).exists() else ({}, None)
        self.old = (old or {}).get("files", {}) if isinstance(old, dict) else {}
        self.files: dict = {}
        self.fetched = self.kept = 0

    def known_url(self, rel: str) -> str | None:
        return (self.old.get(rel) or {}).get("url") or (self.fetcher.cache_manifest.get(rel) or {}).get("url")

    def file(self, url: str | None, rel: str, transform=None, ua: bool = False) -> bytes:
        """Fetch url into vendor/rel unless the manifest says the file on disk already is that url's content."""
        if rel in self.files:
            return (self.vdir / rel).read_bytes()
        dest = self.vdir / rel
        url = url or self.known_url(rel)
        old = self.old.get(rel)
        if not self.force and old and dest.is_file() and old.get("url") == url:
            data = dest.read_bytes()
            if old.get("sha256") == sha256(data) and old.get("bytes") == len(data):
                self.files[rel] = old
                self.kept += 1
                return data
        data = self.fetcher.get(url, rel, ua)
        if transform:
            data = transform(data)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        self.files[rel] = {"url": url, "bytes": len(data), "sha256": sha256(data)}
        self.fetched += 1
        return data

    def css_with_fonts(self, url: str, rel: str, base: str | None, ua: bool) -> None:
        """A stylesheet plus every url() it references. base: CDN folder the relative urls resolve against (KaTeX);
        None for Google Fonts, whose absolute gstatic urls become local file names beside the css."""
        folder = rel.rsplit("/", 1)[0] + "/"
        remote: dict[str, str] = {}

        def localise(data: bytes) -> bytes:
            def sub(m):
                u = m.group(2)
                if u.startswith(("http://", "https://")):
                    name = gstatic_name(u)
                    remote[name] = u
                    return f"url({name})"
                return m.group(0)
            return URL_RE.sub(sub, data.decode("utf-8")).encode("utf-8")

        css = self.file(url, rel, localise, ua).decode("utf-8")
        for m in URL_RE.finditer(css):
            u = m.group(2)
            if u.startswith("data:") or u.startswith(("http://", "https://")):
                continue
            frel = folder + u.split("?")[0].split("#")[0]
            src = remote.get(u) or (base + u if base else None) or self.known_url(frel)
            self.file(src, frel)

    def run(self, extra_urls: set[str]) -> None:
        for url, rel in REQUIRED:
            if rel.endswith(".css"):
                self.css_with_fonts(url, rel, url.rsplit("/", 1)[0] + "/", False)
            else:
                self.file(url, rel)
        fonts = {FONTS_URL, F2_FONT_URL} | {u for u in extra_urls if GF_CSS_RE.fullmatch(u)}
        for u in sorted(fonts):
            self.css_with_fonts(u, "fonts/" + font_css_name(u), None, True)
        for u in sorted(extra_urls):
            for prefix, folder in PREFIXES.items():
                if u.startswith(prefix):
                    rel = folder + u[len(prefix):].split("?")[0]
                    if rel.endswith(".css"):
                        self.css_with_fonts(u, rel, u.rsplit("/", 1)[0] + "/", False)
                    else:
                        self.file(u, rel)
        # files an older manifest listed but nothing needs now
        for rel in self.old:
            if rel not in self.files and (self.vdir / rel).is_file():
                (self.vdir / rel).unlink()
        manifest = {"generatedBy": "vendor.py (scaffold.py --offline)", "files": dict(sorted(self.files.items()))}
        (self.vdir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def local_for(url: str) -> str | None:
    """CDN URL -> path under assets/vendor/, or None when vendor.py does not vendor it."""
    u = url.replace("&amp;", "&")
    if GF_CSS_RE.fullmatch(u):
        return "fonts/" + font_css_name(u)
    for prefix, folder in PREFIXES.items():
        if u.startswith(prefix):
            return folder + u[len(prefix):].split("?")[0]
    return None


def site_pages(site: Path, pages_dir: str) -> list[Path]:
    out = sorted(site.glob("*.html"))
    if pages_dir and (site / pages_dir).is_dir():
        out += sorted((site / pages_dir).glob("*.html"))
    return out


def page_urls(text: str) -> set[str]:
    urls = set()
    for tag in TAG_RE.findall(text):
        for m in re.finditer(r'\b(?:href|src)\s*=\s*"(https://[^"]+)"', tag):
            urls.add(m.group(1).replace("&amp;", "&"))
    return urls


def rewrite_page(text: str, up: str) -> str:
    text = PRECONNECT_RE.sub("", text)

    def tag(m):
        def attr(a):
            local = local_for(a.group(2))
            return f'{a.group(1)}="{up}assets/vendor/{local}"' if local else a.group(0)
        return re.sub(r'\b(href|src)\s*=\s*"(https://[^"]+)"', attr, m.group(0))
    return TAG_RE.sub(tag, text)


def vendor_site(site: Path, cache: Path | None = None, force: bool = False, rep: Report | None = None, quiet: bool = False) -> dict | None:
    """Vendor + rewrite. Returns the counts, or None on an error (reported to rep). Does not touch site.json."""
    rep = rep or Report("tool", "vendor")
    reg, err = load_json(site / "assets" / "site.json")
    if err or not isinstance(reg, dict):
        rep.error(site / "assets" / "site.json", 1, err or "site.json must be a JSON object")
        return None
    pages_dir = reg.get("pagesDir", "") if isinstance(reg.get("pagesDir", ""), str) else ""
    pages = site_pages(site, pages_dir)
    extra = set()
    for p in pages:
        extra |= {u for u in page_urls(p.read_text(encoding="utf-8-sig")) if local_for(u)}
    v = Vendor(site, Fetcher(cache), force)
    try:
        v.run(extra)
    except VendorError as e:
        rep.error(site / "assets" / "vendor", 1, str(e))
        return None
    rewritten = 0
    for p in pages:
        up = "../" * (len(p.relative_to(site).parts) - 1)
        raw = p.read_bytes().decode("utf-8")
        new = rewrite_page(raw, up)
        if new != raw:
            p.write_bytes(new.encode("utf-8"))
            rewritten += 1
            if not quiet:
                print(f"rewrote        {p.relative_to(site).as_posix()} (CDN -> assets/vendor/)")
    total = sum(f["bytes"] for f in v.files.values())
    if not quiet:
        print(f"vendored       assets/vendor/ ({len(v.files)} files, {total / 1024:.0f} KB; fetched {v.fetched}, kept {v.kept})")
    return {"files": len(v.files), "fetched": v.fetched, "kept": v.kept, "bytes": total, "pages": rewritten}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("siteDir")
    ap.add_argument("--vendor-from", dest="cache")
    ap.add_argument("--force", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    site = Path(args.siteDir).resolve()
    if not (site / "assets" / "site.json").exists():
        return usage_error(f"no assets/site.json in {site} — scaffold the site first")
    cache = Path(args.cache).resolve() if args.cache else None
    if cache is not None and not cache.is_dir():
        return usage_error(f"--vendor-from: no such directory: {cache}")
    rep = Report("tool", "vendor")
    res = vendor_site(site, cache, args.force, rep) or {"files": 0, "fetched": 0, "kept": 0, "bytes": 0, "pages": 0}
    return rep.finish(res)


if __name__ == "__main__":
    sys.exit(main())
