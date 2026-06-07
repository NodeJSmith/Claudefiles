# Design: Show Me Your Work — Decision Trail for Orchestrate Runs

**Date:** 2026-06-07
**Status:** approved
**Scope-mode:** hold
**Research:** /tmp/claude-define-research-trail.md

## Problem

When mine.orchestrate runs overnight, the user comes back to WIP commits and a checkpoint file. The commits show what changed; the checkpoint shows which tasks passed. Neither shows why the agent made the choices it did — why a finding was auto-fixed vs deferred, why a retry was attempted, why a deviation was classified a certain way.

The real cost is trust: without a trail, the user either accepts overnight work on faith or re-investigates decisions that may have been perfectly sound. The checkpoint shows verdicts but not the reasoning behind them — a PASS verdict with questionable evidence is indistinguishable from one with strong evidence.

The `autonomous-run-discipline.md` rule mandates "keep a decision trail" but provides no mechanism. The checkpoint system tracks resume state, not reasoning. Per-task artifacts (executor.md, reviews, gate results) exist in ephemeral tmpdir subdirectories that are lost when `/tmp` is cleared between sessions.

## Goals

- Every significant decision during an orchestrate run is recorded with its evidence in a persistent, human-and-machine-readable trail file
- A future Claude session can read the trail to answer "what happened with T03?" or "why did the executor retry?" without access to the original tmpdir artifacts
- A post-run audit detects structural anomalies in the trail (missing entries, sequence violations, suspicious patterns) before the user reviews the work

## User Scenarios

### Jessica: Solo developer running orchestrate overnight

- **Goal:** Trust or distrust overnight orchestrate output
- **Context:** Returns in the morning to completed or partially-completed orchestrate run

#### Morning review

1. **Opens the feature directory**
   - Sees: `design.md`, `tasks/`, and `trail.tsv` alongside the existing artifacts
   - Decides: Whether to check the trail or just look at the verdict summary
   - Then: If questions arise about any task's outcome, asks Claude to read the trail

2. **Asks Claude about a specific decision**
   - Sees: Claude reads `trail.tsv` and cross-references the relevant entries
   - Decides: Whether the reasoning was sound or needs investigation
   - Then: Accepts the work or digs deeper into the specific task's artifacts

3. **Reviews the audit report (if concerns exist)**
   - Sees: The audit reviewer's findings — structural anomalies like missing entries, sequence violations, or suspicious patterns
   - Decides: Whether flagged entries need manual investigation
   - Then: Investigates flagged entries or proceeds to shipping

#### Audit flags structural anomalies

1. **Reviews the audit report**
   - Sees: Multiple entries flagged — "T03 has verdict but no start entry," "retry with no preceding gate event"
   - Decides: Which flagged entries warrant deeper investigation
   - Then: Asks Claude to read the trail entries surrounding the flagged ones for more context

2. **Investigates a flagged entry**
   - Sees: Claude explains the trail sequence — T03 has a verdict but the start entry is missing (possible log failure or context-pressure skip)
   - Decides: Whether to re-run the task manually or accept the work with the caveat noted
   - Then: Ships with awareness of the weak spots, or re-runs the specific task

#### Incomplete trail after crash

1. **Notices the trail ends mid-run**
   - Sees: Trail entries stop at T03 but the checkpoint shows T05 was the last completed task — two tasks have no trail coverage
   - Decides: Whether the gap matters (are T04-T05 low-risk, or did they touch critical code?)
   - Then: Reviews T04-T05 diffs manually since the trail can't help, or asks Claude to reconstruct reasoning from the remaining per-task artifacts if the tmpdir still exists

## Functional Requirements

- **FR#1** A `log` bin script accepts a trail file path, phase, task ID, event type, and detail text, and appends a single TSV row with an auto-generated timestamp
- **FR#2** The script strips formula-injection characters (`=`, `+`, `@`, `;`) from the leading position of each field value before writing
- **FR#3** The script sanitizes tab, newline, and carriage return characters within field values by replacing them with spaces
- **FR#4** The script writes a TSV header row (`timestamp`, `phase`, `task`, `event`, `detail`) when the trail file does not yet exist
- **FR#5** mine.orchestrate calls `log` at each significant decision point during Phase 2 (per-task loop) and Phase 3 (post-execution pipeline), producing ~7-11 entries per task
- **FR#6** The trail file persists at `<feature_dir>/trail.tsv` as a local-only file (gitignored, like the checkpoint file)
- **FR#7** After Phase 3 completes (before the shipping gate), a Sonnet audit reviewer reads the full trail and produces a structured report flagging structural anomalies: missing entries, sequence violations, retry-without-trigger patterns, timing outliers, and empty detail fields
- **FR#8** The audit is informational — findings are surfaced to the user at the shipping gate but do not block shipping

## Edge Cases

