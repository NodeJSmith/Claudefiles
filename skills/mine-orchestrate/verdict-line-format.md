# Verdict Line Format

Single source of truth for the canonical verdict line emitted by all four reviewers in the mine-orchestrate pipeline.

## Canonical Lines

### Code and integration reviewers

```
**Verdict:** PASS | WARN | FAIL (findings: N, critical: C, high: H, medium: M, low: L)
```

### Spec and visual reviewers

```
**Verdict:** PASS | FAIL             ← spec-reviewer
**Verdict:** PASS | WARN | FAIL      ← visual-reviewer
```

## Verdict Vocabulary

All reviewers use vocabulary aligned with the `cfl gate` verdict set: `PASS`, `WARN`, `FAIL`, `SKIPPED`.

| Reviewer | Verdict values |
|---|---|
| `spec-reviewer-prompt.md` | PASS / FAIL |
| `agents/code-reviewer.md` | PASS / WARN / FAIL |
| `agents/integration-reviewer.md` | PASS / WARN / FAIL |
| `visual-reviewer-prompt.md` | PASS / WARN / FAIL |

## The `**Verdict:**` Prefix is Reserved

No line in any reviewer's report may begin with `**Verdict:**` except the single canonical verdict line. Visual reviewer per-scenario verdicts use `**Scenario verdict:**`.

## Findings Count (code and integration only)

`N` is the total count of findings **introduced by this change**. `C`, `H`, `M`, `L` are the per-severity counts. Pre-existing issues, flagged separately under `## Pre-existing Issues`, are excluded. The per-severity counts must sum to `N`.

The counts are informational. The fixer loop triggers on verdict (`WARN` or `FAIL`), not on counts. A PASS with `findings: N` does not trigger the fixer. Spec and visual carry no count; they route by verdict word alone.

## Extraction Contract

Consumers take the **last line matching** `^\*\*Verdict:\*\*` in the reviewer's output file. The canonical line need not be the file's final line.

Parsing is per-reviewer-type:

- Code/integration: last line matching `^\*\*Verdict:\*\*` and containing `(findings:` — extract verdict word, N, and per-severity counts C/H/M/L
- Spec: last line matching `^\*\*Verdict:\*\*` — extract PASS / FAIL
- Visual: last line matching `^\*\*Verdict:\*\*` — extract PASS / WARN / FAIL

## Concise-Return Mode

Activated when **both** conditions hold:

1. The dispatch prompt contains the **exact literal token** `CONCISE-RETURN-MODE` (verbatim, no paraphrase)
2. The dispatch provides an output file path
When active:
- Write the full report to the provided output file path
- Return **only the canonical verdict line** as the final message to the caller

**Default behavior**: when either condition is absent, return the full report as the final message. Path-less callers such as `/mine-review`, `/mine-ship`, `/mine-commit-push`, `/mine-build`, and `/mine-address-pr-issues` always receive the full report.

The canonical line extracted from the file is always authoritative.

## CONCISE-RETURN-MODE Leak Check

Run the check:

```bash
grep -rl CONCISE-RETURN-MODE skills commands
```

The sentinel may appear **only in orchestrate-internal files**. It must **never** appear in a path-less or non-orchestrate caller such as `mine-ship`, `mine-commit-push`, `mine-review`, `mine-build`, or `mine-address-pr-issues`.

The grep should return exactly these six legitimate hosts:

- `skills/mine-orchestrate/verdict-line-format.md`
- `skills/mine-orchestrate/spec-reviewer-prompt.md`
- `skills/mine-orchestrate/visual-reviewer-prompt.md`
- `skills/mine-orchestrate/findings-fix-loop.md`
- `skills/mine-orchestrate/SKILL.md`
- `skills/mine-orchestrate/post-execution-pipeline.md`
The agent files `agents/code-reviewer.md` and `agents/integration-reviewer.md` also legitimately contain the token, but they are outside `skills/` and `commands/`. Any other grep result is a leak.

## Conformance Check

`bin/lint-verdict-line` reads all four reviewer files and verifies:

1. Each file has exactly one line starting with `**Verdict:**` (prefix reserved)
2. Code/integration: that line contains `(findings:`
3. Spec/visual: that line does not contain `(findings:`

SYNC markers in each reviewer file (`<!-- SYNC: skills/mine-orchestrate/verdict-line-format.md -->`) identify the canonical owner; the lint check is the enforcement.
