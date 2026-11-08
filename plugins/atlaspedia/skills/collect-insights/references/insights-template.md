# Insights template — `topics/<slug>/tmp/INSIGHTS.md`

The main agent creates the file from this template at the start of the interview (header + empty sections + the log). The log is appended after every round. `insight-refiner` fills sections 1–3 and never edits the log. The plan's `## What I want` is a one-line-per-key summary of section 1 + 2; the full text lives here.

```markdown
# Insights: {Title}

**Slug**: {slug}
**Status**: Draft
**Updated**: {YYYY-MM-DD}
**Rounds**: 0

## Refined insight

### Goal
{What the user wants to be able to do afterwards. Detailed, concrete, in the user's own terms made precise.}

### Why
{What brought this up: a project, a gap they hit, a decision, curiosity. Why now.}

### Use
{What the document is for: self-study, reference while building, teaching, deciding. How it will be read.}

### Start
{What the user already knows, has and has tried. Named tools, hardware, data, prior reading.}

### Focus
{Priority angles in order. Must-answer questions as a numbered list. The anchor example (reference platform, dataset, case) and how to use it.}

### Skip
{What to leave out and why. Constraints: time, sources the user trusts or distrusts, regions, languages.}

### Done when
{The success test: "done when the reader can …". Observable, so the site reviewer can check it.}

## How (derived policies)
Set from the insight. Change any row before approving the brief; the brief author reads this table.

| Policy | Value | Because |
|---|---|---|
| Document type | {textbook curriculum \| engineering handbook \| research survey \| project guide} | {…} |
| Format | {site \| single} | {…; "asked with --single/--site" when the user forced it} |
| Depth | {overview \| textbook \| monograph \| mixed: …} | {…} |
| Verify | {strict \| standard \| light} | {…} |
| Freshness | {foundational + through {year} \| foundational only \| cutting-edge \| + history} | {…} |
| Demos | {rich \| moderate \| minimal} | {…} |
| Media | {diagrams only \| diagrams + verified photos \| + video, 3D, PDF} | {…} |
| Language | {English, SI} | {…} |
| Region | {international \| {region} \| skip regulation} | {…} |
| Must cite | {named textbooks, standards, documentation roots the researchers search first \| none} | {from Starting point and Boundaries: sources the user owns, trusts or named} |
| Must avoid | {sources never cited \| none} | {from Boundaries: distrusted or excluded sources} |
| Citation style | {numeric \| author-year} | {author-year when the Use is teaching or a research survey; numeric otherwise} |
| Licence | {all rights reserved, personal use \| CC BY 4.0 \| CC BY-SA 4.0 \| …} | {personal use by default; CC BY when the Use is teaching or the user said they will share it} |
| Accessibility | {none \| large text \| dyslexia \| screen reader \| reduced motion} | {anything the user said about reading: screen, eyesight, phone, assistive technology} |
| Readers | {one or two of: creative student, engineer, software developer, circuit designer, researcher, fundamental sciences, instructor, accessibility/mobile} | {a short quote of the user's Use/Goal words; "no Use/Goal words point elsewhere" for the default creative student — derived, never asked} |
| Discovery | {none \| any of: datasets, code, standards, lectures} | {the Readers persona or the user's own words; none keeps the default search budgets} |

## Open gaps
| # | Question | Blocking | Status |
|---|---|---|---|

## Interview log

### Round 1 — {YYYY-MM-DD}
**Q (goal)**: {question as asked}
Options: {a} · {b} · {c} · {d}
**A**: {answer, verbatim}
```

Rules:
- `Status` becomes `Confirmed` only when every blocking gap is `answered` or `you-decide` and the user has seen the 6-line summary.
- Gap status: `open` (found by the refiner) → `asked` (put to the user) → `answered` or `you-decide` (the recommendation applies).
- The log is the evidence; never rewrite an answer. If the user changes their mind, log a new round.
