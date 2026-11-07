#!/usr/bin/env python
"""Gate for topics/<slug>/PLAN.md (references/contracts.md section 3).

Usage: python check_plan.py <topics/slug/PLAN.md> [--before brief|research|compose] [--hash]

  --before <stage>  adds the cross-file checks that must hold before that stage starts
                    (tmp/INSIGHTS.md, tmp/BRIEF.md, tmp/dossier/00-overview.md are resolved from the plan's folder)
  --hash            prints only `HASH: <12hex>` (the insight hash, contracts section 4) and the RESULT line

Optional policy lines (I1, I5): `**Readers**: <one or two personas>` and `**Discovery**: none|datasets, code,
standards, lectures` in the plan header, and the `Readers` / `Discovery` rows of the INSIGHTS.md How table, are
checked against the persona and source-class vocabularies; a header that differs from its row is a warning.

Prints `<file>:<line> <message>` per problem; ends with
  RESULT: gate=plan status=PASS|FAIL errors=n warnings=n stage=<stage> hash=<12hex|none>
Exit 0 = PASS, 1 = FAIL, 2 = usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (BRIEF_HEADING_RE, CLOSED, DATE_RE, MARKERS, MODULE_ID_RE, NOTE_KINDS, NOTE_RE, SLUG_RE,  # noqa: E402
                     STAGES, STAGE_VOCAB, WHAT_KEYS, Plan, Report, find_section, find_table, header_keys, insight_hash,
                     placeholders, read_lines, result_line, sections, strip_code, usage_error)

PROGRESS_HEADER = ["Status", "Stage", "Output"]
PROGRESS_OUTPUTS = {"insights": "tmp/INSIGHTS.md", "brief": "tmp/BRIEF.md", "research": "tmp/dossier/", "compose": "index.html"}
MODULES_HEADER = ["#", "Module", "Researched", "Checked", "Page"]
# I1 reader emphasis: the personas of TODO.md §2.1, derived by the refiner from the Use/Goal answers (never asked)
PERSONAS = ("creative student", "engineer", "software developer", "circuit designer", "researcher",
            "fundamental sciences", "instructor", "accessibility/mobile")
# I5 discovery extensions: the extra source classes the researchers may search (opt-in; `none` = today's budgets)
DISCOVERY_CLASSES = ("datasets", "code", "standards", "lectures")


def split_policy(value: str) -> list[str]:
    """`engineer, software developer — "reference while building"` → ['engineer', 'software developer']."""
    v = strip_code(value)
    v = re.split(r"\s+[—–]\s+|\s+-\s+", v, maxsplit=1)[0]
    return [p.strip().strip("`*_").lower() for p in re.split(r"[,+·]", v) if p.strip()]


def check_readers(value: str, f, line: int, rep: Report, label: str) -> list[str]:
    names = split_policy(value)
    if not names:
        rep.error(f, line, f"{label} is empty — name one or two personas ({', '.join(PERSONAS)})")
        return []
    for n in names:
        if n not in PERSONAS:
            rep.error(f, line, f"{label} persona `{n}` is not one of: {', '.join(PERSONAS)}")
    if len(names) > 2:
        rep.warn(f, line, f"{label} names {len(names)} personas — one or two set the emphasis")
    return names


def check_discovery(value: str, f, line: int, rep: Report, label: str) -> list[str]:
    names = split_policy(value)
    if names == ["none"]:
        return []
    if not names:
        rep.error(f, line, f"{label} is empty — write `none` or a list of {', '.join(DISCOVERY_CLASSES)}")
        return []
    for n in names:
        if n not in DISCOVERY_CLASSES:
            rep.error(f, line, f"{label} class `{n}` is not one of: none, {', '.join(DISCOVERY_CLASSES)}")
    return names


def policy_rows(lines) -> dict[str, tuple[str, int]]:
    """INSIGHTS.md `## How (derived policies)` rows → {policy: (value, line index)}."""
    sec = find_section(sections(lines), "How (derived policies)")
    if sec is None:
        return {}
    t = find_table(lines, sec[1] + 1, sec[2])
    if t is None:
        return {}
    return {cells[0]: (cells[1] if len(cells) > 1 else "", idx) for idx, cells in t[2] if cells}


def check_reader_policies(plan: Plan, rep: Report, ins_lines, ins_path) -> None:
    """I1 `**Readers**` / I5 `**Discovery**`: optional plan header lines and INSIGHTS.md How rows."""
    f = plan.path
    got = {}
    for key, fn in (("Readers", check_readers), ("Discovery", check_discovery)):
        if key in plan.header:
            got[key] = fn(plan.header[key][0], f, plan.header[key][1] + 1, rep, key)
    if ins_lines is None:
        return
    rows = policy_rows(ins_lines)
    for key, fn in (("Readers", check_readers), ("Discovery", check_discovery)):
        if key not in rows:
            continue
        val, idx = rows[key]
        names = fn(val, ins_path, idx + 1, rep, f"INSIGHTS.md {key} row")
        if key in got and got[key] != names:
            rep.warn(f, plan.header[key][1] + 1, f"{key} header `{', '.join(got[key]) or 'none'}` differs from the INSIGHTS.md {key} row `{', '.join(names)}` — the plan header is the live value; add a `Changed` note")


def check_structure(plan: Plan, rep: Report) -> None:
    f = plan.path
    L = plan.lines
    # --- title and header -------------------------------------------------
    if plan.title is None:
        rep.error(f, 1, "first line must be `# Research plan: <Title>`")
    elif not plan.title:
        rep.error(f, plan.title_idx + 1, "title is empty")
    for key in ("Slug", "Folder", "Stage", "Updated"):
        if key not in plan.header:
            rep.error(f, 2, f"header line `**{key}**: …` missing")
    for key in ("Files", "Site"):
        if key in plan.header:
            rep.error(f, plan.header[key][1] + 1, f"`**{key}**` is no longer a plan header line — the topic folder is the plan's own folder (contracts §3)")
    slug = plan.slug
    if slug is not None:
        line = plan.header["Slug"][1] + 1
        if not SLUG_RE.match(slug):
            rep.error(f, line, f"slug `{slug}` must be kebab-case [a-z0-9-], 1–24 characters")
        if plan.folder_name != slug:
            rep.error(f, line, f"slug `{slug}` must equal the plan's folder name `{plan.folder_name}` (the plan lives at topics/<slug>/PLAN.md)")
        if f.name != "PLAN.md":
            rep.warn(f, line, f"the plan file should be named PLAN.md (got `{f.name}`)")
        if plan.topic_dir.parent.name != "topics":
            rep.warn(f, line, f"the topic folder should sit under `topics/` (found under `{plan.topic_dir.parent.name}/`)")
    folder = plan.header_value("Folder")
    if folder is not None and slug:
        line = plan.header["Folder"][1] + 1
        norm = folder.replace("\\", "/")
        if norm != f"topics/{slug}/":
            rep.error(f, line, f"Folder must be `topics/{slug}/` (got `{folder}`)")
    stage = plan.header_value("Stage")
    if stage is not None and stage not in STAGE_VOCAB:
        rep.error(f, plan.header["Stage"][1] + 1, f"Stage `{stage}` must be one of {', '.join(STAGE_VOCAB)}")
    fmt = plan.header_value("Format")
    if fmt is not None and fmt.strip().lower() not in ("single", "site"):
        rep.error(f, plan.header["Format"][1] + 1, f"Format must be single or site (got `{fmt}`)")
    upd = plan.header_value("Updated")
    if upd is not None and not DATE_RE.match(upd):
        rep.error(f, plan.header["Updated"][1] + 1, f"Updated must be YYYY-MM-DD (got `{upd}`)")

    # --- What I want --------------------------------------------------------
    if plan.what_sec is None:
        rep.error(f, 1, "section `## What I want` missing")
    else:
        line = plan.what_sec[1] + 1
        keys_in_order = [k for k, _ in plan.what_order]
        if keys_in_order != list(WHAT_KEYS):
            expected = ", ".join(WHAT_KEYS)
            rep.error(f, line, f"What I want must have exactly these bullets in order: {expected} (got: {', '.join(keys_in_order) or 'none'})")
        for key in WHAT_KEYS:
            if key in plan.what and not plan.what[key][0]:
                rep.error(f, plan.what[key][1] + 1, f"`{key}` is empty")
        if plan.details_idx < 0:
            rep.error(f, line, "`Details: `tmp/INSIGHTS.md`` line missing in What I want")
        elif "tmp/INSIGHTS.md" not in L[plan.details_idx].replace("\\", "/"):
            rep.error(f, plan.details_idx + 1, "Details line must point at `tmp/INSIGHTS.md` (relative to the topic folder)")
        how = plan.what.get("How", ("", 0))[0].lower()
        if how and not re.search(r"\bverify (strict|standard|light)\b", how):
            rep.warn(f, plan.what["How"][1] + 1, "How line should contain `verify strict|standard|light`")

    # --- Progress -----------------------------------------------------------
    stage_from_rows = None
    if plan.progress_sec is None:
        rep.error(f, 1, "section `## Progress` missing")
    elif plan.progress_header is None:
        rep.error(f, plan.progress_sec[1] + 1, "Progress table missing")
    else:
        hdr, hidx = plan.progress_header
        if hdr != PROGRESS_HEADER:
            rep.error(f, hidx + 1, "Progress header must be `| Status | Stage | Output |`")
        stages = [st for _, _, st, _ in plan.progress]
        if stages != list(STAGES):
            rep.error(f, hidx + 1, f"Progress must have exactly the rows {', '.join(STAGES)} in order (got {', '.join(stages) or 'none'})")
        seen_open = False
        for idx, marker, st, out in plan.progress:
            if marker not in MARKERS:
                rep.error(f, idx + 1, f"marker `{marker}` must be one of [ ], [x], [SKIP]")
                continue
            if marker == "[ ]":
                seen_open = True
            elif seen_open:
                rep.error(f, idx + 1, f"stage `{st}` is closed after an open stage — stages are sequential")
            if not out:
                rep.error(f, idx + 1, "Output column is empty")
            elif st in PROGRESS_OUTPUTS and strip_code(out).replace("\\", "/") != PROGRESS_OUTPUTS[st]:
                rep.error(f, idx + 1, f"Output of `{st}` must be `{PROGRESS_OUTPUTS[st]}` (relative to the topic folder; got `{out}`)")
        stage_from_rows = plan.stage_from_progress()
        if stage is not None and stage in STAGE_VOCAB and stage_from_rows and stage != stage_from_rows:
            rep.error(f, plan.header["Stage"][1] + 1, f"Stage `{stage}` disagrees with Progress (first open row is `{stage_from_rows}`)")

    # --- Modules ------------------------------------------------------------
    skipped: list[tuple[int, str, str]] = []  # (line, id, column)
    if plan.modules_sec is None:
        rep.error(f, 1, "section `## Modules` missing")
    elif plan.modules_header is None:
        rep.error(f, plan.modules_sec[1] + 1, "Modules table header missing (`| # | Module | Researched | Checked | Page |`)")
    else:
        hdr, hidx = plan.modules_header
        if hdr != MODULES_HEADER:
            rep.error(f, hidx + 1, "Modules header must be `| # | Module | Researched | Checked | Page |`")
        seen_ids: dict[str, int] = {}
        last_num = {"M": 0, "S": 0}
        verify_light = "verify light" in plan.what.get("How", ("", 0))[0].lower()
        for idx, mid, title, r, c, p in plan.modules:
            if not MODULE_ID_RE.match(mid):
                rep.error(f, idx + 1, f"module id `{mid}` must be M01…/S01…")
                continue
            if mid in seen_ids:
                rep.error(f, idx + 1, f"duplicate module id `{mid}` (first at line {seen_ids[mid] + 1})")
            seen_ids[mid] = idx
            num = int(mid[1:])
            if num <= last_num[mid[0]]:
                rep.error(f, idx + 1, f"module id `{mid}` is not ascending")
            last_num[mid[0]] = max(last_num[mid[0]], num)
            if not title:
                rep.error(f, idx + 1, "module title is empty")
            for col, val in (("Researched", r), ("Checked", c), ("Page", p)):
                if val not in MARKERS:
                    rep.error(f, idx + 1, f"{col} marker `{val}` must be one of [ ], [x], [SKIP]")
                elif val == "[SKIP]":
                    exempt = col == "Checked" and (mid.startswith("S") or verify_light)
                    if not exempt:
                        skipped.append((idx, mid, col))
        brief_marker = plan.progress_marker("brief")
        research_marker = plan.progress_marker("research")
        compose_marker = plan.progress_marker("compose")
        if brief_marker in CLOSED and not plan.modules:
            rep.error(f, hidx + 1, "brief is closed but the Modules table is empty")
        if brief_marker == "[ ]" and plan.modules:
            rep.warn(f, hidx + 1, "Modules table filled while the brief is still open")
        if research_marker in CLOSED:
            for idx, mid, _, r, c, _ in plan.modules:
                if r not in CLOSED or c not in CLOSED:
                    rep.error(f, idx + 1, f"research is closed but {mid} is still open")
        if compose_marker in CLOSED:
            for idx, mid, _, _, _, p in plan.modules:
                if p not in CLOSED:
                    rep.error(f, idx + 1, f"compose is closed but the page of {mid} is still open")

    # --- Next ---------------------------------------------------------------
    if plan.next_sec is None:
        rep.error(f, 1, "section `## Next` missing")
    elif not plan.next_lines:
        rep.error(f, plan.next_sec[1] + 1, "Next must contain one line")
    elif len(plan.next_lines) > 1:
        rep.warn(f, plan.next_lines[1][0] + 1, "Next should be one line")

    # --- Notes --------------------------------------------------------------
    changed_texts: list[str] = []
    if plan.notes_sec is None:
        rep.error(f, 1, "section `## Notes` missing")
    else:
        counters = {k: 0 for k in NOTE_KINDS}
        for idx, text in plan.notes:
            m = NOTE_RE.match(text)
            if not m:
                rep.error(f, idx + 1, "note must look like `- Changed|Caveat|Lesson n (stage, YYYY-MM-DD): one sentence`")
                continue
            kind, num, st, _, body = m.group(1), int(m.group(2)), m.group(3), m.group(4), m.group(5)
            if num != counters[kind] + 1:
                rep.error(f, idx + 1, f"{kind} notes must be numbered consecutively (expected {kind} {counters[kind] + 1})")
            counters[kind] = max(counters[kind], num)
            if st not in STAGE_VOCAB:
                rep.error(f, idx + 1, f"note stage `{st}` must be one of {', '.join(STAGE_VOCAB)}")
            if kind == "Changed":
                changed_texts.append(body)
        for idx, mid, col in skipped:
            if not any(re.search(r"\b%s\b" % re.escape(mid), t) for t in changed_texts):
                rep.error(f, idx + 1, f"{mid} {col} is [SKIP] but no `Changed` note names {mid}")

    # --- placeholders and length ---------------------------------------------
    for idx, ph in placeholders(L):
        rep.error(f, idx + 1, f"placeholder `{ph}` left from the template")
    if len([l for l in L if l.strip()]) > 120:
        rep.warn(f, len(L), "plan is longer than 120 lines — move detail to tmp/")


def read_insights(plan: Plan, rep: Report, required: bool):
    path = plan.tmp_dir / "INSIGHTS.md"
    if not path.exists():
        if required:
            rep.error(plan.path, plan.header.get("Slug", ("", 1))[1] + 1, f"tmp/INSIGHTS.md missing at {path}")
        return None, path
    return read_lines(path), path


def check_before(plan: Plan, rep: Report, stage: str, ins_lines, ins_path) -> None:
    f = plan.path
    tmp = plan.tmp_dir
    order = STAGES.index(stage)
    # earlier stages closed
    for st in STAGES[:order]:
        if plan.progress_marker(st) not in CLOSED:
            rep.error(f, plan.progress_sec[1] + 1 if plan.progress_sec else 1, f"stage `{st}` must be closed before `{stage}` starts")
    # insights confirmed (before brief and research)
    if stage in ("brief", "research"):
        if ins_lines is not None:
            keys = header_keys(ins_lines, 0, len(ins_lines))
            status = strip_code(keys.get("Status", ("", 0))[0])
            if status != "Confirmed":
                rep.error(ins_path, keys.get("Status", ("", 0))[1] + 1, f"INSIGHTS.md Status must be `Confirmed` (got `{status or 'missing'}`)")
            isecs = sections(ins_lines)
            for name in ("Refined insight", "How (derived policies)"):
                if find_section(isecs, name) is None:
                    rep.error(ins_path, 1, f"INSIGHTS.md section `## {name}` missing")
        for key in WHAT_KEYS:
            if key in plan.what and not plan.what[key][0]:
                rep.error(f, plan.what[key][1] + 1, f"`{key}` must be filled before `{stage}`")
    # brief approved + hash + modules match
    if stage == "research":
        bpath = tmp / "BRIEF.md"
        if not bpath.exists():
            rep.error(f, 1, f"tmp/BRIEF.md missing at {bpath}")
        else:
            bl = read_lines(bpath)
            keys = header_keys(bl, 0, len(bl))
            status = strip_code(keys.get("Status", ("", 0))[0])
            if status != "Approved":
                rep.error(bpath, keys.get("Status", ("", 0))[1] + 1, f"BRIEF.md Status must be `Approved` (got `{status or 'missing'}`)")
            bh = strip_code(keys.get("Insight hash", ("", 0))[0])
            if ins_lines is not None:
                want = insight_hash(plan, ins_lines)
                if bh != want:
                    rep.error(bpath, keys.get("Insight hash", ("", 0))[1] + 1,
                              f"Insight hash `{bh or 'missing'}` ≠ current insight `{want}` — the insight changed after the brief was written; re-run the brief stage")
            heads = []
            for i, line in enumerate(bl):
                m = BRIEF_HEADING_RE.match(line)
                if m:
                    heads.append((i, m.group(1), m.group(2).strip()))
            if not heads:
                rep.error(bpath, 1, "no module headings `### M01 — <Title>` in BRIEF.md")
            plan_rows = [(idx, mid, title) for idx, mid, title, *_ in plan.modules]
            brief_map = {mid: (i, t) for i, mid, t in heads}
            plan_map = {mid: (idx, t) for idx, mid, t in plan_rows}
            for mid, (idx, t) in plan_map.items():
                if mid not in brief_map:
                    rep.error(f, idx + 1, f"{mid} is in the plan but not in BRIEF.md")
                else:
                    bt = brief_map[mid][1]
                    if t != bt and t != re.sub(r"\s*\([^)]*\)\s*$", "", bt).strip():
                        rep.error(f, idx + 1, f"{mid} title `{t}` ≠ brief heading `{bt}`")
            for mid, (i, t) in brief_map.items():
                if mid not in plan_map:
                    rep.error(bpath, i + 1, f"{mid} is in BRIEF.md but not in the plan's Modules table")
            if [m for _, m, _ in plan_rows] != [m for _, m, _ in heads if m in plan_map]:
                rep.warn(f, plan.modules_sec[1] + 1 if plan.modules_sec else 1, "module order differs between the plan and BRIEF.md")
    if stage == "compose":
        for idx, mid, _, r, c, _ in plan.modules:
            if r not in CLOSED or c not in CLOSED:
                rep.error(f, idx + 1, f"{mid} must be researched and checked (or [SKIP]) before compose")
        ov = tmp / "dossier" / "00-overview.md"
        if not ov.exists():
            rep.error(f, 1, f"tmp/dossier/00-overview.md missing at {ov}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--before", choices=["brief", "research", "compose"])
    ap.add_argument("--hash", action="store_true", dest="hash_only")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    path = Path(args.plan)
    if not path.exists():
        return usage_error(f"no such plan: {path}")
    rep = Report("gate", "plan")
    plan = Plan(path)
    stage = plan.header_value("Stage") or plan.stage_from_progress() or "unknown"

    if args.hash_only:
        ins_lines, ins_path = read_insights(plan, rep, required=True)
        h = insight_hash(plan, ins_lines) if ins_lines is not None else "none"
        if plan.what_sec is None:
            rep.error(plan.path, 1, "section `## What I want` missing — hash covers nothing")
        if ins_lines is not None:
            print(f"HASH: {h}")
        rep.print_problems()
        print(result_line(gate="plan", status=rep.status, errors=len(rep.errors), warnings=len(rep.warnings), stage=stage, hash=h))
        return 1 if rep.errors else 0

    check_structure(plan, rep)
    ins_lines, ins_path = read_insights(plan, rep, required=bool(args.before))
    h = insight_hash(plan, ins_lines) if (ins_lines is not None and plan.what_sec is not None) else "none"
    check_reader_policies(plan, rep, ins_lines, ins_path)
    if args.before:
        check_before(plan, rep, args.before, ins_lines, ins_path)
    return rep.finish({"stage": stage, "hash": h})


if __name__ == "__main__":
    sys.exit(main())
