# Review External PR — Reference

Extended guidance for `SKILL.md`. Referenced by SKILL.md; do not reference further files from here.

---

## Comment Draft Template

```markdown
**[<label>] <one-line title of the issue>**

<1-2 sentences: exactly what to change. One ask, concrete enough that the author could
apply it directly. No "or alternatively" menus.>

<1-3 sentences: why, with file:line references and the evidence actually run (the test
that failed, the query result, the consumer that breaks). Not "this looks wrong".>

*— Posted by Claude (AI review assistant)*
```

For a finding whose evidence is `judgment:`, the why gives the reasoning as reasoning, without claiming anything was run or verified.

The author should be able to act on the comment from its first two lines: the label says whether it blocks approval, and the first sentence says what to change. Keep the body to about six lines. Use a short bullet list only when a thread has 3+ sub-points.

**Labels.** `<label>` is one of:
- `Blocking` — Critical and High findings, and any PR claim the investigation disproved.
- `Non-blocking` — Medium and below, and the tests and docs bucket threads.
- `Non-blocking — worth fixing while you're in here` — an issue that predates the PR, in code the PR touches.

The user can flip any label at the Phase 5 shaping gate.

**Question form.** Used only when the user chooses at the shaping gate to post an open question to the author. The header is `**[Question] <title>**`, the first sentence is the one question, and the why says what was checked and why this session couldn't settle it.

The footer is fixed: this exact wording, last line, its own paragraph.

---

## Worked Example — Tests Bucket

From a PR adding a new claims org (4 new task classes, shared utility changes):

```markdown
**[Non-blocking] Add tests for the new task classes and the two shared-code changes**

Please add one scenario per new task class (`ui_claims`, `preproc_claims`, `raw_claims`,
`bronze_claims`), plus cases for `files_exist_in_directory` and the new date format.

The repo's bar is "test one scenario per task class, at minimum", and the only test change
is a deleted assertion that `"yyyy-MM-dd HH:mm:ss"` was *unparseable*. `convert_date_columns`
(`dataframe/pipeline.py:148`) now parses it, and `git grep 'HH:mm:ss' tests/` at HEAD
returns nothing, so no test covers the new behavior.

*— Posted by Claude (AI review assistant)*
```

What makes this work:
- The ask comes first and is one ask, so the author knows what to do without reading further.
- The why quotes the repo's own testing standard, not a generic "should have tests" appeal.
- The evidence proves the claim: a grep of the tests for the format string comes back empty. A passing test suite wouldn't have shown that.

---

## Re-reviewing After New Commits

Re-invoking the skill after the author pushes is normal. It should show which prior findings the new commits addressed and what new issues appeared.

Phase 4 step 1 handles the dedup: fetch existing threads, including resolved ones, and match on file:line plus the same underlying concern, not just the same general topic, regardless of author. A resolved thread whose issue is still present in the code is treated as unresolved. Only draft what is genuinely new or still unaddressed.

---

## Platform Notes

### GitHub

`gh pr comment` creates a top-level conversation comment, not an inline review thread anchored to a file/line. Each comment can cite several locations and survives later pushes that would orphan a line anchor, so file:line references go in the body text.

### Azure DevOps

`ado-api pr thread-add` creates a top-level thread (not inline). Same rationale as GitHub: reference file:line in the body, not as positional anchoring.

Both platforms: use `--body-file` to post the comment body from a temp file rather than passing it as a shell argument. Comment bodies contain markdown, backticks, and quotes that break shell interpolation.
