# Single — the one-page guide

Use when the topic's plan says `**Format**: single`: the whole topic is one page, `index.html`, built from `template/_single.html` in the same stylesheet and runtime, then bundled into one self-contained file. The page frame, the condensed parts, the inline glossary and the aggregated references. Snippets: `single-summary.html`, `single-part.html`, `glossary-inline.html`.

## The page frame

Order (the `_single.html` skeleton carries it): `header.module-hero.home-hero` (eyebrow `Single-page guide · <topic>`, meta strip: reading time, level, parts, deliverable) · `#summary` · optional `#map` (one `figure.diagram` whose boxes link to the parts) · one `section.part` per brief module or synthesis part, in the brief's order · `#checkpoints` (4–8 `.quiz` across the parts) · optional `#exercises` (2–4) · `#glossary` · `#references` · `section.trust` last. `site.json` has `"mode": "single"` and lists exactly one page; app.js then turns the sidebar into this page's contents (one entry per `h2`, the current section's `h3` nested under it), builds no right-rail TOC and no pager, and points search hits at `#id` on the page.

## Summary — `single-summary.html`

`<section><h2 id="summary">In one page</h2>` with `ol.objectives` (3–6 capabilities, from the plan's "Done when") and a `.grid-3` of `.card.finding` (3–6 key takeaways, each ending with an `a.xref` to its part). **Use when** always, right after the hero. **Avoid** a takeaway that no part supports.

## Parts — `single-part.html`

`<section class="part" data-part="M01">` with `<h2 id="m01-short-slug">01 · Title</h2>`; `data-part` is the brief's id (`M01`…, `S01`…). A module condenses into a part:

- **Keep**: the core concepts (one `h3` each), one key equation set (`.math5`, see `math/README.md`), one diagram, one worked example on the running example (`.callout.case`), the pitfalls (an inline `.callout.mistakes`), and a closing `p.part-more` line citing the part's best sources with `a.cite`.
- **Drop**: long derivations (at most one `<details>` per part), product catalogues and long comparison tables (keep the 3–5 rows that decide), more than one demo per part, per-part reading lists, per-part quizzes (they go to `#checkpoints`).
- **Size**: the page budget is `budgetKb` in `site.json` (250 KB of HTML by default); each part gets about budget ÷ parts. A topic that does not fit is a gap in the plan, not a reason to exceed the budget silently: give it an overview paragraph, keywords and a reference.

## Glossary — `glossary-inline.html`

`<section><h2 id="glossary">Glossary</h2><div class="glossary-inline" data-glossary></div></section>`. The runtime renders `window.QC_GLOSSARY` (generated from `assets/glossary.json` by `scaffold.py <site> --sync`) as a filterable, A–Z sorted list; each term gets the id `gl-<slug of the term>`, which search hits link to. Entries are `{term, aka?, def, page: "index.html", anchor?}`; `anchor` adds a "→ section" link to the part that explains the term. 40–120 terms. **Avoid** hand-writing the list; edit the JSON and sync. The widget also works on any site-mode page.

## References

One `ol.refs` in `#references` holds every source of the page (8–25 entries, see `core/refs.html`): authors, year, linked title, venue, status badge, "why read it", and `badge verified` on the dossier's `✓` rows. Parts cite them with `<a class="cite" href="#ref-…">[n]</a>`; there is no per-part reading list.

## Validator messages this module can trigger

`single page lacks #summary` (or `#checkpoints`, `#glossary`, `#references`) · `single page has no ol.refs` · `single page has no data-glossary widget` · `single page has no section.part` · `part section without a valid data-part` · `part <id> has no h2 id` · `single mode: site.json must list exactly one page (the home)` · `single mode: <file> is not allowed (one page only)` · the trust-footer messages (the footer is required on the single page) · warning `single page is <n> KB, over the <b> KB budget`.
