# Assessment — knowledge checkpoints, exercises, persisted checklists, instructor notes, Bloom tags, predict blocks, lab sheets

Use for the `#checkpoints` section of every module (quizzes), the `#exercises` section (problems with hints revealed one by one and a hidden solution), procedures the reader ticks off (design reviews, set-up procedures, release checks, milestone trackers), and the teaching layer on top of them: notes and rubrics only the instructor sees, Bloom levels on objectives and checkpoints with an outcome matrix, predict-then-reveal questions tied to a demo preset, and lab or assignment sheets that print as handouts. Snippets: `quiz.html`, `checklist.html`, `exercise.html`, `instructor.html`, `bloom.html`, `predict.html`, `lab.html`.

## Knowledge checkpoints — `quiz.html`

Shape: `<div class="quiz" data-answer="1"><p class="q">…</p><ol class="opts"><li>…</li>…</ol><div class="explain">…</div></div>`; `data-answer` is the 0-based index of the correct option. 3–6 per module, each testing a concept the reader must transfer, not recall of a number. **Avoid** trick questions and options of unequal length that give the answer away.

## Exercises — `exercise.html`

Shape: `.exercise[id][data-difficulty=1..3]` > `.exercise-head` (`.exercise-label`, `.exercise-diff`, a time badge) + the problem statement + `details.hint` (one or more, revealed one by one) + `details.solution` (never open by default). The runtime renders the difficulty dots, adds a persisted "solved" checkbox (`store`, per browser), and locks hint k+1 until hint k is open; the solution is always openable. 2–4 per module unless the brief says otherwise; the brief's success test may require a count. **Use when** the reader should produce something — a number, a sketch, a few lines of code — with the running example's values. **Avoid** exercises whose solution is a sentence from the text; hints that give the answer; solutions that skip the arithmetic.

## Checklists — `checklist.html`

Shape: `<ul class="checklist" data-key="unique-key"><li>…</li></ul>`. Checkboxes, a per-list progress bar and Reset are added; state is saved per browser under `data-key` (keep keys unique site-wide; items flat, no nested lists). **Use when** design reviews, set-up procedures, release/safety checks, self-assessment, milestone trackers.

## Instructor notes and reading modes — `instructor.html` (B3)

Shape: `div.instructor` > `span.callout-title` "Instructor note" + any content (paragraphs, lists, a `table.rubric` with a `thead` and one criterion per row); `details.instructor` > `summary` + content for a long note. **Use when** the brief's `Use` is teaching or the learning design names an instructor: how to run an activity, what students get wrong, a grading rubric, timing. **Never** put a fact the reader needs only in an instructor block, and never leave one empty.

Runtime: every page has three reading modes on `<html data-mode>` (`reader` = no attribute, `instructor`, `handout`), cycled by the top-bar button `.mode-toggle` (R / I / H, title names the mode) and exposed as `QC.getMode()` / `QC.setMode(mode)`; the page fires `qc:mode` with `{ mode, prev }` on every change. The stylesheet does the work, so nothing leaks when JavaScript is off: reader hides `.instructor`; instructor shows it and opens every `details.solution`, `details.lab-answer` and `details.instructor`; handout hides instructor blocks, solutions, quiz and predict explanations, demo controls (the output stays), the "solved" checkboxes and the lab tools, turns quiz options into tick boxes and shows a `div.handout-head` "Name / Date / Group" line under the hero — print it as the student sheet. `?mode=handout` (or `instructor`, `reader`) in the URL forces a mode for that load without storing it, so a print link can be shared; otherwise the reader's choice persists under `learn:mode`. `QC.printHandout()` prints the page in handout mode and restores the previous mode afterwards (the lab sheet's button uses it). Print CSS: instructor blocks print in instructor mode with their notes; in handout mode the hidden parts stay hidden.

Rules: a rubric table has a `thead` (the first column is the criterion); keep instructor notes short and place them next to the activity they describe; the reviewer checks that no solution is repeated in plain prose outside `details.solution`, because that would print in the handout.

## Bloom tags and the outcome matrix — `bloom.html` (B5)

