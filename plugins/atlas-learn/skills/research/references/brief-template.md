# Research brief template — `topics/<slug>/tmp/BRIEF.md`

Written by `atlas-learn:brief-author`, reviewed by `atlas-learn:brief-reviewer`, approved by the user. Text in `{braces}` is filled from the plan's `## What I want`, `INSIGHTS.md` and `FIELD_MAP.md`; text in *italics* is guidance to delete. Keep the brief in the second person imperative ("Investigate…", "Explain…", "Provide…") — it is instructions to researchers and page writers. Module headings are parsed by scripts: exactly `### M01 — Title` and `### S01 — Title` (two-digit ids, an em dash with spaces).

```markdown
# Research brief: {Title}

**Slug**: {slug}
**Status**: Draft
**Insight hash**: {12 hex, given in the dispatch}
**Updated**: {YYYY-MM-DD}

## 1. Research mission

{Two paragraphs written from the insight, quoting it: "Goal: …" "Focus: …" "Skip: …" "Done when: …". What to study, from what foundations to what frontier; what the report must enable the reader to do; the anchor example / reference platform and how to use it (general principles vs example-specific choices; compare alternatives; explain how designs adapt when components change).}

Document type: {from INSIGHTS.md How table}. Primary reader: {from Start — usually the user themself}. Reader starts at {start level} and should finish able to {Done when}. Progression: {four levels L1–L4 | three levels | flat | tracks}. Scale: {n} modules + {m} synthesis parts.
Reader emphasis: {the Readers row, e.g. "engineer, software developer"} → {what the modules lean on: worked examples | look-up tables and checklists | runnable code | derivations | outcomes and problem sets}.

{Format site:} The output is a Full-Width Interactive Research Report built with the atlas-learn compose stage (see §9).
{Format single:} The output is a single-page interactive guide (one self-contained HTML file, same template) with {n} parts on one page, about {est} KB (see §9).

## 2. Research methodology and source policy

### 2.1 Allowed sources, in priority order
1. {tier 1: academic textbooks; peer-reviewed papers and reviews}
2. {tier 2: official documentation, standards, datasheets, regulators; preprints and theses (marked)}
3. {tier 3: reputable engineering blogs, tutorials, community documentation — only when primary sources are unavailable}
4. {also allowed: video lectures/talks (embedded with attribution) · Wikipedia for orientation only · forums as leads only · vendor pages for availability/price only}
{Sources the user trusts or distrusts, from Skip/Boundaries, stated explicitly.}
Must cite (searched first, every module that touches them cites them): {the Must cite policy row — named textbooks, standards, documentation roots; or "none"}.
Must avoid (never cited, not even as "reported"): {the Must avoid policy row; or "none"}.
Discovery (extra source classes, at most 2 searches per module per class; tune after the first run): {the Discovery row — datasets, code, standards, lectures, with the repositories to search for each; or "none — papers, books and web only, default budgets"}.

Repositories to search: {IEEE Xplore, Google Scholar, arXiv, ScienceDirect, SpringerLink, ACM DL, project documentation sites, standards bodies … as relevant}.

Freshness: {from the How table}. Date-stamp anything that changes (versions, product status, regulations).

### 2.2 Verification and evidence
{Strict: every reference, URL, image and number mechanically verified; unverifiable items dropped from the bibliography and listed. | Standard: every reference mechanically checked; items that fail stay marked "✗" or "not confirmed", never cited as verified. | Light: no separate verifier pass, but every fact still comes from a source the researcher retrieved; the dossier says the links were not re-checked.} The verification level changes how much is re-checked, never what counts as evidence.
Evidence policy (`references/evidence-policy.md`, binding at every level): every statement, number, label, table row, diagram node and edge traces to a retrieved source; nothing comes from model knowledge; a number is computed only by a method the source documents with inputs that are documented or the reader's own; no undocumented relationship, cause or comparison is drawn; conflicting sources are both shown; what the sources do not establish is marked `Not specified`, `Insufficient evidence` or `Not available in sources`, never filled. Never fabricate references, titles, DOIs, specifications, prices, dates or URLs. Distinguish established practice from experimental research. If a topic is too large, give a technically meaningful overview, keywords, reading and a learning direction — each from the sources.

### 2.3 Presentation — interactive visualization first
The primary output of every module is an interactive visualization of what the sources document, chosen by the shape of the evidence (evidence policy §7): documented relationships → interactive diagrams (architecture, flow, signal, block, circuit, protocol, state); documented comparisons → filterable tables; documented formulas with ≥ 2 inputs → calculators and simulations implementing exactly those formulas; published series → plots of exactly those values; dated events → timelines; physical parts → photographs with attribution and hotspots. Every visual cites its sources on the figure or its elements; none is decorative; where the evidence has no visual shape, write evidence-based text, with what the sources do not document marked by a gap badge. Consistent terminology throughout. For every key equation set: (1) formulation, (2) physical interpretation, (3) engineering application, (4) practical implementation, (5) example on {anchor example} — each step from the sources.
Demos: {rich | moderate | minimal}. Media: {from the How table}. Language and units: {…}. Region for regulations: {…}.
Citation style: {numeric | author-year} on every page. Output licence: {Licence row}. Accessibility: {Accessibility row — the compose stage sets the reading defaults from it}.

## 3. Modules

*One subsection per module, in reading order. Topic lists are exhaustive — writers cover every item. 15–40 topics per module is normal for Format site; for Format single, 2–6 parts in total (modules + synthesis) with 5–15 topics each — each module becomes one part of the page.*

### M01 — {Title}
Level: {1–4} · Group: {group} · Priority: {yes|no}
{One-paragraph purpose, tied to the Focus.}
Topics:
- {topic} · {topic} · … *(nest sub-lists for sub-areas; name tools, standards, products and algorithms)*
Running-example instance: {what to show on the anchor example}.
Interactive candidates: {calculator/simulation/playground/diagram ideas with inputs → outputs — candidates for the researchers to document, built only if the sources give the method or the relationships}.
Media: {photos/videos/3D/PDF candidates to verify, or "diagrams only"}.
**Deliverable:** {one concrete artifact: annotated system diagram, implementable model, selection guide, architecture, research plan …}

### M02 — …

## 4. Synthesis parts

*Only those the insight calls for. Same heading format; `Level` is empty.*

### S01 — {Integrated project | Technology stacks | Comparison matrices | Research questions | Learning roadmap}
Group: Synthesis · Priority: no
{What to investigate, per the part: project → stages with objectives, required knowledge, hardware/software, deliverables, tests, common failures, success criteria; stacks → layers, responsibilities, integration, beginner/advanced/research stacks with cost estimates; matrices → categories, columns, established/discontinued/emerging marks; questions → 8–12 with motivation, approaches, papers, metrics; roadmap → levels with objectives, prerequisites, textbooks, exercises, study time, assessment.}
**Deliverable:** {…}

## 5. Must-answer questions
{The numbered must-answer questions from Focus, each mapped to the module that answers it: "Q1 → M04 §…".}

## 6. Out of scope
{From Skip: what is not researched and why. Writers may mention an excluded topic in one sentence with a pointer, never treat it.}

## 7. Anchor example
{Name, why it is representative, what the user says about it (from Start — marked user-provided until a source confirms it), which parameters every module must share and must find a source for — the consolidator's parameter sheet starts here.}

## 8. Quality requirements
1. Technical accuracy outranks decoration, completeness and presentation. 2. Do not oversimplify important mathematics or engineering. 3. Relate theory to real hardware/tools the sources document. 4. Use {anchor example} consistently where useful. 5. Separate deterministic/critical parts from best-effort parts. 6. Distinguish conventional from AI/learning-based approaches where relevant. 7. Explain why simulated or idealised results do not transfer automatically, where the sources say so. 8. Address physical, computational, cost and legal limits the sources state. 9. Every claim, number and visual element cites a retrieved source — not only the important ones. 10. Mark limitations, assumptions and unspecified values with the evidence labels instead of filling them. 11. Do not treat new technology as automatically better. 12. Include safety throughout. 13. No calculation without a documented method and documented or reader-supplied inputs; no relationship without a source that states it. {+ topic-specific rules}

## 9. Interactive report requirements (fixed)
*Format single — use this paragraph instead of the site paragraph below:* The deliverable is one self-contained, full-width interactive page built with the fixed template: a hero with reading time and level; a one-page summary (objectives and key takeaways); an optional map of the parts; one part per module with concepts, the key equation set as a five-step block where one exists, an SVG diagram, a worked running-example case, pitfalls and a pointer to further reading; knowledge checkpoints; exercises when the use is study; a searchable glossary; one reference list with verified badges; a trust footer; navigation as a table of contents with search; interactive calculators implementing documented calculations, citing them and labelling their readouts as model output (at most one per part); every figure citing its sources; gaps marked visibly; verified external media with attribution; light theme by default with dark mode. Budget: about 250 KB of page HTML.

*Format site:* The deliverable is a full-width, multi-page interactive report built with the fixed template: overview page (executive summary, scope, methodology, key findings, system map, curriculum map, deliverables index); persistent navigation with search, glossary and progress; per-module pages with objectives, conceptual introduction, detailed technical sections, mathematical formulation, architecture diagrams (SVG, zoomable, legends distinguishing data/control/power), practical examples, implementation examples, running-example case studies, comparison tables (filterable), common mistakes, further reading, knowledge checkpoints and the module deliverable; interactive calculators/simulations implementing documented calculations, citing them and labelling their readouts as model output; every diagram, table, plot and timeline built from documented facts and relationships and citing them on the figure or its elements; gaps marked visibly where they occur; verified external media with attribution; light theme by default with dark mode.

## 10. Success test
{Done when, verbatim, then one line per module on what it contributes to it. The site reviewer checks the site against this section.}

## 11. Final deliverables
1. Executive overview · 2. Complete curriculum · {3… one line per module deliverable} · {synthesis parts chosen} · Bibliography · Glossary.

## 12. Research allocation
*Suggested grouping for researcher agents: 1–3 modules each, the priority module alone, synthesis parts with the modules they overlap most. One line per group.*
- Group A: M01, M02 (foundations; share sources)
- Group B: M04 (priority)
- …

## 13. Learning design
*Filled only when the Document type is a textbook curriculum or the Use is teaching; otherwise this section is the one line `n/a — {why}`. Outcomes are observable (a Bloom verb and an object: "compute…", "compare…", "justify…"), never "understand"; every outcome has an assessment; hours are the reader's study time per module and feed the site's study planner.*

### M01 — {Title}
Outcomes:
- O1 ({remember|understand|apply|analyze|evaluate|create}): {the reader can …}
- O2 ({level}): {…}
Assessment: {O1 → checkpoint (which concept) · O2 → exercise (what the reader produces) · deliverable → the module deliverable}
Hours: {n} · Session: {week or session number} · Prerequisites: {M00, or none}

### M02 — …

Course alignment: {sessions or weeks in order, which modules each covers, total hours; the roadmap part (if any) repeats this for the reader}.

## Appendix — Derived policies (copied from INSIGHTS.md)
| Policy | Value | Because |
|---|---|---|
| Document type | … | … |
| Format | … | … |
| Depth | … | … |
| Verify | … | … |
| Freshness | … | … |
| Demos | … | … |
| Media | … | … |
| Language | … | … |
| Region | … | … |
| Must cite | … | … |
| Must avoid | … | … |
| Citation style | … | … |
| Licence | … | … |
| Accessibility | … | … |
| Readers | … | … |
| Discovery | … | … |
```

