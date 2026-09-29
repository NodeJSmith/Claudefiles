# Context: One fact, one home in design docs

## Problem & Motivation
The `mine-define` and `mine-sketch` design templates make the writer list the same behaviors in several parallel places: Functional Requirements, a separate top-level Acceptance Criteria list, Test Strategy > New Test Coverage (define only), Operational Lifecycle's instruction to restate outcomes as FRs and ACs, and repeated file lists. The fine-toothed comb reads for cross-section consistency, so every restatement is a place two copies can drift apart. In hassette spec 115, three comb passes each found a new pair of lists that disagreed. This change gives each fact one home: ACs nest under the FR they verify, Test Strategy keeps only concerns that span requirements, and a "One fact, one home" content rule tells writers (and the comb) to cite the home rather than restate it.

## Visual Artifacts
None.

## Key Decisions
1. **Nested AC#N, not dropped ACs.** Each FR is followed by its own indented `**AC#N**` bullets. AC IDs stay global and sequential so task `implements` fields and cfl snapshots keep working. Dropping ACs or switching to EARS sentences was rejected because tasks cite ACs heavily.
2. **The Template change map in design.md is the one home for where each change lands in each template.** The two templates have different sections (sketch has no Section Rules, Edge Cases, Architecture, Replacement Targets, or Test Strategy). Implement each template's column of that table exactly; do not assume "both templates" share a section that one lacks.
3. **cfl parser is anchored, not worked around.** `_FR_PATTERN`/`_AC_PATTERN` in `packages/cfl/src/cfl/snapshot.py` match only when the bolded ID starts a list item (`^\s*-\s+\*\*FR#(\d+)\*\*`, same for AC). A bolded citation mid-sentence and a struck-through removal (`- ~~**FR#N**~~`) no longer count. No authoring rule about bolding is added.
4. **The mine-plan validator records no location for FR/AC IDs.** Its Steps 3–4 match by ID only, so Step 1 becomes one extraction pass with no "section it appears in" field.
5. **The comb convergence check is out of scope** (issue #599). This change only adds the comb agent's consolidate-don't-sync instruction and fixes `comb-gate.md`'s caller list.

## Constraints & Anti-Patterns
- AC and FR IDs keep the `**FR#<int>**` / `**AC#<int>**` form; the `implements` validator in `packages/cfl/src/cfl/spec.py` must not change.
- Do not add a cross-run convergence check, SYNC comments, or any change to `ledger-procedure.md` / `synthesis-procedure.md` — that is issue #599.
- Do not migrate archived specs or `027-how-skill` / `033-orchestration-cost-analysis`.
- Do not touch issue templates (`agents/issue-refiner.md`, `skills/mine-create-issue/worker.md`); their "Acceptance Criteria" sections are unrelated.
- Do not add a one-line-per-FR digest to templates; FR#4 treats a summary as a copy.
- A count or one-line summary of a fact elsewhere in a template is itself a restatement — cite the home instead.
- Never hardcode `~/.claude` in skill/agent text; use `${CLAUDE_CONFIG_DIR:-~/.claude}` (the repo lints this).
- Commit types: `docs:` for skill, template, and agent changes; `fix:` for the `snapshot.py` anchoring; `test:` for tests.

## Design Doc References
- ## Functional Requirements — FR#1–FR#12, each with its nested ACs; the ACs are the Verify criteria
- ## Architecture > Template shape — the nested block shape and why the parser gets anchored
- ## Architecture > Template change map — per-template location of every template change (authoritative for T02)
- ## Architecture > Comb — why the comb agent instruction lives in the agent file
- ## Key Constraints — ID format constraints and the AC-usage evidence
- ## Test Strategy — required test layers (cfl unit tests, root prose contract tests)
- ## Impact > Changed Files — the full file inventory
- ## Impact > Behavioral Invariants — what must not change

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
