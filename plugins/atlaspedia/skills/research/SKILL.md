---
name: research
description: Stages 2 and 3 of the atlaspedia learning workflow — writes the research brief from the confirmed insight (brief-author + fresh-eyes reviewer), gets it approved, then runs parallel researcher, verifier and consolidator agents that fill topics/<slug>/tmp/dossier/ with verified sources. Use when invoked as /atlaspedia:research <slug>, or by /atlaspedia:go when the plan's stage is brief or research. Needs a plan whose insights row is [x].
argument-hint: "<slug> [--brief-only]"
disable-model-invocation: true
---

# atlaspedia:research — stage 2 (brief) and stage 3 (research)

You dispatch, gate and flip. Agents write every content file. Above everything: `${CLAUDE_PLUGIN_ROOT}/references/evidence-policy.md` — the dossier holds only what retrieved sources state, with locators, documented calculations (`C` ids) and documented relationships (`R` ids); `check_dossier.py` enforces the mechanical half (no `estimate`, no `model knowledge`, every demo candidate on a `C` id, every page block's demos and diagrams traced) and you never pass a file it fails. Contracts: `${CLAUDE_PLUGIN_ROOT}/references/contracts.md` (§3 plan, §5 brief, §6 dossier, §9 scripts, §10 agents, §11 dispatch, §13 topic.json). References in this skill: `references/brief-template.md`, `references/research-protocol.md`, `references/dossier-template.md`.

`PLUGIN_ROOT` = `${CLAUDE_PLUGIN_ROOT}` (contracts §12). `TOPIC_DIR` = `<repo root>/topics/<slug>/`. `PLAN` = `<TOPIC_DIR>/PLAN.md`. `TMP` = `<TOPIC_DIR>/tmp/`. `SCRIPTS` = `<PLUGIN_ROOT>/scripts`. `REFS` = `<PLUGIN_ROOT>/skills/research/references`. Date = today, `YYYY-MM-DD`. Absolute paths in every dispatch; label every value with the agent's input name (contracts §11).

Every dispatch below ends with: `End with Friction lines and the RESULT line (contracts §10).` On every report: parse `RESULT:`; `files=` empty → nothing is flipped; run the gate on each named file; flip only on PASS. **Retry rule:** one retry, narrowed to the failing items with the gate's lines pasted verbatim; a second failure → `[SKIP]` + `Changed n` note, continue. Never do an agent's work yourself.

## Part A — the brief (stage `brief`)

**HARD GATE:** `python <SCRIPTS>/check_plan.py <PLAN> --before brief` must PASS. FAIL → show the lines, stop (stage 1 owns the fix). If the Progress row `brief` is already `[x]`, skip to Part B.

1. **Hash.** `python <SCRIPTS>/check_plan.py <PLAN> --hash` → `HASH: <12hex>`. Keep it; the author writes it into the brief.
2. **Author.** Read the plan's title, `**Format**` (missing = `site`) and `How` line — nothing else.

   ```
   Agent  subagent_type: "atlaspedia:brief-author"
   SLUG: <slug>   TITLE: <plan title>   DATE: <date>   PLUGIN_ROOT: <abs>
   PLAN: <PLAN>   (read "## What I want" only)
   INSIGHTS: <TMP>/INSIGHTS.md
   FIELD_MAP: <TMP>/FIELD_MAP.md   (may be missing)
   TEMPLATE: <REFS>/brief-template.md     PROTOCOL: <REFS>/research-protocol.md (§1, §5)
   HASH: <12hex>
   HOW: <the How line>
   FORMAT: <site|single>
   OUT: <TMP>/BRIEF.md   (write ONLY this file; Status Draft; the hash in the header)
   ```

   Report keys: `modules= synthesis= topics= priority=`. `modules=0` or `priority=` missing → retry once narrowed ("the brief has no priority module / no modules").
2a. **Size check — Format single only.** Run `python <SCRIPTS>/estimate_size.py <PLAN>`. `fits=yes` → go on. `fits=no` → the topic is too long for one page; `AskUserQuestion`, header `Format`, the question naming the numbers ("The brief has <parts> parts and <topics> topics, about <est_kb> KB; one page holds about <budget_kb> KB."):
   - `Full multi-page site (Recommended)` — "Same template, every topic kept, one page per module." → set the plan's `**Format**: site`, `Changed n` note, re-dispatch the author with `FORMAT: site` and `FIX: format is now site — rescale to the site sizes (8–16 modules, 15–40 topics), keep every topic the single brief had, switch §1's output line and §9 to the site variant; keep the hash`.
   - `Single page, trimmed to fit` — "Keep one page; the least important topics move to Out of scope." → re-dispatch the author with `FORMAT: single`, `BUDGET: <budget_kb> KB; current estimate <est_kb> KB; per part: <the script's part lines>` and `FIX: trim to the budget`. Run the estimate again; still `fits=no` after this one trim → keep it and add a `Caveat n` ("the single page is over budget: about <est_kb> KB").
   - `Single page, keep everything` — "One long page of about <est_kb> KB; slower to scroll and load." → `Caveat n` note with the estimate; go on.
   Any change of format goes into `topic.json` `format` at the stage close. Format site → skip this step (the outline still shows the estimate).
3. **Fresh-eyes review.** The reviewer never sees the interview log or the author's reasoning.

   ```
   Agent  subagent_type: "atlaspedia:brief-reviewer"
   SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
   BRIEF: <TMP>/BRIEF.md
   PLAN: <PLAN>   (read "## What I want" only)
   INSIGHTS: <TMP>/INSIGHTS.md   (sections "## Refined insight" and "## How (derived policies)" ONLY — never "## Interview log")
   OUT: <TMP>/BRIEF_REVIEW.md   (write ONLY this file)
   ```

   `verdict=REVISE` with `must_fix>0` → re-dispatch the author with `FIX: F-01, F-02 …` ("apply these must-fix items from <TMP>/BRIEF_REVIEW.md; change nothing else; keep the hash"). Then review again. At most two review rounds; after that, remaining must-fix items go to the user as part of the outline.
4. **Outline for the user.** Read only the brief's module headings and each module's first line and `Deliverable` line (Grep `^### [MS]\d\d|^\*\*Deliverable|^Level:`). Show in chat: the format ("one single page" or "full multi-page site"), one line per module (`M01 Title — scope — deliverable`), the synthesis parts, the `How` line, the priority module, estimated size (single: `est_kb` from `estimate_size.py` against the budget; site: modules × 70–160 KB), and open must-fix items if any. If the user's revision text asks for the other format, apply it as in step 2a's first option (or its reverse) and show the outline again.
5. **Approval gate.** `AskUserQuestion`, header `Brief`: `Approve — start research (Recommended)` · `Revise (I'll comment)` · `Approve brief only — stop`.
   - Revise → the user's text becomes a narrowed author dispatch (`FIX:` + the user's words: "apply these changes; keep everything else"); review again (step 3) only if modules were added or removed; show the outline again; ask again.
   - Either approve → set `**Status**: Approved` and `**Updated**` in `BRIEF.md`; transcribe the module headings (`### M01 — Title`, `### S01 — Title`, in order) into `## Modules` of the plan as `| M01 | Title | [ ] | [ ] | [ ] |`; `Checked` is `[SKIP]` for every `S` row and for every row when the `How` line says `verify light`. Flip `brief` to `[x]`, `**Stage**: research`, `**Updated**`, `## Next`. Set `topic.json` `status: "research"`, `updated`, `format` (the plan header); run `python <SCRIPTS>/build_index.py <repo root>`.
   - **Run the gate:** `python <SCRIPTS>/check_plan.py <PLAN> --before research` must PASS (it recomputes the hash against the brief). FAIL on `hash` → the insight changed after the author ran: go back to step 1.
   - "Approve brief only — stop" or `--brief-only` → write `## Next` (``Run `/atlaspedia:go <slug>` — it will research the <n> modules.``), report (modules, priority, size estimate, next command) and stop.

