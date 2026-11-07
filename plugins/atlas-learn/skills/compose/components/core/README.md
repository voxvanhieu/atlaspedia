# Core — frame, hero, text, callouts, layout, tabs, tables, code, references

Every page uses this module: the frame the runtime injects, one hero, text-level semantics, callouts, layout blocks (cards, stat cards, findings, objectives, steps, timeline, collapsibles), tabs, tables, code blocks and the references list. Snippets: `hero.html`, `text-semantics.html`, `callout.html`, `layout.html`, `section-meta.html`, `tabs.html`, `table.html`, `code.html`, `refs.html`.

Legend — **Use when** tells you when the component earns its place; **Avoid** tells you the common misuse.

## Page frame (never hand-written)

`app.js` injects: reading-progress bar, top bar (brand, search, reading settings, theme toggle), sidebar (groups from the registry `assets/site.json`, served to the browser as the generated `assets/site.js`, progress), breadcrumb (`nav.breadcrumb`, first child of `<main>`: Home › group › page title from the registry; on a single page: title › the section in view), on-page TOC from `h2`/`h3` (right rail ≥ 1500 px wide, scroll-spy, expand/collapse-all when the page has > 2 `<details>`), prev/next pager, "Mark module as completed" (pages with `level`), footnote. Pages only provide `<main>` with sections. Give every `h2` and important `h3` a stable `id`; app.js generates missing ids from the text, but generated ids are fragile cross-link targets.

**A4 keyboard shortcuts** (every page, never while typing in a field, never with Ctrl/Alt/⌘): `/` search · `j` / `k` next / previous `h2` section (scrolls to it and focuses the heading) · `n` / `p` next / previous page from the pager (single page: next / previous part) · `t` back to top · `?` opens the shortcut list `div.kbd-help[role=dialog]` · `←` / `→` step through a focused step diagram · `Esc` closes dialogs, tooltips and the search results. Writers do nothing; a page script may call `QC.shortcutsHelp()`.

**F2 reading settings** (every page): the top-bar "Aa" button `button.settings-toggle` opens `div.reading-settings[role=dialog]` with text size (S / M / L / XL → `<html data-font-scale>` and `--font-scale` 0.9 / 1 / 1.15 / 1.3, scaling body text and the rem-based headings), line width (narrow / normal / wide → `data-measure`, the `p, li` measure 62 / 80 / 100 ch), font (default / dyslexia-friendly → `data-font="dyslexic"`: Atkinson Hyperlegible, loaded from Google Fonts only when chosen, taller line height), motion (normal / reduced → `data-motion`; the OS `prefers-reduced-motion` setting counts until the reader chooses), contrast (normal / high → `data-contrast="high"`: black or white ink, stronger lines, no translucent top bar, works with dark mode) and a Reset. Choices persist per browser under `nav:settings`; `site.json` `a11y: { "font": "default"|"dyslexic", "scale": 1|1.15|1.3, "motion": "normal"|"reduced", "contrast": "normal"|"high" }` sets the site's defaults for readers who have not chosen. Pages never set these attributes; a page script may call `QC.readingSettings.get()`, `.set(key, value)`, `.reset()`. Everything works offline and in the single-page bundle (only the optional font is fetched).

## Hero — `hero.html`

Shape: `<header class="module-hero"><div class="eyebrow">…</div><h1>…</h1><p class="lede">…</p><dl class="meta-strip">…</dl></header>`. **Use when** every page (exactly once, first child of `<main>`). `.diff[data-level=1..5]` is the difficulty meter. The overview's variant (`home-hero` + live counts) is `overview/hero-home.html`. The runtime inserts the breadcrumb above the hero (A4) — never write one; the hero's own prerequisite links stay in its `meta-strip`, the per-section ones go on the `h2` (`section-meta.html`).

## Text-level semantics — `text-semantics.html`

