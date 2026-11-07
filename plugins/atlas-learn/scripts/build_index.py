#!/usr/bin/env python
"""Build the repo-root topic dictionary from every topics/*/topic.json (contracts §9 and §13).

Usage: python build_index.py [<repo root>] [--force] [--template <root-index.html>]

  <repo root>   folder that contains `topics/`; default: the current directory or the nearest parent with
                `topics/`, else the nearest parent of this script with `topics/`
  --force       overwrite <repo>/index.html with the template (default: copy it only when absent)
  --template    the dictionary page to copy (default: <PLUGIN_ROOT>/templates/root-index.html)

Writes <repo>/index.html  the topic dictionary as ONE self-contained file: the payload {"generated": "<ISO timestamp>",
                          "topics": [... sorted by updated desc, then name]} is embedded inline in a
                          <script id="topics-data" type="application/json"> block, so the page works from file://
                          with no sidecar data file. The template is copied when the file is absent (or --force);
                          an existing page keeps its markup and only the data block is replaced (a legacy
                          `<script src="index.js">` include is converted, a page without any block gets one
                          inserted after <head>).
Never reads or writes anything inside a topic except its topic.json. A topic.json that fails validation is
reported (`<file>:<line> warning: …`) and left out of the index; it does not fail the run.
Ends with
  RESULT: tool=build_index status=PASS|FAIL topics=n written=[index.html] warnings=n skipped=<codes|none>
Exit 0 = PASS, 1 = FAIL (nothing could be written), 2 = usage.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DATE_RE, Report, SLUG_RE, TAG_RE, TOPIC_STATUS, display, result_line, usage_error  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = PLUGIN_ROOT / "templates" / "root-index.html"
REQUIRED = ("code", "name", "description", "tags", "status", "created", "updated", "pages", "entry")
OPTIONAL = ("format",)  # "single" | "site" (missing = site); copied into index.json
FORMATS = ("single", "site")
DATA_BLOCK = '<script id="topics-data" type="application/json">'
DATA_BLOCK_RE = re.compile(r'<script id="topics-data" type="application/json">[\s\S]*?</script>')
LEGACY_INCLUDE = '<script src="index.js"></script>'


def find_repo_root(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit).resolve()
        return p if (p / "topics").is_dir() else None
    for start in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        for cand in (start, *start.parents):
            if (cand / "topics").is_dir():
                return cand
    return None


def key_line(text: str, key: str) -> int:
    m = re.search(r'^\s*"%s"\s*:' % re.escape(key), text, re.M)
    return text.count("\n", 0, m.start()) + 1 if m else 0


def validate_topic(path: Path, folder: str, rep: Report) -> dict | None:
    """Returns the cleaned topic object, or None when it must be left out."""
    try:
        text = path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
    except OSError as e:
        rep.warn(path, 0, f"cannot read: {e}")
        return None
    except json.JSONDecodeError as e:
        rep.warn(path, e.lineno, f"invalid JSON: {e.msg}")
        return None
    if not isinstance(data, dict):
        rep.warn(path, 1, "topic.json must be a JSON object")
        return None
    problems = 0

    def bad(key: str, msg: str) -> None:
        nonlocal problems
        problems += 1
        rep.warn(path, key_line(text, key) or 1, msg)

    for key in REQUIRED:
        if key not in data:
            bad(key, f"`{key}` missing")
    if problems:
        return None
    code = data["code"]
    if not isinstance(code, str) or not SLUG_RE.match(code):
        bad("code", f"code must be kebab-case [a-z0-9-], ≤ 24 characters (got {json.dumps(code)})")
    elif code != folder:
        bad("code", f"code `{code}` must equal the folder name `{folder}`")
    if not isinstance(data["name"], str) or not data["name"].strip():
        bad("name", "name must be a non-empty string")
    desc = data["description"]
    if not isinstance(desc, str) or not desc.strip():
        bad("description", "description must be a non-empty sentence")
    elif len(desc) > 160:
        bad("description", f"description is {len(desc)} characters; keep it ≤ 160")
    tags = data["tags"]
    if not isinstance(tags, list) or not (1 <= len(tags) <= 8):
        bad("tags", "tags must be a list of 1–8 strings")
    else:
        for t in tags:
            if not isinstance(t, str) or not TAG_RE.match(t):
                bad("tags", f"tag {json.dumps(t)} must be lowercase kebab-case")
                break
    if data["status"] not in TOPIC_STATUS:
        bad("status", f"status {json.dumps(data['status'])} must be one of {', '.join(TOPIC_STATUS)}")
    for key in ("created", "updated"):
        v = data[key]
        if not isinstance(v, str) or not DATE_RE.match(v):
            bad(key, f"{key} must be YYYY-MM-DD (got {json.dumps(v)})")
    if isinstance(data["created"], str) and isinstance(data["updated"], str) and data["updated"] < data["created"]:
        bad("updated", "updated is earlier than created")
    pages = data["pages"]
    if not isinstance(pages, int) or isinstance(pages, bool) or pages < 0:
        bad("pages", "pages must be a non-negative integer")
    entry = data["entry"]
    if not isinstance(entry, str) or not entry.endswith(".html") or entry.startswith(("/", "\\")) or ".." in entry:
        bad("entry", "entry must be a relative .html path inside the topic folder (usually index.html)")
    elif data.get("status") == "done" and not (path.parent / entry).exists():
        rep.warn(path, key_line(text, "entry") or 1, f"status is done but `{entry}` does not exist yet")
    if "format" in data and data["format"] not in FORMATS:
        rep.warn(path, key_line(text, "format") or 1, f"format {json.dumps(data['format'])} must be single or site — key left out of the index")
        del data["format"]
    for key in data:
        if key not in REQUIRED and key not in OPTIONAL:
            rep.warn(path, key_line(text, key) or 1, f"`{key}` is not a topic.json field and is passed through unchanged")
    return None if problems else data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--template")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    repo = find_repo_root(args.root)
    if repo is None:
        return usage_error("no `topics/` folder found" + (f" in {args.root}" if args.root else " in the current directory or its parents"))
    template = Path(args.template).resolve() if args.template else DEFAULT_TEMPLATE
    rep = Report("tool", "build_index")
    topics_dir = repo / "topics"
    topics: list[dict] = []
    skipped: list[str] = []
    for folder in sorted(p for p in topics_dir.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        tj = folder / "topic.json"
        if not tj.exists():
            rep.warn(folder, 0, "no topic.json — not listed in the dictionary")
            skipped.append(folder.name)
            continue
        data = validate_topic(tj, folder.name, rep)
        if data is None:
            skipped.append(folder.name)
            continue
        topics.append(data)
        print(f"topic          {folder.name:<26} {data['status']:<9} updated {data['updated']}  {data['name']}")
    topics.sort(key=lambda t: (t["updated"], t["name"].lower()))
    topics.sort(key=lambda t: t["updated"], reverse=True)
    index = {"generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "topics": topics}
    payload = json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    written: list[str] = []
    html = repo / "index.html"
    if not html.exists() or args.force:
        if not template.exists():
            rep.warn(template, 0, "dictionary template missing — index.html not written")
        else:
            try:
                shutil.copyfile(template, html)
                print("copied         index.html")
            except OSError as e:
                rep.error(html, 0, f"cannot write: {e}")
    if html.exists():
        try:
            text = html.read_text(encoding="utf-8")
            block = DATA_BLOCK + payload.rstrip("\n") + "</script>"
            new_text, n = DATA_BLOCK_RE.subn(lambda m: block, text, count=1)
            if n == 0:  # migrate a page the template did not produce
                if LEGACY_INCLUDE in text:
                    new_text = text.replace(LEGACY_INCLUDE, block)
                elif re.search(r"<head\b[^>]*>", text, flags=re.I):
                    new_text = re.sub(r"(<head\b[^>]*>)", lambda m: m.group(1) + "\n" + block, text, count=1, flags=re.I)
                else:
                    new_text = block + "\n" + text
            html.write_text(new_text, encoding="utf-8", newline="\n")
            written.append("index.html")
            print("updated        index.html (topics-data block)")
        except OSError as e:
            rep.error(html, 0, f"cannot write: {e}")
    print(f"wrote          index.html ({len(topics)} topic(s); {len(skipped)} left out)")
    rep.print_problems()
    print(result_line(tool="build_index", status=rep.status, topics=len(topics), written=written, warnings=len(rep.warnings), skipped=skipped))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
