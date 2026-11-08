# Interview guide — adaptive questions about the goal and the direction

The interview has no fixed questions. It has a **checklist of seven dimensions**, rules for writing each round from what the user said before, and stop rules. The main agent asks with `AskUserQuestion`; the refiner agent turns the log into the insight and names the gaps.

## 1. The checklist

| Dimension | What it clarifies | Seed (adapt the wording to the topic and the last answer) |
|---|---|---|
| Goal | what the user wants to be able to do afterwards | "After this, what should you be able to do with {topic}?" |
| Motivation | why now; what triggered it | "What brought this up — a project, something that broke, a decision, curiosity?" |
| Use | what the document is for and how it will be read | self-study · reference while building · teaching others · deciding something |
| Starting point | what the user already knows, has and has tried | "Which of these do you already know well?" (options from the answer + field map) |
| Direction | the angles that matter, the must-answer questions, the anchor example | "You said {X} — which part is the real blocker?" / "What should the report anchor on?" |
| Boundaries | what to leave out; constraints; sources trusted or distrusted | "What should the research not spend time on?" |
| Success test | how the user will know it worked | "Done when you can …?" |

A dimension is **closed** when the user answered it, the opening message answered it, or the user said "you decide" (then the recommended option is logged as the answer with "(you decide)").

## 2. Writing a round

- 1–3 questions, each on one open dimension; never two questions on the same dimension in one round.
- **Options come from the previous answers and from `FIELD_MAP.md`** (its subfields, tools, platforms, example candidates, safety angles) — not from a generic list. Name the field's real things.
- Recommended option first, label ending in "(Recommended)". Labels ≤ 5 words, headers ≤ 12 characters, 2–4 options. Every option's description says **what choosing it changes in the research** (which modules appear, what gets deep treatment, what is dropped).
- `multiSelect: true` when answers are not exclusive (starting point, boundaries, must-answer questions).
- Round 1 is Goal, plus Motivation or Use. Rounds 2+ are built from the answers: quote the user's words in the question ("You said you want to …").
- Never ask what the opening message or an earlier round already answered. Never ask a delivery question (§3). Never ask "does this look right?" — restate instead (§6).
- When a free-text answer covers several dimensions, close all of them and log the answer under each.

## 3. Never asked — derived instead

Delivery policies are decided by the refiner from the insight, written to `INSIGHTS.md` → `## How (derived policies)` with a "Because", and shown to the user at brief approval, where one line of free text overrides any of them.

