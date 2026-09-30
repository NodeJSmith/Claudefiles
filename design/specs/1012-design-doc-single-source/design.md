# Design: One fact, one home in design docs

**Date:** 2026-09-29
**Status:** approved
**Scope-mode:** hold
**Research:** design/research/2026-09-29-design-doc-single-source/research.md

## Problem

The `mine-define` template makes the writer list the same behaviors in several parallel places: Functional Requirements, a separate Acceptance Criteria list that "maps to" FRs, Test Strategy > New Test Coverage that maps to FRs again, Operational Lifecycle (whose placeholder says to restate its content as FRs and ACs), and any inventory table in Architecture. Edge Cases has no such instruction but in practice repeats FR and AC behavior as prose. Files get listed in Architecture, Replacement Targets, and Impact. `mine-sketch` has the same FR/AC split.

The fine-toothed comb reads for cross-section consistency, so every restatement is something it can find out of sync. In hassette spec 115, three comb passes each found a new pair of lists that disagreed. Since 2026-08-01, 77% of fine-toothed-comb runs across all projects reported at least one blocking finding (289 of 373 when the research was written; `agent-stats --type fine-toothed-comb --since 2026-08-01` reproduces it). That counts every comb transcript, not only the combs recorded as cfl gates.

## Goals

- A design written with the new templates passes the comb in two runs or fewer without findings about two restatements disagreeing.
- `mine-plan`, cfl snapshots, and task `implements` traceability keep working with the same IDs; the only parser change is the anchoring in FR#6.
- When two statements of one fact disagree, the comb recommends consolidating them into one home rather than syncing the copies.

## Non-Goals

