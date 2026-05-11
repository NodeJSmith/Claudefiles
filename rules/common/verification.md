# Verification Before Completion (CRITICAL)

Never claim work is done without evidence from actual command output. "Should work" is not verification.

## Evidence Requirements

| Claim | Required evidence |
|---|---|
| "Tests pass" | Fresh test output showing 0 failures (use `timeout 300 pytest` per `testing.md`) |
| "Bug is fixed" | Reproduction steps that now produce the correct result |
| "Build succeeds" | Build command output with exit code 0 |
| "Linter is clean" | Linter output showing no errors |
| "Type checker passes" | Type checker output with no errors |
| "Feature works" | Demonstrated via test, script, or browser screenshot |

Run the command, read the output, confirm it matches the claim. If the output is ambiguous, dig deeper — don't round up.

## Red-Flag Language

These phrases signal a claim without evidence. If you catch yourself writing one, stop and verify first:

- "should pass / should work / should be fine"
- "probably fixed"
- "seems to work"
- "I believe this resolves..."
- "Done!" / "All set!" before running verification

## Scope

This applies to **all completion claims** — mid-task status updates, commit messages, PR descriptions, and responses to the user. The git-workflow.md pre-commit verification is a subset of this rule; this rule covers everything upstream of the commit too.

## Not a Blanket Re-run Mandate

This does not mean re-run every command after every edit. Verify the specific claim you're about to make. If you changed test code, run the tests. If you changed a type signature, run the type checker. Match verification to the claim.
