"""Shared helpers for the atlas-learn scripts. Standard library only, Python >= 3.11.

Conventions (references/contracts.md section 9):
  - problems print as `<file>:<line> <message>` (warnings carry a `warning:` prefix)
  - exactly one final `RESULT: key=value ...` line
  - exit code 0 = PASS, 1 = FAIL, 2 = usage error
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

# Windows consoles and captured pipes default to a legacy code page; the reports contain ≠ — ✓.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

MARKERS = ("[ ]", "[x]", "[SKIP]")
CLOSED = ("[x]", "[SKIP]")
STAGES = ("insights", "brief", "research", "compose")
STAGE_VOCAB = STAGES + ("done",)
FORMATS = ("single", "site")
WHAT_KEYS = ("Goal", "Why", "Use", "Start", "Focus", "Skip", "Done when", "How")
NOTE_KINDS = ("Changed", "Caveat", "Lesson")

PLACEHOLDER_RE = re.compile(r"\{[^{}\n]+\}")
HEADER_KEY_RE = re.compile(r"^\*\*([^*]+?)\*\*:\s*(.*)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")  # contracts §1: kebab-case, ≤ 24 characters
HEX_COLOUR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
THEME_KEYS = ("accent", "accentSoft")
TOPIC_STATUS = STAGE_VOCAB
TAG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NOTE_RE = re.compile(r"^- (Changed|Caveat|Lesson) (\d+) \(([a-z]+), (\d{4}-\d{2}-\d{2})\): (.+)$")
MODULE_ID_RE = re.compile(r"^[MS]\d{2}$")
BRIEF_HEADING_RE = re.compile(r"^### ([MS]\d{2}) [—–-] (.+?)\s*$")
DASHES = "—–-"


# ---------------------------------------------------------------- output ---
def display(path) -> str:
    """Path as printed in problem lines: relative to the CWD when inside it."""
    p = str(path)
    try:
        rel = os.path.relpath(p)
        out = rel if not rel.startswith("..") else p
    except ValueError:  # different drive on Windows
        out = p
    return out.replace("\\", "/")


def result_line(**pairs) -> str:
    parts = []
    for k, v in pairs.items():
        if isinstance(v, (list, tuple)):
            v = ",".join(str(x) for x in v) if v else "none"
        v = str(v)
        if v == "":
            v = "none"
        parts.append(f"{k}={v.replace(' ', '_')}")
    return "RESULT: " + " ".join(parts)


class Report:
    """Collects problems; prints them and the RESULT line; returns the exit code."""

    def __init__(self, kind: str, name: str):
        self.kind, self.name = kind, name  # kind: "gate" or "tool"
        self.errors: list[tuple[str, int, str]] = []
        self.warnings: list[tuple[str, int, str]] = []

    def error(self, file, line: int, msg: str) -> None:
        self.errors.append((str(file), int(line), msg))

    def warn(self, file, line: int, msg: str) -> None:
        self.warnings.append((str(file), int(line), msg))

    @property
    def status(self) -> str:
        return "FAIL" if self.errors else "PASS"

    def print_problems(self) -> None:
        for f, l, m in self.errors:
            print(f"{display(f)}:{l} {m}")
        for f, l, m in self.warnings:
            print(f"{display(f)}:{l} warning: {m}")

    def finish(self, extra: dict | None = None, quiet: bool = False) -> int:
        if not quiet:
            self.print_problems()
        pairs: dict = {self.kind: self.name, "status": self.status,
                       "errors": len(self.errors), "warnings": len(self.warnings)}
        if extra:
            pairs.update(extra)
        print(result_line(**pairs))
        return 1 if self.errors else 0


def usage_error(msg: str) -> int:
    print(msg, file=sys.stderr)
    print(result_line(status="USAGE", error=msg.split("\n")[0][:60]))
    return 2


# -------------------------------------------------------------- markdown ---
def read_lines(path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def sections(lines: list[str], level: int = 2) -> list[tuple[str, int, int]]:
    """Headings of exactly `level` hashes: (title, heading_index, end_index_exclusive).
    A section ends at the next heading of the same or a higher level."""
    open_re = re.compile(r"^#{%d} (?!#)(.*)$" % level)
    close_re = re.compile(r"^#{1,%d} (?!#)" % level)
    out: list[list] = []
    for i, line in enumerate(lines):
        m = open_re.match(line)
        if m:
            if out:
                out[-1][2] = i
            out.append([m.group(1).strip(), i, len(lines)])
        elif out and close_re.match(line):
            out[-1][2] = i
    return [tuple(s) for s in out]


def find_section(secs, title: str, exact: bool = True):
    t = title.lower()
    for s in secs:
        st = s[0].lower()
        if (exact and st == t) or (not exact and st.startswith(t)):
            return s
    return None


def section_body(lines: list[str], sec) -> list[str]:
    """Lines of a section without its heading line."""
    if sec is None:
        return []
    return lines[sec[1] + 1:sec[2]]


def split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}")


def find_table(lines: list[str], start: int, end: int):
    """First markdown table in lines[start:end].
    Returns (header_cells, header_index, [(row_index, cells), ...]) or None."""
    i = start
    while i < end - 1:
        if lines[i].lstrip().startswith("|") and SEP_RE.match(lines[i + 1] or ""):
            header = split_row(lines[i])
            rows = []
            j = i + 2
            while j < end and lines[j].lstrip().startswith("|"):
                rows.append((j, split_row(lines[j])))
                j += 1
            return header, i, rows
        i += 1
    return None


def col_index(header: list[str], *names: str) -> int:
    """Index of the first header cell that starts with one of `names` (case-insensitive), else -1."""
    low = [h.lower() for h in header]
    for n in names:
        n = n.lower()
        for i, h in enumerate(low):
            if h.startswith(n):
                return i
    return -1


def header_keys(lines: list[str], start: int, end: int) -> dict[str, tuple[str, int]]:
    """`**Key**: value` lines in lines[start:end] -> {key: (value, index)}."""
    out = {}
    for i in range(start, min(end, len(lines))):
        m = HEADER_KEY_RE.match(lines[i].strip())
        if m and m.group(1) not in out:
            out[m.group(1).strip()] = (m.group(2).strip(), i)
    return out


def strip_code(value: str) -> str:
    return value.strip().strip("`").strip()


def placeholders(lines: list[str]) -> list[tuple[int, str]]:
    out = []
    for i, line in enumerate(lines):
        for m in PLACEHOLDER_RE.finditer(line):
            out.append((i, m.group(0)))
    return out


# ------------------------------------------------------------------ plan ---
class Plan:
    """Lenient parse of topics/<slug>/PLAN.md; validation lives in check_plan.py.
    The topic folder is the plan's own folder: tmp/ and the site are resolved from it, never from the text."""

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.lines = read_lines(self.path)
        self.secs = sections(self.lines)
        self.title, self.title_idx = None, -1
        for i, line in enumerate(self.lines):
            if line.strip():
                m = re.match(r"^# Research plan: (.*)$", line.strip())
                if m:
                    self.title, self.title_idx = m.group(1).strip(), i
                break
        first_sec = self.secs[0][1] if self.secs else len(self.lines)
        self.header = header_keys(self.lines, 0, first_sec)
        # What I want
        self.what: dict[str, tuple[str, int]] = {}
        self.what_order: list[tuple[str, int]] = []
        self.details_idx = -1
        sec = find_section(self.secs, "What I want")
        self.what_sec = sec
        if sec:
            for i in range(sec[1] + 1, sec[2]):
                m = re.match(r"^- \*\*([^*]+?)\*\*:\s*(.*)$", self.lines[i].strip())
                if m:
                    key = m.group(1).strip()
                    self.what_order.append((key, i))
                    self.what.setdefault(key, (m.group(2).strip(), i))
                elif self.lines[i].strip().startswith("Details:"):
                    self.details_idx = i
        # Progress
        self.progress: list[tuple[int, str, str, str]] = []
        self.progress_header = None
        sec = find_section(self.secs, "Progress")
        self.progress_sec = sec
        if sec:
            t = find_table(self.lines, sec[1] + 1, sec[2])
            if t:
                self.progress_header = (t[0], t[1])
                for idx, cells in t[2]:
                    cells = (cells + ["", "", ""])[:3]
                    self.progress.append((idx, cells[0], cells[1], cells[2]))
        # Modules
        self.modules: list[tuple[int, str, str, str, str, str]] = []
        self.modules_header = None
        sec = find_section(self.secs, "Modules")
        self.modules_sec = sec
        if sec:
            t = find_table(self.lines, sec[1] + 1, sec[2])
            if t:
                self.modules_header = (t[0], t[1])
                for idx, cells in t[2]:
                    cells = (cells + ["", "", "", "", ""])[:5]
                    self.modules.append((idx, cells[0], cells[1], cells[2], cells[3], cells[4]))
        # Next
        self.next_lines: list[tuple[int, str]] = []
        sec = find_section(self.secs, "Next")
        self.next_sec = sec
        if sec:
            self.next_lines = [(i, self.lines[i].strip()) for i in range(sec[1] + 1, sec[2]) if self.lines[i].strip()]
        # Notes
        self.notes: list[tuple[int, str]] = []
        sec = find_section(self.secs, "Notes")
        self.notes_sec = sec
        if sec:
            self.notes = [(i, self.lines[i].rstrip()) for i in range(sec[1] + 1, sec[2]) if self.lines[i].strip()]

    # convenience -------------------------------------------------------
    def header_value(self, key: str) -> str | None:
        v = self.header.get(key)
        return strip_code(v[0]) if v else None

    @property
    def slug(self) -> str | None:
        return self.header_value("Slug")

    @property
    def format(self) -> str:
        """Output format from the optional `**Format**: single|site` header line; missing → site."""
        v = self.header_value("Format")
        return v.strip().lower() if v else "site"

    @property
    def topic_dir(self) -> Path:
        """The topic folder (= the site root): the plan's own folder."""
        return self.path.parent

    @property
    def folder_name(self) -> str:
        return self.path.parent.name

    @property
    def tmp_dir(self) -> Path:
        return self.path.parent / "tmp"

    @property
    def site_dir(self) -> Path:
        return self.path.parent

    def progress_marker(self, stage: str) -> str | None:
        for _, marker, st, _ in self.progress:
            if st == stage:
                return marker
        return None

    def stage_from_progress(self) -> str | None:
        """First Progress row that is `[ ]`; `done` when every row is closed; None when unparsable."""
        if not self.progress:
            return None
        for _, marker, st, _ in self.progress:
            if marker == "[ ]":
                return st
            if marker not in CLOSED:
                return None
        return "done"

    def what_text(self) -> list[str]:
        return section_body(self.lines, self.what_sec)


