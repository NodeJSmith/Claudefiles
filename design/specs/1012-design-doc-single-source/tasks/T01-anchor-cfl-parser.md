---
task_id: "T01"
title: "Anchor cfl FR/AC patterns to list-item start"
status: "done"
depends_on: []
implements: ["FR#6", "AC#6"]
---

## Summary
cfl's snapshot parser currently counts any line containing a bolded `**FR#N**` or `**AC#N**` as a requirement definition, because its patterns are unanchored. Nested ACs (indented under their FR) must keep parsing, while a bolded ID cited mid-sentence or a struck-through removed requirement must not count. This task anchors both patterns to the start of a list item and adds a nested-format fixture test proving the parse matches the flat format.

## Target Files
- modify: `packages/cfl/src/cfl/snapshot.py`
- modify: `packages/cfl/tests/test_snapshot.py`
- read: `packages/cfl/tests/helpers.py`
- read: `design/specs/1012-design-doc-single-source/design.md`

## Prompt
In `packages/cfl/src/cfl/snapshot.py`, change `_FR_PATTERN` and `_AC_PATTERN` (currently `r"\*\*FR#(\d+)\*\*\s+(.*)"` and the AC equivalent, lines 19–20) so they only match when the bolded ID is the first thing in a Markdown list item, at any indentation: `^\s*-\s+\*\*FR#(\d+)\*\*\s+(.*)` and `^\s*-\s+\*\*AC#(\d+)\*\*\s+(.*)`. `_parse_requirements` keeps calling `.search(line)`; with the `^` anchor that behaves as a start-of-line match. Do not change group numbering — callers read `group(1)` (the number) and `group(2)` (the text).

In `packages/cfl/tests/test_snapshot.py`, add a test (name it so `-k nested` selects it, e.g. `test_snapshot_nested_format_matches_flat`) that writes a nested-format design.md and asserts the parsed result equals what the equivalent flat format produces. The nested fixture must contain:
- FRs as `- **FR#1** ...` list items with ACs indented beneath them as `  - **AC#1** ...`;
- one AC carrying an `(also FR#2)` suffix;
- a prose line citing a bolded ID mid-sentence (e.g. `This depends on **FR#1** being done first.`), which must NOT be counted;
- a struck-through removal line `- ~~**FR#9**~~ **Removed** — dropped.`, which must NOT be counted.

Assert the same `fr_count`, `ac_count`, and requirement IDs and texts as a flat fixture holding the same FRs and ACs. Follow the existing fixture pattern in this file (`spec_and_run`, `feature_dir`, `insert_spec_with_run`, `insert_task`) — read how the existing tests call `snapshot_plan` and read back `plan_snapshots` before writing yours. Keep the existing flat fixture unchanged; it is the comparison baseline.

## Focus
- `_parse_requirements` (snapshot.py:29–63) checks the FR pattern before the AC pattern and `continue`s on a match; keep that order.
- The only production caller is `cfl.cli` (`snapshot_plan` at run start). Of 579 bolded-ID lines across existing `design/specs/*/design.md`, the only 3 that stop matching are struck-through removals — an intended correction, not a regression.
- Run tests the way CI/prek does: `mise run test:cfl` (runs `uv run --group dev pytest` inside `packages/cfl`). For the single test: from `packages/cfl`, `uv run --group dev pytest tests/test_snapshot.py -k nested`.
- Commit type for the parser change is `fix:`; the test ships in the same commit.

## Verify
- [ ] FR#6: `snapshot.py`'s `_FR_PATTERN` and `_AC_PATTERN` are anchored with `^\s*-\s+`, and `mise run test:cfl` (full cfl suite) passes with the existing flat-fixture tests unchanged.
- [ ] AC#6: from `packages/cfl`, `uv run --group dev pytest tests/test_snapshot.py -k nested` passes; the test's nested fixture includes an `(also FR#N)` suffix, a bolded mid-sentence citation, and a struck-through removal, and asserts the same `fr_count`, `ac_count`, and IDs as the flat fixture with neither the citation nor the removal counted.