## Part B — research (stage `research`)

**HARD GATE:** `python <SCRIPTS>/check_plan.py <PLAN> --before research` must PASS. Then `python <SCRIPTS>/next_stage.py <PLAN>` lists the open rows; work only on them (a resumed session dispatches only what is still `[ ]`).

Policies from the `How` line: `DEPTH`, `VERIFY`; `FORMAT` from the plan header. **Format single**: researchers get `FORMAT: single`, and the dossier gate runs with `--depth overview` unless `DEPTH` is `monograph` (a part of one page needs fewer sources than a page of its own). Format site: the gate depth is `DEPTH`. Module file names: `<TMP>/dossier/<id lowercase>-<title slug ≤ 30 chars>.md`, e.g. `m01-coordinates.md`, `s01-project.md` — decide them once, use the same names in every dispatch and in `## Notes`. Running example: the brief's §7 anchor example.

### B1. Researcher waves

Group the open `Researched` rows: the priority module alone; otherwise 1–3 modules per agent, related modules together; `S` rows go with the agent whose modules overlap most (the brief's `## 12. Research allocation` suggests groups — follow it unless a row is already done). **≤ 5 agents per wave, all in one message**; further waves after the first returns.

```
Agent  subagent_type: "atlaspedia:module-researcher"
SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
MODULES: M04, M05
FILES: M04 → <TMP>/dossier/m04-….md, M05 → <TMP>/dossier/m05-….md   (write ONLY these files)
BRIEF: <TMP>/BRIEF.md   (read §1, §2, §7 and the sections of your modules only)
PLAN: <PLAN>   (read "## What I want" only)
PROTOCOL: <REFS>/research-protocol.md     TEMPLATE: <REFS>/dossier-template.md
HOW: <the How line>   FORMAT: <site|single>
EXAMPLE: <anchor example and where its numbers are: brief §7, or <TMP>/dossier/00-overview.md §1 if it exists>
POLICY: <PLUGIN_ROOT>/references/evidence-policy.md
Only what a retrieved source states, with its locator; formulas to Documented calculations (C ids), relationships to Documented relationships (R ids); user-stated values as `user`; what you cannot establish under Could not verify with its evidence label. Never estimate, never from memory.
```

Per report: for each named file run `python <SCRIPTS>/check_dossier.py <file> --depth <gate depth>` (see above). PASS → flip that row's `Researched` to `[x]`. FAIL → retry rule (`NARROW:` + the gate's lines, same file). `status=PARTIAL` with a module not written → that module stays `[ ]` and joins the next wave. `unverified=` > 0 → remember the count for the caveat note.