# --------------------------------------------------------------- hashing ---
def normalise(lines: list[str]) -> str:
    return "\n".join(" ".join(l.split()) for l in lines if l.strip())


def insight_hash(plan: Plan, insights_lines: list[str]) -> str:
    """SHA-256 (first 12 hex) over the plan's `## What I want` + INSIGHTS.md `## Refined insight`
    + `## How (derived policies)` section bodies, normalised, in that order."""
    isecs = sections(insights_lines)
    parts = [
        plan.what_text(),
        section_body(insights_lines, find_section(isecs, "Refined insight")),
        section_body(insights_lines, find_section(isecs, "How (derived policies)")),
    ]
    text = "\n".join(normalise(p) for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------- site registry ---
SITE_JS_HEADER = ("/* Site registry — GENERATED from assets/site.json by scaffold.py.\n"
                  "   Edit the JSON, then run: python <PLUGIN_ROOT>/scripts/scaffold.py <siteDir> --sync */\n")
GLOSSARY_JS_HEADER = ("/* Glossary data — GENERATED from assets/glossary.json by scaffold.py.\n"
                      "   Entry shape: { term, aka?, def, page, anchor? }. Edit the JSON, then run:\n"
                      "   python <PLUGIN_ROOT>/scripts/scaffold.py <siteDir> --sync */\n")


def site_js(obj) -> str:
    return SITE_JS_HEADER + "window.SITE = " + json.dumps(obj, indent=2, ensure_ascii=False) + ";\n"


def glossary_js(obj) -> str:
    return GLOSSARY_JS_HEADER + "window.QC_GLOSSARY = " + json.dumps(obj, indent=2, ensure_ascii=False) + ";\n"


def validate_theme(theme, file, rep, line: int = 1) -> None:
    """site.json `theme` (contracts §8): optional accent / accentSoft, and `dark` with the same keys; hex colours only."""
    if not isinstance(theme, dict):
        rep.error(file, line, "theme must be a JSON object with accent / accentSoft (and optionally dark: {accent, accentSoft})")
        return

    def check_block(block, label):
        for k, v in block.items():
            if k == "dark" and label == "theme":
                continue
            if k not in THEME_KEYS:
                rep.warn(file, line, f"{label}.{k} is not a theme key (accent, accentSoft) and is ignored")
            elif not isinstance(v, str) or not HEX_COLOUR_RE.match(v.strip()):
                rep.error(file, line, f"{label}.{k} must be a CSS hex colour like #0b5cad (got {json.dumps(v)})")

    check_block(theme, "theme")
    if "dark" in theme:
        if not isinstance(theme["dark"], dict):
            rep.error(file, line, "theme.dark must be a JSON object with accent / accentSoft")
        else:
            check_block(theme["dark"], "theme.dark")


def load_json(path):
    """(value, error_message)"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig")), None
    except FileNotFoundError:
        return None, f"{display(path)} missing"
    except json.JSONDecodeError as e:
        return None, f"{display(path)} invalid JSON: {e.msg} (line {e.lineno})"


# ------------------------------------------------- I4 derived policies: site.json a11y ---
# site.json `a11y` (contracts §8): the reading defaults derived from the Accessibility policy — the nav workstream's
# reading settings apply them when the reader has not chosen. Written by scaffold.py from the SITE_PLAN `**A11y**` line.
A11Y_VALUES: dict[str, tuple] = {"font": ("default", "dyslexic"), "scale": (1, 1.15, 1.3),
                                 "motion": ("normal", "reduced"), "contrast": ("normal", "high")}


def validate_a11y(a11y, file, rep, line: int = 1) -> None:
    """site.json `a11y`: an object whose keys are font / scale / motion / contrast with the values in A11Y_VALUES;
    unknown keys are warnings (ignored by the runtime), wrong values are errors. Like validate_theme."""
    if not isinstance(a11y, dict):
        rep.error(file, line, "a11y must be a JSON object with font / scale / motion / contrast")
        return
    for k, v in a11y.items():
        if k not in A11Y_VALUES:
            rep.warn(file, line, f"a11y.{k} is not an a11y key (font, scale, motion, contrast) and is ignored")
            continue
        allowed = A11Y_VALUES[k]
        ok = (isinstance(v, (int, float)) and not isinstance(v, bool) and any(abs(v - a) < 1e-9 for a in allowed)) if k == "scale" \
            else (isinstance(v, str) and v in allowed)
        if not ok:
            want = ", ".join(str(a) for a in allowed[:-1]) + f" or {allowed[-1]}"
            rep.error(file, line, f"a11y.{k} must be {want} (got {json.dumps(v)})")


# ---- E3 notation (scholar): the rows of table.notation / table.constants, shared by validate.py and build_site_data.py ----
import html as _html_e3  # noqa: E402
import re as _re_e3  # noqa: E402

TEX_SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ",
    "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "varrho": "ϱ",
    "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "ϕ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ",
    "Omega": "Ω", "infty": "∞", "partial": "∂", "nabla": "∇", "hbar": "ℏ", "ell": "ℓ", "times": "×", "cdot": "·", "pm": "±", "deg": "°",
    "circ": "°", "prime": "′", "to": "→", "rightarrow": "→", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "approx": "≈",
    "propto": "∝", "sqrt": "√", "sum": "Σ", "int": "∫", "oplus": "⊕", "emptyset": "∅",
}
_TEX_WRAP_RE = _re_e3.compile(r"\\(?:mathbf|mathrm|mathit|boldsymbol|text|textbf|textrm|operatorname|vec|hat|bar|tilde|dot|ddot|mathcal|mathbb)\s*\{([^{}]*)\}")
_TEX_CMD_RE = _re_e3.compile(r"\\([A-Za-z]+)")
_CLS_SYM_RE = _re_e3.compile(r'\bclass="(?:[^"]*\s)?sym(?:\s[^"]*)?"')


def tex_to_text(tex: str) -> str:
    """Plain-text form of a short TeX symbol: \\lambda -> λ, \\mathbf{v} -> v, R_e -> R_e, \\hat{x} -> x. Good enough to compare and
    sort symbols; the runtime still renders the TeX itself."""
    s = tex.strip()
    for _ in range(3):
        s = _TEX_WRAP_RE.sub(r"\1", s)
    s = _TEX_CMD_RE.sub(lambda m: TEX_SYMBOLS.get(m.group(1), m.group(1)), s)
    s = _re_e3.sub(r"\\[,;:!\s]", "", s)
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    return _re_e3.sub(r"\s+", "", s)


def notation_rows(text: str) -> list[dict]:
    """Every data row of the table.notation (Symbol | Meaning | Unit | Where defined) and table.constants (Constant | Symbol | Value |
    Unit | Source) blocks in a page text (comments and scripts blanked by the caller):
    [{kind, symbol, tex, meaning, unit, value, where, table_id, pos}] — pos indexes `text` (for line numbers), symbol is the plain text
    of the td.sym cell (TeX converted), tex its inline-maths source when the cell holds \\( … \\). Rows without a symbol or a meaning
    are skipped."""
    rows: list[dict] = []
    for tm in _re_e3.finditer(r'<table\b[^>]*\bclass="(?:[^"]*\s)?(notation|constants)(?:\s[^"]*)?"[^>]*>', text):
        kind = "constant" if tm.group(1) == "constants" else "symbol"
        idm = _re_e3.search(r'\sid="([^"]+)"', tm.group(0))
        end = text.find("</table>", tm.end())
        body = text[tm.end():end if end >= 0 else len(text)]
        for rm in _re_e3.finditer(r"<tr\b[^>]*>([\s\S]*?)</tr>", body):
            if "<th" in rm.group(1):
                continue
            cells = [(cm.group(1), cm.group(2)) for cm in _re_e3.finditer(r"<td\b([^>]*)>([\s\S]*?)</td>", rm.group(1))]
            if not cells:
                continue
            sym_i = next((i for i, (a, _) in enumerate(cells) if _CLS_SYM_RE.search(a)), None)
            if sym_i is None:
                sym_i = 1 if kind == "constant" and len(cells) > 1 else 0
            plain = [_re_e3.sub(r"\s+", " ", _html_e3.unescape(_re_e3.sub(r"<[^>]+>", " ", c))).strip() for _, c in cells]
            raw_sym = plain[sym_i] if sym_i < len(plain) else ""
            mm = _re_e3.search(r"\\\(([\s\S]*?)\\\)", raw_sym)
            tex = mm.group(1).strip() if mm else ""
            symbol = tex_to_text(tex) if tex else raw_sym.strip("$ ")
            others = [plain[i] for i in range(len(plain)) if i != sym_i]
            col = lambda i: others[i] if i < len(others) else ""  # noqa: E731
            if kind == "constant":
                row = {"meaning": col(0), "value": col(1), "unit": col(2), "where": col(3)}
            else:
                row = {"meaning": col(0), "unit": col(1), "where": col(2), "value": ""}
            if not symbol or not row["meaning"]:
                continue
            row.update(kind=kind, symbol=symbol, tex=tex, table_id=idm.group(1) if idm else None, pos=tm.end() + rm.start())
            rows.append(row)
    return rows
