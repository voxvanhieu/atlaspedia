---
name: compose
description: Stage 4 of the atlaspedia learning workflow — builds the full-width interactive documentation site (multi-page, offline-first static HTML with the fixed Lectern-style template) in topics/<slug>/ from the approved brief and the consolidated dossier, using parallel page-writer agents, the Python scaffold/validate scripts and a fresh-eyes site reviewer. Use when invoked as /atlaspedia:compose <slug>, or by /atlaspedia:go when the plan's stage is compose. Needs a plan whose research row is [x].
argument-hint: "<slug>"
disable-model-invocation: true
---

# atlaspedia:compose — stage 4, the site

You plan the pages, run the scripts, dispatch writers and the reviewer, and flip rows. You write no page. The site is an **interactive visualization of the dossier and nothing else** (`${CLAUDE_PLUGIN_ROOT}/references/evidence-policy.md`): every figure and demo cites its evidence, nothing is computed without a documented method, every gap is visible — `validate.py` enforces the mechanical half, the site reviewer traces the rest, and you never flip a page either of them failed. Contracts: `${CLAUDE_PLUGIN_ROOT}/references/contracts.md` (§6 build notes, §7 SITE_PLAN.md, §8 layout, page kinds and registry, §9 scripts, §10 agents, §11 dispatch, §13 topic.json). References: `references/authoring-rules.md` (the rules every writer reads), the component catalog `components/` (`INDEX.md` + one folder per module, loaded on demand by the writers — you only read `INDEX.md`'s module column to derive `Modules:` lines), the fixed template in `template/` (page-kind skeletons `_module.html`, `_synthesis.html`, `_reference.html`).

`PLUGIN_ROOT` = `${CLAUDE_PLUGIN_ROOT}` (contracts §12). `TOPIC_DIR` = `<repo root>/topics/<slug>/`. `PLAN` = `<TOPIC_DIR>/PLAN.md`. `TMP` = `<TOPIC_DIR>/tmp/`. `SITE` = `TOPIC_DIR` (the site lives at the topic root: `index.html`, `pages/`, `assets/`). `SCRIPTS` = `<PLUGIN_ROOT>/scripts`. `REFS` = `<PLUGIN_ROOT>/skills/compose/references`. `CATALOG` = `<PLUGIN_ROOT>/skills/compose/components`. Absolute paths in every dispatch; label every value with the agent's input name (contracts §11). Every dispatch ends with: `End with Friction lines and the RESULT line (contracts §10).`

**Retry rule:** one retry, narrowed to the failing pages with the validator's lines pasted verbatim; a second failure → the page stays `[ ]`, a `Changed n` note, and the stage ends with the failure in the report. Never write or patch a page yourself. **Never edit `assets/style.css` or `assets/app.js`** in a site; a missing component is added to the plugin (one catalog module + one template block, `check_components.py` green), then the assets are copied again.

## 0. Gate and resume

1. `python <SCRIPTS>/check_plan.py <PLAN> --before compose` must PASS; FAIL → show the lines, stop.
2. `python <SCRIPTS>/next_stage.py <PLAN>`. If `<TMP>/SITE_PLAN.md` exists, this is a resume: skip to step 3 and dispatch only pages whose Status is `[ ]`. If `SITE/pages/` already holds pages but no `SITE_PLAN.md` exists, ask: overwrite · resume from what is there · stop.
3. **Format.** `format=` in the `RESULT:` line of `next_stage.py`. `single` → follow **§S Single page** below instead of steps 1–7. `site` → continue here. A `SITE_PLAN.md` written for the other format (its `**Format**` header differs) is renamed to `SITE_PLAN.<old format>.md` and the plan is written fresh.

## 1. Plan the pages — `SITE_PLAN.md` (the registry comes first)

Read `<TMP>/dossier/00-overview.md` **§8 Build notes only** (Grep `^### Page |^\*\*(Groups|Levels|Priority module)\*\*`, then read the §8 block) and the brief's module headings. Write `<TMP>/SITE_PLAN.md` per contracts §7:

- **Header**: Title (from the brief), Subtitle `Interactive Research Report`, Prefix = slug, `Pages dir: pages/`, Levels from the build notes, Footnote = one sentence with the topic's safety/legal caveat, optional `Theme` line (accent colours for this topic), `**Status**: Draft`.
- **E6 version / F4 hours** — add `**Version**: 1.0` to the header (`scaffold.py` writes `site.json version`; every page footer and `changelog.html` show it; bump it at every stage close) and an optional `Hours` column to the Pages table (`25` or `20–30` per module, from the brief's learning design when it has §13 — the user-approved plan; otherwise leave the column out rather than invent study times: the planner then lists the modules without scheduling them; `scaffold.py` writes `pages[].hours`, the study planner's input).
- **I4 derived policies** — two optional header lines from the brief's appendix (the INSIGHTS.md `## How` rows; Grep `^\| (Licence|Accessibility) \|`): `**Licence**: <Licence row>` (omit the line when the row is `all rights reserved, personal use`), and `**A11y**: …` derived from the Accessibility row — `large text` → `scale 1.15`, `dyslexia` → `font dyslexic · scale 1.15`, `reduced motion` → `motion reduced`, `screen reader` → `contrast high`, `none` → no line. `scaffold.py` writes them into `site.json` as `licence` and `a11y` (contracts §7, §8); the footer stamp shows the licence and the reading settings start from the `a11y` defaults.
- **I2 learning design** — when the brief has `## 13. Learning design`: copy each module's hours into the Pages table's `Hours` column (the study planner reads it), and paste the module's outcomes and assessment-plan rows into its writer block under `- Outcomes:` so the writer tags objectives with `data-bloom` and checkpoints with `data-objective`. Without §13 the column stays empty and nothing is pasted.
- **`## Pages`** — one row per `### Page` block, in reading order: `| File | Num | Title | Group | Level | Desc | Spec | Writer | Size | Status |`. File = basename. One page per module (`mNN-slug.html`, numbered as the brief numbers them); synthesis pages only when the brief has the part (project → `s01-project.html`, stacks, matrices, research questions, roadmap); `bibliography.html` and `glossary.html` always; `index.html` first with `Num` `00`. Groups = 4–7 sidebar sections in reading order (Overview · Foundations · Core · Advanced · Synthesis · Reference); `Level` 1–4 for modules only. `Desc` = one sentence (search and curriculum cards use it). `Spec` = `00-overview.md#page-<file>`. Sizes: module 70–160 KB, priority module up to 250 KB, synthesis 80–160 KB, overview 30–50 KB, bibliography 60–120 KB.
- **Writers**: `W0` = `index.html` (written last, opus); `W1…` 1–3 pages each, the priority module alone (opus), related pages together, ≤ 6 writers; the writer of `bibliography.html`/`glossary.html` also owns `assets/glossary.json` — say so in its block.
- **`## Writers`** — one `### Wn — <pages>` block per writer: the `### Page` spec blocks copied verbatim from the build notes, the interactive requirement derived from the `How` line and bounded by the evidence (`demos rich` → "a calculator or simulation for every documented calculation (`C` id) with ≥ 2 inputs, a playground per documented algorithm family"; `moderate` → "filterable tables, quizzes, zoomable diagrams from the documented relationships; calculators only for the page's key `C` ids"; `minimal` → "diagrams and quizzes only"; at every level: "build each visual the block's evidence supports, none it does not — a line that says `none — <why>` gets cited text instead"), the cross-links to make, the size targets, and **one `Kind:` / `Modules:` line per page** (below).
- **`## Conventions`** — frames, units, symbols, naming and the running-example numbers, copied from `00-overview.md` §1 and the brief §2.3. Every writer gets this section.

**Kind and modules per page** — derived, never asked. One line per page inside its writer block: `- <file> — Kind: module|synthesis|reference|index · Modules: <ids>`. The ids are the folder names of `CATALOG` (`core math diagrams media demos assessment overview trust`):

| Page | Always | Add when (from the page's `### Page` block and the `How` line) |
|---|---|---|
| module (`mNN-*`) | `core assessment trust` | `math` when `- Topics`/`- Numbers` name equations, models or filters; `diagrams` when `- Diagrams` is not `none`/`n/a`; `media` when `- Media` is not `n/a`; `demos` when `- Demos` names a `C` id (never for `How` alone: a demo needs a documented calculation) |
| synthesis (`sNN-*`) | `core trust` | `diagrams`, `media`, `demos`, `math` by the same lines; `assessment` when the brief's part asks for checkpoints |
| reference (`bibliography.html`) | `core trust` | — |
| index (`index.html`, W0) | `core overview diagrams` | — (no trust footer on the overview) |
| single (`index.html`, Format single) | `core single trust` | the union over all parts of the module rule: `math`, `diagrams`, `media`, `demos`; `assessment` always (checkpoints) |
| any module or synthesis page (and every single-page part) | + `sitewide` | always — `span.claim[data-src]` is how writers cite facts (E5); the indexes page, backlinks, evidence tables and the manifest are built from the pages by `build_site_data.py` (A1 A3 G4 H6), so the writer adds nothing else |
| any page — learn features (B3 B5 B6 B7) | — | `assessment` also when the brief has a learning design (outcomes with Bloom verbs → `data-bloom` on objectives and checkpoints, the outcome matrix on the page and `data-outcomes="site"` on the overview or roadmap), when the `Use` is teaching or an instructor audience is named (instructor notes, rubrics, handout printing), when a `- Demos` line asks the reader to guess first (a predict block tied to a demo preset), or when a deliverable is a lab, practical or assignment (the lab sheet) — tell the writer which of the four in its dispatch |
| any page with `demos` (compute D1 D2 D3 D4 D6) | — | no extra module: the `demos` module already carries URL state, presets, the demo menu (copy, export, link, sensitivity, reset), unit-aware inputs and tolerance helpers; when the page's `- Demos` line mentions units, imperial/metric, SI prefixes, tolerances, worst case, uncertainty or presets, name `demo-units.html` / `demo-uncertainty.html` and the preset names in the writer's page spec |
| any page (C5–C7 plots) | — | `plots` when the page's `- Demos` or `- Diagrams` line mentions plots, curves, log axes, error bars, heatmaps, function plots, vector fields, phase portraits or sweeps and names the `C` id or source # the plotted values come from |
| any page (C8 circuit) | — | `circuit` when the page's `- Diagrams`, `- Topics` or `- Demos` line names a schematic, circuit, symbol, pinout, pin map, connector, register or register map, or the topic is electronics hardware (name `pinout.html` / `regmap.html` / `schematic.html` / `symbols.html` in the writer's page spec) |
| any page (C2–C4 protocol) | — | `protocol` when the page covers a protocol, bus, register layout or message exchange — the page's `- Diagrams` line names a timing or waveform diagram, a register map, bit field, packet or frame format, a sequence diagram, a handshake or a state machine (snippets `timing.html`, `bitfield.html`, `sequence.html`, `fsm.html`) |
| any page (scholar: B2, E2, E3, E1) | — | `math` also when the page states theorems, lemmas or definitions, numbers equations the text refers back to, or introduces symbols or constants (snippets `theorem.html`, `eq-numbered.html`, `notation.html`); every `ol.refs` entry carries the E1 citation fields of `core/refs.html` — no extra module |
| any page (study: B4 flashcards, F1 notes) | — | `study` on a page that carries a flashcards deck: `glossary.html` (the template already has one — the glossary owner only keeps `glossary.json` at 3 terms or more, optionally with `tags` / `group` per entry) and a module whose `- Topics` line or the brief's `Use` names memorising vocabulary, exam preparation or self-study (one deck of that module's key terms after the section that defines them); `index.html` also gets `study` when the `Use` is self-study or a course (the `notes.html` callout in the how-to-use section). Notes, highlights, bookmarks and resume need no module: the runtime adds them to every page (opt out per page with `main[data-no-notes]`, per site with `site.json` `"notes": false`) |
| any page (D5 runners) | — | `runner` when the page's `- Demos` or `- Topics` line names an algorithm the reader should edit and run (a filter step, a bit trick, a numeric method) → `runner-js.html`; standard-library Python → `runner-python.html` on `site` format only (single-format pages keep JavaScript runners: the bundle is offline-first) |