### B2. Verifier wave

Skip when `VERIFY` is `light` (rows already `[SKIP]`). Otherwise one agent per dossier file whose `Researched` is `[x]` and `Checked` is `[ ]`, all in one message (≤ 8; haiku is cheap):

```
Agent  subagent_type: "atlaspedia:source-verifier"
SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
FILE: <TMP>/dossier/m04-….md
VERIFY: <strict|standard>
Run first: python <PLUGIN_ROOT>/scripts/check_links.py <FILE>   (writes the .links.md report beside the file)
Edit ONLY the Verified column of "## Sources" and "## Media candidates" in FILE (and empty Author/Licence/Artist cells of media rows), add "## Could not verify" lines when strict, append "## Verification log". Never delete a row.
```

Per report: `files=` names the dossier file → run `check_dossier.py` on it again (the file must still pass) → flip `Checked` to `[x]`. `failed=` > 0 is normal (the writer will see the marks); it is not a FAIL. A report naming no file → retry once; then `Checked` stays `[ ]` with a `Caveat` note.

### B2a. OpenAlex enrichment (I5, opt-in)

Run only when the brief's §2.1 `Discovery` line is not `none` or `VERIFY` is `strict`; otherwise skip (default runs are unchanged). It spends no web searches.

```
python <SCRIPTS>/enrich_openalex.py <TOPIC_DIR>          (set ATLAS_OPENALEX_MAILTO in the environment to join OpenAlex's polite pool; never write an address into a file)
```

