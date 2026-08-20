---
task_id: "T05"
title: "Add contract tests and verify all acceptance criteria"
status: "planned"
depends_on: ["T01", "T02", "T03", "T04"]
implements: ["FR#24", "AC#5", "AC#6", "AC#10", "AC#11", "AC#17", "AC#18", "AC#19"]
---

## Summary
Create the contract test file that guards all three mandatory challenge invocations in their skill files, plus the `challenge-gate.md` parameter block, the `blocking`/`minor` key names, the define Revise handler, and the sketch upgrade prompt. Run the full test suite to verify all acceptance criteria pass. This task depends on all others because it tests the final state of files they modified.

## Target Files

- create: `tests/test_challenge_mandate_contracts.py`
- read: `skills/mine-define/SKILL.md`
- read: `skills/mine-sketch/SKILL.md`
- read: `skills/mine-orchestrate/post-execution-pipeline.md`
- read: `skills/mine-challenge/challenge-gate.md`
- read: `skills/mine-challenge/findings-protocol.md`
- read: `packages/cfl/tests/test_finding.py`
- read: `packages/cfl/tests/test_db.py`

## Prompt

### 1. Contract test file

Create `tests/test_challenge_mandate_contracts.py` following the pattern in `tests/test_mine_orchestrate_protocol_contracts.py`. Use the same test structure: parametrized test with `(relative_path, required_anchors)` tuples, where each anchor is `(label, regex_pattern)`.

```python
REPO_ROOT = Path(__file__).resolve().parent.parent

@pytest.mark.parametrize(
    ("relative_path", "required_anchors"),
    [
        (
            "skills/mine-define/SKILL.md",
            [
                # FR#1: challenge phase between comb and sign-off
                ("define challenge phase heading", r"^## Phase 5\.5: Challenge$"),
                ("define challenge gate reference", r"challenge-gate\.md"),
                ("define challenge gate type", r"define-challenge"),
                # FR#2: no "Challenge first" option
                ("no challenge first option", ...),  # see negative anchor below
            ],
        ),
        (
            "skills/mine-sketch/SKILL.md",
            [
                # FR#4: challenge phase between comb and handoff
                ("sketch challenge phase heading", r"^## Phase 4\.5: Challenge$"),
                ("sketch challenge gate reference", r"challenge-gate\.md"),
                ("sketch challenge gate type", r"sketch-challenge"),
                # FR#5: --critics=2
                ("sketch critics pinned", r"--critics=2"),
                # FR#6: upgrade-to-caliper prompt
                ("sketch upgrade prompt", r"Upgrade to full caliper"),
            ],
        ),
        (
            "skills/mine-orchestrate/post-execution-pipeline.md",
            [
                # FR#7: Step 3.5 between Step 3 and Step 4
                ("orchestrate challenge step heading", r"^## Step 3\.5: Challenge$"),
                # FR#8: dispatches challenge rather than delegating
                ("orchestrate challenge invocation", r"/mine-challenge"),
                ("orchestrate challenge gate reference", r"challenge-gate\.md"),
                ("orchestrate challenge gate type", r"ship-challenge"),
            ],
        ),
        (
            "skills/mine-challenge/challenge-gate.md",
            [
                # FR#24: challenge-gate.md exists with parameter block
                ("gate recipe heading", r"^# Challenge Gate$"),
                ("gate parameters section", r"^## Parameters the caller supplies$"),
                ("gate sequence section", r"^## The sequence$"),
                # FR#11, AC#16: blocking and minor key names
                ("blocking key in data", r'"blocking"'),
                ("minor key in data", r'"minor"'),
            ],
        ),
    ],
)
def test_challenge_mandate_contract(
    relative_path: str, required_anchors: list[tuple[str, str]]
) -> None:
    text = (REPO_ROOT / relative_path).read_text()
    missing = [
        label
        for label, pattern in required_anchors
        if re.search(pattern, text, re.MULTILINE) is None
    ]
    assert missing == [], f"{relative_path} is missing contract anchor(s): {missing}"
```

**Negative anchors** (separate test function — `re.search` returns None means PASS):

```python
@pytest.mark.parametrize(
    ("relative_path", "forbidden_pattern", "label"),
    [
        # FR#2, AC#1: no "Challenge first" in mine-define sign-off
        ("skills/mine-define/SKILL.md", r"Challenge first", "define has no Challenge first option"),
        # FR#9, AC#1: no "Challenge first" in orchestrate shipping gate
        ("skills/mine-orchestrate/post-execution-pipeline.md", r"Challenge first", "orchestrate has no Challenge first option"),
        # FR#16, AC#13: no challenge-results* detection in challenge SKILL.md
        ("skills/mine-challenge/SKILL.md", r"challenge-results\*", "challenge has no file-based detection"),
    ],
)
def test_challenge_mandate_negative(
    relative_path: str, forbidden_pattern: str, label: str
) -> None:
    text = (REPO_ROOT / relative_path).read_text()
    assert re.search(forbidden_pattern, text) is None, f"{relative_path}: {label}"
```

