---
task_id: "T01"
title: "Canonical verdict line + concise-return across all four reviewers"
status: "done"
depends_on: []
implements: ["FR#1", "FR#2", "FR#3", "AC#4", "AC#5"]
---

## Summary

Establish the reviewer output contract the whole feature rests on. Create a single source-of-truth file for the canonical verdict line, make all four reviewers emit it, add the opt-in concise-return mode (gated on a literal sentinel + a file path), and build a permanent conformance check plus a concise-return leak check. This is the foundational task — T02/T03 consume this contract. It is also the highest-risk task because `code-reviewer` and `integration-reviewer` are shared agents; the changes here must be additive for non-orchestrate callers.

## Target Files

- create: `skills/mine-orchestrate/verdict-line-format.md`
- create: `bin/lint-verdict-line` (or repo-conventional name) — the conformance check
- modify: `.pre-commit-config.yaml` — wire the conformance check
- modify: `agents/code-reviewer.md`
- modify: `agents/integration-reviewer.md`
- modify: `skills/mine-orchestrate/spec-reviewer-prompt.md`
- modify: `skills/mine-orchestrate/visual-reviewer-prompt.md`
- read: `design/specs/034-orchestrate-verdict-only/design.md`
- read: `.pre-commit-config.yaml` (existing `lint-agent-models` entry as the wiring model)
- read: `bin/lint-agent-models` (style/structure model for the new check)

## Prompt

Implement the canonical verdict-line contract and concise-return mode described in the design doc's `## Architecture` §1 and §2, `## Functional Requirements` FR#1–FR#3, and `## Key Constraints`.

