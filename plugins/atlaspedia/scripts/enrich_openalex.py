#!/usr/bin/env python
"""OpenAlex enrichment of the dossier sources (I5; references/contracts.md section 9).

Usage: python enrich_openalex.py <topic> [--offline] [--refresh] [--no-write] [--timeout 15]

<topic> is the topic folder (`topics/<slug>/`), its PLAN.md, or a slug resolved as `topics/<slug>/` under the
current folder. Every module and synthesis file in `tmp/dossier/` (`mNN-*.md`, `sNN-*.md`) is read; each `## Sources`
row with a DOI (or an arXiv id, looked up as `10.48550/arXiv.<id>`) is looked up at
  https://api.openalex.org/works/doi:<doi>        (+ `mailto=<address>` only when ATLAS_OPENALEX_MAILTO is set)
and the record is kept in `tmp/openalex.json`: open-access URL, cited_by_count, publication year, venue, type and
retraction status. A cached DOI is never fetched again unless --refresh is given.

Per source the dossier file gets one line in a `## OpenAlex enrichment` section (rewritten on every run):
  - Enriched: #2 — doi:10.1080/… · 2018 · <venue> · journal-article · cited by 123 · OA <url> · not retracted
Problems:
  error    a retracted work (drop or replace the source, or say why it is still cited)
  warning  the year cited in the Reference cell differs from OpenAlex's publication year
  warning  a network error (the run degrades to the cache) or an id OpenAlex does not know
Network-optional: --offline reads only the cache; the first network error switches the rest of the run to the
cache. ATLAS_OPENALEX_API overrides the endpoint (tests point it at a closed local port). Ends with
  RESULT: tool=enrich_openalex status=PASS|FAIL errors=n warnings=n files=n sources=n ids=n enriched=n cached=n
          fetched=n missing=n retracted=n offline=yes|no cache=<path>
Exit 0 = PASS, 1 = a retracted work was found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, col_index, find_section, find_table, read_lines, sections, usage_error  # noqa: E402

API = "https://api.openalex.org/works/"
UA = "atlaspedia-enrich-openalex/0.1 (+local research tool)"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s|<>\"'`]+")
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/[0-9]{7})", re.I)
PAREN_YEAR_RE = re.compile(r"\((1[5-9]\d\d|20\d\d)[a-z]?\)")
YEAR_RE = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
SECTION = "OpenAlex enrichment"
MODULE_FILE_RE = re.compile(r"^[ms]\d{2}-.+\.md$")


def clean_doi(raw: str) -> str:
    d = raw.rstrip(".,;:")
    while d.endswith(")") and d.count(")") > d.count("("):
        d = d[:-1]
    return d.lower()


def source_id(ref: str, link: str) -> str | None:
    """The DOI of a source row (link first, then the reference text), or the arXiv DOI."""
    for text in (link, ref):
        m = DOI_RE.search(urllib.parse.unquote(text))
        if m:
            return clean_doi(m.group(0))
    for text in (link, ref):
        m = ARXIV_RE.search(text)
        if m:
            return "10.48550/arxiv." + re.sub(r"v\d+$", "", m.group(1)).lower()
    return None


def cited_year(ref: str) -> int | None:
    m = PAREN_YEAR_RE.search(ref) or YEAR_RE.search(ref)
    return int(m.group(1)) if m else None


def resolve_topic(arg: str) -> Path | None:
    p = Path(arg)
    if p.is_file() and p.name == "PLAN.md":
        p = p.parent
    if p.is_dir() and (p / "tmp").is_dir():
        return p.resolve()
    q = Path.cwd() / "topics" / arg
    if q.is_dir() and (q / "tmp").is_dir():
        return q.resolve()
    return None


def record_from(work: dict, today: str) -> dict:
    loc = work.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = work.get("open_access") or {}
    return {
        "status": "ok",
        "id": work.get("id"),
        "title": work.get("title") or work.get("display_name"),
        "year": work.get("publication_year"),
        "venue": src.get("display_name"),
        "type": work.get("type"),
        "cited_by_count": work.get("cited_by_count"),
        "oa_url": oa.get("oa_url") or (work.get("best_oa_location") or {}).get("pdf_url"),
        "is_retracted": bool(work.get("is_retracted")),
        "checked": today,
    }


def fetch(doi: str, timeout: float, today: str) -> tuple[dict | None, str]:
    """(record, error). A 404 is a cached `not_found` record; other failures return (None, message)."""
    base = os.environ.get("ATLAS_OPENALEX_API") or API
    url = base.rstrip("/") + "/doi:" + urllib.parse.quote(doi, safe="/.()")
    mailto = os.environ.get("ATLAS_OPENALEX_MAILTO", "").strip()
    if mailto:
        url += "?" + urllib.parse.urlencode({"mailto": mailto})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return record_from(json.loads(r.read().decode("utf-8", "replace")), today), ""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"status": "not_found", "checked": today}, ""
        return None, f"HTTP {e.code}"
    except (socket.timeout, TimeoutError):
        return None, "timeout"
    except urllib.error.URLError as e:
        return None, str(getattr(e, "reason", e))
    except (ValueError, OSError) as e:
        return None, str(e)


def load_cache(path: Path, rep: Report) -> dict:
    if not path.exists():
        return {"version": 1, "works": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("works"), dict):
            return data
        rep.warn(path, 1, "cache has no `works` object — starting an empty cache")
    except (ValueError, OSError) as e:
        rep.warn(path, 1, f"cache unreadable ({e}) — starting an empty cache")
    return {"version": 1, "works": {}}


def note_for(num: str, doi: str, rec: dict) -> str:
    if rec.get("status") == "not_found":
        return f"- Enriched: #{num} — doi:{doi} · not in OpenAlex ({rec.get('checked', '?')})"
    parts = [f"doi:{doi}", str(rec.get("year") or "year ?"), rec.get("venue") or "venue ?", rec.get("type") or "type ?",
             f"cited by {rec.get('cited_by_count') if rec.get('cited_by_count') is not None else '?'}",
             f"OA {rec['oa_url']}" if rec.get("oa_url") else "no OA copy",
             "RETRACTED" if rec.get("is_retracted") else "not retracted"]
    return f"- Enriched: #{num} — " + " · ".join(parts) + f" (OpenAlex, {rec.get('checked', '?')})"


def write_section(path: Path, lines: list[str], notes: list[str]) -> None:
    secs = sections(lines)
    sec = find_section(secs, SECTION)
    block = [f"## {SECTION}"] + notes + [""]
    if sec is not None:
        new = lines[:sec[1]] + block + lines[sec[2]:]
    else:
        body = lines[:]
        while body and not body[-1].strip():
            body.pop()
        new = body + [""] + block
    path.write_text("\n".join(new).rstrip("\n") + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("topic")
    ap.add_argument("--offline", action="store_true", help="read only tmp/openalex.json; never touch the network")
    ap.add_argument("--refresh", action="store_true", help="fetch cached ids again")
    ap.add_argument("--no-write", action="store_true", help="do not write the Enriched lines into the dossier files")
    ap.add_argument("--timeout", type=float, default=15)
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    topic = resolve_topic(args.topic)
    if topic is None:
        return usage_error(f"no topic folder with tmp/ for `{args.topic}`")
    dossier = topic / "tmp" / "dossier"
    cache_path = topic / "tmp" / "openalex.json"
    rep = Report("tool", "enrich_openalex")
    cache = load_cache(cache_path, rep)
    works: dict = cache["works"]
    today = date.today().isoformat()
    offline = args.offline
    c = {"files": 0, "sources": 0, "ids": 0, "enriched": 0, "cached": 0, "fetched": 0, "missing": 0, "retracted": 0}
    files = sorted(p for p in dossier.glob("*.md") if MODULE_FILE_RE.match(p.name)) if dossier.is_dir() else []
    if not files:
        rep.warn(dossier, 1, "no module or synthesis files (mNN-*.md, sNN-*.md) in tmp/dossier/")
    for path in files:
        lines = read_lines(path)
        sec = find_section(sections(lines), "sources", exact=False)
        t = find_table(lines, sec[1] + 1, sec[2]) if sec else None
        if t is None:
            continue
        c["files"] += 1
        header, _, rows = t
        ni, ri, li = col_index(header, "#"), col_index(header, "reference"), col_index(header, "link")
        notes: list[str] = []
        for idx, cells in rows:
            cell = lambda i: cells[i] if 0 <= i < len(cells) else ""  # noqa: E731
            c["sources"] += 1
            num, ref, link = cell(ni), cell(ri), cell(li)
            doi = source_id(ref, link)
            if not doi:
                continue
            c["ids"] += 1
            rec = works.get(doi)
            if rec is not None and not args.refresh:
                c["cached"] += 1
            elif offline:
                rec = None
            else:
                got, err = fetch(doi, args.timeout, today)
                if got is None:
                    rep.warn(path, idx + 1, f"OpenAlex lookup of {doi} failed ({err}) — continuing from the cache only")
                    offline = True
                else:
                    rec = works[doi] = got
                    c["fetched"] += 1
            if rec is None:
                c["missing"] += 1
                continue
            notes.append(note_for(num, doi, rec))
            if rec.get("status") == "not_found":
                rep.warn(path, idx + 1, f"#{num} {doi} is not in OpenAlex — check the DOI")
                continue
            c["enriched"] += 1
            if rec.get("is_retracted"):
                c["retracted"] += 1
                rep.error(path, idx + 1, f"#{num} {doi} is RETRACTED (OpenAlex) — drop or replace the source, or cite it only as retracted")
            cy, oy = cited_year(ref), rec.get("year")
            if cy and isinstance(oy, int) and cy != oy:
                rep.warn(path, idx + 1, f"#{num} year mismatch: cited {cy}, OpenAlex {oy}")
        if notes and not args.no_write:
            write_section(path, lines, notes)
    if c["fetched"] or (not cache_path.exists() and works):
        cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if c["missing"]:
        why = "offline" if args.offline else "network unavailable"
        rep.warn(cache_path, 1, f"{c['missing']} id(s) not looked up ({why}, not in the cache)")
    return rep.finish({**c, "offline": "yes" if offline else "no", "cache": str(cache_path).replace("\\", "/")})


if __name__ == "__main__":
    sys.exit(main())
