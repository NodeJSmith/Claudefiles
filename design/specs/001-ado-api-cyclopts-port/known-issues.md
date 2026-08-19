# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: `missed_prod.py` module docstring references a Rhyme-only file that doesn't exist here

Status: resolved — fixed during known issues walkthrough
Run: 17
Source: impl-review
Reason not fixed now: out-of-scope
Observed in: T01 (commit f78f77c)
Affected files:
- packages/ado-api/src/ado_api/commands/missed_prod.py

Issue:
The module's own docstring says build tags are "set by `tag_pipeline_run.py`" — a Rhyme-monorepo
producer script that does not exist in this repo. This is the same class of stale cross-reference
that `src/ado_api/tags.py`'s docstring was deliberately rewritten to avoid during the port.

Why deferred:
T01's design only named `tags.py`'s docstring for rewrite (design.md, "Vendoring the Rhyme
coupling"). Rewriting `missed_prod.py`'s docstring too would be a reasonable improvement but
expands beyond the task's stated scope, and the reference is not user-facing (no CLI output or
error message surfaces it) — it only misleads a developer reading the source.

Recommended follow-up:
Rewrite `missed_prod.py`'s module docstring the same way `tags.py`'s was: state plainly that these
are one organization's build-tag conventions and that the command is inert at an org tagging builds
differently, without naming a Rhyme-only producer script.

Acceptance criteria:
- `grep -rn "tag_pipeline_run\|workflow_creator\|add_pr_comment\|dbx-pipeline-health" packages/ado-api/src` returns nothing. (Previously missing `-r`, which made the check a silent no-op against a directory target — verified it now recurses into `commands/` and would have caught `missed_prod.py:212`'s former `tag_pipeline_run.py` reference before that line was reworded during the final review pass.)

## KI-002: `commands/retry_stage.py` uses pydantic `BaseModel` where the rest of the package uses plain dataclasses

Status: open
Run: 17
Source: clean-code
Reason not fixed now: out-of-scope
Observed in: T01 (commit f78f77c)
Affected files:
- packages/ado-api/src/ado_api/commands/retry_stage.py

Issue:
`RetryRecord`, `BuildRef`, and `WatchRecord` in `retry_stage.py` are pydantic `BaseModel`
subclasses, while every other data holder in the package (`AdoConfig`, `AdoContext` in
`az_client.py`, `AdoCliContext` in `cli/context.py`) is a plain `@dataclass(frozen=True)`.
Grep confirms the split: `grep -rn "BaseModel\|dataclass" src/ado_api/*.py
src/ado_api/commands/*.py` returns `BaseModel` only in `retry_stage.py` (3 classes) and
`dataclass` only in `az_client.py` (2 classes). None of the three pydantic models validate
external input directly — they're built from already-processed API responses — so the code
in use is `model_copy(update=...)` (immutable partial updates) and `model_dump(mode="json")`
(JSON serialization of `StrEnum` fields), both of which `dataclasses.replace()` plus
`formatting.json_output`'s existing `default=str` fallback could likely cover with a plain
dataclass instead.

Why deferred:
This file was ported wholesale from analytics per design.md's "Wholesale replacement, not a
merge" approach — the pydantic/dataclass split already existed in the source and is not a
choice made during this port. Converting three classes with heavy internal use
(`model_copy(update=...)` appears at every `_classify`/`_execute`/`_watch_stages` branch,
and `model_dump(mode="json")` is on the CLI's JSON-output path) is a real refactor with
behavioral risk — enum serialization and `None`-handling can differ subtly between
`model_dump(mode="json")` and a hand-rolled `dataclasses.asdict()` + `default=str` — not a
mechanical style fix, and T01-T05's approved scope was the port itself, not a package-wide
data-modeling unification.

Recommended follow-up:
If the mixed style is worth resolving, convert `RetryRecord`, `BuildRef`, and `WatchRecord`
to `@dataclass(frozen=True)` with `dataclasses.replace()` in place of `model_copy(update=...)`,
and verify `json_output`'s `default=str` serializes the `StrEnum` fields (`Action`, `Outcome`,
`WatchResult`) the same way `model_dump(mode="json")` does today — as its own reviewed change,
with the retry-stage test suite (`tests/test_retry_stage.py`) as the equivalence check.

Acceptance criteria:
- `grep -n "BaseModel" packages/ado-api/src/ado_api/commands/retry_stage.py` returns nothing, or a comment explains why pydantic is still needed there.
- `uv run --project packages/ado-api pytest tests/test_retry_stage.py` passes with the same assertions as before the change.