- Trail file path contains spaces or special characters — `log` must quote correctly
- Detail text is empty — write the row with an empty detail field rather than failing
- Detail text exceeds a reasonable length — truncate to 500 characters to keep entries concise and context-efficient
- Orchestrate resumes from checkpoint — append to the existing trail file rather than overwriting it
- Orchestrate run has zero tasks (edge case: empty task list) — trail file gets only the header row and Phase 3 entries
- Audit reviewer finds no issues — report states "no findings" rather than being empty
- `log` fails (disk full, permissions error) — the orchestrate run must not abort; log the failure via stderr and continue execution without the trail entry. The orchestrator maintains an inline failure counter; if any `log` calls returned non-zero, the shipping gate surfaces "trail logging had N failures during this run — check disk space and file permissions" so users can distinguish write failures from behavioral omissions
- Audit reviewer subagent fails or times out — surface the failure at the shipping gate as "trail audit: failed to complete" rather than blocking; the trail file itself is still available for manual review
- Trail file is corrupted (e.g., partial write from a killed process) — the audit reviewer should note the corruption as a finding rather than crashing. Single-process sequential `>>` appends on Linux are effectively atomic in practice, so corruption is unlikely but not impossible on non-POSIX filesystems
- Orchestrate crashes mid-run — the trail contains entries up to the crash point. On resume, the orchestrator logs a synthetic start entry (`log <trail> p0 - start "resuming from checkpoint; last completed: <task_id>; base_commit: <sha>"`) to create an unambiguous context anchor. New entries then append normally. The audit reviewer can detect gaps (e.g., a task with a verdict but no start entry) and flag them

## Acceptance Criteria

- **AC#1** After an orchestrate run completing 3+ tasks, `trail.tsv` exists in the feature directory and contains a header row plus at least 7 entries per completed task (FR#1, FR#5)
- **AC#2** No field value in the trail begins with `=`, `+`, `@`, or `;` (FR#2)
- **AC#3** No field value in the trail contains literal tab, newline, or carriage return characters (FR#3)
- **AC#4** The trail file exists in the feature directory after an orchestrate run and is readable by a future Claude session (FR#6)
- **AC#5** The Phase 3 shipping gate includes audit findings (or "no findings") alongside the existing impl-review and clean-code results (FR#7, FR#8)
- **AC#6** A resumed orchestrate run appends to the existing trail rather than overwriting it (FR#1)
- **AC#7** Detail fields longer than 500 characters are truncated with a trailing `...` (FR#1)

## Key Constraints

- The orchestrator is the sole trail writer — executor subagents do not call `log` directly. The orchestrator extracts key decisions from executor output files and logs on the executor's behalf. This avoids changes to the already-long `implementer-prompt.md`.
- Trail detail fields must pipe raw command or artifact output (e.g., `cat test-gate.md | head -c 400`) rather than agent-composed prose summaries. This shifts each `log` call from "write a summary" (high cognitive load, degrades under context pressure) to "route this output" (low cognitive load, degrades to an empty field rather than a misleading one).
- The `log` script must NOT strip leading `-` (hyphen) from fields — only `=`, `+`, `@`, `;`. Leading hyphens appear legitimately in prose and the DDE risk from `-` is lower than from the other characters.

## Dependencies and Assumptions

- `spec-helper` continues to manage checkpoint state — `log` is a parallel artifact, not a replacement for the checkpoint
- TSV format remains parseable by standard tools (`awk -F'\t'`, Python `csv.reader`)
- The orchestrate SKILL.md structure (numbered steps, Phase 2/3 boundaries) remains stable enough for `log` call sites to be maintained

## Architecture

### Trade-offs

This approach optimizes for simplicity and auditability at the cost of instruction surface area. Adding ~15 `log` calls to the already-570-line orchestrate SKILL.md increases the instruction count, and under context pressure the agent may skip some calls. The audit reviewer mitigates this by detecting gaps in the trail — missing entries are themselves a finding. The alternative (hook-based automatic capture) would avoid instruction bloat but would produce high-noise, low-signal entries because hooks fire on tool calls, not decisions.

### `bin/log`

A bin script following the same conventions as `get-skill-tmpdir` and `get-tmp-filename`: `set -euo pipefail`, `--help` support, clear error messages.

Interface: `log <trail-file> <phase> <task> <event> <detail>`

- `trail-file`: absolute path to the TSV file
- `phase`: `p0`, `p1`, `p2`, or `p3`
- `task`: task ID (`T01`, `T02`, ...) or `-` for phase-level events
- `event`: short verb from a fixed, validated vocabulary: `start`, `dispatch`, `verdict`, `contested`, `gate`, `retry`, `review`, `fix`. The script validates the event field against this vocabulary and emits a stderr warning for undeclared values (but still writes the row to avoid blocking the run)
- `detail`: raw command or artifact output piped from the relevant step (not agent-composed prose)

