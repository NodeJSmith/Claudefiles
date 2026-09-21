# REVIEW.md Authoring

`REVIEW.md` is a per-directory file of review questions that forces investigation instead of confirmation. `code-reviewer`, `integration-reviewer`, and `wtf-reviewer` all read it explicitly via `find-review-md` (see each agent's own Step 1) and answer each question against the current code. It lives in its own file, not `CLAUDE.md`, specifically so its content is never auto-injected into non-reviewer agents that also touch the directory — only an agent that goes looking for it reads it.

This covers the authoring side: what makes a `REVIEW.md` question actually catch bugs, versus one a reviewer skims and confirms.

## Questions, Not Assertions

Write review content as a question the reviewer must go answer by reading code — not as a stated fact the reviewer can use to confirm the code already matches.

- Bad (assertion): `build_manifest_info only includes tracked entries.`
- Good (question): `Does build_manifest_info include all instance states, or only tracked ones?`

An assertion reads as already-true, so the model uses it to confirm the code — including on code where the assertion is false. A question forces tracing the actual code path before answering, which is where the bug surfaces.

This was tested directly: the same review content written as assertions and as questions, graded against the same 7 confirmed bugs in one fixture. Assertions caught 0/7 — the reviewer used them to confirm the code matched, producing PASS verdicts on buggy code. Questions caught 4/7 (code-reviewer) and 5/7 (integration-reviewer). Concrete hits included a sibling-parity question catching a handler missing the try/except its counterpart had, and a data-completeness question catching a builder function that silently iterated only a subset of the states it claimed to cover.

## Where Cross-Module Pointers Go

When a directory's code reads or depends on state defined elsewhere in the repo, put the pointer in the *consuming* module's `REVIEW.md`, not the dependency's. `check-review-questions` scans every tracked `REVIEW.md`, extracts its backtick-quoted file references, and matches each one against the branch's changed files by exact repo-relative path — so `api/REVIEW.md` naming `` `core/models.py` `` (a full path) gets flagged stale whenever `core/models.py` changes, even though nothing in `api/` changed. That's the intended direction: a diff is more likely to touch the consumer than the thing it depends on.

Write cross-module references as full repo-relative paths in backticks (`` `core/models.py` ``), not a bare filename. A bare filename resolves relative to the `REVIEW.md`'s own directory, so it silently fails to match a file that actually lives elsewhere in the repo.

## Size

Keep each `REVIEW.md` file under ~40 total lines, counting its section headings — 3-6 sharp questions, not a checklist. A longer file drifts toward generic coverage instead of the specific cross-cutting concerns this directory's code actually has. If a directory needs more than that, the directory itself is probably a candidate to split.

## Worked Example

```markdown
# REVIEW.md — api/

## Data Completeness
Does `list_items()` return every item, or only ones matching a hidden default
filter (e.g. `status=active`)? Check the query the DB layer builds, not just
the function signature.

## Sibling Parity
`create_item()` wraps its DB write in try/except and logs on failure. Does
`update_item()` do the same, or does a DB error there propagate unhandled to
the caller?

## Field Propagation
`core/models.py`'s `Item` has an `owner_id` field. Is it present in every
response this module returns, or does one serialization path drop it?
```

Optional further reading: `design/research/2026-09-19-nested-instruction-files/research.md` (size and staleness rules for nested instruction files) and `design/research/2026-09-19-llm-code-review-prompts/research.md` (why reviewers miss cross-cutting bugs without structured investigation) — neither is required to apply the rules above.