| Snippet | Use when | Avoid |
|---|---|---|
| `<dfn>term</dfn>` | first definition of a glossary term in prose | styling emphasis |
| `<abbr title="Digital Object Identifier">DOI</abbr>` | first use of an acronym per page | every occurrence |
| `<kbd>/</kbd>` | keys the reader presses | code identifiers |
| `<code>` | identifiers, parameters, file names | prose emphasis |
| `<a class="xref" href="m03-research.html#verification">M03 · Verification</a>` | pointing to another page/section ("→ chip") | external links |
| `<a class="cite" href="#ref-liu2023">[2]</a>` | inline citation to an `ol.refs` entry on the same page; the target entry highlights | citing without a matching `id="ref-…"` |
| `<span class="badge established|experimental|emerging|discontinued|verified|safety|neutral">…</span>` | maturity and verification status of a claim, product or reference | decoration |
| `<span class="badge documented|not-specified|insufficient|unavailable|conflict|user-input">…</span>` (evidence policy §3) | evidence status: `not-specified` (a source covers the subject but not this value), `insufficient` (too little to state it), `unavailable` (no source covers it — required beside every `<!-- GAP: … -->` marker, the validator counts them), `conflict` (two sources disagree; show both values and cites), `user-input` (a value from the user, never shown as sourced), `documented` (optional: a cite already says it) | filling a gap with a guess; a gap comment without a visible badge |
| `<span class="badge illustrative">Model output</span>` | the head of a `.demo` or a computed figure only: its readouts are computed by the cited documented model from the reader's inputs, not measured | a stated number in prose, a table or a callout — the validator fails it there; cite the number or mark it missing |
| `<div class="keywords"><span>Mercator</span>…</div>` | search terms for further reading, at the top of each major topic | long phrases |
| `<p class="lede">` | the page's standfirst only | body paragraphs |
| `<h5>` | small-caps labels inside cards/blocks | section headings (use h2/h3/h4) |
| `<abbr class="gloss">` — **made by the runtime, never hand-written** (H3) | nothing to write: in every `h2` section the first occurrence of each glossary term (`term` or `aka`, whole words, any case) becomes a tooltip with the definition, the `term_local` and a link to the glossary (Enter follows it); headings, links, code, `<dfn>`, figures, quizzes, exercises, demos, table headers and badges are skipped; at most 400 terms and 200 links per page | linking glossary terms by hand — write `<dfn>` once where the term is defined and let the runtime do the rest |
| `<span class="no-gloss">…</span>` / `<main data-no-glossary-links>` | opt out of automatic glossary links for one element / the whole page (a page that mentions every term in passing, a quotation) | opting out by default |

## Callouts — `callout.html`

Shape: `<div class="callout note"><span class="callout-title">Title</span><p>…</p></div>`.

| Variant | Use when |
|---|---|
| `note` | definitions, conventions, how-to-read notes |
| `tip` | practical advice, rules of thumb, shortcuts |
| `warn` | limitations, assumptions, "verify before relying" |
| `safety` | physical, legal or financial risk — keep in every hands-on section |
| `case` | the running example / reference instance of a concept |
| `research` | open questions, experimental results, conflicting findings |
| `mistakes` | the "Common engineering mistakes" section and inline pitfalls |

**Avoid** more than two callouts in a row; stacked callouts read as noise. The snippet shows every variant — keep only the one you need.

## Layout — `layout.html`, `tabs.html`

| Snippet | Use when |
|---|---|
| `.grid-2 / .grid-3 / .grid-4` containing `.card` | parallel items of equal weight: options, roles, subsystems, findings |
| `.card.link-card` (an `<a>`) | cards that are links |
| `.card.stat` with `.stat-value` + `.stat-label` | 2–6 headline numbers |
| `.card.finding` with `<span class="f-num">01</span>` | key findings on the overview |
| `ol.objectives` | learning objectives (numbered 01…) — once per module |
| `ol.steps` | procedures, workflows, staged roadmaps (numbered circles) |
| `ul.timeline` with `<span class="tl-when">1907</span>` | history, release timelines, staged plans with dates |
| `<details><summary>Title <span class="badge …">…</span><span class="summary-hint">hint</span></summary><div class="details-body">…</div></details>` | long derivations, secondary detail, per-item deep dives — keeps a 100 KB page scannable |
| `details.deep` | optional research-level deep dive (summary gets a "Deep dive" tag) |
| `.tabs` (`tabs.html`) | the same thing in several languages/tools/variants |
| `<hr>` | rarely — sections already separate with `h2` rules |
| `h2[data-prereq][data-related][data-time][data-reviewed]` (`section-meta.html`) | section metadata: the runtime (A2) inserts `div.section-meta` after the heading — reading time, prerequisite and related chips, "reviewed <date>" (below) |

Tabs: `.tabs` > `.tab-list` buttons with `data-tab` keys + one `.tab-panel` per key; the first button carries `class="active"`. **Use when** 2–5 alternatives that the reader chooses between (languages, simulators, vendor variants). **Avoid** hiding required content in a non-default tab. Plots inside a hidden panel redraw when the panel is shown.

## Section metadata — `section-meta.html`

