---
name: go
description: Entry command of the atlas-learn learning workflow — runs the next unfinished stage (insights → brief → research → compose) of a topic from topics/<slug>/PLAN.md, or starts a new topic. Use when the user types /atlas-learn:go, says "continue the research", "next stage", "resume <slug>", or "start researching <topic>".
argument-hint: "<topic or slug> [--all] [--single|--site]"
disable-model-invocation: true
---

# atlas-learn:go — run the next stage

One command, one stage. The plan decides what happens; you only read it, run the stage's skill and stop. Every stage runs under `${CLAUDE_PLUGIN_ROOT}/references/evidence-policy.md` (interactive visualization of verified information; nothing the sources do not establish); when you relay a stage's result, relay its caveats and gaps as they are, never as complete. Contracts: `${CLAUDE_PLUGIN_ROOT}/references/contracts.md` (§1 stages, §2 files, §3 plan, §12 plugin root).

## Steps

1. **Resolve the plugin root.** `PLUGIN_ROOT` = `${CLAUDE_PLUGIN_ROOT}`. If that text is not an absolute path, find it once with Glob `**/plugins/atlas-learn/.claude-plugin/plugin.json` and use its folder. Pass `PLUGIN_ROOT` to every script call and dispatch.
2. **Find the plan.** Glob `topics/*/PLAN.md` from the repo root; the slug is the folder name.
   - The argument matches an existing slug (exactly, or as the only slug that contains every word of the argument) → that plan.
   - No match → treat the argument as a new topic. Derive the slug: lowercase, words joined by `-`, only `[a-z0-9-]`, ≤ 24 characters, no leading/trailing `-`, short and memorable (`map-projections`, not `how-map-projections-work-for-my-maps`). If `topics/<slug>/PLAN.md` now exists, use it; else go to step 3.
   - No argument and no plan → ask in chat, in one line, for the topic. No argument and exactly one plan → use it. Several plans → list them (slug and `**Stage**`) and stop.
3. **New topic** → invoke the skill `atlas-learn:collect-insights` with the topic text and the `--single`/`--site` flag when given (Skill tool). When it finishes, go to step 6.
3a. **Format flag on an existing plan** (`--single` or `--site`): when the plan's `**Format**` differs and `**Stage**` is not `done`, set the header to the new value, append `Changed n (<stage>, <date>): format <old> → <new>, asked by the user`, and continue. The stage skills read the header; a brief written for the other format is re-checked at the brief stage, and at the compose stage the switch reuses the dossier as it is. At `done`, say that a rebuild means running compose again and stop.
4. **Existing plan** → run the gate first, then the stage reader. Do not read the plan by eye to decide the stage:
   ```
   python <PLUGIN_ROOT>/scripts/check_plan.py topics/<slug>/PLAN.md
   python <PLUGIN_ROOT>/scripts/next_stage.py topics/<slug>/PLAN.md
   ```
   If the gate FAILs, show its lines to the user and stop — a broken plan is fixed by the user or by the stage that owns the broken part, never by guessing.
5. **Invoke the stage skill** named by the `stage=` value of the `RESULT:` line:
   | `stage=` | Skill to invoke | What it does |
   |---|---|---|
   | `insights` | `atlas-learn:collect-insights <slug>` | finishes the interview (log and plan exist) |
   | `brief` | `atlas-learn:research <slug>` | writes and approves the brief; on "Approve — start research" it continues into research |
   | `research` | `atlas-learn:research <slug>` | researches the open module rows, verifies, consolidates |
   | `compose` | `atlas-learn:compose <slug>` | builds, validates and reviews the site, or the single page (`format=single`) |
   | `done` | — | say the topic is done; offer: open `topics/<slug>/index.html`, add modules (needs a new brief round), start a new topic |
6. **Stop or continue.**
   - Without `--all`: stop after the stage's skill returns. Reply with the plan's `## Next` line so the user knows the next command.
   - With `--all`: run `next_stage.py` again and invoke the next skill, until `done` or until a skill stops at a gate (brief approval, a stage that failed twice, an existing-slug question). Gates always ask; `--all` never skips them.

## Rules

- You never write the plan, `topic.json` or the root dictionary in this skill; the stage skills own them. The one exception is step 3a: the `**Format**` header line and its `Changed` note.
- Never run two stage skills for two different slugs in one call.
- If a stage skill ends with the Progress row still `[ ]`, say so plainly with the reason it gave; do not retry it from here.
