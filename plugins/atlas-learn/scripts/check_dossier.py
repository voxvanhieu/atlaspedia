#!/usr/bin/env python
"""Gate for dossier files (references/contracts.md section 6).

Usage: python check_dossier.py <file.md> [--overview] [--depth overview|textbook|monograph]

Module / synthesis file (dossier/mNN-slug.md, sNN-slug.md): every template section present (a section with
nothing to say contains `none`); every Sources row has a number, Tier 1–3, a Status from the vocabulary, an
http(s) link and a non-blank Verified cell that never says `model knowledge`; every Key-facts row cites an existing
source number and a Locator; every Documented-calculations (C1…) and Documented-relationships (R1…) row cites an
existing source number and a Locator; Running-example rows cite a source number or `user` (a user-provided value);
`estimate` is never accepted (references/evidence-policy.md §2, §5); every Interactive-demo candidate names a
documented calculation by its C id; every Media row has a licence and a URL. An optional `Kind` column (I5) holds one of paper, dataset, code,
standard, lecture, book, web per row (unknown = error, blank = warning) and adds `kinds=paper:n,…` to RESULT.

--overview (dossier/00-overview.md): sections `## 1. …` to `## 8. …`, every parameter-sheet row with a source (or
`user`), the Groups/Levels/Priority module lines and at least one `### Page <file> — <Title> (…)` block with the
eight dash-lines in Build notes; a `- Demos:` line that is not `none`/`n/a` names a C id, a `- Diagrams:` line
that is not `none`/`n/a` names an R id or a source # (evidence policy §5, §6).

Ends with
  RESULT: gate=dossier status=PASS|FAIL errors=n warnings=n sources=n t1=n t2=n t3=n unverified=n media=n demos=n [calcs=n relations=n] [pages=n] [kinds=…]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Report, col_index, find_section, find_table, placeholders, read_lines, sections, usage_error  # noqa: E402

REQUIRED_SECTIONS = [  # (prefix used to find the heading, canonical name)
    ("keywords", "Keywords"),
    ("sources", "Sources"),
    ("key facts", "Key facts and numbers"),
    ("documented calculations", "Documented calculations"),
    ("documented relationships", "Documented relationships"),
    ("conflicts", "Conflicts and limitations"),
    ("running-example", "Running-example parameters"),
    ("media candidates", "Media candidates (verified)"),
    ("interactive demo", "Interactive demo candidates"),
    ("suggested diagrams", "Suggested diagrams and tables"),
    ("open questions", "Open questions / research directions"),
    ("freshness", "Freshness notes"),
    ("could not verify", "Could not verify"),
]
# I5: the optional `Kind` column of a Sources table (and of the overview's bibliography seed)
KIND_VOCAB = ("paper", "dataset", "code", "standard", "lecture", "book", "web")
STATUS_VOCAB = ("foundational", "established", "recent", "experimental", "discontinued", "preprint")
UNVERIFIED_RE = re.compile(r"unverified|not confirmed|✗|dead|unreachable|could not", re.I)
MODEL_KNOWLEDGE_RE = re.compile(r"model knowledge", re.I)   # evidence policy §3: a reference nobody retrieved is not a source
ESTIMATE_RE = re.compile(r"\bestimate[sd]?\b", re.I)
MIN_SOURCES = {"overview": 4, "textbook": 8, "monograph": 12}

OVERVIEW_SECTIONS = [
    "Running-example parameter sheet", "Overlaps and ownership", "Glossary seed", "Bibliography seed",
    "Media list", "Conflicts and limitations", "Unverified items", "Build notes",
]
PAGE_HEADING_RE = re.compile(r"^### Page (\S+\.html) [—–-] (.+?)\s*(\(.*\))?\s*$")
PAGE_LINES = ("Topics", "Diagrams", "Tables", "Demos", "Sources", "Media", "Cross-links", "Numbers")


def body_is_empty(lines, sec) -> bool:
    return not any(l.strip() for l in lines[sec[1] + 1:sec[2]])


def check_kind(path: Path, rep: Report, idx: int, cell: str, kinds: dict) -> None:
    """Validate one `Kind` cell (I5); blank is a warning, an unknown kind an error."""
    k = cell.strip().strip("`*_").lower()
    if not k:
        rep.warn(path, idx + 1, f"Kind cell is blank (one of {', '.join(KIND_VOCAB)})")
        return
    if k not in KIND_VOCAB:
        rep.error(path, idx + 1, f"Kind `{cell.strip()}` must be one of {', '.join(KIND_VOCAB)}")
        return
    kinds[k] = kinds.get(k, 0) + 1


def kinds_value(kinds: dict) -> str:
    return ",".join(f"{k}:{kinds[k]}" for k in KIND_VOCAB if k in kinds) or "none"


def source_refs_ok(cell: str, numbers: set[int], allow_user: bool = False) -> tuple[bool, str]:
    """A Source # cell: existing source numbers; `user` only where a user-provided value is allowed. Never `estimate`."""
    c = cell.strip()
    hint = "a source #" + (" or `user`" if allow_user else "")
    if not c:
        return False, f"no source (write {hint}; an item without one goes to `## Could not verify`)"
    if ESTIMATE_RE.search(c):
        return False, f"`{c}` is not evidence — write {hint}, or move the item to `## Could not verify` (evidence policy §5)"
    if allow_user and re.fullmatch(r"`?user`?(\s*[—–:-].*)?", c, re.I):
        return True, ""
    found = [int(n) for n in re.findall(r"\d+", c)]
    if not found:
        return False, f"source cell `{c}` has no source # (write {hint})"
    missing = [n for n in found if n not in numbers]
    if missing:
        return False, f"source #{', #'.join(map(str, missing))} does not exist in Sources"
    return True, ""


