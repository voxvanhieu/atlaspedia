# Trust — the provenance footer

Use on every page except `index.html` and `glossary.html`, as the **last** section inside `<main>`: it shows the reader how much of the page is verified, when it was reviewed, which simplifications its demos rest on and which gaps are still open. Snippet: `trust-footer.html`.

## Shape

`<section class="trust" data-reviewed="YYYY-MM-DD">` > `<h2 id="trust">Trust &amp; provenance</h2>` + `<div class="trust-stats" aria-live="polite"></div>` (filled by the runtime) + `details.trust-assumptions` (one `li` per assumption the page's demos and numbers rest on) + `details.trust-gaps` (one `li` per entry of your `## Gaps` list as `page#section: what is missing`; omit the whole `details` when there are none).

## What the runtime computes

For `section.trust`, app.js counts the page's `ol.refs > li` entries and those carrying `badge verified`, the `.demo` blocks, and the open gaps (every `<!-- GAP: … -->` comment under `<main>`, or the `li` entries of `.trust-gaps`, whichever is larger — they describe the same gaps), and renders four `.trust-stat` pills into `.trust-stats`: *n / m sources verified* (`good` when all, `warn` otherwise), *reviewed YYYY-MM-DD*, *n interactive demos · documented models*, *n open gaps* (`good` at zero, `bad` otherwise). The `.trust-gaps` summary becomes "Open gaps (n)". When `assets/site.json` has an `issueUrl`, a "Report a problem with this page" link is appended.

## Rules

- `data-reviewed` is the date you finished the page (ISO). The main agent may bump it after a fix round.
- Mark references from the dossier's Verified `✓` rows with `badge verified` (see `core/refs.html`) — the footer's first number is only honest when you do.
- List every assumption of every demo on the page (copy from the `.demo-note`s) and every entry of your Gaps report. Never remove a `<!-- GAP: … -->` marker to lower the count; the reviewer greps for them.
- Every gap in the list also has its `<!-- GAP: … -->` marker and a visible gap badge (`badge unavailable|not-specified|insufficient`) at the spot (evidence policy §8); the validator fails a page with more markers than badges.
- Nothing follows the trust section inside `<main>`.

**Use when** every page except the overview and the glossary. **Avoid** placing it anywhere but last, and hand-writing the stats line (the runtime overwrites it).

## Validator messages this module can trigger

`page has no trust footer (components/trust/trust-footer.html)` · `trust footer data-reviewed is not a date` · `trust footer must be the last section`.

**E5 evidence** — the runtime appends `details.trust-evidence` to every trust footer (before the issue link): "Claims and sources (n claims · m sources)" over a table claim → source → Verified, built from the page's own `span.claim[data-src]` spans and bare `a.cite` links, so it works without `assets/data.js`; when `DATA.evidence` exists it adds "cited on k pages" and the labels of sources on other pages. Writers add nothing to the footer for it — they wrap claims in prose (`components/sitewide/claim.html`). Validator: `claim cites missing source #ref-x` · `claim without data-src`.

**E6 last change** — when `assets/changelog.json` has an entry whose `pages` names this page, the runtime appends a fifth pill, *last change YYYY-MM-DD* (the newest such entry; its version and note as the tooltip), after the four computed ones. The compose skill appends an entry at every stage close, so the pill follows fix rounds without any edit to the page; `data-reviewed` stays the writer's date.
