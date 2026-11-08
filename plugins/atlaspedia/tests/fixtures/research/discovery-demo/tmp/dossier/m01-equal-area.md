# M01 — Equal-area projections and their sources
Researched 2026-11-07 · verification: standard · freshness: foundational + through 2026

## Keywords
equal-area projection, Equal Earth, Mollweide, authalic latitude, PROJ, Natural Earth

## Sources
| # | Tier | Status | Kind | Reference (authors, year, title, venue) | Link (DOI/arXiv/official) | Why worth studying | Verified |
|---|---|---|---|---|---|---|---|
| 1 | 1 | foundational | book | Snyder, J. P. (1987). Map Projections — A Working Manual. USGS Professional Paper 1395 | https://doi.org/10.3133/pp1395 | Every forward formula in one place | Crossref ✓ |
| 2 | 1 | established | paper | Šavrič, B., Patterson, T., Jenny, B. (2019). The Equal Earth map projection. International Journal of Geographical Information Science 33(3) | https://doi.org/10.1080/13658816.2018.1504949 | A modern equal-area design, step by step | Crossref ✓ |
| 3 | 2 | recent | paper | Gott, J. R., Goldberg, D. M., Vanderbei, R. J. (2021). Flat maps that improve on the Winkel Tripel. arXiv | https://arxiv.org/abs/2102.08176 | A quantitative way to compare world maps | arXiv ✓ |
| 4 | 1 | established | paper | Wakefield, A. J. et al. (1998). Ileal-lymphoid-nodular hyperplasia … The Lancet 351(9103) | https://doi.org/10.1016/S0140-6736(97)11096-0 | Fixture only: a well-known retracted work | Crossref ✓ |
| 5 | 2 | established | code | PROJ contributors (2026). PROJ coordinate transformation software, source repository | https://github.com/OSGeo/PROJ | The implementation the reader compares against | fetched ✓ |
| 6 | 2 | established | dataset | Natural Earth (2026). Admin 0 – Countries, 1:110m cultural vectors | https://www.naturalearthdata.com/downloads/110m-cultural-vectors/ | The country polygons of the anchor map | fetched ✓ |
| 7 | 2 | established | standard | ISO 19111:2019 Geographic information — Referencing by coordinates | https://www.iso.org/standard/74039.html | The standard behind CRS definitions | fetched ✓ |
| 8 | 3 | established | lecture | Jenny, B. (2020). Map projections, lecture slides and syllabus | https://doi.org/10.5281/zenodo.0000000 | A course that teaches the same progression | not confirmed automatically — DOI did not resolve |

## Key facts and numbers
| Claim / value | Source # | Locator | Date / version | Confidence | Notes (conditions, as the source states them) |
|---|---|---|---|---|---|
| Equal Earth keeps areas exact at every latitude | 2 | design section | 2019 | high | by construction |

## Documented calculations
| Id | Calculation (formula or algorithm, as the source writes it) | Inputs (source # or `reader input`) | Output, unit | Validity | Source # | Locator |
|---|---|---|---|---|---|---|
| C1 | Equal Earth forward equations | latitude band: reader input; R: running example | area ratio | sphere | 2 | forward equations |

## Documented relationships
none

## Conflicts and limitations
none

## Running-example parameters
| Parameter | Value | Unit | Source # | Confidence |
|---|---|---|---|---|
| Earth radius (authalic) | 6371.0072 | km | 1 | high |

## Media candidates (verified)
none

## Interactive demo candidates
1. **Area checker** — inputs: latitude band; model: C1, the Equal Earth forward equations (source 2); outputs: area ratio; the reader sees the ratio stay 1.

## Suggested diagrams and tables
- Table: projection, property, distortion pattern; ~6 rows.

## Open questions / research directions
none

## Freshness notes
- PROJ version current as of November 2026.

## Could not verify
- Source 8 — the lecture DOI is a placeholder in this fixture; recommendation: link the course root page.