Shape: `<h2 id="distortion" data-prereq="m01-globe.html#scale, glossary.html#terms" data-related="#mistakes" data-time="8 min" data-reviewed="2026-11-07">…</h2>` — every attribute optional, on the `h2` only. `data-prereq` / `data-related`: comma-separated targets written like any cross-link from this page (`page.html#id`, `#id`, `../index.html#id` from a module page); the runtime shows them as `a.xref` chips labelled "Needs" / "Related" with the target's registry title (`01 · Title › heading` when the anchor is on this page) and builds the href, so chips work from `pages/`, from the overview and in the single-page bundle (`#id` targets). `data-time`: free text (`8 min`) that replaces the estimate. `data-reviewed`: `YYYY-MM-DD`, for a section checked on a date other than the page's trust footer. Reading time = words ÷ 220, shown from 120 words on; module pages (registry `level`) get it under every `h2`, other pages only where an attribute is set. Runtime: A2 at `enhance`; `QC.sectionMeta(main)` re-runs it. **Use when** a section depends on another one, two sections complement each other, the estimate misleads (code- or table-heavy sections) or one section was reviewed separately. **Avoid** `data-prereq` on `h3` (ignored, warning) and chips on every section — one or two per page say more than ten.

Validator: `section meta: prerequisite <target> not found` · `section meta: related <target> not found` · `section meta: data-reviewed "<value>" is not a date` (errors) · `section meta: data-prereq on <h3> is ignored (h2 only)` · `section meta: data-prereq is empty` (warnings; also for `data-related`).

## Tables — `table.html`

Shape: `.table-wrap` > `.table-tools` (title, `input.table-filter`, `select.table-filter-select`, `.tt-count`, all with `data-target="<table id>"`) + `table.sortable` + `.table-note`. Select options auto-populate from the column (split on `, ; /`; `data-values` overrides). `data-sort` on a cell overrides the sort key; `th.num`/`td.num` right-align numbers. Plain `<table>` (optionally `.compact`) for small static tables; app.js wraps every table for horizontal scrolling. **Use when** ≥ 5 rows that readers compare or look up (components, algorithms, simulators, deliverables index, FMEA, bibliography). **Avoid** tables as layout.

## Code — `code.html`

Shape: `<pre><code class="language-python">…</code></pre>`. Languages: `c cpp python rust bash yaml json verilog matlab javascript`. A language label and Copy button are added; highlight.js loads from cdnjs when online (plain text offline). Keep examples realistic, commented, and labelled "example" when they are not run. Escape `<` as `&lt;` and `&` as `&amp;` inside code. **Use when** the reader will implement it. **Avoid** screenshots of code and pseudo-code when real code is as short.

**H4 executed examples — `code-executed.html`.** Shape: `<pre data-executed="YYYY-MM-DD" data-env="Python 3.13"><code class="language-python">…</code></pre>` immediately followed by `<pre class="output"><samp>…</samp></pre>` holding the real output. Runtime: the code block gets a `span.badge.executed` reading "Executed 2026-11-07 · Python 3.13" and the output block is labelled for assistive technology; nothing is computed in the browser. Rules (authoring rules §7): set `data-executed` only after you ran the snippet yourself — `python -I` or `node` in a scratch folder, never from the topic folder — and pasted its output unchanged; one executed example per implementation section is enough; `data-env` names the interpreter or tool with its version; a snippet you did not run stays a plain code block labelled "example". The site reviewer re-runs one executed example per page and a mismatch is a must-fix. **Use when** the reader will copy the code and expect that output. **Avoid** faking an output, trimming it silently (say "output shortened" in the output block instead), or executing anything with side effects. Validator: `executed example without an output block` (error) · `data-executed "…" is not a date` (error) · `executed example without data-env` (warning) · `output block without an executed example` (warning).

## References — `refs.html`