def check_module(path: Path, lines, rep: Report, depth: str) -> dict:
    secs = sections(lines)
    counts = {"sources": 0, "t1": 0, "t2": 0, "t3": 0, "unverified": 0, "media": 0, "demos": 0, "calcs": 0, "relations": 0}
    # H1
    first = next((l for l in lines if l.strip()), "")
    if not re.match(r"^# [MS]\d{2} [—–-] \S", first.strip()):
        rep.error(path, 1, "first line must be `# M01 — <Module title>` (or S01 for a synthesis part)")
    if not any(re.search(r"verification:\s*(strict|standard|light)", l, re.I) for l in lines[:6]):
        rep.warn(path, 2, "header line `Researched <date> · verification: … · freshness: …` missing")
    # sections
    found = {}
    for prefix, name in REQUIRED_SECTIONS:
        sec = find_section(secs, prefix, exact=False)
        if sec is None:
            rep.error(path, 1, f"section `## {name}` missing")
        else:
            found[prefix] = sec
            if body_is_empty(lines, sec):
                rep.error(path, sec[1] + 1, f"section `{sec[0]}` is empty (write `none` when nothing applies)")
    # Sources
    numbers: set[int] = set()
    kinds: dict[str, int] = {}
    sec = found.get("sources")
    if sec:
        t = find_table(lines, sec[1] + 1, sec[2])
        if t is None:
            if not re.search(r"^\s*none\s*$", "\n".join(lines[sec[1] + 1:sec[2]]), re.M):
                rep.error(path, sec[1] + 1, "Sources table missing")
        else:
            header, hidx, rows = t
            ci = {"num": col_index(header, "#"), "tier": col_index(header, "tier"), "status": col_index(header, "status"),
                  "link": col_index(header, "link"), "verified": col_index(header, "verified"),
                  "kind": col_index(header, "kind")}
            for key, name in (("num", "#"), ("tier", "Tier"), ("status", "Status"), ("link", "Link"), ("verified", "Verified")):
                if ci[key] < 0:
                    rep.error(path, hidx + 1, f"Sources table has no `{name}` column")
            for idx, cells in rows:
                def cell(key):
                    i = ci[key]
                    return cells[i] if 0 <= i < len(cells) else ""
                counts["sources"] += 1
                num = cell("num")
                if not num.isdigit():
                    rep.error(path, idx + 1, f"source row without a number (got `{num}`)")
                else:
                    numbers.add(int(num))
                tier = cell("tier")
                if tier in ("1", "2", "3"):
                    counts["t" + tier] += 1
                else:
                    rep.error(path, idx + 1, f"Tier `{tier}` must be 1, 2 or 3")
                status = cell("status").lower()
                if not status or status.split()[0].strip("*_`") not in STATUS_VOCAB:
                    rep.error(path, idx + 1, f"Status `{status or 'blank'}` must be one of {', '.join(STATUS_VOCAB)}")
                link = cell("link")
                if not re.search(r"https?://\S+", link):
                    rep.error(path, idx + 1, "source row without an http(s) link")
                if ci["kind"] >= 0:
                    check_kind(path, rep, idx, cell("kind"), kinds)
                ver = cell("verified")
                if not ver:
                    rep.error(path, idx + 1, "Verified cell is blank")
                elif MODEL_KNOWLEDGE_RE.search(ver):
                    rep.error(path, idx + 1, "Verified cell says `model knowledge` — a reference nobody retrieved is not a source: "
                                             "fetch it, or move it to `## Could not verify` (evidence policy §3, §4)")
                elif UNVERIFIED_RE.search(ver):
                    counts["unverified"] += 1
            if ci["kind"] >= 0:
                counts["kinds"] = kinds_value(kinds)
            minimum = MIN_SOURCES.get(depth, 8)
            if counts["sources"] < minimum:
                rep.warn(path, hidx + 1, f"only {counts['sources']} sources (expected ≥ {minimum} for depth {depth})")
    # Key facts, documented calculations and relationships, running-example: source refs (+ locators, ids)
    calc_ids: set[str] = set()
    for prefix, label, need_locator, id_prefix, allow_user in (
            ("key facts", "Key facts", True, None, False),
            ("documented calculations", "Documented calculations", True, "C", False),
            ("documented relationships", "Documented relationships", True, "R", False),
            ("running-example", "Running-example", False, None, True)):
        sec = found.get(prefix)
        if not sec:
            continue
        t = find_table(lines, sec[1] + 1, sec[2])
        if t is None:
            if id_prefix and not re.search(r"^\s*none\b", "\n".join(lines[sec[1] + 1:sec[2]]), re.M | re.I):
                rep.error(path, sec[1] + 1, f"{label} table missing (write `none` when the sources document none)")
            continue
        header, hidx, rows = t
        si = col_index(header, "source")
        if si < 0:
            rep.error(path, hidx + 1, f"{label} table has no `Source #` column")
            continue
        li = col_index(header, "locator")
        if need_locator and li < 0:
            rep.error(path, hidx + 1, f"{label} table has no `Locator` column (section, page, table or equation in the source — evidence policy §4)")
        ii = col_index(header, "id") if id_prefix else -1
        if id_prefix and ii < 0:
            rep.error(path, hidx + 1, f"{label} table has no `Id` column ({id_prefix}1, {id_prefix}2 …)")
        for idx, cells in rows:
            cell = cells[si] if si < len(cells) else ""
            ok, msg = source_refs_ok(cell, numbers, allow_user)
            if not ok:
                rep.error(path, idx + 1, f"{label}: {msg}")
            if need_locator and li >= 0 and not (cells[li].strip() if li < len(cells) else ""):
                rep.error(path, idx + 1, f"{label}: Locator is blank (where the source states it; `whole page` for a short page)")
            if ii >= 0:
                rid = (cells[ii].strip().strip("`*") if ii < len(cells) else "")
                if not re.fullmatch(id_prefix + r"\d+", rid):
                    rep.error(path, idx + 1, f"{label}: Id `{rid or 'blank'}` must be {id_prefix}1, {id_prefix}2 …")
                elif id_prefix == "C":
                    calc_ids.add(rid)
                counts["calcs" if id_prefix == "C" else "relations"] += 1
    # Media
    sec = found.get("media candidates")
    if sec:
        t = find_table(lines, sec[1] + 1, sec[2])
        if t is not None:
            header, hidx, rows = t
            li, ui = col_index(header, "licen"), col_index(header, "url")
            if li < 0:
                rep.error(path, hidx + 1, "Media table has no `Licence` column")
            for idx, cells in rows:
                counts["media"] += 1
                lic = cells[li] if 0 <= li < len(cells) else ""
                if not lic or lic.lower() in ("none", "?", "unknown", "-", "—"):
                    rep.error(path, idx + 1, "media row without a licence — delete the row or find the licence")
                url = cells[ui] if 0 <= ui < len(cells) else ""
                if ui >= 0 and not re.search(r"https?://\S+", url):
                    rep.error(path, idx + 1, "media row without an http(s) URL")
    # Demos: every candidate implements a documented calculation (evidence policy §5)
    sec = found.get("interactive demo")
    if sec:
        for i in range(sec[1] + 1, sec[2]):
            if not re.match(r"^\s*\d+\.\s+\S", lines[i]):
                continue
            counts["demos"] += 1
            named = re.findall(r"\bC\d+\b", lines[i])
            if not named:
                rep.error(path, i + 1, "demo candidate names no documented calculation (a C id from `## Documented calculations`; "
                                       "a demo without a documented method is not built — evidence policy §5)")
            for cid in named:
                if found.get("documented calculations") and cid not in calc_ids:
                    rep.error(path, i + 1, f"demo candidate names {cid}, which is not in `## Documented calculations`")
    for idx, ph in placeholders(lines):
        rep.error(path, idx + 1, f"placeholder `{ph}` left from the template")
    return counts


