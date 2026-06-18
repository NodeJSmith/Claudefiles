---
tool: claude, codex, antigravity
---

# Verification Before Completion (CRITICAL)

Never claim work is done without concrete evidence. "Should work" is not verification.

## Evidence Requirements

| Claim | Required evidence |
|---|---|
| "Tests pass" | Fresh test output showing 0 failures (use `timeout 300 pytest` per `references/common/testing.md`) |
| "Bug is fixed" | Reproduction steps that now produce the correct result |
| "Build succeeds" | Build command output with exit code 0 |
| "Linter is clean" | Linter output showing no errors |
| "Type checker passes" | Type checker output with no errors |
| "Feature works" | Demonstrated via test, script, or browser screenshot |

Run the verification, read the output, confirm it matches the claim. If the evidence is ambiguous, dig deeper — don't round up.

## Script the Check

The strongest proof is a deterministic script that re-runs the same comparison, not a one-time eyeball. When practical, write the check as a script a reviewer can re-run instead of trusting your word.

## Trust Artifacts Not Self-Reports

When verifying delegated work (subagent output, automated pipeline results), inspect the actual output artifact (git diff, file contents, runtime behavior), not the delegate's summary. Agents report what they intended, not always what happened.

## Red-Flag Language

These phrases signal a claim without evidence. If you catch yourself writing one, stop and verify first:

- "should pass / should work / should be fine"
- "probably fixed"
- "seems to work"
- "I believe this resolves..."
- "Done!" / "All set!" before running verification

## Scope

This applies to **all completion claims** — mid-task status updates, commit messages, PR descriptions, and responses to the user. The pre-commit verification in `commit-conventions.md` is a subset of this rule; this rule covers everything upstream of the commit too.

## Observe the Running System

When you reach for a test file to verify behavior, pause and ask: "How would I observe this if I had no test suite?"

A passing test proves the test passes. It does not prove the running system behaves correctly. Prefer observing the actual running system — a CLI invocation, an HTTP request, logged output — when the surface is reachable.

Use tests to verify behavior you can't observe directly. Don't substitute test assertions for system observation when both are available.

## Name Observability Gaps

When you cannot observe a behavior because the system emits no signal for it — no log, no metric, no CLI output, no visible state — do not silently skip the verification.

Name it explicitly as an observability gap finding:

> **Observability gap:** `<behavior>` cannot be verified without `<what's missing>`. This is a gap in the system's instrumentation, not a verification shortcut.

This turns a silent skip into an actionable finding that can drive follow-up instrumentation work.

## Not a Blanket Re-run Mandate

This does not mean re-run every command after every edit. Verify the specific claim you're about to make. If you changed test code, run the tests. If you changed a type signature, run the type checker. Match verification to the claim.
