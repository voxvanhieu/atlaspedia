# M01 — From the globe to the plane
Researched 2026-11-05 · verification: standard · freshness: foundational + through 2026

## Keywords
map projection, sphere, latitude, longitude, developable surface, cylinder, cone, azimuthal, scale factor

## Sources
| # | Tier | Status | Reference (authors, year, title, venue) | Link (DOI/arXiv/official) | Why worth studying | Verified |
|---|---|---|---|---|---|---|
| 1 | 1 | foundational | Snyder, J. P. (1987). Map Projections — A Working Manual. USGS Professional Paper 1395 | https://doi.org/10.3133/pp1395 | The standard reference with every forward formula | Crossref ✓ |
| 2 | 1 | established | Šavrič, B., Patterson, T., Jenny, B. (2019). The Equal Earth map projection. International Journal of Geographical Information Science 33(3) | https://doi.org/10.1080/13658816.2018.1504949 | A modern equal-area design, explained step by step | Crossref ✓ |
| 3 | 1 | established | Snyder, J. P. (1993). Flattening the Earth: Two Thousand Years of Map Projections. University of Chicago Press | https://press.uchicago.edu/ucp/books/book/chicago/F/bo3632853.html | Why each family of projections was invented | fetched ✓ |
| 4 | 1 | foundational | Snyder, J. P., Voxland, P. M. (1989). An Album of Map Projections. USGS Professional Paper 1453 | https://doi.org/10.3133/pp1453 | Every common projection drawn with its distortion | Crossref ✓ |
| 5 | 2 | recent | Gott, J. R., Goldberg, D. M., Vanderbei, R. J. (2021). Flat maps that improve on the Winkel Tripel. arXiv | https://arxiv.org/abs/2102.08176 | A quantitative way to compare world maps | arXiv ✓ |
| 6 | 2 | established | PROJ contributors: Mercator projection (PROJ documentation) | https://proj.org/en/stable/operations/projections/merc.html | What the anchor tool does | fetched ✓ |
| 7 | 3 | established | Munroe, R. xkcd 977: Map Projections (comic) | https://xkcd.com/977/ | The best-known first picture of projection choice | fetched ✓ |
| 8 | 2 | preprint | Jenny, B. et al. Projection Wizard (online tool) | https://projectionwizard.org/ | Suggests a projection from the map's extent | not confirmed automatically — tool home page, no citable description |

## Key facts and numbers
| Claim / value | Source # | Locator | Date / version | Confidence | Notes (conditions, as the source states them) |
|---|---|---|---|---|---|
| Mercator scale factor on the sphere: k = sec φ | 1 | Mercator projection chapter, scale-factor formula | 1987 | high | exact, sphere |
| Web Mercator is cut at about ±85.05° latitude so the map is square | 6 | whole page | 2026 | high | as the PROJ page states it |

## Documented calculations
| Id | Calculation (formula or algorithm, as the source writes it) | Inputs (source # or `reader input`) | Output, unit | Validity | Source # | Locator |
|---|---|---|---|---|---|---|
| C1 | Mercator scale factor k = sec φ | φ: reader input | k, dimensionless | sphere; latitude below 90° in magnitude | 1 | Mercator projection chapter, scale-factor formula |
| C2 | Mercator and Lambert cylindrical equal-area forward equations | φ, λ: reader input; R: running example (user) | x, y in km | sphere | 1 | forward equations of both projections |

## Documented relationships
| Id | From | Relation | To | Source # | Locator |
|---|---|---|---|---|---|
| R1 | sphere | is projected onto | a developable surface (cylinder, cone or plane) | 3 | introduction |

## Conflicts and limitations
- Notation: source 1 writes the scale factor as k and h, source 2 as a single factor; the site uses k.

## Running-example parameters
| Parameter | Value | Unit | Source # | Confidence |
|---|---|---|---|---|
| Earth radius (sphere) | 6371 | km | user — the anchor sphere chosen in the interview | user-provided |
| Web Mercator latitude limit | 85.05 | ° | 6 | high |

## Media candidates (verified)
| Kind (photo/video/model/pdf) | URL to embed | Source page | Author | Licence | Suggested use |
|---|---|---|---|---|---|
| photo | https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Mercator_1569.png/330px-Mercator_1569.png | https://commons.wikimedia.org/wiki/File:Mercator_1569.png | Gerardus Mercator | Public domain | introduction sidebar |

## Interactive demo candidates
1. **Scale factor by latitude** — inputs: latitude φ; model: C1 (source 1); outputs: scale factor and area exaggeration; what the reader learns: why Greenland looks huge; assumptions: sphere, Mercator.
2. **Projection comparison** — inputs: a city's latitude and longitude; model: C2, the Mercator and Lambert cylindrical equal-area forward equations (source 1); outputs: x, y in both; learns: what conformal and equal-area cost.

## Suggested diagrams and tables
- Diagram: globe, cylinder and plane with one meridian traced through; Table: projection families across sources 1, 3, 4 (~10 rows).

## Open questions / research directions
- none

## Freshness notes
- PROJ moved its documentation under /en/stable/ in 2023; the link above is the current page as of November 2026.

## Could not verify
- Source 8 (Projection Wizard) — tool home page linked, not a citable description; recommendation: link the home page.
