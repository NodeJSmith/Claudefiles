# Verdict Line Format

Single source of truth for the canonical verdict line emitted by all four reviewers in the mine-orchestrate pipeline.

## Canonical Lines

### Code and integration reviewers

```
**Verdict:** PASS | WARN | FAIL (findings: N)
```

### Spec and visual reviewers

```
**Verdict:** PASS | WARN | FAIL      ← spec-reviewer
**Verdict:** PASS | WARN | FAIL      ← visual-reviewer
```

## Verdict Vocabulary

All reviewers use a normalized vocabulary aligned with the `cfl gate` verdict set (`PASS`, `WARN`, `FAIL`, `SKIPPED`).

| Reviewer | Verdict values |
|---|---|
| `spec-reviewer-prompt.md` | PASS / WARN / FAIL |
| `agents/code-reviewer.md` | PASS / WARN / FAIL |
| `agents/integration-reviewer.md` | PASS / WARN / FAIL |
| `visual-reviewer-prompt.md` | PASS / WARN / FAIL |

## The `**Verdict:**` Prefix is Reserved

No line in any reviewer's report may begin with `**Verdict:**` except the single canonical verdict line. Visual reviewer per-scenario verdicts use `**Scenario verdict:**` instead.

## Findings Count (code and integration only)

`N` is the count of findings **introduced by this change**. Pre-existing issues — flagged separately under a `## Pre-existing Issues` header — are excluded from the count.

The count is informational — it tells the orchestrator how many findings the reviewer raised, but the fixer loop triggers on verdict (WARN or FAIL), not on the count. A PASS with `findings: N` does not trigger the fixer. Spec and visual carry no count because their findings never trigger the fixer — they route by verdict word alone.

## Extraction Contract

Consumers take the **last line matching** `^\*\*Verdict:\*\*` in the reviewer's output file. Reviewers may emit reasoning or pre-existing sections after the canonical line — it need not be the file's final line.

Parsing is per-reviewer-type:

- Code/integration: last line matching `^\*\*Verdict:\*\*` and containing `(findings:` — extract verdict word and N
- Spec: last line matching `^\*\*Verdict:\*\*` — extract PASS / WARN / FAIL
- Visual: last line matching `^\*\*Verdict:\*\*` — extract PASS / WARN / FAIL

## Concise-Return Mode

Activated when **both** conditions hold:

1. The dispatch prompt contains the **exact literal token** `CONCISE-RETURN-MODE` (verbatim, no paraphrase)
2. The dispatch provides an output file path

When active:
- Write the full report to the provided output file path
- Return **only the canonical verdict line** as the final message to the caller

**Default behavior** (when either condition is absent): return the full report as the final message. Path-less callers — `/mine-review`, `/mine-ship`, `/mine-commit-push`, `/mine-build`, `/mine-address-pr-issues`, Phase-3 — always receive the full report.

The canonical line extracted from the file is always authoritative. Concise-return compliance affects only the return-message context cost, not correctness.

## CONCISE-RETURN-MODE Leak Check

Run the check:

```bash
grep -rl CONCISE-RETURN-MODE skills commands
```

The intent of this check is fixed: the sentinel may appear **only in orchestrate-internal files** (the single source of truth, the orchestrate-local reviewer prompts, and the orchestrate per-task dispatch machinery) — it must **never** appear in a path-less / non-orchestrate caller (`mine-ship`, `mine-commit-push`, `mine-review`, `mine-build`, `mine-address-pr-issues`).

The grep returns exactly these five legitimate orchestrate-internal hosts:

- `skills/mine-orchestrate/verdict-line-format.md` — this file: the single source of truth, which both documents and demonstrates the token.
- `skills/mine-orchestrate/spec-reviewer-prompt.md` — orchestrate-local prompt that defines activation.
- `skills/mine-orchestrate/visual-reviewer-prompt.md` — orchestrate-local prompt that defines activation.
- `skills/mine-orchestrate/findings-fix-loop.md` — instructs the orchestrator to emit the verbatim sentinel in its re-review re-dispatches.
- `skills/mine-orchestrate/SKILL.md` — the per-task Step 8 dispatch that activates concise-return.

The agent files (`agents/code-reviewer.md`, `agents/integration-reviewer.md`) also legitimately contain the token but are in `agents/`, not `skills/` or `commands/`, so they don't appear in this grep. Any **other** path appearing in the grep output is a leak — the sentinel must never reach a path-less / non-orchestrate caller.

## Conformance Check

`bin/lint-verdict-line` (pre-commit hook, `always_run: true`) reads all four reviewer files and verifies:

1. Each file has exactly one line starting with `**Verdict:**` (prefix reserved)
2. Code/integration: that line contains `(findings:`
3. Spec/visual: that line does not contain `(findings:`

SYNC markers in each reviewer file (`<!-- SYNC: skills/mine-orchestrate/verdict-line-format.md -->`) identify where the canonical format is specified; the conformance check is the actual enforcement.