def check_overview(path: Path, lines, rep: Report) -> dict:
    secs = sections(lines)
    counts = {"sources": 0, "t1": 0, "t2": 0, "t3": 0, "unverified": 0, "media": 0, "demos": 0, "pages": 0}
    numbered = {}
    for title, start, end in secs:
        m = re.match(r"^(\d)\.\s+(.+)$", title)
        if m:
            numbered[int(m.group(1))] = (m.group(2).strip(), start, end)
    for n, name in enumerate(OVERVIEW_SECTIONS, 1):
        got = numbered.get(n)
        if got is None:
            rep.error(path, 1, f"section `## {n}. {name}` missing")
        elif not got[0].lower().startswith(name.lower().split()[0]):
            rep.error(path, got[1] + 1, f"section {n} should be `{name}` (got `{got[0]}`)")
        elif not any(l.strip() for l in lines[got[1] + 1:got[2]]):
            rep.error(path, got[1] + 1, f"section `{n}. {name}` is empty (write `none` when nothing applies)")
    # counts from the bibliography seed and media list
    for n, key in ((4, "sources"), (5, "media")):
        got = numbered.get(n)
        if got:
            t = find_table(lines, got[1] + 1, got[2])
            if t:
                header, _, rows = t
                counts[key] = len(rows)
                if key == "sources":
                    ti, ki = col_index(header, "tier"), col_index(header, "kind")
                    kinds: dict[str, int] = {}
                    for idx, cells in rows:
                        tier = cells[ti] if 0 <= ti < len(cells) else ""
                        if tier in ("1", "2", "3"):
                            counts["t" + tier] += 1
                        if ki >= 0:
                            check_kind(path, rep, idx, cells[ki] if ki < len(cells) else "", kinds)
                    if ki >= 0:
                        counts["kinds"] = kinds_value(kinds)
    # §1 parameter sheet: every value has a source (file + #) or is `user`; never `estimate` (evidence policy §2, §5)
    got = numbered.get(1)
    if got:
        t = find_table(lines, got[1] + 1, got[2])
        if t:
            header, hidx, rows = t
            si = col_index(header, "source")
            if si < 0:
                rep.error(path, hidx + 1, "parameter sheet has no `Source` column")
            else:
                for idx, cells in rows:
                    c = cells[si].strip() if si < len(cells) else ""
                    if not c or ESTIMATE_RE.search(c):
                        rep.error(path, idx + 1, f"parameter `{cells[0] if cells else '?'}` has no source (`{c or 'blank'}`): "
                                                 "cite the dossier file + # or `user`; a value no source states is not a parameter")
    got = numbered.get(7)
    if got:
        body = lines[got[1] + 1:got[2]]
        t = find_table(lines, got[1] + 1, got[2])
        counts["unverified"] = len(t[2]) if t else sum(1 for l in body if re.match(r"^\s*[-*]\s+(?!none\b)\S", l))
    # Build notes
    got = numbered.get(8)
    if got:
        body_start, body_end = got[1] + 1, got[2]
        text = "\n".join(lines[body_start:body_end])
        for key in ("Groups", "Levels", "Priority module"):
            if not re.search(r"^\*\*%s\*\*:\s*\S" % re.escape(key), text, re.M):
                rep.error(path, got[1] + 1, f"Build notes need a `**{key}**: …` line")
        page_blocks = [(i, PAGE_HEADING_RE.match(lines[i])) for i in range(body_start, body_end) if lines[i].startswith("### Page ")]
        if not page_blocks:
            rep.error(path, got[1] + 1, "Build notes need at least one `### Page <file>.html — <Title> (<id>, level <n>, <size>)` block")
        for k, (i, m) in enumerate(page_blocks):
            if m is None:
                rep.error(path, i + 1, "page block heading must be `### Page <file>.html — <Title> (…)`")
                continue
            counts["pages"] += 1
            nxt = page_blocks[k + 1][0] if k + 1 < len(page_blocks) else body_end
            block = lines[i + 1:nxt]
            for name in PAGE_LINES:
                hit = next(((j, l) for j, l in enumerate(block) if re.match(r"^\s*- \*{0,2}%s\*{0,2}\s*:" % re.escape(name), l)), None)
                if hit is None:
                    rep.error(path, i + 1, f"page block `{m.group(1)}` lacks the `- {name}:` line")
                    continue
                value = hit[1].split(":", 1)[1].strip().strip("*").strip()
                if not value or re.match(r"^(none|n/a|—|-)(\W|$)", value, re.I):
                    continue
                ln = i + 2 + hit[0]
                # evidence policy §5–§6: a demo implements a documented calculation, a diagram draws documented relationships
                if name == "Demos":
                    counts["demos"] += 1
                    if not re.search(r"\bC\d+\b", value):
                        rep.error(path, ln, f"page block `{m.group(1)}`: `- Demos:` names no documented calculation (C id) — write `none — <why>` when there is none")
                if name == "Diagrams" and not re.search(r"\bR\d+\b|#\d+", value):
                    rep.error(path, ln, f"page block `{m.group(1)}`: `- Diagrams:` cites no documented relationship (R id) or source # — write `none — <why>` when there is none")
    for idx, ph in placeholders(lines):
        rep.error(path, idx + 1, f"placeholder `{ph}` left from the template")
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--overview", action="store_true")
    ap.add_argument("--depth", choices=list(MIN_SOURCES), default="textbook")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    path = Path(args.file)
    if not path.exists():
        return usage_error(f"no such file: {path}")
    lines = read_lines(path)
    rep = Report("gate", "dossier")
    counts = check_overview(path, lines, rep) if args.overview else check_module(path, lines, rep, args.depth)
    return rep.finish(counts)


if __name__ == "__main__":
    sys.exit(main())
