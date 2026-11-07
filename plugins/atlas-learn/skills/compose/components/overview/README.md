# Overview — the index.html widgets, the study planner, the concept map and the changelog

Use on `index.html` (writer W0): the home hero with live counts, the level-filtered curriculum map and the clickable site map — everything renders from the registry (`assets/site.js`), so the registry must be complete before the overview is written. Any page may add the study planner (`planner.html`), a page-scoped concept map (`concept-map.html`) and the changelog widget (`changelog.html`); they render from `assets/data.js`, which `build_site_data.py` (run by `scaffold.py --sync`) builds from the pages, the glossary and `assets/changelog.json`. The whole-site concept map and the full changelog are the template pages `concepts.html` and `changelog.html`, which `scaffold.py` copies and registers under Reference — no writer touches them. Snippets: `hero-home.html`, `widgets.html`, `planner.html`, `concept-map.html`, `changelog.html`.

## Hero — `hero-home.html`

The module hero with `home-hero` added and `<div class="hero-stats" data-stats></div>` at the end (auto-rendered counts: modules, synthesis parts, levels, completed in this browser). **Use when** the overview, exactly once.

## Declarative widgets — `widgets.html`

| Element | Renders |
|---|---|
| `<div class="hero-stats" data-stats></div>` | module count, synthesis count, levels, completed-in-this-browser |
| `<div class="map-filters" id="map-filters"></div>` + `<div class="curriculum" data-curriculum="map-filters"></div>` | level filter chips + one card per page (title, group, level, `desc`, done state) |
| `<svg data-sitemap>` inside `figure.diagram` | clickable group map from the registry |

Prefer a hand-drawn thematic SVG for the system map (the subject in the middle, modules around it, clickable blocks wrapped in `<a href="pages/…">`; a coloured data/control/power path only where a page documents that relationship, linked to the section that cites it — evidence policy §6); the auto-generated map is the fallback. The rest of the overview — executive summary, scope, methodology, key findings (`core/layout.html` finding cards), deliverables index (`core/table.html`), how to use — is ordinary `core` content; `template/index.html` has every required section in order.

## Study planner — `planner.html` (F4)

**Use when** the overview or a roadmap synthesis page wants a personal study schedule, once per site. **Shape**: a `<p>` of introduction and an empty `<div class="planner" data-planner></div>`.

**Data**: `DATA.planner = { pages: [{ file, title, num, hours }] }`, built by `build_site_data.py` from the registry: every module (page with a `level`) and every page with `hours`. The hours come from the site plan's optional `Hours` column (`25` or `20–30` → 25, written by `scaffold.py` into `site.json pages[].hours`), else from the module hero's `Study time` (`≈ 20–30 h` → 25), else `null` (the module is listed but not scheduled). Without `data.js` the widget falls back to the registry's modules.