- **C9–C11 visual (diagrams, media)** — `diagrams` also when `- Diagrams` names an exploded view, layers, an overlay or a stack the reader should switch on and off (`diagram-layers.html`); `media` also when `- Media` or `- Diagrams` names labelled parts of a photo (`photo-hotspots.html`) or a before/after, side-by-side or two-projections comparison (`compare.html`). Downloading a diagram as SVG/PNG and the photo lightbox need no module: every `figure.diagram` and `figure.photo` gets them.

Exercises come with `assessment` (2–4 per module unless the brief's success test says otherwise); `trust` is the footer every page except `index.html` and `glossary.html` ends with. A writer that needs a module you did not list loads it anyway and reports it in a Friction line — record it as a `Lesson` and fix the rule here.

- **nav (A2 section metadata · A4 breadcrumb and shortcuts · F2 reading settings · F3 bilingual glossary · H3 glossary links) — part of `core`, no module of its own**: every page gets the breadcrumb, the keyboard shortcuts, the reading settings and the automatic glossary links from the runtime; module pages also get a reading-time strip under every `h2`. Tell a writer (in its block) to set `data-prereq` / `data-related` on an `h2` when the page's `- Cross-links` line names sections the reader needs first or alongside (`core/section-meta.html`). When the `How` line's language policy names a second language, put `**Second language**: <name>` in the `SITE_PLAN.md` header (→ `site.json secondLanguage`) and tell the glossary owner to fill `term_local` / `def_local`; `site.json a11y` defaults come from the policies (pipeline I4).
- **pages (C12, E6, F4)** — `overview` also when a page carries the study planner (`div.planner[data-planner]`: the overview or a roadmap synthesis page) or a page-scoped concept map (`svg[data-concept-map="page"]` in a module's keywords section); `concepts.html` and `changelog.html` are template reference pages `scaffold.py` copies and registers — no writer, no Modules line.
- **H4 executed examples** (part of `core`, no extra module) — a page whose `- Demos` or `- Topics` lines name code, scripts, commands or an implementation gets executed examples: add `- Executed examples: yes` to its writer block so the writer runs the snippets (authoring rules §7) and the reviewer re-runs one; pages with no runnable code get nothing.
- **I1 reader emphasis** — the plan's `**Readers**` header (the INSIGHTS.md / brief appendix `Readers` row; missing → `creative student`) adds modules on top of the rules above, never removes one; the first persona leads, the second adds what fits. Persona → modules (`protocol`, `circuit`, `study`, `runner` are wave-4 catalog modules; list one only when its folder exists in `CATALOG`):

  | Readers | Add to module and synthesis pages |
  |---|---|
  | creative student | `assessment` steps and quizzes on every module page, `diagrams` step-through, `study` (flashcards) |
  | engineer | `demos` with units and uncertainty (`demo-units.html`, `demo-uncertainty.html`), `trust`, `assessment` checklists |
  | software developer | `protocol` (timing, packets, sequences), `runner` on pages with runnable code |
  | circuit designer | `circuit` (schematics, pinouts, registers), `plots` (Bode, log axes, waveforms) |
  | researcher | `math` numbering, theorems and notation, `sitewide` claims (`span.claim[data-src]` on every quantitative claim) |
  | instructor | `assessment` instructor notes, Bloom tags and the lab sheet; offer the print/offline export (handouts, offline bundle) in the stage report |
  | fundamental sciences | `math` derivations and notation, `plots` function plots |
  | accessibility/mobile | no extra module — the `a11y` defaults (I4) and the reading settings carry it |

## 2. Scaffold

```
python <SCRIPTS>/scaffold.py <SITE> --plan <TMP>/SITE_PLAN.md
```
PASS → `SITE` holds `assets/` (fixed assets, `site.json` + generated `site.js`, `glossary.json` + generated `glossary.js`), `index.html`, and `pages/` with `glossary.html` and the skeletons `_skeleton.html`, `_module.html`, `_synthesis.html`, `_reference.html` (one per page kind; writers copy the one their `Kind:` names); `PLAN.md`, `topic.json` and `tmp/` are untouched. FAIL → fix `SITE_PLAN.md` by the lines it names, run again. Registry edits later go into `assets/site.json` followed by `python <SCRIPTS>/scaffold.py <SITE> --sync`; file names never change after writers start.

## 3. Writer wave

All writers of the wave in **one message**. The priority module's writer and `W0` run with `model: opus`; the rest default (sonnet).

```
Agent  subagent_type: "atlaspedia:page-writer"   (model: opus for the priority module)
SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
SITE: <SITE>
FILES: m04-….html, m05-….html   (basenames; create or modify ONLY these under SITE/pages/ — plus assets/glossary.json when GLOSSARY=yes)
PAGE_KIND: m04-….html: module; m05-….html: module   (copy SITE/pages/_<kind>.html for each)
MODULES: core, math, diagrams, demos, assessment, trust   (the union of the pages' Modules lines; read CATALOG/INDEX.md and these modules' README.md only; open a snippet when you use it)
CATALOG: <CATALOG>
MODE: pages   GLOSSARY: no
BRIEF: <TMP>/BRIEF.md   (§2, §8–§10 and your modules' sections)
DOSSIER: <TMP>/dossier/m04-….md, <TMP>/dossier/m05-….md, <TMP>/dossier/00-overview.md   (§1 numbers, §2 ownership, §5 media, §6 conflicts, your "### Page" blocks in §8)
SITE_PLAN: <TMP>/SITE_PLAN.md   (your "### Wn" block and "## Conventions")
DONE_WHEN: <the plan's "Done when" line>
POLICY: <PLUGIN_ROOT>/references/evidence-policy.md   (read it before the authoring rules)
No web access: cite only what the dossier verified; build each visual the page block's evidence supports, citing it on the figure (data-cite); compute only documented calculations (C ids); a needed fact that is not there is a gap (<!-- GAP: … --> plus a visible gap badge in the page, listed in your reply — never invented, estimated or derived).
Before finishing run: python <SCRIPTS>/validate.py <SITE> --pages <your files> and fix every line for your files.
```

Per report (`pages= sizes= gaps= validate=`):
1. `files=` empty → nothing flips; retry rule.
2. **Run the gate yourself:** `python <SCRIPTS>/validate.py <SITE> --pages <its files>`. PASS → set the page rows to `[x]` in `SITE_PLAN.md` and, for module rows, the `Page` column of the plan. FAIL → retry rule (`FIX:` + the failing lines).
3. `gaps>0` → read the writer's `## Gaps` list; one narrowed researcher, then the writer again:

   ```
   Agent  subagent_type: "atlaspedia:module-researcher"
   SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
   MODULES: M04   FILES: M04 → <TMP>/dossier/m04-….md   (edit ONLY this existing file: add rows to "## Sources" / "## Key facts and numbers")
   NARROW: <the gap lines, verbatim>
   BRIEF: <TMP>/BRIEF.md (§2)   PROTOCOL: <REFS of research>/research-protocol.md   HOW: <the How line>   POLICY: <PLUGIN_ROOT>/references/evidence-policy.md
   Only what a retrieved source states, with its locator; what you cannot establish goes under Could not verify with its evidence label. Budget: ≤ 8 searches.
   ```
   Gate the dossier file (`check_dossier.py --depth …`), then re-dispatch the owning writer with `FIX: fill <page>#<section> from the new rows #n–#m of <dossier file>; change nothing else; run validate.py --pages again`. One gap round per page; what is still missing stays on the page with its visible gap badge and becomes a `Caveat` — a gap is never closed by letting the writer fill it.

## 4. Overview page, last

When every other page is `[x]`: dispatch `W0` with the writer template, `model: opus`, `FILES: index.html` (at the site root, not under `pages/`), `PAGE_KIND: index.html: index`, `MODULES: core, overview, diagrams`, `MODE: index`, `DONE_WHEN` and: "Read every page's `#objectives` list, hero `.lede` and `#deliverable` heading (Grep, not whole pages), `00-overview.md` §1–§2 and §6–§7, and the brief §1 and §10. Write `SITE/index.html`: executive summary, scope/objectives, methodology (verification level, what was not verified, how gaps are marked), key findings the pages state (each linking `pages/<file>#id` to the section that cites it — none the pages do not make), a thematic clickable system map SVG (modules around the subject, each linking to its page; a path between modules only where a page documents that relationship, linked to the citing section; `data-sitemap` fallback allowed), the curriculum map widget, the deliverables index table, how to use, a closing safety/limitations callout, and `#sources` for anything the overview cites itself." Gate with `validate.py --pages index.html`; flip.

## 5. Validate the whole site

First `python <SCRIPTS>/build_site_data.py <SITE>` (rebuilds `assets/data.js` from the finished pages: indexes, backlinks, evidence, notation, changelog — the reference pages render from it), then `python <SCRIPTS>/validate.py <SITE>` — fix routing: every page-level line goes back to its owning writer (retry rule); site-level lines (registry ↔ files, JSON ↔ JS sync, glossary entries, layout) are yours: fix `site.json`/`glossary.json`, run `scaffold.py --sync` (which also rebuilds `data.js`), validate again. Nothing proceeds to review on a FAIL.

- **H1 consistency lint** — the `warning:` lint lines (`dfn … is not in glossary.json`, `term … is written as …`, `unit written as …`, `notation symbol …`; `lint=n` in the RESULT line) never fail the gate and are not routed now: the reviewer runs the validator itself and turns them into findings (site-reviewer 7c). Only a `dfn` that is plainly a missing glossary entry is yours: add it to `glossary.json` and `--sync`.

## 6. Fresh-eyes review

```
Agent  subagent_type: "atlaspedia:site-reviewer"
SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
SITE: <SITE>   (index.html and pages/*.html)
BRIEF: <TMP>/BRIEF.md   (§1, §3 topic lists, §5, §6, §8, §10)
OVERVIEW: <TMP>/dossier/00-overview.md   (§1, §2, §6, §7, §8)
DOSSIER_DIR: <TMP>/dossier/   (for the evidence trace: only the rows the sampled cites point to)
POLICY: <PLUGIN_ROOT>/references/evidence-policy.md
SITE_PLAN: <TMP>/SITE_PLAN.md   ("## Pages" for owners, "## Writers" for each page's Kind/Modules line, "## Conventions")
CATALOG: <CATALOG>   (INDEX.md, then only the README.md of the modules the pages list)
DONE_WHEN: <the plan's "Done when" line>
OUT: <TMP>/SITE_REVIEW.md   (write ONLY this file: "Verdict: READY|FIX", must-fix table with owner writers, "## Caveats for the final report")
```

`verdict=FIX` → one fix wave: each `per_page=` entry goes to the page's owning writer with `FIX:` + its must-fix rows ("apply these for your page; change nothing else; validate your pages"); then step 5 again and one more review. At most two review rounds; remaining must-fix rows become `Caveat` notes, verbatim.

## 7. Close the stage

1. `SITE_PLAN.md`: every page `[x]`, `**Status**: Built`. Plan: every module row's `Page` `[x]` (or `[SKIP]` with a `Changed` note), `compose` row `[x]`, `**Stage**: done`, `**Updated**`, `## Next`: ``Open `topics/<slug>/index.html` in a browser. To add modules, run `/atlaspedia:go <slug>` after editing the brief.``
2. `## Notes`: `Caveat n` for every row of `SITE_REVIEW.md` `## Caveats` and every unresolved gap (one sentence each, pointing at `tmp/SITE_REVIEW.md`); `Lesson n` per `Friction:` line; `Changed n` per skipped page.
3. `topic.json`: `status: "done"`, `updated`, `format: "site"`, `pages` = `index.html` + the number of `pages/*.html` files (not the `_*.html` skeletons); run `python <SCRIPTS>/build_index.py <repo root>`.
4. **Run the gate:** `python <SCRIPTS>/check_plan.py <PLAN>` must PASS.
- **E6 changelog** — append one entry to `<SITE>/assets/changelog.json` (create it as `[]` when absent): `{ "date": "<date>", "version": "<the plan's Version>", "note": "first build" | "fix round n", "pages": [<the files written or fixed>] }`, then `python <SCRIPTS>/scaffold.py <SITE> --sync` so `assets/data.js`, the footer stamps and `changelog.html` follow.

## 8. Report to the user

Plainly: pages and sizes (from the validator's table); the evidence state (claims, open gaps, how many statements and figures the reviewer traced — never "fully verified" beyond that); how to open (`topics/<slug>/index.html`, or the root `index.html` dictionary); what works offline (everything except fonts, KaTeX, highlight.js and click-to-load media); **every caveat** from `SITE_REVIEW.md` and the plan's notes, verbatim where useful; "validated with scripts, not opened in a browser" when true; the next options (open it, more modules, a new topic).

- **G3 Markdown/LMS export** — one of the next options, run only when the user asks: `python <SCRIPTS>/export_markdown.py <SITE> --out <TOPIC_DIR>/tmp/export [--no-solutions] [--lms]` writes one `.md` per page (diagrams as SVG files under `figures/`), `index.md` with the reading order and, with `--lms`, a thin `imsmanifest.xml` (IMS Common Cartridge-style, not SCORM; copy it next to `index.html` and zip the site folder for the LMS). `--no-solutions` makes a handout without solutions or quiz answers. Report its RESULT line.
- **G1 offline / G2 PDF** — when the plan's `Use` mentions teaching, a class, printing, handouts or offline use, offer both (run only on a yes): `python <SCRIPTS>/scaffold.py <SITE> --offline` vendors KaTeX, highlight.js and the fonts into `assets/vendor/` (about 2.5 MB, network once; then the site works with no network) and must PASS, followed by `validate.py <SITE>`; for a single page re-run `bundle.py` afterwards (the bundle then inlines them, about 1 MB). `python <SCRIPTS>/print_pdf.py <SITE> --out <TOPIC_DIR>/tmp/pdf [--handout]` prints every page to PDF in reading order (handout = no solutions) with a local Chrome/Edge; exit 2 = no browser found, say so. Guide: `references/export.md`. Report the RESULT lines.

## S. Single page (`**Format**: single`)

Same template, same agents, same gates; one page, written by one writer, bundled into one file. `SITE` = `<TMP>/site/` (the editable source, git-ignored). `OUT` = `<TOPIC_DIR>/index.html` (the self-contained page, the only built file in the topic folder).

**S1. Plan.** Read the build notes as in step 1. Write `<TMP>/SITE_PLAN.md` with the step-1 header plus `**Format**: single`, `**Budget**: 250 KB`, `**Pages dir**: flat`, Subtitle `Single-page guide`; `## Pages` = one row `| index.html | 00 | <Title> | Guide | | <one sentence> | 00-overview.md#page-index.html | W1 | ≤ 250 KB | [ ] |`; `## Writers` = one block `### W1 — index.html` holding: the line `- index.html — Kind: single · Modules: core single trust <+ math diagrams media demos assessment by the derivation table, unioned over every part>`; every module and synthesis `### Page` block verbatim, in brief order, each headed "Part <id>" (they become `section.part` blocks); the `index.html`, `bibliography.html` and `glossary.html` blocks as sources for the hero, `#summary`, `#map`, `#references` and `#glossary`; the size per part (250 KB minus 40 KB for the frame, divided by the parts); the interactive requirement from the `How` line, capped at one demo per part; and `## Conventions` as in step 1.

**S2. Scaffold.** `python <SCRIPTS>/scaffold.py <SITE> --plan <TMP>/SITE_PLAN.md` → `SITE` holds `assets/` (with `site.json` `mode: single`), and `_single.html`.

**S3. Writer.** One dispatch, `model: opus`, the step-3 template with these values: `SITE: <SITE>` · `FILES: index.html` · `PAGE_KIND: index.html: single` (copy `SITE/_single.html`) · `MODULES: <the W1 Modules line>` · `MODE: single` · `GLOSSARY: yes` (40–120 terms from `00-overview.md` §3, `page: "index.html"`, anchors on the page; then `scaffold.py <SITE> --sync`) · `DOSSIER: every module and synthesis file + 00-overview.md` · `BRIEF`, `SITE_PLAN`, `DONE_WHEN`, `CATALOG` as in step 3. Gate: `python <SCRIPTS>/validate.py <SITE>` must PASS; flip on PASS; retry rule otherwise. The gap loop is step 3's, with one researcher per module that has gaps.

**S4. Too long?** The validator warns `single page is n KB, over the b KB budget` when the written page passes the budget. On that warning, `AskUserQuestion`, header `Format`, naming the size:
- `Full multi-page site (Recommended)` — "No new research: the dossier is reused, one page per module." → set the plan's `**Format**: site`, `Changed n` note, and run steps 1–8 from the start. `SITE_PLAN.md` becomes `SITE_PLAN.single.md`, and `tmp/site/` is left as it is.
- `Condense to the budget` — "One page; long sections are shortened and secondary detail moves into collapsibles." → re-dispatch the writer in fix mode with `FIX: condense to <b> KB: shorten the largest parts first, move derivations into one details block per part, keep every topic named at least in one sentence, keep the trust footer and the references`, then validate again. Still over budget → keep it with a `Caveat`.
- `Keep the long page` — `Caveat n` with the size.

**S5. Review.** Step 6 with `SITE: <SITE> (index.html only)`. `verdict=FIX` → one fix round to W1, then validate and review once more.

**S6. Bundle.** `python <SCRIPTS>/build_site_data.py <SITE>` once more, then `python <SCRIPTS>/bundle.py <SITE> --out <OUT>` must PASS. The result is the deliverable: one file with the stylesheet and scripts inlined; fonts, KaTeX and highlight.js still load from their CDNs when online.

**S7. Close.** As in step 7, with these differences. `SITE_PLAN.md` `**Status**: Built`; every module row's `Page` `[x]`, since each module is a part of the page. `topic.json` gets `format: "single"`, `pages: 1`, `entry: "index.html"`. The report names `topics/<slug>/index.html` as the one file to open or share, and says the editable source is `tmp/site/` (re-run `bundle.py` after any edit).

## Rules

- Never read a page in full; read `RESULT:` lines, validator output and the review's tables.
- Never flip a page on a report that names no files; never flip on your own reading — on `validate.py`.
- `AskUserQuestion` only when a page fails twice and the user must choose (drop it or stop), when `SITE/pages/` already contains pages without a `SITE_PLAN.md` (overwrite / resume / stop), or when a single page is over its budget (S4).
- The writers decide markup; you decide only what each page must contain (the spec blocks), which catalog modules it loads (the `Kind:`/`Modules:` lines) and the file names.
- Never read a catalog README or snippet yourself; `INDEX.md`'s module column is all you need.
