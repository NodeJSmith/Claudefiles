"""Contract guards for the "one fact, one home" design-doc template changes.

Guards spec 1012's FR#1-FR#5: the `mine-define` and `mine-sketch` design
templates nest acceptance criteria (AC#N) directly under their functional
requirements (FR#N) instead of listing them in a separate top-level
`## Acceptance Criteria` section, `mine-define`'s Test Strategy drops
`### New Test Coverage`, and both templates carry the AC numbering/citation
rules and the "One fact, one home" content rule. Later tasks in this feature
append their own parametrized cases or test functions here as they land the
remaining FR/AC pairs (FR#6-FR#12).
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFINE_TEMPLATE = "skills/mine-define/design-template.md"
SKETCH_TEMPLATE = "skills/mine-sketch/design-template.md"
DESIGN_DOC_FORMAT = "skills/mine-define/design-doc-format.md"
PLAN_VALIDATOR_PROMPT = "skills/mine-plan/validator-prompt.md"
PLAN_SKILL = "skills/mine-plan/SKILL.md"
CHALLENGE_FINDINGS_PROTOCOL = "skills/mine-challenge/findings-protocol.md"
IMPLEMENTATION_REVIEW_PROMPT = "skills/mine-implementation-review/reviewer-prompt.md"
ORCHESTRATE_TDD = "skills/mine-orchestrate/tdd.md"
FINE_TOOTHED_COMB_AGENT = "agents/fine-toothed-comb.md"
COMB_GATE = "skills/mine-comb/comb-gate.md"


def _text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text()


# AC#1 (also FR#1, FR#5): no top-level "## Acceptance Criteria" heading, no
# remaining text naming Acceptance Criteria as a section, and the Functional
# Requirements placeholder nests an indented AC bullet under an FR bullet.
@pytest.mark.parametrize(
    "relative_path",
    [DEFINE_TEMPLATE, SKETCH_TEMPLATE],
)
def test_no_standalone_acceptance_criteria_section(relative_path: str) -> None:
    text = _text(relative_path)
    assert re.search(r"^## Acceptance Criteria$", text, re.MULTILINE) is None, (
        f"{relative_path} still has a standalone '## Acceptance Criteria' heading"
    )


@pytest.mark.parametrize(
    "relative_path",
    [DEFINE_TEMPLATE, SKETCH_TEMPLATE],
)
def test_no_text_names_acceptance_criteria_as_a_section(relative_path: str) -> None:
    """No remaining text may name Acceptance Criteria as a section.

    Text describing ACs as a concept (e.g. the AC#N identifier-format rule)
    is allowed to stay — this only forbids phrasing that treats "Acceptance
    Criteria" as a section name ("the Acceptance Criteria section", a
    "## Acceptance Criteria" heading, or a content-rules list that still
    enumerates it alongside other section names).
    """
    text = _text(relative_path)
    assert re.search(r"Acceptance Criteria section", text) is None
    assert (
        re.search(r"Functional Requirements,\s*Edge Cases,\s*Acceptance Criteria", text)
        is None
    )


@pytest.mark.parametrize(
    "relative_path",
    [DEFINE_TEMPLATE, SKETCH_TEMPLATE],
)
def test_functional_requirements_placeholder_nests_acs(relative_path: str) -> None:
    text = _text(relative_path)
    fr_section_match = re.search(
        r"^## Functional Requirements$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    assert fr_section_match is not None, (
        f"{relative_path} has no '## Functional Requirements' section"
    )
    fr_section = fr_section_match.group(1)
    assert re.search(r"^- \*\*FR#\d+\*\*", fr_section, re.MULTILINE) is not None
    assert re.search(r"^\s+- \*\*AC#\d+\*\*", fr_section, re.MULTILINE) is not None


# AC#2: mine-define's Test Strategy no longer has a "New Test Coverage"
# subsection.
def test_define_test_strategy_drops_new_test_coverage() -> None:
    text = _text(DEFINE_TEMPLATE)
    assert re.search(r"New Test Coverage", text) is None


def test_define_test_strategy_keeps_exactly_three_subsections() -> None:
    text = _text(DEFINE_TEMPLATE)
    test_strategy_match = re.search(
        r"^## Test Strategy$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    assert test_strategy_match is not None
    subsections = re.findall(r"^### (.+)$", test_strategy_match.group(1), re.MULTILINE)
    assert subsections == [
        "Required Test Types",
        "Existing Tests to Adapt",
        "Tests to Remove",
    ]


def test_define_required_test_types_carries_moved_guidance() -> None:
    """FR#2: layer-identification and Operational Lifecycle guidance moved
    from the deleted New Test Coverage subsection into Required Test Types.
    """
    text = _text(DEFINE_TEMPLATE)
    required_types_match = re.search(
        r"^### Required Test Types$(.*?)(?=^### )", text, re.MULTILINE | re.DOTALL
    )
    assert required_types_match is not None
    required_types = required_types_match.group(1)
    assert re.search(
        r"which testing layer \(unit, integration, E2E\) each behavior needs",
        required_types,
    )
    assert re.search(r"retry bounds", required_types)
    assert re.search(r"recovery/reset", required_types)
    assert re.search(r"completion/status accounting", required_types)


# Shared format-contract file (challenge Finding 1, ship-time re-evaluation):
# both templates cite skills/mine-define/design-doc-format.md for the AC
# numbering/citation rules and "one fact, one home" instead of each carrying
# its own copy of the rule text — the byte-identical duplication a challenge
# critic found is the drift risk this replaces.
def test_design_doc_format_file_exists_with_canonical_rules() -> None:
    text = _text(DESIGN_DOC_FORMAT)
    # Collapse whitespace for substring checks below so prose line-wrapping
    # in the source file doesn't break a check spanning a wrap point.
    flat = re.sub(r"\s+", " ", text)
    assert re.search(r"^## FR/AC Definition$", text, re.MULTILINE)
    assert re.search(r"^## Nested ACs and Numbering Rules$", text, re.MULTILINE)
    assert re.search(r"^## One Fact, One Home$", text, re.MULTILINE)
    assert re.search(r"^## Where Tests Are Named$", text, re.MULTILINE)
    # (a) global sequential numbering, never hierarchical
    assert re.search(r"global and sequential", flat)
    assert re.search(r"never hierarchical", flat)
    # (b) primary FR + (also FR#N) citation, uncovered FR gets its own AC
    assert re.search(r"\(also FR#N\)", flat)
    assert re.search(r"no AC fully verifies gets its own AC", flat)
    # (c) whole-suite checks are not ACs
    assert re.search(r"all tests pass", flat)
    assert re.search(r"not ACs", flat)
    # one fact, one home
    assert re.search(r"is a copy of it, so it cites the home too", flat)
    assert re.search(r"several requirements depend on the same mapping", flat)
    # FR/AC definition anchoring, matching the cfl parser
    assert re.search(r"first thing in a Markdown list item", flat)
    assert re.search(r"mid-sentence", flat)
    assert re.search(r"struck-through", flat)


# AC#3/AC#4 (superseded by the ship-time challenge's convergence resolution):
# both templates cite the shared file instead of restating the rules inline.
@pytest.mark.parametrize(
    ("relative_path", "section_heading"),
    [
        (DEFINE_TEMPLATE, "## Section Rules"),
        (SKETCH_TEMPLATE, "## Content Rules"),
    ],
)
def test_numbering_and_citation_rules_cite_shared_file(
    relative_path: str, section_heading: str
) -> None:
    text = _text(relative_path)
    escaped_heading = re.escape(section_heading)
    section_match = re.search(
        rf"^{escaped_heading}$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert section_match is not None, (
        f"{relative_path} has no '{section_heading}' section"
    )
    section = section_match.group(1)
    assert re.search(r"design-doc-format\.md", section)
    assert re.search(r"Nested ACs and Numbering Rules", section)
    # the rule text itself must not be duplicated here anymore
    assert re.search(r"global and sequential", section) is None


@pytest.mark.parametrize(
    "relative_path",
    [DEFINE_TEMPLATE, SKETCH_TEMPLATE],
)
def test_one_fact_one_home_cites_shared_file(relative_path: str) -> None:
    text = _text(relative_path)
    content_rules_match = re.search(
        r"^## Content Rules$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert content_rules_match is not None
    content_rules = content_rules_match.group(1)
    assert re.search(r"One fact, one home", content_rules)
    assert re.search(r"design-doc-format\.md", content_rules)
    assert re.search(r"One Fact, One Home", content_rules)
    # the rule's own body text must not be duplicated here anymore
    assert (
        re.search(r"is a copy of it, so it cites the home too", content_rules) is None
    )


def test_templates_dont_byte_duplicate_shared_rule_text() -> None:
    """The specific duplication a challenge critic found: confirm it's gone."""
    define_text = _text(DEFINE_TEMPLATE)
    sketch_text = _text(SKETCH_TEMPLATE)
    assert "global and sequential" not in define_text
    assert "global and sequential" not in sketch_text
    assert "is a copy of it, so it cites the home too" not in define_text
    assert "is a copy of it, so it cites the home too" not in sketch_text


