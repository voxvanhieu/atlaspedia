# Research plan: How map projections work

**Slug**: map-projections
**Folder**: topics/map-projections/
**Stage**: research
**Updated**: 2026-11-05

## What I want
- **Goal**: Understand and choose map projections for my own maps, and implement the forward equations.
- **Why**: My world maps make Greenland look as big as Africa and I want to understand why, not just pick a preset.
- **Use**: Self-study first, then a reference while making maps.
- **Start**: I know trigonometry and basic calculus; weak on geodesy and on what GIS tools do internally.
- **Focus**: Conformal vs equal-area trade-offs, Tissot's indicatrix, how PROJ implements Mercator; anchor on my own world and country maps.
- **Skip**: Long proofs, ellipsoid geodesy beyond the sphere, historical map art.
- **Done when**: I can compute Mercator and equal-area coordinates for a city, compare them with PROJ and justify my projection choice.
- **How**: depth textbook · verify standard · demos rich · media diagrams + verified photos · English, SI

Details: `tmp/INSIGHTS.md`

## Progress
| Status | Stage | Output |
|---|---|---|
| [x] | insights | tmp/INSIGHTS.md |
| [x] | brief | tmp/BRIEF.md |
| [ ] | research | tmp/dossier/ |
| [ ] | compose | index.html |

## Modules
| # | Module | Researched | Checked | Page |
|---|---|---|---|---|
| M01 | From the globe to the plane | [x] | [x] | [ ] |
| M02 | Mercator and conformal projections | [x] | [x] | [ ] |
| M03 | Equal-area projections | [x] | [ ] | [ ] |
| M04 | Compromise projections and Tissot's indicatrix | [ ] | [ ] | [ ] |
| M05 | Choosing a projection for a map | [ ] | [ ] | [ ] |
| M06 | Inside Web Mercator tile servers | [SKIP] | [SKIP] | [ ] |
| S01 | Project: my own world map | [ ] | [SKIP] | [ ] |

## Next
Run `/atlaspedia:go map-projections` — it will research M04 and M05, verify M03, then consolidate.

## Notes
- Changed 1 (research, 2026-11-05): M06 skipped — tile-server internals have no citable source at standard level; folded into M04 as an overview.
- Caveat 1 (research, 2026-11-05): 2 references in M03 unverified; listed in tmp/dossier/00-overview.md.
- Lesson 1 (research, 2026-11-05): researcher dispatch lacked the running-example numbers path.
