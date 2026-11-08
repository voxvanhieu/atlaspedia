# Plan template — `topics/<slug>/PLAN.md`

Copy the block below to `topics/<slug>/PLAN.md`. Replace every `{…}`. Keep it short: one sentence per line, simple words, no detail that belongs in `tmp/`. `check_plan.py` enforces the shape (see `contracts.md` §3).

```markdown
# Research plan: {Title}

**Slug**: {slug}
**Folder**: topics/{slug}/
**Stage**: insights
**Format**: {site | single}
**Readers**: {one or two personas from the INSIGHTS.md Readers row; creative student by default}
**Discovery**: {the Discovery row, e.g. code, standards — delete this line when the row is none}
**Updated**: {YYYY-MM-DD}

## What I want
- **Goal**: {what I want to be able to do afterwards}
- **Why**: {what brought this up}
- **Use**: {what the document is for}
- **Start**: {what I already know or have}
- **Focus**: {priority angles, must-answer questions, anchor example}
- **Skip**: {what to leave out}
- **Done when**: {how I will know it worked}
- **How**: depth {textbook} · verify {standard} · demos {rich} · media {diagrams + verified photos} · {English, SI}

Details: `tmp/INSIGHTS.md`

## Progress
| Status | Stage | Output |
|---|---|---|
| [ ] | insights | tmp/INSIGHTS.md |
| [ ] | brief | tmp/BRIEF.md |
| [ ] | research | tmp/dossier/ |
| [ ] | compose | index.html |

## Modules
| # | Module | Researched | Checked | Page |
|---|---|---|---|---|

## Next
Run `/atlaspedia:go {slug}` — it will ask a few questions to pin down the goal.

## Notes
```

`**Readers**` (I1) and `**Discovery**` (I5) are optional header lines copied from the INSIGHTS.md `How` rows of the same names; like `**Format**` they sit outside `## What I want`, so they do not change the insight hash. `check_plan.py` checks the persona names (`creative student`, `engineer`, `software developer`, `circuit designer`, `researcher`, `fundamental sciences`, `instructor`, `accessibility/mobile`) and the classes (`none`, `datasets`, `code`, `standards`, `lectures`).

Filled example (stage 3 in progress):

```markdown
# Research plan: How map projections work

**Slug**: map-projections
**Folder**: topics/map-projections/
**Stage**: research
**Format**: site
**Readers**: creative student, engineer
**Updated**: 2026-11-05

## What I want
- **Goal**: Choose the right projection for my own maps and implement the forward equations.
- **Why**: My web maps make Greenland look as big as Africa and I want to understand why, not just switch a setting.
- **Use**: Self-study first, then a reference while building.
- **Start**: I know trigonometry and basic GIS; weak on geodesy, datums and distortion measures.
- **Focus**: Conformal vs equal-area trade-offs, Tissot's indicatrix, how PROJ and Web Mercator do it; anchor on a world map of country areas.
- **Skip**: Long proofs, polyhedral and artistic projections, surveying-grade geodesy.
- **Done when**: I can project my dataset with PROJ, compare Mercator with an equal-area projection and explain each choice.
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
| M01 | Latitude, longitude and the datum | [x] | [x] | [ ] |
| M02 | Mercator and conformal projections | [x] | [x] | [ ] |
| M03 | Measuring distortion: Tissot's indicatrix | [x] | [ ] | [ ] |
| M04 | Equal-area and compromise projections | [ ] | [ ] | [ ] |
| M05 | Choosing a projection for a map | [ ] | [ ] | [ ] |
| M06 | Inside PROJ's pipeline engine | [SKIP] | [SKIP] | [ ] |
| S01 | Project: my world map, three ways | [ ] | [SKIP] | [ ] |

## Next
Run `/atlaspedia:go map-projections` — it will research M04 and M05, verify M03, then consolidate.

## Notes
- Changed 1 (research, 2026-11-05): M06 skipped — PROJ's pipeline internals have no citable source beyond the code at standard level; folded into M05 as an overview.
- Caveat 1 (research, 2026-11-05): 2 references in M03 unverified; listed in tmp/dossier/00-overview.md.
- Lesson 1 (research, 2026-11-05): researcher dispatch lacked the running-example numbers path.
```