Shape: `data-bloom="remember|understand|apply|analyze|evaluate|create"` on `ol.objectives > li`, on `.quiz`, `.exercise` (also `.predict` and `.lab`); `data-objective="1,3"` on a checkpoint, predict block, exercise or lab = the 1-based positions in the page's objectives list it assesses; `<div class="outcomes" data-outcomes></div>` renders the page matrix, `data-outcomes="site"` the site-wide one, `data-outcomes="#id"` names the objectives list when a page has more than one (the style guide does). **Use when** the brief has a learning design (§13 of the brief template) with outcomes written as Bloom verbs: tag every objective with its level and every checkpoint and exercise with the objective it assesses, and put the page matrix at the end of `#objectives` or in `#deliverable`; the site matrix belongs on the overview or a roadmap page.

Runtime (`enhance`): a `span.bloom[data-level]` chip after each tagged item (six colours from the status variables) plus a small "obj. 1, 3" reference; the page matrix is a `table.outcome-matrix` with one row per objective (its text), one column per level (✓ for the objective's own level, plus links to the items that assess it at that level), and an "Assessed by" column; objectives nobody assesses are marked "not assessed". The site matrix lists every page of `DATA.manifest.pages[]` that carries `bloom` counts (the sitewide manifest builder counts the tags per page) with a totals row; without `assets/data.js` or without counts it shows a one-line note, never an error.

Rules: tag the level of the *objective*, not of the page; a checkpoint's `data-bloom` says what it tests, which may be lower than the objective's; indexes must stay valid when objectives are reordered.

## Predict-then-reveal — `predict.html` (B6)

Shape: `div.predict[data-demo="demo-budget"][data-preset="over"][data-answer="1"]` > `p.q` + `ol.opts` + `div.explain` — the quiz shape; `data-demo` is the id of a `.demo` on the same page, `data-preset` the name of a preset that demo defines (`demos/README.md`, `button[data-preset]`), `data-answer` the 0-based correct option. **Use when** a demo has a state worth guessing about before the reader sees it — the moment the formula stops being intuitive. Place it directly above the demo.

Runtime (`enhance`): options become buttons; on answer the block marks right/wrong, shows `.explain`, then calls `QC.applyPreset(demoId, preset)` when the demo block provides it and it returns true (the demo jumps to the predicted case), else scrolls the demo into view; a "Show me in the demo" link applies the preset again and scrolls. Handout mode hides the explanation and the link and turns the options into tick boxes.

Rules: one predict block per preset; the explanation says what the demo will show and why; the preset must exist on the demo (the validator checks the demo id, the runtime tolerates a missing preset).

## Lab sheet — `lab.html` (B7)

Shape: `section.lab[id][data-duration="45 min"]` > `div.lab-head` (`h3` title + badges: level, equipment count; the duration badge is added from `data-duration`) + `p.lab-aim` + `h4` "Procedure" + `ol.steps` + `h4` + `ul.checklist[data-key]` (safety or pre-flight, unique key) + `h4` "Readings" + `table.lab-record` (empty `td` cells are the fields to fill in) + `div.lab-report` (what to hand in) + optional `details.lab-answer` (expected results, never open). **Use when** the deliverable is something the reader does and hands in: a measurement, a build, a procedure with recorded values. A lab may carry `data-bloom` and `data-objective` like an exercise.

Runtime (`enhance`): the duration badge, a progress line "Checklist n / m" in the head that follows the checklist's own persisted state (including its Reset), and a "Print lab sheet" button that prints the page in handout mode (no solutions, no expected results, the Name / Date line) and restores the reader's mode. In print the lab keeps together where possible and empty cells get a dotted line to write on.

Rules: the checklist key is unique site-wide; steps are imperative and numbered; the readings table names the unit in its own column; expected results go only in `details.lab-answer` (instructor mode opens it, handout mode removes it).

## Validator messages this module can trigger

`quiz data-answer=n out of range (m options)` · `quiz without data-answer` · `module page has no knowledge checkpoints` · `exercise without id` · `exercise <id> has no solution` · `exercise <id>: solution open by default` · `exercise <id>: data-difficulty must be 1..3` · `instructor block is empty` · `table.rubric has no thead` · `data-bloom "x" is not a Bloom level` · `data-objective "x" is not a list of objective numbers` · `data-objective n but the page has m objectives` · `outcome matrix but the page has no ol.objectives` · `outcome matrix names missing list #id` · `predict block without data-answer` · `predict data-answer=n out of range (m options)` · `predict block without data-demo` · `predict block targets missing demo <id>` · `lab section without id` · `lab <id> has no steps` · `lab <id> has no checklist` · `lab <id>: checklist without data-key` · `lab <id>: answer open by default`.
