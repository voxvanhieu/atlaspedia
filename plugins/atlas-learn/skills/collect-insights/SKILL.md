---
name: collect-insights
description: Stage 1 of the atlas-learn learning workflow — an adaptive AskUserQuestion interview that pins down what the user wants to learn and why (goal, motivation, use, starting point, direction, boundaries, success test — never delivery details), refines it through a subagent into topics/<slug>/tmp/INSIGHTS.md and writes the short topics/<slug>/PLAN.md. Use when the user wants to "research a topic", says "I want to learn/study X", "plan a learning document about X", or invokes /atlas-learn:collect-insights. Not for quick factual questions.
argument-hint: "<topic> [--single|--site]"
---

# atlas-learn:collect-insights — stage 1, the insight

You run the interview yourself (only the main agent can ask the user). Everything else — mapping the field, refining the answers into a clear insight — goes to agents. The whole workflow runs under `${CLAUDE_PLUGIN_ROOT}/references/evidence-policy.md`; at this stage that means two things: interview options are questions, not findings, and a fact the user states is recorded as user-provided, to be checked by the research, never as established. Contracts: `${CLAUDE_PLUGIN_ROOT}/references/contracts.md` (§2 files, §3 plan, §4 INSIGHTS.md, §10 agents, §11 dispatch, §13 topic.json). Question rules: `references/interview-guide.md`. File shapes: `references/insights-template.md`, `${CLAUDE_PLUGIN_ROOT}/references/plan-template.md`.

`PLUGIN_ROOT` = `${CLAUDE_PLUGIN_ROOT}` (resolve per contracts §12). `TOPIC_DIR` = `<repo root>/topics/<slug>/`. `TMP` = `<TOPIC_DIR>/tmp/`. `PLAN` = `<TOPIC_DIR>/PLAN.md`. Today's date in `YYYY-MM-DD`. Absolute paths in every dispatch; label every value with the agent's input name (contracts §11).

## 0. Start

1. Topic text from the argument; none → ask for it in chat, one line, before any `AskUserQuestion`. A `--single` or `--site` flag is not part of the topic: keep it as `FORMAT` for the refiner. The format is never asked in the interview; it is derived or forced.
2. Slug: lowercase, words joined by `-`, `[a-z0-9-]` only, ≤ 24 characters, short and memorable (`map-projections`).
3. **Existing slug rule.** If `TOPIC_DIR` exists: `AskUserQuestion` — `Resume (Recommended)` (keep the log, continue from the open gaps) · `Start over` (overwrite `tmp/INSIGHTS.md` and the plan; dossier and site, if any, are left alone) · `New slug` (type it). Never overwrite silently.
4. Create `TOPIC_DIR`, `TMP` and `TMP/INSIGHTS.md` from `references/insights-template.md`: header filled (Title = topic in title case, Slug, `Status: Draft`, Updated, `Rounds: 0`), sections 1–3 left as the template's placeholders, `## Interview log` empty. Do **not** create the plan or `topic.json` yet — they are written once, complete, in step 4.
5. **Launch the scout in the background now**, before the first question, so its map is ready by round 2:

   ```
   Agent  subagent_type: "atlas-learn:field-scout"   run_in_background: true
   TOPIC: <topic text, verbatim>
   SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
   OUT: <TMP>/FIELD_MAP.md   (write ONLY this file)
   Budget: 2–5 WebSearch calls, standard mode, in one batch. No deep research.
   End with Friction lines and the RESULT line (contracts §10).
   ```

## 1. Interview — adaptive, goal and direction only

**HARD GATE: every question is about one of the seven dimensions in `interview-guide.md` (goal, motivation, use, starting point, direction, boundaries, success test). Delivery policies (depth, verification, freshness, media, demos, language, region, page count) are never asked; the refiner derives them.**

Loop, one `AskUserQuestion` call per round:

1. Mark each dimension `known` (answered by the opening message or an earlier round), `you-decide`, or `open`. Pick the 1–3 open dimensions whose answer would change the research most. Round 1 is always Goal (+ Motivation or Use); later rounds are written from the previous answers.
2. Write the questions by the rules in `interview-guide.md` §2: options derived from the user's last answer and from `TMP/FIELD_MAP.md` when it exists (read it once per round; if the scout has not finished, phrase options from the field's common vocabulary — do not wait; an option is a direction the user may choose, never a factual claim, and nothing in it reaches a page without research); recommended option first with "(Recommended)"; every option says what it changes; `multiSelect` where answers are not exclusive; headers ≤ 12 characters.
3. Ask. Then **append the round to `## Interview log` immediately** (`### Round n — date`, each question with dimension, options offered, answer verbatim) and bump `**Rounds**`. Free-text answers are logged verbatim too.
4. Reply with one line restating what is settled so far (guide §6), then the next round.
5. Stop when every dimension is `known` or `you-decide`, after 5 rounds, or when the user says "enough" / "go". Minimum two rounds unless the opening message already covers goal and direction (guide §4 fast paths).

