# Dossier templates

Three shapes live in `topics/<slug>/tmp/dossier/`: one file per module or synthesis part (`mNN-slug.md`, `sNN-slug.md`), the consolidated `00-overview.md`, and the `## Verification log` the verifier appends. `check_dossier.py` enforces the first two (`contracts.md` §6).

## A. Module file — `dossier/mNN-slug.md` (and `sNN-slug.md`)

```markdown
# M{NN} — {Module title}
Researched {date} · verification: {strict|standard|light} · freshness: {policy}

## Keywords
{comma-separated search terms and technical terminology, incl. synonyms and abbreviations}

## Sources
| # | Tier | Status | Kind | Reference (authors, year, title, venue) | Link (DOI/arXiv/official) | Why worth studying | Verified |
|---|---|---|---|---|---|---|---|
| 1 | 1 | foundational | book | … | https://doi.org/… | … | Crossref ✓ |
| 2 | 2 | established | standard | … | https://docs… | … | fetched ✓ |
| … | 3 | recent | code | … | … | … | not confirmed automatically — blocked (403) |

## Key facts and numbers
| Claim / value | Source # | Locator | Date / version | Confidence | Notes (conditions, as the source states them) |
|---|---|---|---|---|---|

## Documented calculations
| Id | Calculation (formula or algorithm, as the source writes it) | Inputs (source # or `reader input`) | Output, unit | Validity | Source # | Locator |
|---|---|---|---|---|---|---|
| C1 | … | … | … | … | … | … |

## Documented relationships
| Id | From | Relation | To | Source # | Locator |
|---|---|---|---|---|---|
| R1 | … | … | … | … | … |

## Conflicts and limitations
- {claim}: source A says X (year, conditions), source B says Y (year, conditions); how to present both. The cause of the difference only when a source states it.

## Running-example parameters
| Parameter | Value | Unit | Source # (or `user`) | Confidence |
|---|---|---|---|---|

## Media candidates (verified)
| Kind (photo/video/model/pdf) | URL to embed | Source page | Author | Licence | Suggested use |
|---|---|---|---|---|---|

## Interactive demo candidates
1. **{Name}** — implements: C{n}; inputs: {…, each documented or `reader input`}; outputs: {…}; what the reader sees; what the method does not model (as the source states it).
2. …

## Suggested diagrams and tables
- Diagram: {what boxes/paths} — from R{n}, R{m} (every edge is a documented relationship); Table: {columns, ~rows} — rows from source #{n}, #{m}.

## Open questions / research directions
- …

## Freshness notes
- {tool/product} renamed/discontinued/released {date}; version {x} current as of {month year}.

## Could not verify
- {item} — {Not specified | Insufficient evidence | Not available in sources}: {why}; recommendation: drop / cite as arXiv only / link root page / leave as a gap on the page.
```

`Kind` (I5) is optional — `paper | dataset | code | standard | lecture | book | web`; when the column is there, every row has a kind from that list (an unknown kind fails the gate, a blank one warns) and the gate's RESULT line gains `kinds=paper:n,…`. Write it whenever the brief's `Discovery` line is not `none`. `enrich_openalex.py` may later append a `## OpenAlex enrichment` section with one `- Enriched: #n — …` line per source with a DOI; never edit it by hand.

Rules (checked by `check_dossier.py`; the why is `references/evidence-policy.md` §2–§6): every section above is present — a section with nothing to say contains the single word `none`; every row in Sources has an `http(s)` link, a Tier in {1,2,3}, a Status in {foundational, established, recent, experimental, discontinued, preprint} and a non-blank Verified cell that never says `model knowledge`; every Key-facts row cites a source # that exists and a Locator; every Documented-calculations and Documented-relationships row has its id (`C1…`, `R1…`), an existing source # and a Locator; Running-example rows cite a source # or `user` (a value the user gave — shown as user-provided, never as sourced); `estimate` is never a source; every demo candidate names the `C` id it implements; media rows without a licence are deleted. Numbers never appear without a source # — a number nobody stated goes to `## Could not verify`. Source counts by depth: overview ≥ 4, textbook ≥ 8, monograph ≥ 12 (a warning below, never a failure). Synthesis files (`sNN`) use the same sections; "Running-example parameters" is usually `none`.

