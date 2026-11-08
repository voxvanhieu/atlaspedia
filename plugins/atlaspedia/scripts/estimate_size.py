#!/usr/bin/env python
"""Estimate the page size a brief implies, to decide whether it fits one page (contracts section 9).

Usage: python estimate_size.py <topics/slug/PLAN.md> [--budget 250] [--max-parts 6]

Reads the plan's optional `**Format**` header and the `**How**` line (`depth X`, `demos Y`), then
`<plan dir>/tmp/BRIEF.md`. Parts = every `### M01 — ` / `### S01 — ` heading. Topics per part = the bullet lines
after the part's `Topics:` line (until the first non-bullet, non-blank line), each bullet counted as the number
of `·`-separated items it holds (nested bullets count too). Estimate in KB:

  est = 20 + sum over parts of (12 + 2.5 × topics) × depth_factor  +  demos_per_part × modules
  depth_factor: overview 0.7 · textbook 1.0 · mixed 1.2 · monograph 1.6 (unknown → 1.0)
  demos_per_part: rich 8 · moderate 4 · minimal 0 (counted for M parts only)

Prints one line per part `<BRIEF path>:<line> M01 topics=n est=nKB`, then
  RESULT: tool=estimate_size status=PASS format=<f> parts=n topics=n est_kb=n budget_kb=250 fits=yes|no
fits = est_kb <= budget and parts <= max-parts (for the site format it is informative only).
Exit 1 (status=FAIL) only when the plan or BRIEF.md is unreadable or the brief has no parts; 2 on usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import BRIEF_HEADING_RE, Plan, display, read_lines, result_line, usage_error  # noqa: E402

DEPTH_FACTOR = {"overview": 0.7, "textbook": 1.0, "mixed": 1.2, "monograph": 1.6}
DEMOS_PER_PART = {"rich": 8, "moderate": 4, "minimal": 0}
BASE_KB = 20
PART_KB = 12
TOPIC_KB = 2.5


def how_value(how: str, key: str) -> str | None:
    m = re.search(rf"\b{key}\s+([a-z]+)", how.lower())
    return m.group(1) if m else None


def count_items(text: str) -> int:
    return sum(1 for item in text.split("·") if item.strip(" *_\t"))


def parse_parts(lines: list[str]) -> list[tuple[str, int, int]]:
    """[(id, heading line index, topics)] for every ### M/S heading."""
    heads = [(i, m.group(1)) for i, line in enumerate(lines) if (m := BRIEF_HEADING_RE.match(line.strip()))]
    parts = []
    for n, (i, pid) in enumerate(heads):
        end = len(lines)
        for j in range(i + 1, len(lines)):
            s = lines[j].lstrip()
            if s.startswith("### ") or s.startswith("## "):
                end = j
                break
        topics = 0
        k = i + 1
        while k < end and not re.match(r"^\s*\**Topics\**\s*:", lines[k]):
            k += 1
        if k < end:
            rest = re.sub(r"^\s*\**Topics\**\s*:\s*", "", lines[k])
            topics += count_items(rest) if rest.strip() else 0
            for j in range(k + 1, end):
                s = lines[j].strip()
                if not s:
                    continue
                if re.match(r"^[-*+]\s+", s):
                    topics += count_items(re.sub(r"^[-*+]\s+", "", s))
                else:
                    break
        parts.append((pid, i, topics))
    return parts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("plan")
    ap.add_argument("--budget", type=int, default=250)
    ap.add_argument("--max-parts", type=int, default=6)
    try:
        args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        return usage_error("Usage: python estimate_size.py <PLAN.md> [--budget 250] [--max-parts 6]")
    plan_path = Path(args.plan)

    def fail(file, line, msg, fmt="site"):
        print(f"{display(file)}:{line} {msg}")
        print(result_line(tool="estimate_size", status="FAIL", format=fmt, parts=0, topics=0, est_kb=0,
                          budget_kb=args.budget, fits="no"))
        return 1

    if not plan_path.exists():
        return fail(plan_path, 1, "plan not found")
    try:
        plan = Plan(plan_path)
    except (OSError, UnicodeDecodeError) as e:
        return fail(plan_path, 1, f"plan unreadable: {e}")
    fmt = plan.format
    how = plan.what.get("How", ("", 0))[0]
    depth = how_value(how, "depth") or "textbook"
    demos = how_value(how, "demos") or "rich"
    df = DEPTH_FACTOR.get(depth, 1.0)
    dpp = DEMOS_PER_PART.get(demos, 0)
    brief = plan.tmp_dir / "BRIEF.md"
    if not brief.exists():
        return fail(brief, 1, "BRIEF.md not found", fmt)
    try:
        lines = read_lines(brief)
    except (OSError, UnicodeDecodeError) as e:
        return fail(brief, 1, f"BRIEF.md unreadable: {e}", fmt)
    parts = parse_parts(lines)
    if not parts:
        return fail(brief, 1, "brief has no `### M01 — Title` / `### S01 — Title` parts", fmt)
    total = float(BASE_KB)
    topics_total = 0
    for pid, i, t in parts:
        est = (PART_KB + TOPIC_KB * t) * df + (dpp if pid.startswith("M") else 0)
        total += est
        topics_total += t
        print(f"{display(brief)}:{i + 1} {pid} topics={t} est={round(est)}KB")
    est_kb = round(total)
    fits = est_kb <= args.budget and len(parts) <= args.max_parts
    print(result_line(tool="estimate_size", status="PASS", format=fmt, parts=len(parts), topics=topics_total,
                      est_kb=est_kb, budget_kb=args.budget, fits="yes" if fits else "no"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