- Migrating archived specs, or the non-archived `027-how-skill` and `033-orchestration-cost-analysis`. Archived docs are frozen, and both parse unchanged (see FR#6).
- Restructuring Goals or User Scenarios. They sit at a different altitude and weren't where the drift came from.
- Detecting comb findings that converge on one mechanism across runs. That is issue #599, to build only if combs still fail to converge once this ships; the issue carries the design worked out so far.
- Issue templates (`agents/issue-refiner.md`, `skills/mine-create-issue/worker.md`), which have their own unrelated AC sections.

## User Scenarios

### Designer: runs `/mine-define` or `/mine-sketch`
- **Goal:** get a signed-off design without a comb loop that never settles
- **Context:** Phase 4 writes the doc, Phase 5 combs it

#### Write and comb a design

1. **Agent writes design.md**
   - Sees: the template, where each FR is followed by its own AC bullets, and the one-fact-one-home rule
   - Then: every inventory is written once and cited everywhere else
2. **Comb runs**
   - Then: findings are about substance, because no two lists need to agree
   - Then: if two statements of one fact do disagree, the finding names the fact and every place it's stated, and recommends one home
3. **Sign-off, then `/mine-plan`**
   - Then: FR and AC IDs are read as today, tasks cite them in `implements`, and cfl snapshots count them

## Functional Requirements

Each FR's own acceptance criteria follow it directly. Contract checks in the ACs run as `pytest tests/test_design_doc_contracts.py`, referred to below as "the contract tests."

**Template shape**

- **FR#1** The `mine-define` template places each requirement's acceptance criteria directly under that FR as indented `**AC#N**` bullets and has no top-level `## Acceptance Criteria` section.
  - **AC#1** The contract tests pass a check that `skills/mine-define/design-template.md` has no `## Acceptance Criteria` heading, that no remaining text names Acceptance Criteria as a section, and that its Functional Requirements placeholder contains an indented `**AC#` bullet.
- **FR#2** Test Strategy in the `mine-define` template holds only concerns that span requirements: `### Required Test Types`, `### Existing Tests to Adapt`, `### Tests to Remove`. `### New Test Coverage` is removed, because the ACs now name what each behavior's test proves; its two pieces of guidance that don't belong to any single requirement move into `### Required Test Types`: identify which testing layer (unit, integration, E2E) each behavior needs, and, when Operational Lifecycle is present, cover repeated transient failure, user-action-required or terminal failure, retry bounds, recovery/reset, mixed realistic populations, and completion/status accounting, since isolated single-transition tests do not prove convergence.
  - **AC#2** `grep -n "New Test Coverage" skills/mine-define/design-template.md` returns no matches.
- **FR#3** Each template states these rules, in the section the Template change map names: (a) AC numbers are global and sequential across the doc, never hierarchical like `AC#3.2`; (b) an AC that verifies several FRs sits under its primary FR and names the others as `(also FR#N)` or `(also FR#N, FR#M)`, but only when it verifies each cited FR's behavior on its own; an FR that no AC fully verifies gets its own AC; (c) checks that apply to the whole suite ("all tests pass", "lint clean") are not ACs, because task Verify and orchestrate already enforce them.
  - **AC#3** The contract tests find rules (a) through (c) in each template, in the section the Template change map names.
- **FR#4** Each template carries a "One fact, one home" content rule. Any enumeration (an inventory table, a file list, a coverage list) lives in exactly one section, and every other section cites it by ID or name without re-listing it. A count or one-line summary of a fact is a copy of it, so it cites the home too. When several requirements depend on the same mapping, the mapping is written once, usually as a table, and the requirements cite it. The placeholder changes that apply this rule to each template are in the Template change map.
  - **AC#4** The contract tests find the `One fact, one home` rule, including its summary and shared-mapping clauses, in each template's Content Rules, and find each placeholder change the Template change map assigns to FR#4.
- **FR#5** The `mine-sketch` template gets every change the Template change map lists for it, including nested ACs with no top-level `## Acceptance Criteria`.
  - **AC#5** The contract tests pass the FR#1 check against `skills/mine-sketch/design-template.md`.

**Parsing and planning**

- **FR#6** cfl counts an FR or AC as defined only when its bolded ID starts a list item, flat or nested, and parses a nested-format doc into the same FR and AC IDs and texts as the equivalent flat doc. `snapshot.py` anchors both patterns to list-item start; `spec.py` needs no change.
  - **AC#6** `pytest packages/cfl/tests/test_snapshot.py -k nested` passes. The test uses a fixture with ACs indented under FRs, including one with an `(also FR#N)` suffix, a prose line citing a bolded ID mid-sentence, and a struck-through removal line (`- ~~**FR#N**~~ **Removed**`). It asserts the same `fr_count`, `ac_count`, and requirement IDs as the flat fixture, with neither the mid-sentence citation nor the removal counted.
- **FR#7** The `mine-plan` validator's Step 1 extracts FR and AC identifiers with their text in one pass, wherever they appear, and records no location. The current "the section it appears in" field is dropped because Steps 3 and 4 match by ID only and never read it.
  - **AC#7** The contract tests confirm `skills/mine-plan/validator-prompt.md` Step 1 describes a single extraction pass and no longer contains "the section it appears in."
- **FR#8** `mine-plan/SKILL.md`'s extraction list describes Test Strategy as the subsections FR#2 keeps and describes ACs as nested under their FRs.
  - **AC#8** The contract tests confirm `skills/mine-plan/SKILL.md`'s extraction list names exactly the Test Strategy subsections FR#2 keeps and describes ACs as nested under their FRs.

**Other writers and readers**

- **FR#9** When the challenge's Inline Resolution Flow applies a finding to a `design-doc` target, the edit follows the Content Rules of the template that produced the doc (`mine-sketch`'s when the header has `**Mode:** sketch`, otherwise `mine-define`'s), so ACs stay nested and no fact gets restated.
  - **AC#9** The contract tests find a reference to the design template's Content Rules in `skills/mine-challenge/findings-protocol.md`'s Inline Resolution Flow.
- **FR#10** `skills/mine-implementation-review/reviewer-prompt.md` looks for named tests in the design's ACs and Test Strategy, not in New Test Coverage.
  - **AC#10** The contract tests find that `skills/mine-implementation-review/reviewer-prompt.md`'s missing-test check names the design's ACs as a place tests are named.

**Comb**

- **FR#11** When `agents/fine-toothed-comb.md` finds two statements of the same fact that disagree, it reports the fact, every place it's stated, and a recommendation to consolidate into one home rather than sync the copies.
  - **AC#11** The contract tests find the consolidate-don't-sync instruction in `agents/fine-toothed-comb.md`.
- **FR#12** `comb-gate.md`'s intro lists exactly the skills that reference it (`mine-comb`, `mine-define`, `mine-sketch`, `mine-plan`) and no longer names `mine-orchestrate`, which does not read it.
  - **AC#12** The contract tests compute which files under `skills/` reference `comb-gate.md` and assert that the intro names exactly those skills.

## Edge Cases

- **Combs of plans and implementations.** FR#11's instruction lives in the comb agent, so it applies to every artifact the comb reads, including task files and code.
- **Old-format docs.** They still parse (FR#6), and `mine-plan` reads the same IDs from them.

## Key Constraints

- AC IDs must keep the `**AC#<int>**` form. The snapshot regex (`packages/cfl/src/cfl/snapshot.py:20`) and the `implements` validator (`packages/cfl/src/cfl/spec.py:23`) both require it, and tasks depend on AC IDs: in the cfl database on 2026-09-29, 368 of 452 snapshotted tasks cite at least one AC, and the 89 snapshotted plans hold 1,028 AC citations against 1,525 FR citations. Source: `sqlite3 ~/.local/share/claudefiles/cfl.db "select j.value from task_snapshots t, json_each(t.implements) j"`, counted by prefix.

## Dependencies and Assumptions

- **Accepted costs** (confirmed during discovery):
  - The FR section gets longer and loses its compact list of FRs. Bold group headings within the section are the skimmable outline; a one-line-per-FR digest was rejected because FR#4 treats it as a copy.
  - A reader looking only at an FR can miss an AC that sits under another FR marked `(also FR#N)`. Coverage checks match by ID, so they're unaffected.
- **Run 3+ comb loops still end in "Fix and finish"** until issue #599 lands. That is today's behavior, not a regression (user decision at challenge).

## Architecture

### Template shape

A requirement block looks like this:

```markdown
- **FR#N** <one behavior>
  - **AC#M** <command-verifiable outcome>
  - **AC#M+1** <outcome> (also FR#K)
```

`_parse_requirements` in `packages/cfl/src/cfl/snapshot.py:29-63` scans line by line and ignores sections and indentation. Today its patterns are unanchored (`re.search`), so any line containing a bolded `**FR#<int>**` or `**AC#<int>**` counts as a definition, and a bolded citation mid-sentence would create a duplicate or misclassified entry. FR#6 anchors both patterns to list-item start (`^\s*-\s+\*\*FR#(\d+)\*\*`, same for AC), so a nested AC still parses and a citation never does. Of 555 bolded-ID lines in pre-existing specs (excluding this spec's own), only 3 would stop matching: struck-through removals (`- ~~**FR#N**~~`), where the `~~` sits between the dash and the ID. Those are removed requirements and should not count. `mine-plan`'s coverage checks (`skills/mine-plan/reviewer-prompt.md:9-10`) and `skills/mine-plan/task-format.md` work purely by ID and need no change.

### Template change map

The two templates have different sections, so this table is the one home for where each change lands. FR#1 through FR#5 cite it.

| Change | `mine-define` template | `mine-sketch` template |
|---|---|---|
| Nested ACs, no top-level Acceptance Criteria (FR#1, FR#5) | `## Functional Requirements` placeholder shows nested ACs; `## Acceptance Criteria` deleted | Same |
| Content Rules list of requirements sections (FR#1) | Line naming "Requirements sections (Problem, Goals, User Scenarios, Functional Requirements, Edge Cases, Acceptance Criteria)" drops Acceptance Criteria; ACs are covered as part of Functional Requirements | n/a, no such list |
| Numbering and citation rules (FR#3) | `## Section Rules` | `## Content Rules` (sketch has no Section Rules) |
| One-fact-one-home rule (FR#4) | `## Content Rules` | `## Content Rules` |
| Test Strategy trim (FR#2) | `### New Test Coverage` deleted; its layer and Operational Lifecycle guidance moves to `### Required Test Types` | n/a, no Test Strategy |
| Operational Lifecycle (FR#4) | The placeholder's closing line ("Express every applicable lifecycle outcome as an FR#N or AC#N below") is rewritten: the section explains the model, and each outcome is an FR with its ACs | Same rewrite of its equivalent closing line |
| Edge Cases (FR#4) | Placeholder says it holds context only; implied behavior becomes an FR with ACs | n/a, no Edge Cases |
| File-list home (FR#4) | `### Changed Files` is the home; `## Architecture` and `## Replacement Targets` placeholders say to cite it | `## Changed Files` is the home; `## Approach` placeholder says to cite it |

### Comb

The comb agent change (FR#11) is the reviewer side of the same rule the templates give the writer (FR#4). It lives in the agent file so it covers every artifact the comb reads.

### Why this shape

Among the formats surveyed in the research brief, OpenSpec nests scenarios under each requirement, Kiro makes the EARS sentence the acceptance criterion, and Spec Kit nests acceptance scenarios under user stories. None keeps parallel top-level lists of the same facts. Nested AC#N was chosen over dropping ACs because tasks cite ACs heavily (figures in Key Constraints).

### Existing code leverage

| Sub-problem | Existing code | Coverage |
|---|---|---|
| Parse nested FR/AC | `snapshot.py` `_parse_requirements` | Partial — reads nesting already; patterns need anchoring (FR#6) |
| Validate `implements` IDs | `spec.py` `_IMPLEMENTS_RE` | Full — reuse as-is |
| Parallel FR/AC/New Test Coverage | both `design-template.md` files | Replace — nested ACs |
| Two-pass FR/AC extraction | `mine-plan/validator-prompt.md` Step 1 | Replace — one pass, no location field |
| Prose contract tests | `tests/test_challenge_mandate_contracts.py` | Full — reuse the pattern |

## Implementation Preferences

- Contract tests use the parametrized regex-anchor style of `tests/test_challenge_mandate_contracts.py`.
- Commits use `docs:` for skill, template, and agent changes and `fix:` for the `snapshot.py` anchoring. Tests ship in the same commit as the change they pin.

## Replacement Targets

- The standalone Acceptance Criteria sections and New Test Coverage, as the Template change map lists.
- The two-pass extraction in `validator-prompt.md` Step 1 is replaced (FR#7).

## Convention Examples

### Prose contract test

**Source:** `tests/test_challenge_mandate_contracts.py`

```python
@pytest.mark.parametrize(
    ("relative_path", "required_anchors"),
    [
        (
            DEFINE_SKILL,
            [
                ("define challenge phase heading", r"^## Phase 5\.5: Challenge$"),
                ("define challenge gate reference", r"challenge-gate\.md"),
            ],
        ),
```

### Snapshot fixture

**Source:** `packages/cfl/tests/test_snapshot.py` (IDs shown as `<n>` for readability)

```python
(d / "design.md").write_text(
    "**Scope-mode:** hold\n"
    "## Functional Requirements\n"
    "- **FR#<n>** Users can create widgets\n"
    "## Acceptance Criteria\n"
    "- **AC#<n>** Widget list shows all widgets (FR#<n>)\n"
)
```

## Alternatives Considered

- **Drop AC# and give each FR a Verify line.** Rejected: most tasks cite ACs (see Key Constraints), and every consumer would change.
- **EARS sentences as the requirement and criterion in one.** Rejected: it drops AC# too, and it's the biggest style change for the writer.
- **Add a cross-run convergence check to the comb gate in this change.** Deferred to issue #599: the template changes don't depend on it, and whether combs still fail to converge once facts have one home is unknown until this ships.

## Test Strategy

### Required Test Types

- Unit tests (pytest, `packages/cfl/tests/`) for parsing the nested format (FR#6).
- Prose contract tests (pytest regex anchors, a new `tests/test_design_doc_contracts.py`) for template, comb, and consumer wording.
- **Gap:** no harness runs a skill end to end, so nothing automated shows the comb converges faster. The observed evidence is this doc's own comb-run count plus `define-comb` gate stats afterward.

### Existing Tests to Adapt

No existing tests affected. `test_snapshot.py`'s flat fixture stays as the comparison baseline for AC#6.

### Tests to Remove

No tests to remove.

## Documentation Updates

No README or REFERENCE.md changes: no skills, agents, or scripts are added or renamed. The CHANGELOG entry is added at PR time.

## Impact

### Changed Files

- modify `skills/mine-define/design-template.md` — its column of the Template change map (FR#1–FR#4)
- modify `skills/mine-sketch/design-template.md` — its column of the Template change map (FR#3–FR#5)
- modify `skills/mine-comb/comb-gate.md` — caller list (FR#12)
- modify `agents/fine-toothed-comb.md` — consolidate-don't-sync instruction (FR#11)
- modify `skills/mine-challenge/findings-protocol.md` — design-doc edits follow the template Content Rules (FR#9)
- modify `skills/mine-plan/SKILL.md` — extraction list wording (FR#8)
- modify `skills/mine-plan/validator-prompt.md` — one-pass extraction, no location field (FR#7)
- modify `skills/mine-implementation-review/reviewer-prompt.md` — named-test lookup (FR#10)
- modify `packages/cfl/src/cfl/snapshot.py` — anchor `_FR_PATTERN` and `_AC_PATTERN` to list-item start (FR#6)
- modify `packages/cfl/tests/test_snapshot.py` — nested fixture (FR#6)
- create `tests/test_design_doc_contracts.py` — contract tests

### Behavioral Invariants

- FR and AC ID formats and task `implements`/Verify rules are unchanged. cfl snapshot output is unchanged for list-item definitions; struck-through removed IDs stop counting.
- The comb gate's core rule stays: findings are never cleared by acknowledgement alone.

### Blast Radius

Every future `mine-define`, `mine-sketch`, and `mine-plan` run, and every comb-gate caller. Nothing changes at runtime for archived specs.

## Open Questions

None.

