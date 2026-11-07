# Evidence and visualization policy — the global rules

Every skill, agent, template, component and script in atlas-learn works under this file. It sits at the top of the instruction hierarchy:

1. **This file** — global principles and the plugin-wide policy (what counts as evidence, what may be calculated, what a visualization may show).
2. **`contracts.md`** — the machine interface: file shapes, markers and gates that carry these rules.
3. **Skill files** (`skills/*/SKILL.md`) — how each stage applies them.
4. **Agent files** (`agents/*.md`), **references**, **component READMEs and snippets** — how each role or building block applies them.

A lower level may be stricter than a higher one, never looser. When two files disagree, the higher one wins and the lower one is a bug to fix. Files cite this policy as "evidence policy §n" instead of repeating it.

## 1. Principles

**Accuracy over completeness. Evidence over assumptions. Documentation over model knowledge. Interactive visualization over passive presentation.**

- The common output of atlas-learn is an **interactive visualization of verified information**: a diagram, table, plot, timeline, demo or map that the reader can explore, built only from what the sources establish.
- Information integrity wins over visual completeness, presentation quality and apparent completeness of the answer. A smaller site that says only what the sources say is correct; a fuller one that fills holes is wrong.
- The model's own knowledge and reasoning are never evidence. They may plan work (which topics to research, which sources to search, how to lay out a page), never supply a fact.

## 2. Classes of information

| Class | What it is | May be presented as established? | How it is marked |
|---|---|---|---|
| **Documented fact** | a statement, value, relationship or property explicitly stated in a retrieved source | yes | the source number in the dossier; `span.claim[data-src]`, `a.cite` or `data-cite` on the page |
| **Documented calculation** | a formula or algorithm the source states, applied to inputs the source states or the reader enters | yes, as the source's method | a row in the dossier's `## Documented calculations`; the demo or figure cites it |
| **User-provided** | a value or statement the user gave in the interview, or a value the reader types into a demo | only as the user's input, never as a sourced fact | `user` in the dossier's Source cell; the `user-input` badge or the demo's own controls on the page |
| **Missing** | anything the sources do not establish | **no** | `Not specified` / `Insufficient evidence` / `Not available in sources` (§3) |

Only the first two classes are established information. A user statement that a source contradicts is shown as a conflict (§4), not silently corrected and not silently accepted.

## 3. Evidence labels

One vocabulary across dossiers, pages and reports:

| Label | Meaning | Dossier | Page |
|---|---|---|---|
| **Documented** | stated in a retrieved source | a row citing a source # | `badge documented` (optional; a cite already says it) |
| **Source verified** | the source was retrieved and its metadata checked mechanically | Verified cell `Crossref ✓`, `fetched ✓` … | `badge verified` on the reference entry |
| **Not specified** | a retrieved source covers the subject but does not state this value or property | `## Could not verify` line `Not specified — <what>` | `badge not-specified` |
| **Insufficient evidence** | sources touch it, but not enough to state it (one weak source, a snippet only, conditions differ) | `Insufficient evidence — <why>` | `badge insufficient` |
| **Not available in sources** | no retrieved source covers it | `Not available in sources — <what>` | `badge unavailable` |
| **Sources conflict** | two sources state different values | `## Conflicts and limitations` | `badge conflict`, both values shown with both sources |
| **User-provided** | from the user or the reader, not from a source | Source cell `user` | `badge user-input` |

A Verified cell never says `model knowledge`: a reference that was not retrieved is not a source (§4).

## 4. Retrieval and traceability