Guidance:
- Module topic lists are where the brief earns its keep. Write them from `FIELD_MAP.md` plus the field's standard curriculum; group related items; include the tools, standards, products and algorithms by name. A topic line is a research target, not a claim: it reaches a page only through a retrieved source, and a topic the research cannot document becomes a marked gap.
- Facts the user stated in the interview (their hardware, a value they believe) appear in §7 as `user-provided` and are listed for the researchers to check, never as established facts (evidence policy §2).
- Every must-answer question (§5) must land in at least one module's topic list; every Skip item must appear in §6 and nowhere in §3.
- Deliverables must be concrete artifacts a writer can build on a page (a diagram, a model with code, a selection guide with calculator, a research plan), not "an understanding of".
- Exactly one module has `Priority: yes` — the one the Focus names first.
- Keep §8 and §9 verbatim apart from the marked slots; they are what makes every report consistent.
- The hash and the Status line are machine-read: never reformat the header.
- §13 (learning design) uses the module headings of §3 as `### M01 — Title` sub-headings too; the compose stage copies `Hours` into the site plan and the outcomes into the writers' blocks, so each outcome must name its module.
- Must-cite sources are searched first and cited by every module they touch; must-avoid sources never appear in a dossier or on a page. The citation style, licence and accessibility rows reach the compose stage unchanged.