**Ordering anchors** (verify phase/step positioning):

```python
def test_define_challenge_between_comb_and_signoff() -> None:
    """FR#1, AC#2: Phase 5.5 sits between Phase 5 (comb) and Phase 6 (sign-off)."""
    text = (REPO_ROOT / "skills/mine-define/SKILL.md").read_text()
    comb_pos = text.index("## Phase 5:")
    challenge_pos = text.index("## Phase 5.5: Challenge")
    signoff_pos = text.index("## Phase 6:")
    assert comb_pos < challenge_pos < signoff_pos

def test_sketch_challenge_between_comb_and_handoff() -> None:
    """FR#4, AC#3: Phase 4.5 sits between Phase 4 (comb) and Phase 5 (handoff)."""
    text = (REPO_ROOT / "skills/mine-sketch/SKILL.md").read_text()
    comb_pos = text.index("## Phase 4:")
    challenge_pos = text.index("## Phase 4.5: Challenge")
    handoff_pos = text.index("## Phase 5:")
    assert comb_pos < challenge_pos < handoff_pos

def test_orchestrate_challenge_between_step3_and_step4() -> None:
    """FR#7, AC#4: Step 3.5 sits between Step 3 and Step 4."""
    text = (REPO_ROOT / "skills/mine-orchestrate/post-execution-pipeline.md").read_text()
    step3_pos = text.index("## Step 3:")
    challenge_pos = text.index("## Step 3.5: Challenge")
    step4_pos = text.index("## Step 4:")
    assert step3_pos < challenge_pos < step4_pos
```

**Revise handler anchor** (FR#3, AC#17):

```python
def test_define_revise_recombs_without_rechallenge() -> None:
    """FR#3, AC#17: Revise re-runs the comb but does not invoke challenge."""
    text = (REPO_ROOT / "skills/mine-define/SKILL.md").read_text()
    # Find the Revise handler section
    revise_start = text.index('### On "Revise"')
    # Find the next section after Revise
    next_section = text.index("###", revise_start + 1)
    revise_text = text[revise_start:next_section]
    # Must mention comb re-run
    assert re.search(r"[Cc]omb", revise_text), "Revise handler must mention comb"
    # Must NOT mention challenge
    assert not re.search(r"challenge|Challenge", revise_text), "Revise handler must not mention challenge"
```

**Sketch upgrade anchor** (FR#6, AC#18):

```python
def test_sketch_upgrade_between_challenge_and_handoff() -> None:
    """FR#6, AC#18: Upgrade-to-caliper prompt sits between challenge phase and handoff gate."""
    text = (REPO_ROOT / "skills/mine-sketch/SKILL.md").read_text()
    challenge_pos = text.index("## Phase 4.5: Challenge")
    upgrade_pos = text.index("Upgrade to full caliper")
    handoff_pos = text.index("## Phase 5:")
    assert challenge_pos < upgrade_pos < handoff_pos
```

### 2. Full test suite verification

After creating the contract test file, run both test suites:

```bash
mise run test:root
mise run test:cfl
```

Verify both pass, including:
- The new `test_challenge_mandate_contracts.py`
- The updated `test_db.py` (schema version 8, EXPECTED_TABLES with findings, migration and convergence tests)
- The updated `test_cli.py` (expected_commands with finding)
- The updated `test_gate.py` (membership assertions for the three challenge gate types)
- The new `test_finding.py`

Also run:
```bash
prek run --all-files --stage pre-commit
```

## Focus

- The contract test file guards against silent deletion of the mandate. If someone removes the challenge phase heading from any of the three skill files, the test fails in CI. This is the structural enforcement the design doc describes — the strongest available rung for skill-file mandates.
- The `text.index()` calls for ordering will raise `ValueError` if the heading is missing entirely, which is a correct failure mode — the parametrized anchor test catches it with a better message, but either test failing blocks the commit.
- The Revise handler test is particularly important: it's the negative assertion that challenge does NOT re-run on revise. A naively written executor might add challenge to the revise loop, and this test catches it.
- The `re.MULTILINE` flag is needed for `^` anchors to match at the start of a line (not just start of string).

## Verify
- [ ] FR#24: `tests/test_challenge_mandate_contracts.py` exists and fails when any of the three mandatory challenge invocations is removed from its skill file
- [ ] AC#5: `mise run test:root` passes, including `test_challenge_mandate_contracts.py`
- [ ] AC#6: `mise run test:cfl` passes, including `test_finding.py`
- [ ] AC#10: A v7 database upgraded in place gains the `findings` table with all pre-existing rows intact (verified by migration test in `test_db.py`)
- [ ] AC#11: A freshly created database and a migrated database produce identical `findings` schemas (verified by convergence test in `test_db.py`)
- [ ] AC#17: The define Revise handler re-combs without re-challenging (verified by contract anchor)
- [ ] AC#18: The sketch upgrade prompt sits between the challenge phase and handoff gate (verified by contract anchor)
- [ ] AC#19: `prek run --all-files --stage pre-commit` passes