| Policy | Default | Raised / lowered when |
|---|---|---|
| Document type | textbook curriculum | use = "reference while building" → project guide; use = "deciding" → engineering handbook; goal = "read the literature" → research survey |
| Format | site | use = quick reference, cheat sheet, one-pager, "explain it to me / to a colleague", a decision memo; goal = one technique or concept rather than a field; start = expert refresh → single. A forced `--single`/`--site` wins. A single page holds about 2–6 parts; the brief stage checks the size and asks before switching |
| Depth | textbook | starting point = expert refresh → overview; goal = research-ready → monograph on the focus modules; mixed when the focus is narrow and the rest is context |
| Verify | standard | success test involves numbers the reader will act on, or safety → strict; "just orient me" → light |
| Freshness | foundational + through the current year | focus names a tool or product → its current version, dated; motivation = "history/why" → + history |
| Demos | rich | depth overview or use = teaching slides → moderate; "static document" → minimal |
| Media | diagrams + verified photos | anchor example is a physical object → + photos; lectures named in Start → + video |
| Language, units | English, SI | user writes in another language or names units |
| Region | international overview | focus or boundaries name a jurisdiction |
| Must cite | none | starting point or boundaries name sources the user owns, trusts or must follow (a textbook, a standard, a vendor's documentation, a course reader) → listed; the researchers search them first and every module that touches them cites them |
| Must avoid | none | boundaries name distrusted or excluded sources ("no blog numbers", "not vendor X", "no Wikipedia-only facts") → listed; never cited, not even as "reported" |
| Citation style | numeric | use = teaching, or goal = read the literature / research survey → author-year |
| Licence | all rights reserved, personal use | use = teaching others, or the user says the result will be shared or published → CC BY 4.0 (CC BY-SA 4.0 when they say share-alike); a licence the user names wins |
| Accessibility | none | anything the user says about reading: "big screen"/"small phone"/"eyes tire" → large text; dyslexia named → dyslexia; a screen reader or keyboard-only use → screen reader; motion sickness or "no animations" → reduced motion |
| Readers | creative student | use/goal = reference while building, sizing, choosing parts → engineer; firmware, protocols, "code it" → software developer; schematics, PCB, analog → circuit designer; read the literature, a thesis → researcher; derivations from first principles → fundamental sciences; teaching, a course → instructor; phone reading or assistive technology as the main constraint → accessibility/mobile. One or two personas, with the user's words quoted as the reason |
| Discovery | none (today's search budgets) | software developer → code, standards; researcher → datasets (+ code when reproducing results); engineer, circuit designer → standards; instructor → lectures; fundamental sciences → datasets; a class the user names ("real data", "open-source code", "the IEEE standard", "lecture videos") → added. Each class adds at most 2 searches per module |

**Personas are derived, never asked (I1).** There is no persona round and no "who is this for?" question: the reader emphasis (the `Readers` row) comes from the Use and Goal answers, and the source classes (the `Discovery` row) from Use, Goal and Readers. When the words point two ways, the refiner records its choice and at most one non-blocking `you-decide` gap; that gap is never asked as a question.

Scope (the module list) is also not asked as a fixed round: Direction answers feed the brief author, and the user confirms the proposed modules at brief approval.

## 4. Fast paths

- **Detailed opening message** → close every dimension it answers (log them as "Round 0 — from the opening message"); ask only the open ones. If goal and direction are both covered, one round (boundaries + success test) is enough.
- **"Defaults" / "you decide"** → close the named dimensions with recommendations; still ask Goal if it is not stated — the goal cannot be guessed.
- **An existing brief, prompt file or notes** named by the user → read it, log what it answers, ask only what it lacks (usually motivation, starting point, success test).
- **A one-word topic** → round 1 asks Goal and Use with options phrased in the field's common vocabulary (the scout is not back yet). Options are directions to choose, not facts: nothing in them reaches the site without research (`references/evidence-policy.md` §1).

## 5. Stop rules

Stop asking when all seven dimensions are closed, after 5 rounds, or when the user says "enough", "go", "that's it". Minimum two rounds unless §4 applies. Then dispatch the refiner. Gap rounds (asked after the refiner) count separately: at most two.

## 6. Between rounds

One line, then the next `AskUserQuestion`: "So far: goal {…}; use {…}; focus {…}; skip {…}; open: {dimensions still open}." Corrections arrive as free text; log them as part of the next round.

## 7. Gap admission test (applied by the refiner)

A gap goes into `## Open gaps` only if a human must decide it. It is **blocking** only if the answer would change which modules exist or what the research goes after (direction, anchor example, a boundary that removes a theme). Everything else is non-blocking: the refiner picks a recommendation, writes it into the insight with "(recommended)" and lists the gap as `you-decide`. Wording, formatting and policy choices are never gaps.

## 8. Worked example

Topic: "map projections".

**Round 1** — Goal: "After this, what should you be able to do with map projections?" · `Choose and apply one for my own maps (Recommended)` — research leans to practical modules, code and tooling · `Pass a cartography or GIS course/exam` — derivations and exercises lead · `Compare projections for a project` — comparison tables lead · `Read the research literature` — survey and open problems lead. Use: `Self-study (Recommended)` · `Reference while building` · `Teach it`.
User: *"pick the right one for my world maps and code the equations; self-study then reference while building."* → Goal, Use closed; Motivation partly (a mapping project).

**Round 2** — written from that answer and `FIELD_MAP.md`: Direction (multiSelect) "You said world maps — which parts are the real blockers?" `Why sizes look wrong and how to measure it (Recommended)` — a module on distortion and Tissot's indicatrix · `Conformal vs equal-area trade-offs` — a comparison module and demo · `Datums and coordinate systems` — a geodesy module · `Doing it in code` — an implementation module with PROJ and Python. Starting point (multiSelect) "Which do you already know well?" `Trigonometry` · `Basic GIS tools` · `Python` · `None of these`.
User: *"distortion and the trade-offs; I know the maths, not the GIS tooling."* → Direction, Starting point closed.

**Round 3** — Boundaries (multiSelect) "What should the research leave out?" `Long derivation proofs (Recommended)` · `Polyhedral and artistic projections` · `Surveying-grade geodesy` · `Keep everything`. Success test "Done when you can …?" `Project your dataset with PROJ and compare Mercator with an equal-area map (Recommended)` — the project module ends with that comparison · `Draw Tissot's indicatrix for three projections` · `Explain each choice to a teammate`.
User picks the recommended options and adds *"My data is a world table of country areas."* → all closed after 3 rounds. The refiner then derives: project guide with textbook modules, depth textbook on distortion + trade-offs, verify standard, freshness foundational + current PROJ version dated, demos rich on distortion, media diagrams + historical maps — and raises one non-blocking gap ("anchor on Equal Earth or Mollweide as the equal-area example?") as `you-decide` with Equal Earth recommended.

A different round-1 answer ("pass my exam") would have produced entirely different rounds 2 and 3 (derivation depth, exercise style, which theorems).