The script:
1. Auto-generates an ISO 8601 timestamp
2. Strips formula-injection prefixes (`=`, `+`, `@`, `;`) from the leading position of each field
3. Replaces tabs, newlines, and carriage returns in field values with spaces (using `tr '\n\t\r' '   '`)
4. Truncates the detail field to 500 characters (appending `...` if truncated)
5. If the trail file does not exist, writes the header row and data row in a single `printf` call to eliminate the two-step race window
6. If the trail file already exists, appends the data row via `printf '%s\t%s\t%s\t%s\t%s\n' ... >> "$trail_file"`

### Decision points in mine.orchestrate

The orchestrator calls `log` at these points in the per-task loop (Phase 2):

| Step | Event | What's logged |
|------|-------|---------------|
| Step 1 | `start` | Task announced, entering execution |
| Step 4-5 | `dispatch` | Executor agent type selected and why (from agent-routing.md), executor launched |
| Step 7 | `contested` | Each CONTESTED criterion: accept/reject decision and by whom |
| Step 9 | `gate` | Test gate and lint gate results (pass/regress, counts) |
| Step 10 | `retry` | WARN classification (fixable/structural) and retry decision |
| Step 11 | `review` | Visual reviewer verdict and reasoning |
| Step 12 | `fix` | Review findings fix loop: what was auto-fixed, what was deferred, iteration count |
| Step 14-15 | `verdict` | Assembled task verdict with reasoning |

Phase 3 decision points:

| Step | Event | What's logged |
|------|-------|---------------|
| Step 2 | `gate` | Implementation review verdict |
| Step 3 | `review` | Cross-file consistency review result |
| Step 4 | `fix` | Clean code findings: N fixed, M deferred |
| Step 4.5 | `review` | Structural simplification findings and user decision |
| Step 5 | `review` | Final review pass result |
| Step 5.5 (new) | `review` | Trail audit findings summary |

### Trail file location

`<feature_dir>/trail.tsv` — alongside `design.md`, outside `tasks/`. The file is gitignored via a `.gitignore` entry added at Phase 0 init time (the orchestrator writes `trail.tsv` and `trail-audit.md` to `<feature_dir>/.gitignore`). This means:
- It persists through the orchestrate run and across session boundaries within the same working directory
- It is available for a future Claude session to read when investigating decisions
- It must be manually deleted when no longer needed — `spec-helper archive` does not clean up files outside `tasks/`

### Orchestrate checkpoint integration

In Phase 0, after checkpoint init, log the first trail entry: `log <trail_path> p0 - start "orchestrate run started"`. If this fails, surface a warning: "Trail logging unavailable — check permissions at `<feature_dir>/`. Run will continue; trail will be absent." This is an early-detection probe at negligible cost.

The trail file path is derived as `<feature_dir>/trail.tsv` from the checkpoint's existing `feature_dir` field — no new checkpoint fields are needed. The orchestrator and audit subagent both derive the path from `feature_dir` using this convention. On resume, the orchestrator reads `trail_path` from the checkpoint and appends to the existing trail — the header row check in `log` handles this naturally.

Since the trail file is gitignored, no WIP commit staging is needed — the trail persists locally alongside the checkpoint.

### Post-run audit (Phase 3, Step 5.5)

A new step inserted between Step 5 (final review pass) and Step 6 (shipping gate) in `post-execution-pipeline.md`.

Launch a single `general-purpose` subagent with `model: sonnet`:

```
You are auditing the structural integrity of the decision trail from an overnight orchestrate run.

Read the trail file at: <feature_dir>/trail.tsv

## Expected sequence per task

For each task, the expected sequence is: start → [dispatch] → [contested*] → [gate] → [retry*] → [review] → [fix*] → verdict. Optional steps are bracketed; * means zero or more occurrences. Flag deviations from this sequence.

## What to check

1. Missing entries: a task with a verdict but no start entry, or vice versa
2. Sequence anomalies: entries out of expected order, or unexpected gaps between start and verdict
3. Retry patterns: a retry event with no preceding gate or review event that would have triggered it
4. Timing outliers: unusually short intervals between start and verdict (suggests skipped steps)
5. Empty detail fields: entries where the detail is blank or trivially short (under 20 characters)

Do NOT attempt to verify whether the content of detail fields is accurate — you cannot cross-reference against the actual command outputs. Focus on structural patterns the trail reveals about the execution flow.

## Output format

Start your report with: ## Summary
N findings (or "no findings")

Then list each finding with: the task ID, the structural issue, and why it matters.

Write your audit report to: <feature_dir>/trail-audit.md
```

The audit report is written to `<feature_dir>/trail-audit.md` (alongside `trail.tsv`) so it persists across session boundaries. The audit findings are surfaced at the shipping gate alongside the existing impl-review, clean-code, and final review results.