**Runtime** (`f4-planner`, phase `enhance`): inputs *hours per week* (default 6), *start date* (default today) and *rest days* (weekday checkboxes, none by default), a Reset button; a schedule table — `#`, module (linked), hours, week number, from, to, status (`✓ done` from the module's mark-complete button, `in progress`, `behind`, `planned`, `no estimate`); a summary line (modules, total hours, weeks, finishing date); a progress bar (completed hours, with the hours *planned by today* for comparison); *Add to calendar (.ics)* downloads one all-day event per module (`QC.download` when the site has it, else a Blob link). The schedule is a day-by-day walk: each study day offers `hours per week ÷ study days` and the modules consume them in registry order. Settings persist under `pages:planner` in this browser; everything works when storage is blocked. `QC.renderPlanner(div)` and `QC.studySchedule(pages, perWeek, startDate, restDays)` are exposed for page scripts.

**Rules**: one planner per site is enough; do not hand-write hours into the page — put them in the site plan (`Hours`) or the hero (`Study time`). Print hides the controls and the download button.

## Concept map — `concept-map.html` (C12)

**Use when** a page wants the map of its own glossary terms and their neighbours: a module's keywords section, the overview. The whole-site map is `concepts.html`. **Shape**: `figure.diagram` > `svg[data-concept-map][viewBox="0 0 960 600"]` (with an accessible `<title>`) + `figcaption` + an empty `div.concept-info`. `data-concept-map="page"` keeps the terms whose glossary entry points at this page plus their direct neighbours; a bare `data-concept-map` shows every term.

**Data**: `DATA.concepts = { nodes: [{ id, term, page, anchor, group }], edges: [{ a, b, kind }] }`. Nodes are the glossary entries (ids `gl-<slug>`, the inline glossary widget's rule; `group` = the registry group of the entry's page). Edges: `related` from an entry's `"related": ["Term", …]` list (names of other terms or their akas; an unknown name is a warning), `mentions` when another term's name (≥ 4 letters, plural allowed) occurs in the definition, at most 8 per term; each pair once, a curated link wins over a mention.

**Runtime** (`c12-concept-map`, phase `enhance`, after the diagram tools): a force-directed layout (repulsion, springs, gravity, 150 iterations, fixed seed, ≤ 400 nodes) computed once per page load and drawn inside the svg's own viewBox, so zoom, pan and fullscreen come from the diagram tools unchanged. Nodes are coloured by group (`g1…g6` cycle the chart series colours; a legend is added after the caption), sized by degree; `related` lines are solid, `mentions` dashed; terms of the current page are bold. Click a node (or focus it and press Enter) to highlight its neighbours and show the definition, aka, group, neighbour chips and links (*where it is explained*, *glossary*) in `.concept-info`; Esc or a click on the background clears. Maps over 80 nodes label only the selected node and its neighbours. No data (or no term on this page) shows one line of text in the figure. `QC.conceptMap(svg, data, scope)` renders a map from your own `{ nodes, edges }`.

**Rules**: keep `viewBox="0 0 960 600"` (the layout fills it); never hard-code colours; keep the `concept-info` div empty.

## Changelog — `changelog.html` (E6)

**Use when** a "What changed" section on the overview or a roadmap page; the full list is the template page `changelog.html`. **Shape**: a `<p>` of introduction and an empty `<div class="changelog" data-changelog></div>`.

**Data**: `assets/changelog.json` = `[{ "date": "YYYY-MM-DD", "version": "1.0", "note": "…", "pages": ["m01-….html"] }]`; the compose skill appends an entry at every stage close (`first build`, `fix round n`); `build_site_data.py` turns it into `DATA.changelog = { version, entries }` (newest first; `version` = `site.json version`, written by `scaffold.py` from the site plan's `**Version**:` header, else the newest entry's).

**Runtime** (`e6-changelog`, phase `post`): the widget lists entries newest first — date, version badge, note, the pages touched as links (the current page's entry is outlined). On every page with a module footer a `p.site-stamp` is appended after the footnote: *Version 1.0 · 2026-11-07 · Text: CC BY-SA 4.0 · Changelog* (the date is the newest entry's, else the page's `data-reviewed`; the licence is `site.json licence`; the link appears when `changelog.html` is registered). A trust footer gets a fifth pill, *last change YYYY-MM-DD*, when an entry's `pages` names the page (see `trust/README.md`). Any element with `data-version` receives the version text. `QC.renderChangelog(div)` is exposed.

**Rules**: never write entries into a page — edit `assets/changelog.json` and run `scaffold.py --sync`; keep `version` a string (`"1.0"`, not `1.0`); name pages by their registry file names.

## Validator messages this module can trigger

None page-level beyond the core checks; the registry checks (`registry lists … but the file does not exist`, `duplicate page num`) come from `assets/site.json`. Site-level (all from the `pages` block of `validate.py`): `glossary term "X": related "Y" is not a glossary term` and `glossary term "X": related must be a list of term names` (warnings) · `changelog.json must be a JSON array` · `changelog entry #n must be an object` · `changelog entry #n: date "x" is not a date` · `changelog entry #n: version must be a string` · `changelog entry #n: pages must be a list of file names` (errors) · `changelog entry #n: unknown page x.html` (warning) · `site.json version must be a string` · `<file>: hours must be a number > 0` (errors). `scaffold.py --plan` fails on `Hours \`x\` must be a number or a range like \`20–30\``.