1. **Create `skills/mine-orchestrate/verdict-line-format.md`** — the single source of truth. It must specify:
   - The canonical line. **Code & integration reviewers:** `**Verdict:** <VERDICT> (findings: N)`. **Spec & visual reviewers:** `**Verdict:** <VERDICT>` (no count).
   - `<VERDICT>` vocab per reviewer: spec PASS/WARN/FAIL; code & integration APPROVE/WARN/BLOCK; visual VERIFIED/WARN/FAIL.
   - The `**Verdict:**` prefix is **reserved** for this one line in every reviewer's report. No other line may begin with `**Verdict:**`.
   - `N` (code/integration only) = count of findings **introduced by this change**, excluding any "Pre-existing Issues" the reviewer lists separately. Single count, no blocking/advisory split.
   - The extraction contract: consumers take the **last line matching** `^\*\*Verdict:\*\*` (reviewers may emit reasoning / pre-existing sections after it — it need not be the file's final line).
   - The concise-return sentinel: the literal token `CONCISE-RETURN-MODE`. When a dispatch contains this token **and** supplies an output file path, the reviewer's final message is only its canonical verdict line; the full report still goes to the file. Default (and any path-less dispatch) = full report.

2. **Edit the four reviewers** to emit the canonical line and honor concise-return, each carrying a `<!-- SYNC: skills/mine-orchestrate/verdict-line-format.md -->` marker near the verdict-line spec:
   - `agents/code-reviewer.md` — in `### Assessment`, change the `**Verdict:** APPROVE | WARN | BLOCK` line to `**Verdict:** <VERDICT> (findings: N)` where N = count of CRITICAL+HIGH+MEDIUM+LOW findings introduced by this change (exclude the "Pre-existing" ones per the existing rule at line ~119). `**Reasoning:**` may stay after it. Add a concise-return clause to the output instructions.
   - `agents/integration-reviewer.md` — replace the summary-table `**VERDICT: APPROVE / WARN / BLOCK**` line (~259) with the canonical `**Verdict:** <VERDICT> (findings: N)` where N = count of findings across the dimension table excluding the `## Pre-existing Issues` section. `## Pre-existing Issues` may stay after it. Add a concise-return clause.
   - `skills/mine-orchestrate/spec-reviewer-prompt.md` — the output already opens with `**Verdict:** PASS | WARN | FAIL` (~88); keep it as the single canonical line (NO count added — spec carries no findings count). Add a concise-return clause.
   - `skills/mine-orchestrate/visual-reviewer-prompt.md` — rename the per-scenario `**Verdict:**` lines (~76) to `**Scenario verdict:**`; replace `**Overall verdict:** ...` (~71) with the canonical `**Verdict:** <VERDICT>` (no count). Add a concise-return clause.

3. **Create the conformance check** `bin/lint-verdict-line` (match the structure/error style of `bin/lint-agent-models`). It must **read the four reviewer files** and verify each specifies a conformant canonical line (correct `**Verdict:**` prefix; `(findings: N)` present for code & integration, absent for spec & visual; prefix reserved). It must fail (non-zero) with a clear message when any reviewer drifts. Do NOT test hardcoded sample strings — read the actual files. Wire it into `.pre-commit-config.yaml` following the `lint-agent-models` pattern (`language: system`, `pass_filenames: false`, `always_run: true`).

4. **Concise-return leak check** — verify (and document how to verify) that `CONCISE-RETURN-MODE` appears only where orchestrate per-task dispatches will emit it, never in a path-less / non-orchestrate caller's dispatch. The reviewer agent files themselves legitimately contain the token (to define activation) and are excluded. A `grep -rl CONCISE-RETURN-MODE skills commands` should, at this task's completion, return only the reviewer files (T03 adds the orchestrate dispatch). Document the expected final state in `verdict-line-format.md`.

Run the conformance check and confirm it passes; run `agnix-check` and `lint-agent-models` and confirm no regressions.

## Focus

- **Shared-agent blast radius (highest risk).** `code-reviewer` and `integration-reviewer` are consumed by `/mine-ship`, `/mine-commit-push`, `/mine-review`, `/mine-build`, `/mine-address-pr-issues`, and Phase-3. All read the full report via an LLM (none deterministically parses the verdict string), so the canonical-line reformat is additive — but the concise-return clause MUST default to the full report and activate only on `CONCISE-RETURN-MODE` + a file path. `/mine-review` passes no file path → it must always get the full report. Word the clause so an incidental "be brief" never triggers it.
- Do not change the `model:` frontmatter of either agent (`lint-agent-models` pins them Sonnet).
- Integration-reviewer's severities live in a per-dimension table (DUPLICATE=CRITICAL … ORPHANED=LOW) and its verdict is category-based — define N as the count of newly-introduced findings listed in the report (excluding `## Pre-existing Issues`), not a re-bucketing into CRITICAL/HIGH.
- The latent bug being fixed: today's Step 13 grep (`**Verdict:**`/`**Overall verdict:**`) never matches integration's `**VERDICT: ...**`; standardizing fixes it. The `**Overall verdict:**` alternative is removed from the grep in T03.
- Pre-commit wiring model is `.pre-commit-config.yaml:29-34` (`lint-agent-models`). Pick a check name consistent with the existing `lint-*` convention.

## Verify

- [ ] FR#1: Each of the four reviewer files specifies exactly one canonical line — code/integration `**Verdict:** <VERDICT> (findings: N)`, spec/visual `**Verdict:** <VERDICT>` — with `**Verdict:**` reserved (visual per-scenario renamed to `**Scenario verdict:**`); `verdict-line-format.md` documents the format and the last-matching-line extraction rule.
- [ ] FR#2: `(findings: N)` is present only for code & integration, is a single count, and is documented to exclude pre-existing findings.
- [ ] FR#3: All four reviewers default to the full report and enter concise-return (final message = canonical line only; full report still written to file) only when the dispatch contains `CONCISE-RETURN-MODE` AND provides a file path.
- [ ] AC#4: The `bin/lint-verdict-line` check reads the four reviewer files and passes; a single `^\*\*Verdict:\*\*` pattern matches the canonical line in all four (parsing per-file for the optional count); it is wired into `.pre-commit-config.yaml`.
- [ ] AC#5: `grep -rl CONCISE-RETURN-MODE skills commands` (excluding the reviewer agent files that define the token) returns no path-less / non-orchestrate caller; the default-full-report behavior is stated in each reviewer.
