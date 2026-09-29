---
task_id: "T02"
title: "Restructure both design templates to nest ACs under FRs"
status: "planned"
depends_on: []
implements: ["FR#1", "AC#1", "FR#2", "AC#2", "FR#3", "AC#3", "FR#4", "AC#4", "FR#5", "AC#5"]
---

## Summary
Rewrite the `mine-define` and `mine-sketch` design templates so each Functional Requirement carries its own acceptance criteria as nested bullets, the standalone Acceptance Criteria sections disappear, `mine-define`'s Test Strategy loses New Test Coverage, and both templates gain the numbering/citation rules and a "One fact, one home" content rule. Also create the prose contract test file that pins these template changes; later tasks append their own checks to it.

## Target Files
- modify: `skills/mine-define/design-template.md`
- modify: `skills/mine-sketch/design-template.md`
- create: `tests/test_design_doc_contracts.py`
- read: `design/specs/1012-design-doc-single-source/design.md`
- read: `tests/test_challenge_mandate_contracts.py`

## Prompt
Read `design/specs/1012-design-doc-single-source/design.md`, sections `## Functional Requirements` (FR#1–FR#5 and their ACs) and `## Architecture > Template change map`. The Template change map is authoritative: implement each template's column of every row exactly, and use "n/a" rows to know what NOT to add to `mine-sketch`.

For each template:
1. **Nested ACs (FR#1, FR#5).** Replace the `## Functional Requirements` placeholder bullets with a nested example: each `- **FR#N** ...` placeholder followed by indented `  - **AC#N** ...` placeholder bullets carrying the AC guidance that currently lives under `## Acceptance Criteria` (measurable, observable, verifiable by a local command; no CI/post-merge/PR-state criteria — those go to Dependencies and Assumptions). Delete the `## Acceptance Criteria` section. In `mine-define` only, edit the Content Rules line that lists "Requirements sections (Problem, Goals, User Scenarios, Functional Requirements, Edge Cases, Acceptance Criteria)" to drop Acceptance Criteria; no other remaining text may name Acceptance Criteria as a section (text about ACs as a concept, e.g. the AC#N identifier-format rule, stays).
2. **Test Strategy trim (FR#2, mine-define only).** Delete `### New Test Coverage` and its placeholder. Keep `### Required Test Types`, `### Existing Tests to Adapt`, `### Tests to Remove`. Move any still-needed guidance (e.g. Operational Lifecycle convergence-test expectations) into Required Test Types or into the nested-AC guidance rather than dropping it. Update the Scope Mode Effects table's Test Strategy row if it references FR coverage in a way that implies a separate list.
3. **Numbering and citation rules (FR#3).** Add rules (a)–(c) from FR#3 in the section the map names (`## Section Rules` in mine-define, `## Content Rules` in mine-sketch): (a) AC numbers are global and sequential across the doc, never hierarchical like `AC#3.2`; (b) an AC verifying several FRs sits under its primary FR and names the others as `(also FR#N)` or `(also FR#N, FR#M)`, only when it verifies each cited FR's behavior on its own, and an FR that no AC fully verifies gets its own AC; (c) whole-suite checks ("all tests pass", "lint clean") are not ACs, because task Verify and orchestrate already enforce them.
4. **One fact, one home (FR#4).** Add a `One fact, one home` rule to each template's `## Content Rules`: any enumeration (inventory table, file list, coverage list) lives in exactly one section and other sections cite it by ID or name without re-listing it; a count or one-line summary of a fact is a copy, so it cites the home too; when several requirements depend on the same mapping, write the mapping once (usually a table) and cite it. Then apply the map's FR#4 placeholder rows: rewrite the Operational Lifecycle placeholder's closing "Express every applicable lifecycle outcome as an FR#N or AC#N ..." line in both templates to say the section explains the model and each outcome is an FR with its ACs; in mine-define, make the Edge Cases placeholder say it holds context only and any implied behavior becomes an FR with ACs; make `### Changed Files` (mine-define) / `## Changed Files` (mine-sketch) the file-list home and have the `## Architecture` + `## Replacement Targets` (mine-define) / `## Approach` (mine-sketch) placeholders say to cite it.

Then create `tests/test_design_doc_contracts.py` in the parametrized regex-anchor style of `tests/test_challenge_mandate_contracts.py` (module docstring naming what it guards, `REPO_ROOT` from `Path(__file__)`, path constants at the top). Add checks for AC#1–AC#5 as written in the design. Structure the file so later tasks can append their own parametrized cases or test functions without restructuring it.

## Focus
- Current anchors (mine-define): `## Functional Requirements` line 38, `## Edge Cases` 43, `## Operational Lifecycle` 47–51, `## Acceptance Criteria` 53–58, `## Architecture` 72, `## Replacement Targets` 80, `### New Test Coverage` 112–113, `## Content Rules` 153 (requirements-sections list at 155), `## Scope Mode Effects` 159, `## Section Rules` 172 (AC rules at 177–178). mine-sketch: `**Mode:** sketch` line 10, `## Functional Requirements` 22, `## Operational Lifecycle` 27–29, `## Acceptance Criteria` 31–34, `## Approach` 38, `## Changed Files` 46, `## Content Rules` 60 (AC format rule at 63).
- The templates' own example IDs: the placeholder block is inside a fenced ```markdown template. Keep placeholder IDs bolded at list-item start so the example reads like real output.
- Apply the rule to your own edits: don't add a sentence that re-lists or counts what another section already holds (e.g. don't write "Test Strategy has three subsections" anywhere).
- `mine-sketch` has NO Section Rules, Edge Cases, Architecture, Replacement Targets, or Test Strategy — do not add them.
- Run root tests with `mise run test:root`; single file: `uv run --with pytest pytest tests/test_design_doc_contracts.py`.
- Commit type: `docs:` for templates, with the new test file in the same commit (or `test:` for a separate test commit before it).

## Verify
- [ ] FR#1: `skills/mine-define/design-template.md` has no `## Acceptance Criteria` section and its Functional Requirements placeholder shows ACs nested under an FR.
- [ ] AC#1: the contract test for AC#1 passes (no `## Acceptance Criteria` heading in the mine-define template, no remaining text naming Acceptance Criteria as a section, and an indented `**AC#` bullet in the Functional Requirements placeholder).
- [ ] FR#2: mine-define's Test Strategy contains exactly `### Required Test Types`, `### Existing Tests to Adapt`, `### Tests to Remove`.
- [ ] AC#2: `grep -n "New Test Coverage" skills/mine-define/design-template.md` returns no matches.
- [ ] FR#3: rules (a)–(c) appear in mine-define's `## Section Rules` and mine-sketch's `## Content Rules`.
- [ ] AC#3: the contract test for AC#3 passes, finding rules (a) through (c) in each template in the section the Template change map names.
- [ ] FR#4: both templates' `## Content Rules` carry the `One fact, one home` rule with its summary and shared-mapping clauses, and every FR#4 row of the Template change map is applied.
- [ ] AC#4: the contract test for AC#4 passes, finding the rule in each template's Content Rules and each FR#4 placeholder change.
- [ ] FR#5: `skills/mine-sketch/design-template.md` has every change its column of the Template change map lists, including nested ACs and no `## Acceptance Criteria` section.
- [ ] AC#5: the contract test for AC#5 passes (the AC#1 check run against the mine-sketch template).
