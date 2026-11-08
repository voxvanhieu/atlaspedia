# Insights: How map projections work

**Slug**: map-projections
**Status**: Confirmed
**Updated**: 2026-11-05
**Rounds**: 3

## Refined insight

### Goal
Understand how a sphere is mapped onto a plane well enough to choose a projection for each of my maps, implement the forward equations for Mercator and one equal-area projection, and replace the default projection of my mapping tool with a choice I can defend.

### Why
My world maps make Greenland look as big as Africa, although Africa is about fourteen times larger. I want to understand the distortion rather than pick a preset, because my next maps (a country map and a thematic map of population density) need the same understanding.

### Use
Self-study first, read in order over a few weeks; then a reference while making maps: the comparison module and the choosing module will be reopened often.

### Start
I know trigonometry and basic calculus. I use QGIS and Python, I have heard of EPSG codes, and I have never looked at what PROJ does internally.

### Focus
1. The conformal vs equal-area trade-off, and why no flat map can be both.
2. Tissot's indicatrix as the tool for seeing distortion.
3. How PROJ implements Mercator and Web Mercator, as a comparison target.
Anchor example: my own world and country maps; every module should end on those numbers.
Must answer: why Mercator is conformal; why Web Mercator (EPSG:3857) stops at about 85° latitude; what a compromise projection such as Robinson gives up.

### Skip
Derivation proofs beyond what the equations need, ellipsoid geodesy beyond the sphere, historical map art, and blog numbers without a source. Sources I trust: textbooks, USGS publications, papers, PROJ documentation.

### Done when
I can compute Mercator and equal-area coordinates for a city by hand, compare them with PROJ on the same point, and explain my projection choice for each map in one sentence.

## How (derived policies)
Set from the insight. Change any row before approving the brief; the brief author reads this table.

| Policy | Value | Because |
|---|---|---|
| Document type | project guide with textbook modules | use = reference while making maps |
| Depth | textbook on distortion and choice, overview elsewhere | focus |
| Verify | standard | self-study; the map numbers are the user's own |
| Freshness | foundational + current PROJ version, dated | anchor on current tools |
| Demos | rich on the distortion and choosing modules | the success test needs intuition for distortion |
| Media | diagrams + verified photos | default |
| Language | English, SI | default |
| Region | skip regulation | not in scope |

## Open gaps
| # | Question | Blocking | Status |
|---|---|---|---|
| G-01 | Which PROJ version does the user's QGIS ship? | no | you-decide |

## Interview log

### Round 1 — 2026-11-05
**Q (goal)**: After this, what should you be able to do with map projections?
Options: choose one for my own maps · pass a cartography exam · pick a GIS preset · explain it to a team
**A**: choose one for my own maps and compute the coordinates myself
