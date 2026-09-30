# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: Regex anchoring is inconsistent across sibling list-item patterns in snapshot.py

Status: resolved — invalid. Investigation during the known-issues walkthrough found
`_TARGET_FILE_PATTERN`/`_VERIFY_PATTERN` are matched against `stripped` (`line.strip()`,
`_parse_task_file` line 90), not the raw line, so leading indentation is already removed before
either pattern runs. They already parse indented Target Files/Verify items identically to flat
ones — `_FR_PATTERN`/`_AC_PATTERN` just achieve the same tolerance a different way (a `^\s*` anchor
on the raw line vs. pre-stripping). There is no behavior gap and no behavior-change risk from
aligning the patterns cosmetically; the original finding mischaracterized a code-shape difference
as a functional inconsistency.
Run: 147
Source: clean-code
Observed in: commit b72a220
Affected files:
- packages/cfl/src/cfl/snapshot.py

Issue:
`_FR_PATTERN` and `_AC_PATTERN` (lines 23-24) now anchor with `^\s*-\s+`,
tolerating leading indentation so nested FR/AC list items match. The two
structurally similar patterns beside them — `_TARGET_FILE_PATTERN` (line 29,
`^-\s+`) and `_VERIFY_PATTERN` (line 30, `^- \[[ x]\] `) — still require zero
leading whitespace. All four patterns answer "does this line start a Markdown
list item of a given shape," but only two of the four tolerate indentation.

## KI-002: Single-letter `m` reused across five distinct regex matches in snapshot.py

Status: resolved — fixed during known issues walkthrough
Fixed in: rename to fr_match/ac_match/scope_mode_match/complexity_match/target_file_match (pure rename, no behavior change)
Run: 147
Source: clean-code
Reason not fixed now: out-of-scope
Observed in: commit b72a220
Affected files:
- packages/cfl/src/cfl/snapshot.py

Issue:
`_parse_requirements` and `_parse_task_file` reuse the name `m` five times
(lines 45, 49, 54, 58, 109) for five different regex `Match` objects
(`_FR_PATTERN`, `_AC_PATTERN`, `_SCOPE_MODE_PATTERN`, `_COMPLEXITY_PATTERN`,
`_TARGET_FILE_PATTERN`). None of these lines fall inside a hunk this PR
changed (the PR's only snapshot.py hunk is lines 19-24) — this naming
predates the current diff.

Why deferred:
Out of scope for this PR — the finding is on unchanged, pre-existing lines.

Recommended follow-up:
Rename each `m` to a descriptive match variable (e.g. `fr_match`,
`ac_match`, `scope_mode_match`, `complexity_match`, `target_file_match`) in
a follow-up pass, ideally alongside other snapshot.py hygiene cleanup so the
diff isn't a pure rename with no other justification.

Acceptance criteria:
- No single-letter `m` reused across unrelated regex matches in
  `_parse_requirements`/`_parse_task_file`.
