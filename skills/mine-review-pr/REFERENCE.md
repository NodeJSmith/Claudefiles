# Review External PR — Reference

Extended guidance for `SKILL.md`. Referenced by SKILL.md; do not reference further files from here.

---

## Comment Draft Template

```markdown
**<one-line bolded title of the issue>**

<1-4 sentences: what the finding is, with file:line references, and the concrete evidence
that makes it true. Not "this looks wrong," but the actual line, the actual duplicate, the
actual missing case.>

<1-2 sentences: the suggested fix, concrete enough that the PR author could apply it
directly. If the fix is genuinely a judgment call rather than a clear improvement, say so
("...unless the duplication is deliberate for a reason not obvious from the code.").>

*— Posted by Claude (AI review assistant)*
```

Keep each draft to one screen's worth of text. A thread that requires scrolling reads as a report dump, not a review comment. If a bucket has 3+ sub-findings, use a short bullet list rather than a wall of prose.

The footer line is fixed text. Always this exact wording, always the last line, always as its own paragraph (blank line before it).

---

## Worked Example — Tests Bucket

From a PR adding a new claims org (4 new task classes, shared utility changes):

```markdown
**Test coverage gaps**

This PR adds 4 new task classes (`ui_claims`, `preproc_claims`, `raw_claims`, `bronze_claims`
under `claims/ui/`) and changes behavior in 3 shared files, but the only test-suite change is
a single deleted assertion. A few gaps stand out:

- No test for any of the 4 new UI task classes.
- No test for the new `files_exist_in_directory` utility (`utils.py`). The shared
  `PreProcTask.launch()` fix has no test proving it behaves correctly on an empty-but-existing
  directory.
- The new date format `"yyyy-MM-dd HH:mm:ss"` added to `convert_date_columns`
  (`dataframe/pipeline.py:148`) replaces a test case that previously asserted this exact
  string was *unparseable*. No new case proves it now parses to the right date.

Given the project's test-coverage bar of "test one scenario per task class, at minimum," would
be good to see the new task classes and the two shared-code changes covered before merge.

*— Posted by Claude (AI review assistant)*
```

What makes this work:
- File:line references throughout, not vague pointers.
- A direct quote from the repo's own testing standard, not a generic "should have tests" appeal.
- Explains *why* the removed test case matters: it asserted the opposite of the new behavior, not just that a line was deleted.

---

## Why Phase 4 (verification) is mandatory

Reviewers read a diff, not the PR. In practice this produces a specific, recurring failure: flagging a change as "silent" or "undisclosed" when the PR author already named it in the description. Posting that framing tells the author their description wasn't read, which undermines every other finding. Cross-checking against the description before drafting catches this.

The same applies to line numbers and "this exists twice" claims. Diffs go stale as soon as a follow-up commit lands. Read the file at current HEAD, not the patch.

---

## Re-reviewing After New Commits

PRs evolve. Re-invoking this skill on the same PR after the author pushes changes is normal. You want to see if new commits addressed prior findings and whether new issues appeared.

Phase 4 step 3 handles the dedup: fetch existing threads, match on the Claude footer, drop anything already posted. Only draft what is genuinely new or materially changed.

---

## Platform Notes

### GitHub

`gh pr comment` creates a top-level conversation comment (not an inline review thread anchored to a file/line). This is the correct behavior. External review comments are general observations, not line-level nitpicks. File:line references go in the comment body text.

### Azure DevOps

`ado-api pr thread-add` creates a top-level thread (not inline). Same rationale as GitHub: reference file:line in the body, not as positional anchoring.

Both platforms: use `--body-file` to post the comment body from a temp file rather than passing it as a shell argument. Comment bodies contain markdown, backticks, and quotes that break shell interpolation.
