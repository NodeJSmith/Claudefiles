# Context: Show Me Your Work

## Problem & Motivation
When mine.orchestrate runs overnight, the user returns to WIP commits and a checkpoint file. The commits show what changed; the checkpoint shows which tasks passed. Neither shows why the agent made the choices it did. The real cost is trust: a PASS verdict with questionable evidence is indistinguishable from one with strong evidence. The `autonomous-run-discipline.md` rule mandates "keep a decision trail" but provides no mechanism to actually do it.

## Visual Artifacts
None.

## Key Decisions
1. The orchestrator is the sole trail writer. Executor subagents do not call `log.sh` directly. The orchestrator extracts decisions from executor output files and logs on their behalf, avoiding changes to `implementer-prompt.md`.
2. Trail detail fields pipe raw command or artifact output, not agent-composed prose. This shifts each call from "write a summary" (degrades under context pressure) to "route this output" (degrades gracefully).
3. The trail file is local-only (gitignored), not committed to git. It persists in the feature directory for investigation but is a runtime artifact, not archival.
4. The audit reviewer is scoped to structural gap detection (missing entries, sequence anomalies), not veracity verification. It cannot verify whether cited numbers are real.
5. The audit is informational, not a hard gate. Findings are surfaced at the shipping gate but do not block shipping.
6. Formula injection stripping covers `=`, `+`, `@`, `;` but NOT `-` (leading hyphens appear legitimately in prose).
7. Event vocabulary is validated at write time with a stderr warning for undeclared values.

## Constraints & Anti-Patterns
- Do NOT have executor subagents call `log.sh` — orchestrator only.
- Do NOT compose prose summaries for trail detail fields — pipe raw output instead.
- Do NOT strip leading hyphens from fields.
- Do NOT make the audit a hard gate — it is informational.
- Do NOT add `trail.tsv` to WIP commits — it is gitignored.
- Do NOT modify `spec-helper` — derive the trail path from the checkpoint's `feature_dir` field.
- Do NOT add an `audit` phase label — Phase 3 events use `p3`.

## Design Doc References
- `## Problem` — the trust cost of missing decision trails
- `## Architecture > bin/log.sh` — script interface, sanitization, truncation
- `## Architecture > Decision points in mine.orchestrate` — exact call-site tables for Phase 2 and Phase 3
- `## Architecture > Post-run audit` — Sonnet subagent prompt with expected-sequence grammar
- `## Architecture > Trail file location` — gitignore and persistence semantics
- `## Edge Cases` — failure handling for log.sh, audit subagent, resume, crashes
- `## Key Constraints` — sole writer, output-piping, no hyphen stripping

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