What the gate cannot read and the researcher must still hold: the locator points at a passage that states the fact itself (not a page about the topic); a calculation's formula is the source's, not a rearrangement or combination the source does not give; a relationship is stated by the source, not inferred from two facts.

## B. Verification log — appended by `atlaspedia:source-verifier`

```markdown
## Verification log
Checked {date} · level: {strict|standard} · report: {file}.links.md
| Source # / media row | Kind | Result | Note |
|---|---|---|---|
| 1 | doi | ✓ | Crossref title matches |
| 7 | page | ✗ dead link | 404; kept as "not confirmed" because the root page is the official doc |
| media 2 | commons | ✓ | licence CC BY-SA 4.0, artist recorded |
Summary: checked {n} · ok {n} · fixed {n} (title/year corrected from metadata) · failed {n}
```

The verifier edits only the `Verified` column of the two tables (and a title/year it can correct from metadata, noted as `fixed`); it never deletes rows or changes any other text.

## C. Consolidated overview — `dossier/00-overview.md`

```markdown
# Overview — {Title}
Consolidated {date} · modules: {n} · synthesis parts: {m} · verification: {level}

## 1. Running-example parameter sheet
| Parameter | Value | Unit | Source (file + # or `user`) | Confidence |
|---|---|---|---|---|
*(one table every writer copies, so numbers agree across pages; a value two sources disagree on is listed in §6 with both, and the row says which one the example uses and that it is a choice)*

## 2. Overlaps and ownership
| Topic | Claimed by | Owner page (full treatment) | Others cross-link to |
|---|---|---|---|

## 3. Glossary seed
| Term | Aka | Owning page | Definition (from the source) | Source (file + #) |
|---|---|---|---|---|
*(every term the dossiers define, up to 400; no quota to fill — a term no source defines is left out or listed as "define in page" only when its page cites a definition)*

## 4. Bibliography seed
| # | Tier | Status | Reference | Link | Modules | Verified |
|---|---|---|---|---|---|---|
*(deduplicated across files)*

## 5. Media list
| Kind | URL | Licence | Attribution | Page that uses it |
|---|---|---|---|---|

## 6. Conflicts and limitations
- {to be presented as such, never resolved silently}

## 7. Unverified items
- {file}: {item} — {recommendation} *(carried into the plan's Caveat note and the final report)*

## 8. Build notes
**Groups**: Overview · Foundations · Core · Advanced · Synthesis · Reference
**Levels**: 1 Foundations · 2 Practical engineering · 3 Advanced topics · 4 Research frontier
**Priority module**: M04

### Page m01-coordinates.html — Latitude, longitude and the datum (M01, level 1, 90–140 KB)
- Topics: BRIEF.md §3 M01 (all items)
- Diagrams: {what boxes/paths, one line each} — m01 R1, R2 (or `none — <why>`)
- Tables: {columns, ~rows} — rows from m01 #n, #m
- Demos: {name — inputs → outputs} — m01 C1 (or `none — the sources give no method with two inputs`)
- Sources: m01 #1, #3, #5–#8; bibliography #12
- Media: {from §5, or "diagrams only"}
- Cross-links: m02-….html#…, s01-project.html#…
- Numbers: {parameters from §1 this page must quote}

### Page s01-project.html — Project: … (S01, level —, 100–150 KB)
- Topics: …
- Diagrams: … · - Tables: … · - Demos: … · - Sources: … · - Media: … · - Cross-links: … · - Numbers: …

### Page index.html — Research overview (00, level —, 30–50 KB)
### Page bibliography.html — Bibliography (B, level —, 60–120 KB)
### Page glossary.html — Glossary (G, level —, data-driven)
```

Rules (checked by `check_dossier.py --overview`): sections 1–8 present with these exact numbers and titles; §1 has at least one row or `none`, and every §1 row has a source (file + #) or `user`; §8 has the three bold lines and at least one `### Page` block; every `### Page` block has the eight dash-lines `Topics, Diagrams, Tables, Demos, Sources, Media, Cross-links, Numbers`; a `Demos` line names the `C` id it implements and a `Diagrams` line the `R` ids or source #s it draws from, or says `none — <why>` (evidence policy §5–§7). One block per future page, including `index.html`, `bibliography.html` and `glossary.html` (their lines may say `n/a`). Page file names are flat, lowercase, hyphenated, `mNN-` / `sNN-` prefixed for modules and parts, and never change once written here.