It caches every DOI and arXiv record in `<TMP>/openalex.json` and appends a `## OpenAlex enrichment` section with one `Enriched:` line per source to each dossier file. Read only its problem lines and `RESULT:`. `retracted=` > 0 (status FAIL) → re-dispatch the module's researcher narrowed (`NARROW:` + the error lines: "drop or replace the retracted source, or cite it only as retracted with a reason"), then run `check_dossier.py` and the script again. Year-mismatch warnings go to the consolidator's dispatch as `ENRICH:` lines. A network failure is a warning, never a stop: the run continues from the cache (`--offline` reads only the cache). Run `check_dossier.py` on each file again; it must still PASS.

### B3. Consolidate

When every row's `Researched` and `Checked` are `[x]` or `[SKIP]`:

```
Agent  subagent_type: "atlaspedia:dossier-consolidator"
SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
DOSSIER_DIR: <TMP>/dossier/   (read every file except *.links.md)
BRIEF: <TMP>/BRIEF.md   (§1–§4, §7, §9, §11 and the module headings)
PLAN: <PLAN>   (read "## Modules" and "## What I want")
TEMPLATE: <REFS>/dossier-template.md   (the 00-overview block)
HOW: <the How line>
OUT: <TMP>/dossier/00-overview.md   (write ONLY this file — sections 1–8, one "### Page …" block per future page incl. index, bibliography, glossary; contracts §6)
POLICY: <PLUGIN_ROOT>/references/evidence-policy.md   (§7: each page block asks for the visuals its evidence supports — Demos name C ids, Diagrams name R ids or source #s, else `none — <why>`)
ENRICH: <the enrich_openalex.py warning lines, when B2a ran — year mismatches go to §6 conflicts; keep each source's Kind in the bibliography seed>
```

**Run the gate:** `python <SCRIPTS>/check_dossier.py <TMP>/dossier/00-overview.md --overview`. FAIL → retry rule; a second failure stops the stage with the lines shown to the user (the consolidator is on the critical path; nothing is skipped here).

### B4. Close the stage

1. Flip `research` to `[x]`, `**Stage**: compose`, `**Updated**`, `## Next`: ``Run `/atlaspedia:go <slug>` — it will build the site (<n> pages).``
2. `## Notes`: a `Changed n` for every `[SKIP]` that needs one (names the id and the reason); a `Caveat n` with the total of unverified items ("listed in tmp/dossier/00-overview.md §7"); a `Lesson n` per `Friction:` line.
3. `topic.json`: `status: "compose"`, `updated`; run `python <SCRIPTS>/build_index.py <repo root>`.
4. **Run the gate:** `python <SCRIPTS>/check_plan.py <PLAN> --before compose` must PASS.

## Report to the user

Six lines at most: modules researched / skipped; sources by tier (sum of the researchers' `t1= t2= t3=`); documented calculations and relationships (sum of `calcs= relations=`); unverified items and items the sources could not establish; `failed=` links the verifier marked; the overview path; the next command. No content from the dossier.

## Rules

- Never read a dossier file in full; read `RESULT:` lines, gate output, and the review's verdict table.
- Never flip a row on a report that names no files. Never flip on your own reading — on the gate.
- `AskUserQuestion` only at the size check (single format, `fits=no`), at the approval gate, and after a second failure of the consolidator.
- The consolidator's build notes are the same for both formats (one `### Page` block per future page), so a later switch from single to site needs no new research.
- A changed `How` line or `## What I want` after approval invalidates the brief (hash) — say so and return to Part A.