def test_validator_cites_shared_fr_ac_definition() -> None:
    """Challenge Finding 4: the validator's extraction rule must not be looser
    than the cfl parser's anchored definition."""
    text = _text(PLAN_VALIDATOR_PROMPT)
    assert re.search(r"design-doc-format\.md", text)
    assert re.search(r"FR/AC Definition", text)
    assert re.search(r"wherever it appears", text) is None


def test_tdd_and_reviewer_prompt_agree_on_test_naming_location() -> None:
    """Challenge Finding 3: tdd.md and reviewer-prompt.md must name the same
    two places a design names its tests (ACs and Test Strategy), not just one."""
    tdd_text = _text(ORCHESTRATE_TDD)
    reviewer_text = _text(IMPLEMENTATION_REVIEW_PROMPT)
    assert re.search(r"Acceptance Criteria", tdd_text)
    assert re.search(r"Test Strategy", tdd_text)
    assert re.search(r"Acceptance Criteria", reviewer_text)
    assert re.search(r"Test Strategy", reviewer_text)


def test_operational_lifecycle_placeholder_reframes_outcomes_as_fr_ac() -> None:
    """FR#4: the Operational Lifecycle placeholder's closing line says the
    section explains the model and each outcome is its own FR with ACs,
    in both templates.
    """
    for relative_path in (DEFINE_TEMPLATE, SKETCH_TEMPLATE):
        text = _text(relative_path)
        lifecycle_match = re.search(
            r"^## Operational Lifecycle$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
        )
        assert lifecycle_match is not None, (
            f"{relative_path} has no '## Operational Lifecycle' section"
        )
        lifecycle = lifecycle_match.group(1)
        assert re.search(r"explains the model", lifecycle)
        assert re.search(r"its own FR#N with ACs", lifecycle)


