#!/usr/bin/env python
"""Bulk link and metadata check for a dossier file (references/contracts.md section 9).

Usage: python check_links.py <file.md> [--out <report.md>] [--timeout 15] [--workers 8]

Finds every http(s) URL (and bare DOI) in the file, classifies it, fetches it (or the matching metadata
endpoint), and writes a report table next to the file (`<name>.links.md`) with one verdict per URL:
  ok             reachable and the metadata matches the kind (title/author/year found; image is an image …)
  ok-no-meta     reachable, nothing to compare (no title, HEAD only, content-type mismatch — see the note)
  redirect-home  the URL lands on a site root — the deep link is gone
  blocked        401/403/429 or an automation wall
  dead           404/410/5xx, DNS failure, connection refused, arXiv/Commons "not found"
  timeout        no answer within --timeout seconds
The verifier agent compares the found metadata with what the dossier cites. Network errors never crash
the script. Ends with
  RESULT: tool=check_links checked=n ok=n meta=n home=n blocked=n dead=n timeout=n report=<path>
(`meta` counts ok-no-meta, `home` counts redirect-home.) Exit 0; 2 on usage error.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import html
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import read_lines, result_line, usage_error  # noqa: E402

UA = "atlaspedia-check-links/0.1 (+local research tool)"
URL_RE = re.compile(r"https?://[^\s<>\"'`|)\]]+")
BARE_DOI_RE = re.compile(r"(?<![/\w])10\.\d{4,9}/[^\s|)\]>\"'`]+")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff")
MAX_BYTES = 65536


# ---------------------------------------------------------------- collect ---
def collect_urls(lines) -> list[tuple[int, str]]:
    seen, out = set(), []
    for i, line in enumerate(lines):
        for m in URL_RE.finditer(line):
            u = m.group(0).rstrip(".,;:!?")
            if u.count("(") < u.count(")"):
                u = u.rstrip(")")
            if u not in seen:
                seen.add(u)
                out.append((i + 1, u))
        for m in BARE_DOI_RE.finditer(line):
            doi = m.group(0).rstrip(".,;:")
            u = "https://doi.org/" + doi
            if u not in seen and not any(x.lower().endswith(doi.lower()) for x in seen):
                seen.add(u)
                out.append((i + 1, u))
    return out


# --------------------------------------------------------------- classify ---
def classify(url: str) -> tuple[str, str]:
    """Return (kind, fetch_url)."""
    p = urllib.parse.urlparse(url)
    host, path = p.netloc.lower(), p.path
    low = url.lower()
    if host in ("doi.org", "dx.doi.org", "www.doi.org"):
        return "doi", "https://api.crossref.org/works/" + urllib.parse.quote(path.lstrip("/"), safe="")
    if host == "api.crossref.org":
        return "doi", url
    m = re.match(r"^/(?:abs|pdf)/([^/?#]+)", path) if host.endswith("arxiv.org") else None
    if m:
        aid = re.sub(r"\.pdf$", "", m.group(1))
        return "arxiv", "https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(aid, safe="")
    if host.endswith("openlibrary.org") and "/isbn/" in path:
        isbn = re.sub(r"\.json$", "", path.split("/isbn/", 1)[1]).strip("/")
        return "isbn", f"https://openlibrary.org/isbn/{isbn}.json"
    if host in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
        return "youtube", "https://www.youtube.com/oembed?url=" + urllib.parse.quote(url, safe="") + "&format=json"
    if host.endswith("vimeo.com") and re.search(r"/\d+", path):
        return "vimeo", "https://vimeo.com/api/oembed.json?url=" + urllib.parse.quote(url, safe="")
    if host == "commons.wikimedia.org" and "File:" in urllib.parse.unquote(path):
        name = urllib.parse.unquote(path).split("File:", 1)[1]
        q = urllib.parse.urlencode({"action": "query", "prop": "imageinfo", "iiprop": "url|extmetadata",
                                    "titles": "File:" + name, "format": "json"})
        return "commons", "https://commons.wikimedia.org/w/api.php?" + q
    if low.split("?")[0].endswith(IMAGE_EXT) or host == "upload.wikimedia.org":
        return "image", url
    if low.split("?")[0].endswith(".pdf"):
        return "pdf", url
    return "page", url


# ------------------------------------------------------------------ fetch ---
class Fetched:
    def __init__(self):
        self.status = 0
        self.ctype = ""
        self.final = ""
        self.body = b""
        self.err = ""
        self.errkind = ""  # timeout | dead | ""


def fetch(url: str, timeout: float, method: str = "GET") -> Fetched:
    out = Fetched()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}, method=method)
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            out.status = r.status
            out.ctype = r.headers.get("Content-Type", "") or ""
            out.final = r.geturl()
            if method == "GET":
                out.body = r.read(MAX_BYTES)
    except urllib.error.HTTPError as e:
        out.status = e.code
        out.ctype = (e.headers.get("Content-Type", "") if e.headers else "") or ""
        out.final = e.geturl() or url
        try:
            out.body = e.read(MAX_BYTES)
        except Exception:  # noqa: BLE001
            pass
        out.err = f"HTTP {e.code}"
    except (socket.timeout, TimeoutError) as e:
        out.err, out.errkind = f"timeout: {e}", "timeout"
    except urllib.error.URLError as e:
        out.err, out.errkind = classify_network_error(getattr(e, "reason", e))
    except Exception as e:  # noqa: BLE001 — never crash on a bad URL
        out.err, out.errkind = classify_network_error(e)
    return out


def classify_network_error(reason) -> tuple[str, str]:
    """Transient or environment failures must not read as `dead` (the verifier would drop a good link):
    timeouts and connection resets -> timeout (retry later); TLS/proxy failures -> blocked (verify by hand);
    DNS failures and refused connections -> dead."""
    name, text = type(reason).__name__, str(reason)
    low = text.lower()
    if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in low:
        return f"timeout: {text}", "timeout"
    if isinstance(reason, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)) or "10054" in low or "reset" in low:
        return f"{name}: {text}", "timeout"
    if isinstance(reason, ssl.SSLError) or "ssl" in low or "certificate" in low or "proxy" in low:
        return f"{name}: {text}", "blocked"
    return f"{name}: {text}", "dead"


# --------------------------------------------------------------- metadata ---
def clean(s: str, n: int = 90) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    s = " ".join(html.unescape(s).split())
    return (s[: n - 1] + "…") if len(s) > n else s


def meta_from(kind: str, f: Fetched) -> tuple[str, bool]:
    """(description, found) — found=False when the response says the item does not exist."""
    text = f.body.decode("utf-8", "replace") if f.body else ""
    try:
        if kind == "doi":
            msg = json.loads(text).get("message", {})
            title = (msg.get("title") or [""])[0]
            authors = ", ".join(a.get("family", a.get("name", "")) for a in msg.get("author", [])[:3])
            year = ""
            for k in ("published-print", "published-online", "issued", "created"):
                dp = (msg.get(k) or {}).get("date-parts") or [[None]]
                if dp and dp[0] and dp[0][0]:
                    year = str(dp[0][0])
                    break
            return clean(f"{title} · {authors} · {year} · {msg.get('container-title', [''])[0] if msg.get('container-title') else ''}"), bool(title)
        if kind == "arxiv":
            ns = {"a": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(text)
            entry = root.find("a:entry", ns)
            if entry is None:
                return "arXiv: no entry", False
            title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
            if title.lower() == "error" or "incorrect id" in (entry.findtext("a:summary", default="", namespaces=ns) or "").lower():
                return "arXiv: no such id", False
            authors = ", ".join((a.findtext("a:name", default="", namespaces=ns) or "") for a in entry.findall("a:author", ns)[:3])
            year = (entry.findtext("a:published", default="", namespaces=ns) or "")[:4]
            return clean(f"{title} · {authors} · {year}"), bool(title)
        if kind == "isbn":
            d = json.loads(text)
            return clean(f"{d.get('title', '')} · {d.get('publish_date', '')} · {', '.join(d.get('publishers', [])[:2])}"), bool(d.get("title"))
        if kind in ("youtube", "vimeo"):
            d = json.loads(text)
            return clean(f"{d.get('title', '')} · {d.get('author_name', '')}"), bool(d.get("title"))
        if kind == "commons":
            pages = json.loads(text).get("query", {}).get("pages", {})
            for pid, pg in pages.items():
                if pid == "-1" or "missing" in pg:
                    return "Commons: file not found", False
                info = (pg.get("imageinfo") or [{}])[0]
                ext = info.get("extmetadata", {})
                lic = ext.get("LicenseShortName", {}).get("value", "")
                artist = clean(ext.get("Artist", {}).get("value", ""), 40)
                return clean(f"{info.get('url', '')} · licence {lic or '?'} · {artist}", 160), bool(info.get("url"))
            return "Commons: empty answer", False
        if kind == "page":
            m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
            return (clean(m.group(1)) if m else ""), bool(m)
    except Exception as e:  # noqa: BLE001
        return f"unparsable answer ({type(e).__name__})", False
    return "", False


BLOCK_TITLES = ("just a moment", "access denied", "attention required", "are you a robot", "captcha", "forbidden")


def check_one(line: int, url: str, timeout: float) -> dict:
    kind, furl = classify(url)
    f = fetch(furl, timeout, "HEAD" if kind in ("image", "pdf") else "GET")
    if kind in ("image", "pdf") and (f.errkind or f.status in (403, 405, 0) or not f.ctype):
        f = fetch(furl, timeout, "GET")
    row = {"line": line, "url": url, "kind": kind, "http": f.status or "—", "ctype": f.ctype.split(";")[0].strip(), "meta": "", "verdict": ""}
    if f.errkind:
        row["verdict"], row["meta"] = f.errkind, clean(f.err, 70)
        return row
    st = f.status
    if st in (401, 403, 429):
        row["verdict"], row["meta"] = "blocked", f"HTTP {st}"
        return row
    if st in (404, 410) or st >= 500:
        row["verdict"], row["meta"] = "dead", f"HTTP {st}"
        return row
    if st < 200 or st >= 400:
        row["verdict"], row["meta"] = "dead", f"HTTP {st}"
        return row
    # reachable
    if kind in ("page", "image", "pdf"):
        o, fin = urllib.parse.urlparse(url), urllib.parse.urlparse(f.final or url)
        if o.path.strip("/") and not fin.path.strip("/") and fin.netloc:
            row["verdict"], row["meta"] = "redirect-home", f"→ {f.final}"
            return row
    if kind == "image":
        ok = row["ctype"].startswith("image/")
        row["verdict"] = "ok" if ok else "ok-no-meta"
        row["meta"] = "image" if ok else f"not an image: {row['ctype'] or 'no content-type'}"
        return row
    if kind == "pdf":
        ok = "pdf" in row["ctype"]
        row["verdict"] = "ok" if ok else "ok-no-meta"
        row["meta"] = "PDF" if ok else f"not a PDF: {row['ctype'] or 'no content-type'}"
        return row
    desc, found = meta_from(kind, f)
    if kind == "page" and desc and desc.lower().startswith(BLOCK_TITLES):
        row["verdict"], row["meta"] = "blocked", desc
        return row
    if kind in ("arxiv", "commons") and not found and desc.startswith(("arXiv: no", "Commons:")):
        row["verdict"], row["meta"] = "dead", desc
        return row
    row["verdict"] = "ok" if found else "ok-no-meta"
    row["meta"] = desc or "no title/metadata in the answer"
    return row


def esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--workers", type=int, default=8)
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    path = Path(args.file)
    if not path.exists():
        return usage_error(f"no such file: {path}")
    out = Path(args.out) if args.out else path.with_suffix(".links.md")
    urls = collect_urls(read_lines(path))
    rows: list[dict] = []
    if urls:
        with cf.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
            futs = [ex.submit(check_one, line, url, args.timeout) for line, url in urls]
            for fu in futs:
                try:
                    rows.append(fu.result())
                except Exception as e:  # noqa: BLE001
                    rows.append({"line": 0, "url": "?", "kind": "?", "http": "—", "ctype": "", "meta": f"{type(e).__name__}: {e}", "verdict": "dead"})
    counts = {"ok": 0, "meta": 0, "home": 0, "blocked": 0, "dead": 0, "timeout": 0}
    key = {"ok": "ok", "ok-no-meta": "meta", "redirect-home": "home", "blocked": "blocked", "dead": "dead", "timeout": "timeout"}
    for r in rows:
        counts[key[r["verdict"]]] += 1
    lines = [f"# Link check: {path.name}", "",
             f"Checked {date.today().isoformat()} · {len(rows)} URLs · timeout {args.timeout:g}s · "
             f"ok {counts['ok']} · ok-no-meta {counts['meta']} · redirect-home {counts['home']} · blocked {counts['blocked']} · dead {counts['dead']} · timeout {counts['timeout']}",
             "", "| # | URL | Kind | HTTP | Content-type | Title / author / year found | Verdict |", "|---|---|---|---|---|---|---|"]
    for n, r in enumerate(rows, 1):
        lines.append(f"| {n} | {esc(r['url'])} | {r['kind']} | {r['http']} | {esc(r['ctype'])} | {esc(r['meta'])} | {r['verdict']} |")
    lines.append("")
    lines.append("Verdicts: ok = reachable and metadata found for its kind · ok-no-meta = reachable, nothing to compare (see note) · "
                 "redirect-home = deep link gone · blocked = automation wall, verify by hand · dead = not found · timeout = retry later.")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in rows:
        if r["verdict"] not in ("ok", "ok-no-meta"):
            print(f"{path}:{r['line']} {r['verdict']} {r['url']} ({r['meta']})")
    print(result_line(tool="check_links", checked=len(rows), ok=counts["ok"], meta=counts["meta"], home=counts["home"],
                      blocked=counts["blocked"], dead=counts["dead"], timeout=counts["timeout"], report=str(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
