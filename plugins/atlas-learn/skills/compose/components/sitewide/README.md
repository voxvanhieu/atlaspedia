# Sitewide — indexes, backlinks, claim → evidence trace, site manifest, media manifest

Use on every module and synthesis page: wrap each cited number or fact in `span.claim[data-src]` (snippet `claim.html`) so the trust footer can list the page's claims with their sources, and let the build script do the rest — `python <PLUGIN_ROOT>/scripts/build_site_data.py <site>` (also run by `scaffold.py --sync`) reads every page once and writes `assets/data.js` (keys `indexes`, `backlinks`, `evidence`, `manifest`), `assets/manifest.json` (the manifest with the plain text of every section, for search, RAG or a hosted tutor) and `assets/media.json` (every photo and embed with its credit and licence). The Indexes reference page (`template/indexes.html`, copied and registered as `IX` by `scaffold.py`) renders the `[data-indexes]` widget (snippet `indexes-widget.html`); backlinks and the evidence table need no markup at all. Snippets: `claim.html`, `indexes-widget.html`.

Legend — **Use when** tells you when the component earns its place; **Avoid** tells you the common misuse.

## Claims — `claim.html` (E5 claim → evidence trace)

Shape: `<span class="claim" data-src="#ref-key">the sentence that states the fact <a class="cite" href="#ref-key">[n]</a></span>`. `data-src` is the id of the `ol.refs` entry the fact rests on (`#ref-key` on the same page, or `other-page.html#ref-key` for an entry on another page). A cite link inside the span belongs to that claim; a bare `a.cite` outside any span counts as a claim of its own (its text is the sentence before the cite). **Use when** a sentence carries a number, a date, a product fact or a result that comes from a dossier source — which, by `authoring-rules.md` §3, is every one. **Avoid** citing anything the dossier does not list (never invent a `data-src`), nesting claims, and spans that wrap whole paragraphs — one claim is one sentence.

Runtime (`sitewide-evidence`, phase `post`): the trust footer gains `details.trust-evidence` (before the issue link) — summary "Claims and sources (n claims · m sources)", table claim → source → Verified. It is built from the page's own DOM (so it works without `assets/data.js`): the source cell links to the entry and shows `Authors (year)`; the badge is **Verified** when the entry carries `badge verified`, **Unverified** when it does not, **Missing** when the id does not exist on the page, "—" when the source lives on another page and `DATA.evidence` has no record of it. With `DATA.evidence` present the cell adds "cited on k pages". Each claim gets an id (`ev-claim-n`, or its own) so the "↑" link scrolls back to it; `span.claim` is drawn with a dotted accent underline and shows its source as a tooltip.

## Evidence on figures and elements — `data-cite` (evidence policy §7)

Shape: `data-cite="#ref-key"` (comma-separated for several; `other-page.html#ref-key` for an entry on another page) on a `figure`, a `.demo`, or any element inside them or in a table or timeline (`g`, `rect`, `path`, `tr`, `li`). Runtime (`evidence-cite`, phase `shell`): a figure or demo gets a `p.fig-sources` "Sources: [n] [m]" line of `a.cite` links appended to its caption or note — so the E1 hover cards and the E5 evidence table include them; every other cited element gets `.cited`, a tooltip "Source: [n] Authors (year)" (an SVG `<title>` inside SVG), `tabindex=0`, and opens its first source on click or Enter. Validator: `data-cite <x> does not resolve` · `empty data-cite` · `figure <id> cites no source` · `demo <id> cites no source for its model` (block `evidence` of `validate.py`). **Use when** a visual element states a fact: the diagram's boxes and edges, a comparison row, a timeline event, a plotted series. **Avoid** citing a source that does not state that element.

## Indexes widget — `indexes-widget.html` (A1 auto-generated indexes)

Shape: `<div class="indexes" data-indexes></div>`; `data-indexes="figures,tables"` limits the tabs. Runtime (`sitewide-indexes`, phase `enhance`): tabs Figures · Tables · Equations · Code · Concepts with counts, a filter box, one list per tab; every entry links to its page and section (`href()` plus the anchor; `#anchor` in single mode). Concepts are grouped A–Z (glossary terms plus every `<dfn>` on the pages). A "Manifest ⤓" button downloads `DATA.manifest` as JSON (`QC.downloadManifest()`, through `QC.download` when another feature provides it). Without data the widget says so instead of rendering nothing. The same figures and tables join the site search as kinds **Figure** and **Table** (`sitewide-search`, phase `shell`). **Use when** `indexes.html` (the template page carries it) or a single page that wants its own index. **Avoid** copying it onto module pages — one index per site.