def test_define_edge_cases_placeholder_holds_context_only() -> None:
    text = _text(DEFINE_TEMPLATE)
    edge_cases_match = re.search(
        r"^## Edge Cases$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    assert edge_cases_match is not None
    edge_cases = edge_cases_match.group(1)
    assert re.search(r"context only", edge_cases)
    assert re.search(r"becomes its own FR#N with ACs", edge_cases)


def test_define_architecture_and_replacement_targets_cite_changed_files() -> None:
    text = _text(DEFINE_TEMPLATE)
    architecture_match = re.search(
        r"^## Architecture$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    replacement_targets_match = re.search(
        r"^## Replacement Targets$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    assert architecture_match is not None
    assert replacement_targets_match is not None
    assert re.search(r"### Changed Files", architecture_match.group(1))
    assert re.search(r"### Changed Files", replacement_targets_match.group(1))


def test_sketch_approach_cites_changed_files() -> None:
    text = _text(SKETCH_TEMPLATE)
    approach_match = re.search(
        r"^## Approach$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    assert approach_match is not None
    assert re.search(r"## Changed Files", approach_match.group(1))


# AC#5: the FR#1/AC#1 nested-AC check, run against the mine-sketch template.
def test_sketch_has_no_standalone_acceptance_criteria_or_edge_cases_or_architecture() -> (
    None
):
    """FR#5: mine-sketch has no Section Rules, Edge Cases, Architecture,
    Replacement Targets, or Test Strategy sections — those are mine-define-only.
    """
    text = _text(SKETCH_TEMPLATE)
    for heading in (
        "## Acceptance Criteria",
        "## Section Rules",
        "## Edge Cases",
        "## Architecture",
        "## Replacement Targets",
        "## Test Strategy",
    ):
        assert re.search(rf"^{re.escape(heading)}$", text, re.MULTILINE) is None, (
            f"mine-sketch template unexpectedly has a '{heading}' section"
        )


# AC#7: validator-prompt.md Step 1 describes a single extraction pass for FR
# and AC identifiers with no location field, and no longer contains "the
# section it appears in".
def test_validator_step1_describes_single_extraction_pass_with_no_location() -> None:
    text = _text(PLAN_VALIDATOR_PROMPT)
    step1_match = re.search(
        r"^## Step 1: Extract Requirements from design\.md$(.*?)(?=^## )",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert step1_match is not None, (
        f"{PLAN_VALIDATOR_PROMPT} has no '## Step 1: Extract Requirements from design.md' section"
    )
    step1 = step1_match.group(1)
    assert re.search(r"the section it appears in", step1) is None, (
        "Step 1 still records 'the section it appears in' — extraction must be a single pass "
        "with no location field"
    )
    assert re.search(r"single pass", step1) is not None
    assert re.search(r"FR#N", step1) is not None
    assert re.search(r"AC#N", step1) is not None


# AC#8: SKILL.md's extraction list names exactly the Test Strategy
# subsections FR#2 keeps (Required Test Types, Existing Tests to Adapt,
# Tests to Remove — no New Test Coverage) and describes ACs as nested under
# their FRs.
def test_skill_extraction_list_names_kept_test_strategy_subsections() -> None:
    text = _text(PLAN_SKILL)
    extract_match = re.search(
        r"^### Extract key information$(.*?)(?=^### |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert extract_match is not None, (
        f"{PLAN_SKILL} has no '### Extract key information' section"
    )
    extract_section = extract_match.group(1)
    assert re.search(r"New Test Coverage", extract_section) is None, (
        "SKILL.md's extraction list still names the removed New Test Coverage subsection"
    )
    for subsection in (
        "Required Test Types",
        "Existing Tests to Adapt",
        "Tests to Remove",
    ):
        assert subsection in extract_section, (
            f"SKILL.md's extraction list is missing the kept Test Strategy subsection "
            f"'{subsection}'"
        )


def test_skill_extraction_list_describes_acs_nested_under_frs() -> None:
    text = _text(PLAN_SKILL)
    extract_match = re.search(
        r"^### Extract key information$(.*?)(?=^### |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert extract_match is not None
    extract_section = extract_match.group(1)
    assert re.search(r"nested under", extract_section) is not None, (
        "SKILL.md's extraction list must describe ACs as nested under their FRs"
    )


# AC#9: the challenge's Inline Resolution Flow references the design
# template's Content Rules for design-doc targets.
def test_challenge_inline_resolution_references_design_template_content_rules() -> None:
    text = _text(CHALLENGE_FINDINGS_PROTOCOL)
    flow_match = re.search(
        r"^## Inline Resolution Flow$(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    assert flow_match is not None, (
        f"{CHALLENGE_FINDINGS_PROTOCOL} has no '## Inline Resolution Flow' section"
    )
    flow = flow_match.group(1)
    assert re.search(r"design-doc", flow) is not None
    assert re.search(r"Content Rules", flow) is not None
    assert re.search(r"mine-sketch/design-template\.md", flow) is not None
    assert re.search(r"mine-define/design-template\.md", flow) is not None
    assert re.search(r"\*\*Mode:\*\* sketch", flow) is not None


# AC#10: the implementation reviewer's missing-test check names the design's
# ACs as a place tests are named, alongside Test Strategy.
def test_implementation_review_missing_test_check_names_acs() -> None:
    text = _text(IMPLEMENTATION_REVIEW_PROMPT)
    section_match = re.search(
        r"^### 7\. Test coverage$(.*?)(?=^### |\Z)", text, re.MULTILINE | re.DOTALL
    )
    assert section_match is not None, (
        f"{IMPLEMENTATION_REVIEW_PROMPT} has no '### 7. Test coverage' section"
    )
    section = section_match.group(1)
    assert re.search(r"Acceptance Criteria", section) is not None, (
        "missing-test check must name the design's Acceptance Criteria as a place tests "
        "are named"
    )
    assert re.search(r"Test Strategy", section) is not None


# AC#11: fine-toothed-comb.md instructs consolidating disagreeing
# restatements into one home rather than syncing the copies.
def test_fine_toothed_comb_recommends_consolidate_not_sync() -> None:
    text = _text(FINE_TOOTHED_COMB_AGENT)
    assert re.search(r"consolidat", text, re.IGNORECASE) is not None
    assert re.search(r"every place it'?s stated", text) is not None
    assert (
        re.search(r"not syncing|instead of restating|not\b.*\bsync", text) is not None
    )


# AC#12: comb-gate.md's intro names exactly the skills under `skills/` that
# reference comb-gate.md.
def test_comb_gate_intro_names_exactly_its_referencing_skills() -> None:
    comb_gate_path = REPO_ROOT / COMB_GATE
    text = comb_gate_path.read_text()

    intro_match = re.search(
        r"^# Comb Gate$\n\n(.+?)\n\n", text, re.DOTALL | re.MULTILINE
    )
    assert intro_match is not None, f"{COMB_GATE} has no intro paragraph"
    intro = intro_match.group(1)

    skills_dir = REPO_ROOT / "skills"
    referencing_skills = set()
    for path in skills_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == comb_gate_path.resolve():
            continue
        try:
            content = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if "comb-gate.md" in content:
            referencing_skills.add(path.relative_to(skills_dir).parts[0])

    assert referencing_skills, "expected at least one skill to reference comb-gate.md"

    named_skills = set(re.findall(r"`(mine-[a-z-]+)`", intro))
    assert named_skills == referencing_skills, (
        f"comb-gate.md intro names {named_skills} but the skills that actually "
        f"reference comb-gate.md are {referencing_skills}"
    )