## 2. Refine

Dispatch the refiner (foreground; it is the critical path):

```
Agent  subagent_type: "atlas-learn:insight-refiner"
SLUG: <slug>   DATE: <date>   PLUGIN_ROOT: <abs>
INSIGHTS: <TMP>/INSIGHTS.md   (the interview log is the evidence; write ONLY this file — fill
          "## Refined insight", "## How (derived policies)", "## Open gaps"; never edit the header's Rounds or the log)
FIELD_MAP: <TMP>/FIELD_MAP.md   (may be missing)
TEMPLATE: <PLUGIN_ROOT>/skills/collect-insights/references/insights-template.md
GUIDE: <PLUGIN_ROOT>/skills/collect-insights/references/interview-guide.md  (§3 policy mapping, §7 gap admission test)
FORMAT: <single|site>   (only when the user passed --single/--site; it wins over the derivation)
End with Friction lines and the RESULT line (contracts §10): … gaps=<n> blocking=<n> …
```

Parse the `RESULT:` line. `files=` empty → treat as FAILED (retry once; then tell the user and stop).

**Gap loop.** `blocking > 0` → read only the `## Open gaps` table, ask the blocking gaps in one `AskUserQuestion` round (same rules; a gap the user answers with "you decide" is closed with the refiner's recommendation), log the round, set those gap rows to `answered` / `you-decide`, and re-dispatch the refiner **narrowed** with `GAPS: G-xx, G-yy` ("update only the sections touched by these gaps; keep the rest"). At most two gap rounds; after that, remaining blocking gaps become `you-decide` and a `Caveat` note in the plan.

## 3. Confirm

1. Read `## Refined insight` and `## How` (they are short). Show the user a **6-line summary** in chat: Goal · Focus · Skip · Done when · How (policies in one line, starting with the format: "one single page" or "full multi-page site") · "Edit `topics/<slug>/tmp/INSIGHTS.md` to change anything, or run `/atlas-learn:go <slug> --single|--site` to switch the format; say 'go' to continue." Do not ask another question unless the user replies with a change — then log a round and go back to step 2 narrowed.
2. Set `**Status**: Confirmed` and `**Updated**` in `INSIGHTS.md`.

## 4. Write the plan, the topic card, the dictionary

1. Create `PLAN` from `plan-template.md`. Fill the header (`Slug`, `Folder: topics/<slug>/`, `Stage: insights`, `Format` = the `Format` row of the policies table, `Readers` = the persona names of the `Readers` row (I1; derived, never asked), `Discovery` = the `Discovery` row (I5; omit the line when it is `none`), `Updated`) and `## What I want`: **one sentence per key, simple words**, transcribed from `## Refined insight` (Goal, Why, Use, Start, Focus, Skip, Done when) and the `How` line from the policies table (`depth … · verify … · demos … · media … · language`). No `{placeholder}` may remain; `## Modules` stays an empty table; `## Notes` empty or with the caveat from the gap loop.
2. Flip the `insights` Progress row to `[x]`, set `**Stage**: brief`, `**Updated**`, and `## Next`: ``Run `/atlas-learn:go <slug>` — it will write the research brief and ask you to approve it.``
3. **Run the gate, do not eyeball:** `python <PLUGIN_ROOT>/scripts/check_plan.py <PLAN>`. FAIL → fix the plan lines it names (shape only; never change the meaning of an answer) and run again. Then `python <PLUGIN_ROOT>/scripts/check_plan.py <PLAN> --before brief` must PASS too.
4. Write `<TOPIC_DIR>/topic.json` (contracts §13): `code` = slug, `name` = the plan title, `description` ≤ 160 characters in plain words, `tags` 1–8 (field-map themes + the user's own words, lowercase kebab-case), `status: "brief"`, `created` = `updated` = today, `pages: 0`, `entry: "index.html"`, `format` = the plan's `**Format**`.
5. Run `python <PLUGIN_ROOT>/scripts/build_index.py <repo root>` so the root dictionary lists the topic (it creates `index.html` at the root the first time).
6. Append every `Friction:` line from the scout and the refiner as `Lesson n (insights, date): …` in `## Notes`.

## 5. Report

Four lines: the slug and plan path; rounds asked and gaps closed; the scout's `themes=`/`modules=` numbers; the next command. Nothing else — the insight is in the files.

## Rules

- Never ask what the user already said; never re-ask a logged answer. Never ask a "looks good?" question — the summary in step 3 is a statement.
- Never write the refined insight yourself; the refiner does. Never read the scout's or refiner's transcript; read their files and `RESULT:` lines.
- Never flip the Progress row on a refiner report that names no files.
- Keep chat short; every detail belongs in `INSIGHTS.md`.
