#!/usr/bin/env python
"""Read topics/<slug>/PLAN.md and print what to run next (contracts section 9).

Usage: python next_stage.py <topics/slug/PLAN.md>

Prints
  Stage: <stage>
  Open researched: M04,M05 | none
  Open checked: ...
  Open pages: ...            (from the topic's tmp/SITE_PLAN.md `## Pages` when it exists, else the plan's Page column)
  Format: single | site      (the plan's optional **Format** header; missing = site)
  Next: /atlas-learn:research <slug> | /atlas-learn:compose <slug> | /atlas-learn:collect-insights | done
  RESULT: tool=next_stage stage=<stage> open_researched=n open_checked=n open_pages=n command=<command> slug=<slug> format=<single|site>
Exit 0; 1 when the plan cannot be parsed; 2 on usage error.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Plan, col_index, find_section, find_table, read_lines, result_line, sections, usage_error  # noqa: E402

COMMANDS = {
    "insights": "/atlas-learn:collect-insights",
    "brief": "/atlas-learn:research",
    "research": "/atlas-learn:research",
    "compose": "/atlas-learn:compose",
    "done": "done",
}


def open_pages_from_site_plan(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    lines = read_lines(path)
    sec = find_section(sections(lines), "Pages")
    if sec is None:
        return None
    t = find_table(lines, sec[1] + 1, sec[2])
    if t is None:
        return None
    header, _, rows = t
    fi, si = col_index(header, "File"), col_index(header, "Status")
    if fi < 0 or si < 0:
        return None
    return [cells[fi] for _, cells in rows if len(cells) > max(fi, si) and cells[si] == "[ ]"]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        return usage_error("Usage: python next_stage.py <plan.md>")
    path = Path(argv[0])
    if not path.exists():
        return usage_error(f"no such plan: {path}")
    plan = Plan(path)
    stage = plan.stage_from_progress() or plan.header_value("Stage")
    if stage is None or stage not in COMMANDS:
        print(f"{path}:1 cannot determine the stage (Progress table or Stage line missing/invalid)")
        print(result_line(tool="next_stage", stage="unknown", open_researched=0, open_checked=0, open_pages=0, command="none", slug=plan.slug or "none", format=plan.format))
        return 1
    slug = plan.slug or "unknown"
    open_r = [mid for _, mid, _, r, _, _ in plan.modules if r == "[ ]"]
    open_c = [mid for _, mid, _, _, c, _ in plan.modules if c == "[ ]"]
    open_p = open_pages_from_site_plan(plan.tmp_dir / "SITE_PLAN.md")
    if open_p is None:
        open_p = [mid for _, mid, _, _, _, p in plan.modules if p == "[ ]"]
    command = COMMANDS[stage]
    next_text = command if command == "done" else (command if stage == "insights" else f"{command} {slug}")
    print(f"Stage: {stage}")
    print(f"Open researched: {','.join(open_r) or 'none'}")
    print(f"Open checked: {','.join(open_c) or 'none'}")
    print(f"Open pages: {','.join(open_p) or 'none'}")
    fmt = plan.format
    if stage == "compose" and fmt == "single":
        next_text += " — build the single page"
    print(f"Format: {fmt}")
    print(f"Next: {next_text}")
    print(result_line(tool="next_stage", stage=stage, open_researched=len(open_r), open_checked=len(open_c),
                      open_pages=len(open_p), command=command, slug=slug, format=fmt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