Shape: `<ol class="refs"><li id="ref-key" data-type="article" data-authors="Liu, N. F.; Lin, K." data-year="2024" data-title="…" data-venue="…" data-doi="10.…" data-url="https://…" data-key="liu2024lost"><span class="ref-authors">…</span> (Year). <a href="…">Title</a>. <span class="ref-venue">…</span> <span class="badge …">…</span><span class="why">…</span></li></ol>`. Entry = authors (surname initials), year, linked title, venue, maturity badge (`established` "Foundational", `emerging`, `experimental`, `neutral` "Tutorial"…), one-sentence "why read it" (the dossier's "Why worth studying" column). **Every entry whose dossier row is Verified `✓` also carries `<span class="badge verified">Verified</span>`** next to its maturity badge — the trust footer counts these against all entries. Every module ends with `#reading` (6–15 entries); the bibliography page aggregates all references into an interactive table. Accuracy rules are in `authoring-rules.md` §3 — they are not optional: every entry comes from the dossier's Sources tables.

**E1 citation export and hover cards (scholar).** The `data-*` fields carry the dossier row as data: `data-type` ∈ `article | book | web | dataset | standard | thesis | report | software`, `data-authors` (`Surname, I.; Surname, I.` — semicolons between authors), `data-year` (4 digits), `data-title`, `data-venue`, `data-doi` (`10.NNNN/…`, no URL prefix) and/or `data-url`, optional `data-key` (BibTeX key; default `<first surname><year>`). **Runtime** (`enhance`): a `div.refs-tools` toolbar above every `ol.refs` — **BibTeX** and **RIS** download the whole list (`<page>-refs.bib` / `.ris`, through `QC.download` when present), **Copy** puts the BibTeX on the clipboard (Shift-click: RIS; fallback "Select & copy"); hovering or focusing an `a.cite[href="#ref-…"]` shows a `div.cite-card` with authors, year, title (linked), venue and the entry's badges (Escape, blur or moving away closes it). Entries without `data-*` still export: the runtime falls back to `.ref-authors`, the year in parentheses, the link text as title, `.ref-venue` and the first http link (a `doi.org` link yields the DOI). `QC.refsBibtex(root)`, `QC.refsRis(root)`, `QC.refData(li)`. **Rules:** fill the fields from the dossier row only — never complete a DOI or a year from memory; keep the visible entry as above (the fields duplicate it as data, they do not replace it).

## Reference pages and skeletons shipped with the template

- `glossary.html` — renders `assets/glossary.js`, which is **generated** from `assets/glossary.json` by `python <PLUGIN_ROOT>/scripts/scaffold.py <siteDir> --sync` (A–Z bar, filter, module select, sort). The glossary owner edits `glossary.json` (entries `{term, aka?, def, page, anchor?}`, one per row of the dossier's glossary seed — each `def` from its sourced definition, up to 400 terms, no minimum) and runs the sync; never hand-write glossary rows or edit `glossary.js`. **F3 bilingual glossary** — an entry may add `term_local` and `def_local` (strings: the term and its definition in the site's second language) and `site.json` `secondLanguage: "Vietnamese"` names that language: the glossary page then shows a filterable "Term (Vietnamese)" column, the inline widget appends `span.gl-local` to the term, the site search matches `term_local`, and the glossary tooltips (H3) show it. Validator (site): `glossary term "<term>": term_local must be a string` (likewise `def_local`), `site.json secondLanguage must be a non-empty string`; warnings `secondLanguage "<name>" is set but no glossary entry has term_local` and `<n> glossary entries have term_local but site.json has no secondLanguage`.
- `index.html` — overview skeleton with every required section (components in the `overview` module).
- `_module.html`, `_synthesis.html`, `_reference.html` — page-kind skeletons with the required sections stubbed in order; `_skeleton.html` is the bare frame. Copy the kind your dispatch names. Files starting with `_` are ignored by the validator and must not be registered.
- `styleguide.html` — this catalog rendered; generated by `scripts/check_components.py --styleguide`; copied into a site with `scaffold.py --with-styleguide` when wanted.

## Validator messages this module can trigger

`duplicate ids: …` · `broken links: …` (a cross-link, cite or xref whose page or anchor does not exist) · `table tool targets missing id …` · `module page lacks #objectives|#mistakes|#reading|#checkpoints|#deliverable` · `module page has no ol.refs`.

**nav (A2, F3)**: `section meta: prerequisite <target> not found` · `section meta: related <target> not found` · `section meta: data-reviewed "<value>" is not a date` · warnings `section meta: data-prereq on <h3> is ignored (h2 only)`, `section meta: data-prereq is empty` · site-level `glossary term "<term>": term_local must be a string` (and `def_local`) · `site.json secondLanguage must be a non-empty string` · warnings `secondLanguage "<name>" is set but no glossary entry has term_local`, `<n> glossary entries have term_local but site.json has no secondLanguage`. A4, F2 and H3 are runtime-only and have no validator messages.

**H4 executed examples**: `executed example without an output block` · `data-executed "…" is not a date` · warnings `executed example without data-env` · `output block without an executed example`. **H1 consistency lint** (site-level warnings, never failures): `dfn "X" (m02) is not in glossary.json` · `term "X" is written as "…" (m01) and "…" (m03)` · `unit written as "msec" (m03) and "ms" (m01)` · `notation symbol "λ" (m01) is not in assets/notation.json`.

**E1 (scholar):** `ref <id|#n>: data-year "x" is not a 4-digit year` · `ref <id|#n>: data-doi "x" is not a DOI (10.NNNN/…)` · `ref <id|#n>: data-type "x" is not one of article|book|web|dataset|standard|thesis|report|software`.