1. **User-provided documents and the user's must-cite sources first**, then authorized searches (the brief's §2.1). Must-avoid sources are never used, not even as leads.
2. **Retrieve before writing.** A fact enters the dossier only from a source the researcher opened (fetched page, PDF, metadata endpoint, or a document the user gave). A search-result snippet is a lead, not evidence, when the original is reachable; when it is not, the fact is `Insufficient evidence — snippet only`.
3. **The source must support the statement directly.** Not "is about the topic": the cited passage states the fact. Record where: a `Locator` (section, page, table, figure, equation, or `whole page` for a short page), plus the source's version or date.
4. **Keep source statements apart from presentation.** The dossier records what the source says; the page may reword it but not extend it. A summary sentence that adds a cause, a comparison or a generalisation the source does not make is an inference (§6).
5. **Expose conflicts.** Two sources that disagree are both recorded with both values, dates and conditions, and both appear on the page. Choosing one value for a worked example is allowed only when the page says it is a choice and shows the other value.
6. **Trace every element.** Text, numbers, table rows, diagram nodes and edges, chart data, timeline events, specifications, labels and annotations each trace to a source number. On pages the trace is visible and, where practical, on the element itself (`data-cite`, §7).
7. **Untraceable means out.** A statement with no source is removed or marked with a §3 label. It is never presented as fact.

## 5. Calculations