### Shipping gate update

The shipping gate question in `post-execution-pipeline.md` Step 6 adds a new field:

```
Trail audit: <N findings — or 'no findings'>
```

## Replacement Targets

No existing code is being replaced. This is purely additive — the checkpoint system continues to serve its resume-state purpose, and the trail is a parallel artifact for decision auditing.

## Convention Examples

### Append-only TSV logging

**Source:** `scripts/hooks/phrase-monitor.sh:108-118`

```bash
log_match() {
  local category="$1" phrase="$2" score="$3"
  local excerpt
  excerpt="$(printf '%s' "$new_text" | grep -oi -m1 ".\{0,60\}${phrase}.\{0,60\}" 2> /dev/null | head -1)" || true
  [ -z "$excerpt" ] && excerpt="$(printf '%s' "$new_text" | head -c 120)"
  excerpt="$(printf '%s' "$excerpt" | tr '\n\t' '  ')"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$now" "$session_id" "$category" "$score" "$phrase" "$excerpt" >> "$log_file" 2> /dev/null || true
}
```

### Bin script structure

**Source:** `bin/get-skill-tmpdir`

```bash
#!/usr/bin/env bash
[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && {
  cat << 'EOF'
Usage: get-skill-tmpdir <skill-name>
...
EOF
  exit 0
}

set -euo pipefail
prefix="${1:?usage: get-skill-tmpdir <skill-name>}"
mktemp -d "${CLAUDE_CODE_TMPDIR:-/tmp}/claude-${prefix}-XXXXXX"
```

### Post-execution pipeline step pattern

**Source:** `skills/mine.orchestrate/post-execution-pipeline.md` (Step 4)

```markdown
## Step 4: Clean code check (automatic, Opus subagent)

After the cross-file consistency review passes, run a clean code check...

Launch a single `general-purpose` subagent with `model: opus` and this prompt:
...
Wait for the subagent to complete. Read `<dir>/clean-code-summary.md`...
```

## Alternatives Considered

### Hook-based automatic capture

A PreToolUse/PostToolUse hook that automatically logs decisions during any long-running skill, not just orchestrate.

Rejected because: hooks fire on tool calls, not decisions. The mapping from "Bash tool invoked" to "significant decision made" requires the semantic context that only the orchestrator has. A hook would produce high-noise, low-signal entries. The explicit `log` call sites in the orchestrate SKILL.md are where the orchestrator already knows what decision is being made.

### Wrapper skill that invokes orchestrate

`show-me-your-work` as a skill you invoke *instead of* orchestrate, wrapping the entire run.

Rejected because: the trail needs to be written at decision points *inside* the orchestrate loop, not before/after it. A wrapper can only observe entry and exit, not the per-step decisions. The integration has to be inside the orchestrate SKILL.md.

### JSON or markdown format instead of TSV

Rejected because: TSV is trivially parseable by `awk -F'\t'` and trivially appendable by `printf`. JSON requires a viewer and is hard to append atomically; markdown tables require column alignment. The phrase-monitor pattern already proves TSV logging works in this codebase.

## Test Strategy

N/A — no test infrastructure in this repo. The `log` script is validated by manual invocation and by observing the trail file after an orchestrate run. The lint-cli-conventions hook validates bin script structure automatically.

## Documentation Updates

- **REFERENCE.md** — add `log` to the bin/ scripts table
- **`rules/common/capabilities-core.md`** — add `log` to the CLI tools table (no trigger phrase needed — it's called by orchestrate, not by the user directly)
- **CHANGELOG.md** — entry for the new trail mechanism

## Impact

### Changed Files

- `bin/log` — new file (the logging helper script)
- `skills/mine.orchestrate/SKILL.md` — insert `log` calls at ~15 decision points in Phase 2
- `skills/mine.orchestrate/post-execution-pipeline.md` — add Step 5.5 (trail audit) and update Step 6 (shipping gate question)
- `REFERENCE.md` — add bin script entry
- `rules/common/capabilities-core.md` — add CLI tool entry

### Behavioral Invariants

- mine.orchestrate's existing Phase 2 step sequence and Phase 3 pipeline must continue working unchanged — `log` calls are additive insertions between existing steps, not modifications to step logic
- The checkpoint system (`spec-helper checkpoint-*`) is unchanged — trail is a parallel artifact
- WIP commits are unaffected — `trail.tsv` is gitignored and not staged
- The shipping gate options (Ship/Challenge/Stop) remain unchanged — only the question text gains a new field

### Blast Radius

- mine.orchestrate is the only consumer — no other skills or agents are affected
- The `log` bin script is general-purpose and could be reused by other skills in the future, but this design does not wire it into anything else

## Open Questions

None — all questions resolved during discovery.
