---
task_id: "T03"
title: "Remove the stronger-model escalation and reshape the gate prompts"
status: "planned"
depends_on: ["T01"]
implements: ["FR#13", "FR#28", "AC#11", "AC#27"]
---

## Summary

Delete `mine-orchestrate`'s "Try again with stronger model" escalation everywhere it appears. It exists only because OpenCode has no per-call model override, which is what forced `bin/opencode-sync` to generate `-opus` agent variants — machinery T05 removes. Deleting the option leaves both task-gate prompts with a single listed option, which the `AskUserQuestion` contract does not permit, so the two choices currently reachable only by typing into the picker's Other field are promoted to real options. Their handlers already exist in both files, so this moves labels rather than writing logic.

This task runs before T04 deliberately: the text it deletes contains `general-purpose` references that would otherwise be migrated and then immediately removed.

## Target Files

- modify: `skills/mine-orchestrate/SKILL.md` — the option at `:640-641`, its handler at `:651`, and the promotion of the two Other-typed choices at `:652-659`
- modify: `skills/mine-orchestrate/spec-fix-loop.md` — the option at `:25-26`, its handler at `:31`, the parenthetical at `:29`, and the promotion of the two Other-typed choices at `:33` and `:35`
- modify: `skills/mine-orchestrate/agent-routing.md` — SYNC CHECKLIST item 5 at `:10-14`
- modify: `skills/mine-orchestrate/known-issues-protocol.md` — the option listing at `:59`
- read: `design/specs/1008-opencode-named-roles/design.md`
- read: `rules/common/interaction.md` — the `AskUserQuestion` block conventions these prompts must satisfy

## Prompt

Read `design/specs/1008-opencode-named-roles/design.md`, FR#13, FR#28, AC#11, AC#27, and **Dependencies and Assumptions** (the entry recording that escalation removal leaves no recovery path for a task failing review repeatedly — this is accepted, do not reintroduce a substitute).

**1. Delete the escalation option and its handlers.**

Five sites, enumerated in FR#13:

- `skills/mine-orchestrate/SKILL.md:640-641` — the `- label: "Try again with stronger model"` option and its description.
- `skills/mine-orchestrate/SKILL.md:651` — the handler bullet.
- `skills/mine-orchestrate/spec-fix-loop.md:25-26` — the option and description.
- `skills/mine-orchestrate/spec-fix-loop.md:31` — the handler paragraph.
- `skills/mine-orchestrate/known-issues-protocol.md:59` — remove `Try again with stronger model` from the list of choices the user picks among.

Both handler paragraphs (`SKILL.md:651`, `spec-fix-loop.md:31`) carry a trailing `<!-- opencode-sync: ok -->` suppression comment. Those go with the text.

**2. Delete `agent-routing.md`'s SYNC CHECKLIST item 5 (`:10-14`).**

It reads, in full, as an instruction to add each new executor agent to `SPECIALIST_AGENTS` in `bin/opencode-sync` so an opus-tier escalated retry gets its own generated variant. Both the escalation and `SPECIALIST_AGENTS` are being removed, so the whole item goes — not just its wording. Renumber the remaining checklist items if they are numbered sequentially.

**3. Reword the parenthetical at `spec-fix-loop.md:29`.**

It currently reads: "If the spec reviewer returns FAIL again, re-present the same options (do not narrow to only block/stop — the user may want to retry with a stronger model)." The instruction to re-present the same options stays; its stated reason does not, because the option it names is gone. Reword so the instruction keeps a valid rationale.

**4. Promote the two Other-typed choices to real options (FR#28).**

After step 1, both prompts list only "Try again". Add "Mark as blocked and skip" and "Stop here" as real `- label:` entries in each block, so each lists exactly three options. Both files already document what each does:

- `spec-fix-loop.md:33` — `cfl task block <task_id> --reason "FAIL persisted after auto-fix"`
- `spec-fix-loop.md:35` — `cfl run stop --at-task <task_id> --reason "user chose stop at spec FAIL persistence prompt"`
- `SKILL.md:652-655` — `cfl task block <task_id> --reason "<blocker description>"`
- `SKILL.md:656-659` — `cfl run stop --at-task <task_id> --reason "user chose stop at task gate"`

Move those handlers so they read as handlers for listed options rather than for Other-typed input. Delete the "(via Other)" phrasing in both files — AC#27 checks for its absence.

## Focus

**This is instruction content, not code.** These files are read by an agent at runtime; the diff must leave prose that still reads coherently. After deleting a handler bullet from a list, check that the surrounding sentence and any "Then:" lead-in still parse.

**Two tests anchor on this area and one of them will move under your feet.** `tests/test_mine_orchestrate_protocol_contracts.py:364` asserts `agent-routing.md` contains the literal string `general-purpose` in its fallback route. That anchor belongs to T04, which rewrites the fallback row to name `standard-worker` — do **not** change `agent-routing.md:24` or `:26` (the routing table's fallback rows) in this task. Your edit to that file is confined to the SYNC CHECKLIST at `:10-14`. Confirm `mise run test:root` still passes when you are done; if `test_mine_orchestrate_protocol_contracts.py` fails, you removed something T04 owns.

**Do not touch the dispatch clauses.** `agent-routing.md`, `SKILL.md`, `known-issues-protocol.md`, and `spec-fix-loop.md` all contain `subagent_type` and `model:` dispatch content that T04 migrates. This task removes only escalation. Leaving those in place is correct.

**The `AskUserQuestion` contract.** Per `rules/common/interaction.md`, a skill's `AskUserQuestion:` block is an instruction to call the tool with those exact labels, and the picker appends "Other" automatically — so three listed options is the target, not four. Do not add an explicit "Other" entry.

**Why this depends on T01, and what that costs you.** T01 and this task both write `skills/mine-orchestrate/SKILL.md` — T01 replaces the inlined `<full spec-reviewer-prompt.md content>` placeholder at `:421` with a `spec-reviewer` dispatch. That edit sits above every line number cited here, so by the time you run, the gate block will no longer be at `:637-642` and its handlers no longer at `:651-659`. **Locate every site in this task by content, not by the line numbers given** — they are the pre-T01 positions, recorded so you can confirm you found the right block. The same applies to `spec-fix-loop.md`, which T01 does not touch, so its numbers should still hold.

**Why removal comes before migration.** `SKILL.md:651` and `spec-fix-loop.md:31` both contain the literal `general-purpose`, and both are among the 25 files a `general-purpose` grep returns. Deleting them here shrinks T04's surface and avoids migrating text into a shape (`worker-opus`, `-opus` variants) that will not exist.

## Verify

- [ ] FR#13: `grep -rn 'stronger model' skills/` returns no matches, and `agent-routing.md` no longer contains a SYNC CHECKLIST item referencing `SPECIALIST_AGENTS` or opus variants.
- [ ] FR#28: Both gate prompts list `Try again`, `Mark as blocked and skip`, and `Stop here` as real options, and neither file describes the latter two as reached "via Other".
- [ ] AC#11: `grep -rn 'stronger model' skills/` returns no matches, and `skills/mine-orchestrate/agent-routing.md` retains no SYNC CHECKLIST item referencing `SPECIALIST_AGENTS` or opus variants.
- [ ] AC#27: The `AskUserQuestion` blocks in `skills/mine-orchestrate/spec-fix-loop.md` and `skills/mine-orchestrate/SKILL.md`'s task gate each list exactly three options — `Try again`, `Mark as blocked and skip`, `Stop here` — and neither file describes the latter two as reached "via Other".
