# Dossier overview — How map projections work
Consolidated 2026-11-05 · 7 dossier files · verification: standard

## 1. Running-example parameter sheet
| Parameter | Value | Unit | Source | Confidence |
|---|---|---|---|---|
| Earth radius (sphere) | 6371 | km | user (m01 running example) | user-provided |
| Web Mercator latitude limit | 85.05 | ° | m01 #6 | high |

## 2. Overlaps and ownership
- Tissot's indicatrix: claimed by M02 and M04; M04 owns the full treatment, M02 cross-links.

## 3. Glossary seed
| Term | Owning module |
|---|---|
| Scale factor | M02 |
| Equal-area | M03 |

## 4. Bibliography seed
| # | Tier | Reference | Link | Topics |
|---|---|---|---|---|
| 1 | 1 | Snyder (1987) | https://doi.org/10.3133/pp1395 | M01, M02 |
| 2 | 2 | Gott et al. (2021) | https://arxiv.org/abs/2102.08176 | M04 |

## 5. Media list
| Kind | URL | Licence | Page |
|---|---|---|---|
| photo | https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Mercator_1569.png/330px-Mercator_1569.png | Public domain | m01-globe-to-plane.html |

## 6. Conflicts and limitations
- Scale-factor symbols k and h vs a single factor — present as a notation note.

## 7. Unverified items
- m01 #8 Projection Wizard — home page linked only.
- m03 #4 and #7 — DOIs not resolvable (see M03 "Could not verify").

## 8. Build notes
**Groups**: Overview · Foundations · Core · Advanced · Synthesis · Reference
**Levels**: 1 Foundations · 2 Practical engineering · 3 Advanced topics · 4 Research frontier
**Priority module**: M04

### Page m01-globe-to-plane.html — From the globe to the plane (M01, level 1, 90–140 KB)
- Topics: BRIEF.md §3 M01, all items
- Diagrams: globe → cylinder → plane (boxes: sphere, developable surface, map; paths: data) — m01 R1
- Tables: projection families across sources 1, 3, 4
- Demos: scale factor by latitude (m01 C1); projection comparison (m01 C2)
- Sources: m01 #1–#7
- Media: Mercator 1569 world map (m01 media row 1)
- Cross-links: m02-mercator.html#scale-factor
- Numbers: Earth radius 6371 km, Web Mercator limit 85.05° (parameter sheet)

### Page m02-mercator.html — Mercator and conformal projections (M02, level 1, 90–140 KB)
- Topics: BRIEF.md §3 M02
- Diagrams: rhumb line vs great circle — m02 #1
- Tables: none
- Demos: latitude slider (m02 C1)
- Sources: m02 #1–#2
- Media: none
- Cross-links: m04-compromise.html#tissot
- Numbers: parameter sheet