What is indexed: `figure.diagram|photo|embed|compare|fnplot|field|sweep` (number parsed from the caption's leading "Figure 2.1 —", caption ≤ 160 chars), every `<table>` (title from the wrapping `.table-wrap .tt-title`, else `<caption>`, else the header row; row count), `div.eq[id]` (label `data-label` or "(n)" in page order, matching E2) and `.math5` blocks (by their section), `pre > code` listings (language, first line), `<dfn>` terms and glossary entries.

## Backlinks (A3, runtime only)

`build_site_data.py` records every internal link (`a[href]` to `page.html`, `page.html#id` or `#id`; cites and anchor links excluded; same-page links only in single mode) under its target. Runtime (`sitewide-backlinks`, phase `post`): a `div.backlinks` "Linked from: <chips>" is appended to every `h2` section of the current page that other pages link to (links to an element inside a section count for that section), and one for page-level links before the trust footer; chips are `a.xref` with the source page's number and title, the linking section's id, and the link text as tooltip; at most 12 chips plus "+n more". `main[data-backlinks="off"]` opts a page out. Nothing is rendered when the data is missing.

## Site manifest (G4)

`assets/manifest.json` — `{ generated, title, subtitle, storagePrefix, version?, licence?, glossary: n, pages: [...] }`, one entry per page: `{ file, path, num, title, group, level, desc, words, readingMin, headings: [{level, id, text}] (h2–h4), objectives: [text], bloom: {remember, understand, apply, analyze, evaluate, create} (counts of data-bloom), counts: {figures, tables, equations, code, demos, quizzes, exercises, refs, verified, gaps, claims}, terms: [dfn texts], reviewed (the trust footer's date), sections: [{id, heading, text}] }` where `sections` holds the plain text (≤ 4000 chars) between consecutive `h2` headings, the first entry (`id: null`) being the hero. `DATA.manifest` is the same object without `sections`, so pages stay light; the learn module's site-wide outcome matrix reads `DATA.manifest.pages[].bloom`. `QC.manifest()` returns it, `QC.downloadManifest()` saves it.

## Media manifest (H6)

`assets/media.json` — `[{ page, id, kind: photo|embed|compare|hotspots, src, alt, title, caption, credit, creditUrl, licence }]` for every `figure.photo` (`hotspots` when it carries `data-hotspots`), `figure.compare` and `figure.embed`; `licence` is parsed from the `.credit` text after the source link (`CC BY-SA 4.0`, `CC0`, `Public domain`, `© …`, `All rights reserved`, …) and is `null` when none is written. The validator warns about photos, compare panes and direct video/model files without one; platform embeds (youtube, vimeo, sketchfab, pdf, iframe) are listed but never warned (the host's terms govern them). See the "H6 media manifest" paragraph in `media/README.md`.

## `DATA` keys written by `build_site_data.py`

- `DATA.indexes = { figures: [{page, id, num, caption, kind, section}], tables: [{page, id, title, rows, section}], equations: [{page, id, label, kind: eq|math5, tex, section}], code: [{page, id, lang, firstLine, section}], concepts: [{term, page, anchor, source: glossary|dfn}] }` — `page` is the file name, `section` the id of the nearest `h2`.
- `DATA.backlinks = { "page.html#id": [{page, id, text}], "page.html": [...] }` — `page` is the linking page, `id` the section the link sits in (`null` in the hero), `text` the link text.
- `DATA.evidence = { pages: { "page.html": { claims: [{text, src, section, verified, ref}], refs: { "ref-key" | "other.html#ref-key": {cited, verified, label} } } }, refs: { "page.html#ref-key": {cited, pages: [...], verified, label} }, claims: n, sources: n }`.
- `DATA.manifest` — the site manifest above without `sections`.

Every key is optional: a site built before the builder ran (or the empty stub `scaffold.py --plan` writes) renders the pages without indexes, backlinks or cross-page labels.

## Validator messages this module can trigger

`claim cites missing source #ref-x` (a `span.claim` whose `data-src` does not resolve to an id) · `claim without data-src` · warnings: `media without a licence: <page> <id>` · `assets/data.js is older than <page> — run build_site_data.py`. `validate.py` adds `claims=n` to its RESULT line.