1. A number may be **computed** only when the source documents the method (formula or algorithm) **and** every input is documented, given by the user, or entered by the reader. The dossier lists such methods in `## Documented calculations` (id `C1…`, formula as the source writes it, inputs with their source or `reader input`, units, validity range, source # and locator).
2. **Not allowed:** deriving a value with a formula the sources do not give; chaining documented formulas into a new result the sources do not state; filling a missing input with a "typical" or remembered value; extrapolating outside the documented validity range; averaging, rounding into ranges, or converting between conditions (temperature, load, version) the source does not cover.
3. Unit conversions with exact definitions (1 in = 25.4 mm) are not new facts and are allowed.
4. **Demos and computed plots** implement documented calculations only. The reader's inputs are user-provided values: the page shows them as inputs, the result as computed from them by the cited method, and states what the method does not model. A demo with no documented method is not built — the section gets a table or text instead.
5. **Exercises** may ask the reader to apply a documented calculation to stated inputs; the solution uses only that method.
6. When the method or an input is missing, the calculation is **not performed**. The page says which input or method is missing (`badge unavailable` or `badge not-specified`) and the writer reports the gap.

## 6. Inference

No undocumented relationships, behaviours, properties, dependencies, causes, comparisons, rankings or predictions. In particular:

- a diagram edge, arrow, grouping or layer exists only when a source states that relationship (dossier `## Documented relationships`, id `R1…`);
- "typical", "usually", "most", "best" and "better" appear only when a source says so;
- examples, products, specifications, behaviours and implementation details come from the dossier, never from memory;
- a hypothesis, interpretation or open question is labelled as such (`callout research`, `badge experimental`) and cites who proposed it.

## 7. Interactive visualization

**Choose the form from the shape of the evidence**, not from the wish to decorate:

| The sources document … | Show it as … | Catalog |
|---|---|---|
| components and the relationships between them | an interactive diagram (zoom, steps, layers) whose nodes and edges carry `data-cite` | `diagrams`, `protocol`, `circuit` |
| comparable properties of several items | a filterable, sortable table, one cited row per item | `core` table |
| a formula with ≥ 2 inputs | a demo or declarative plot implementing it (§5) | `demos`, `plots` |
| a series of measured or published values | a plot of exactly those values, with the source in the caption | `plots` |
| dated events or stages | a timeline or step list | `core` timeline / steps |
| a sequence, protocol or state machine | a sequence, timing or state diagram | `protocol` |
| parts of a physical object | a photo with hotspots or an exploded view | `media`, `diagrams` |
| terms and their documented relations | the concept map from the glossary | `overview` |

Rules for every visualization:

1. **Every element is evidence.** A visual communicates information explicitly supported by the dossier; nothing is drawn for decoration. Missing data points stay missing (gaps in a line, empty cells marked `—`), never interpolated.
2. **Faithful encoding.** Original units, terms, values and relationships are kept; scales start where the data allows and say so; log axes are labelled; no proportions that imply more than the source states.
3. **Visible provenance.** A figure or demo cites its sources — in its caption, on the figure (`figure[data-cite="#ref-a, #ref-b"]`, rendered as source chips) or on its elements (`g[data-cite]`, `tr[data-cite]`, `li[data-cite]`, which show their source on hover and focus and jump to it on click).
4. **Interactions add no claims.** Zoom, filters, steps, layers, tooltips, presets and sensitivity views reveal or recompute what is documented; they never introduce a new fact.
5. **Visible gaps.** What is missing is marked where the reader would look for it (§3 badges) and listed in the trust footer.
6. **Visualization first, text when it fits better.** Prefer the interactive form whenever the evidence has the shape in the table. When the evidence supports no visualization (a definition, a single fact, a contested claim), write evidence-based text; where the reader would expect a visual, state what the sources do not document (with a §3 badge), never why a visual was left out (§10). Never force a visual onto evidence that does not have its shape.

## 8. Gaps are never filled silently

A writer that needs a fact the dossier lacks leaves `<!-- GAP: what is missing -->` at the spot **and** a visible §3 badge beside the affected text, lists the gap in its report and in the trust footer, and moves on. A researcher that cannot establish a fact records it under `## Could not verify` with a §3 label. Neither guesses, estimates, nor writes around the hole as if it were not there.

## 9. Where each rule is enforced

| Rule | Instruction | Gate (fails the stage) |
|---|---|---|
| no `estimate`, no `model knowledge` in a dossier | module-researcher, research protocol, dossier template | `check_dossier.py` |
| every key fact has a source # and a locator | module-researcher, dossier template | `check_dossier.py` |
| demos only from documented calculations | module-researcher, dossier-consolidator | `check_dossier.py` (demo candidates and page `- Demos:` lines name a `C` id) |
| diagrams only from documented relationships or facts | dossier-consolidator | `check_dossier.py --overview` (page `- Diagrams:` lines name an `R` id or a source #) |
| every figure and demo cites its evidence; `data-cite` resolves | page-writer, authoring rules | `validate.py` (evidence block) |
| `illustrative` only on computed output, never on a stated number | page-writer, authoring rules | `validate.py` |
| every GAP marker has a visible badge | page-writer, authoring rules | `validate.py` |
| numbers, conflicts, inferences, decorative visuals, visualization fit | site-reviewer | the review's must-fix table |
| user statements stay user-provided | insight-refiner, brief-author, module-researcher | brief review, site review |
| pages carry no process text (§10) | page-writer, authoring rules | `validate.py` (evidence block: self-reference, decision narration, workflow vocabulary); the site review for the rest |

What a gate cannot read (whether a sentence says more than its source, whether a diagram edge matches the cited passage) is checked by the reviewers, and what they could not check is reported as a caveat, never as compliance.

## 10. The page is about the subject, not about its making

Everything a reader sees — prose, captions, callouts, badges, table notes, the trust footer — states the given or researched information about the subject and where it comes from. It never explains what an agent, a tool or the workflow did or why.

- **No narration of decisions.** Not "this diagram was added to show…", "we chose X because…", "the section omits Y since…", "there is no demo here because…". The content shows itself; a choice needs no justification on the page.
- **No workflow vocabulary.** The reader never sees the dossier, the brief, the site plan, page blocks, build notes, subagents, page writers, researchers, reviewers or verifiers. Cite the source itself (`[n]`), not the file it was copied from.
- **No self-reference.** No "as an AI", "generated by…", first-person "I/we decided/could not find".
- **Gaps are about the sources, not the search.** "The datasheet does not state the switching time" with a §3 badge — not "the researcher could not find it" or "this was not researched".
- **Assumptions are the subject's.** The trust footer's assumptions list the simplifications the content rests on (as the sources state them), not the process steps.
- **Where reasons go.** The reasons behind the page (why a visual fits, why a gap exists, what was skipped) belong in the agents' reports, `SITE_REVIEW.md` and the dossier's build notes — never on the page.

`validate.py` fails a page with self-reference, decision narration or workflow vocabulary in its visible text. Only a page whose subject is the atlas-learn workflow itself carries `<body data-subject="atlas-learn">` (the template home and the style guide) and skips the vocabulary list; in any other site that marker is a warning and is removed when the page is rewritten.
