"""Contract guards for the design-doc templates.

The `mine-define` half guards spec 1012: ACs nest under their FRs instead of
a top-level `## Acceptance Criteria` section, Test Strategy drops
`### New Test Coverage`, and the template cites the shared numbering and
"one fact, one home" rules instead of restating them.

The `mine-sketch` half guards the decision-ledger template (issue #605): no
FR/AC content, one `### D<n>` block per decision carrying the recommendation
rubric and a literal `**Ratified:** pending` marker, a `## Build` checklist
for build mode, and a citation of the shared rubric rather than a copy.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFINE_TEMPLATE = "skills/mine-define/design-template.md"
SKETCH_TEMPLATE = "skills/mine-sketch/design-template.md"
PRESENTING_DECISIONS = "references/common/presenting-decisions.md"
CITES_PRESENTING_DECISIONS = re.escape(Path(PRESENTING_DECISIONS).name)
DESIGN_DOC_FORMAT = "skills/mine-define/design-doc-format.md"
PLAN_VALIDATOR_PROMPT = "skills/mine-plan/validator-prompt.md"
PLAN_SKILL = "skills/mine-plan/SKILL.md"
CHALLENGE_FINDINGS_PROTOCOL = "skills/mine-challenge/findings-protocol.md"
CHALLENGE_SYNTHESIS_PROCEDURE = "skills/mine-challenge/synthesis-procedure.md"
IMPLEMENTATION_REVIEW_PROMPT = "skills/mine-implementation-review/reviewer-prompt.md"
ORCHESTRATE_TDD = "skills/mine-orchestrate/tdd.md"
FINE_TOOTHED_COMB_AGENT = "agents/fine-toothed-comb.md"
COMB_GATE = "skills/mine-comb/comb-gate.md"


def _text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text()


def _section(text: str, heading: str, level: int = 2) -> str | None:
    """Extract a Markdown section's body, from its heading to the next
    heading at the same level (or end of file, if it's the last section).
    Returns None if the heading isn't found.
    """
    marker = "#" * level
    pattern = rf"^{marker} {re.escape(heading)}$(.*?)(?=^{marker} |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else None


# AC#1 (also FR#1, FR#5): no top-level "## Acceptance Criteria" heading, no
# remaining text naming Acceptance Criteria as a section, and the Functional
# Requirements placeholder nests an indented AC bullet under an FR bullet.
def test_no_standalone_acceptance_criteria_section() -> None:
    text = _text(DEFINE_TEMPLATE)
    assert re.search(r"^## Acceptance Criteria$", text, re.MULTILINE) is None, (
        f"{DEFINE_TEMPLATE} still has a standalone '## Acceptance Criteria' heading"
    )


def test_no_text_names_acceptance_criteria_as_a_section() -> None:
    """No remaining text may name Acceptance Criteria as a section.

    Text describing ACs as a concept (e.g. the AC#N identifier-format rule)
    is allowed to stay — this only forbids phrasing that treats "Acceptance
    Criteria" as a section name ("the Acceptance Criteria section", a
    "## Acceptance Criteria" heading, or a content-rules list that still
    enumerates it alongside other section names).
    """
    text = _text(DEFINE_TEMPLATE)
    assert re.search(r"Acceptance Criteria section", text) is None
    assert (
        re.search(r"Functional Requirements,\s*Edge Cases,\s*Acceptance Criteria", text)
        is None
    )


def test_functional_requirements_placeholder_nests_acs() -> None:
    text = _text(DEFINE_TEMPLATE)
    fr_section = _section(text, "Functional Requirements")
    assert fr_section is not None, (
        f"{DEFINE_TEMPLATE} has no '## Functional Requirements' section"
    )
    assert re.search(r"^- \*\*FR#\d+\*\*", fr_section, re.MULTILINE) is not None
    assert re.search(r"^\s+- \*\*AC#\d+\*\*", fr_section, re.MULTILINE) is not None


# AC#2: mine-define's Test Strategy no longer has a "New Test Coverage"
# subsection.
def test_define_test_strategy_drops_new_test_coverage() -> None:
    text = _text(DEFINE_TEMPLATE)
    assert re.search(r"New Test Coverage", text) is None


def test_define_test_strategy_keeps_exactly_three_subsections() -> None:
    text = _text(DEFINE_TEMPLATE)
    test_strategy = _section(text, "Test Strategy")
    assert test_strategy is not None
    subsections = re.findall(r"^### (.+)$", test_strategy, re.MULTILINE)
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
    required_types = _section(text, "Required Test Types", level=3)
    assert required_types is not None
    assert re.search(
        r"which testing layer \(unit, integration, E2E\) each behavior needs",
        required_types,
    )
    assert re.search(r"retry bounds", required_types)
    assert re.search(r"recovery/reset", required_types)
    assert re.search(r"completion/status accounting", required_types)


# Shared format-contract file: the define template cites
# skills/mine-define/design-doc-format.md for the AC numbering/citation rules
# and "one fact, one home" instead of each carrying its own copy of the rule
# text — a byte-identical copy would silently drift from the source.
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


# AC#3/AC#4: the define template cites the shared file instead of restating
# the rules inline.
def test_numbering_and_citation_rules_cite_shared_file() -> None:
    text = _text(DEFINE_TEMPLATE)
    section = _section(text, "Section Rules")
    assert section is not None, f"{DEFINE_TEMPLATE} has no '## Section Rules' section"
    assert re.search(r"design-doc-format\.md", section)
    assert re.search(r"Nested ACs and Numbering Rules", section)
    # the rule text itself must not be duplicated here anymore
    assert re.search(r"global and sequential", section) is None


def test_one_fact_one_home_cites_shared_file() -> None:
    text = _text(DEFINE_TEMPLATE)
    content_rules = _section(text, "Content Rules")
    assert content_rules is not None
    assert re.search(r"One fact, one home", content_rules)
    assert re.search(r"design-doc-format\.md", content_rules)
    assert re.search(r"One Fact, One Home", content_rules)
    # the rule's own body text must not be duplicated here anymore
    assert (
        re.search(r"is a copy of it, so it cites the home too", content_rules) is None
    )


def test_templates_dont_byte_duplicate_shared_rule_text() -> None:
    """Templates must not duplicate the shared rule text verbatim."""
    define_text = _text(DEFINE_TEMPLATE)
    sketch_text = _text(SKETCH_TEMPLATE)
    assert "global and sequential" not in define_text
    assert "global and sequential" not in sketch_text
    assert "is a copy of it, so it cites the home too" not in define_text
    assert "is a copy of it, so it cites the home too" not in sketch_text


def test_validator_cites_shared_fr_ac_definition() -> None:
    """The validator's extraction rule must not be looser than the cfl
    parser's anchored FR/AC definition."""
    text = _text(PLAN_VALIDATOR_PROMPT)
    assert re.search(r"design-doc-format\.md", text)
    assert re.search(r"FR/AC Definition", text)
    assert re.search(r"wherever it appears", text) is None


def test_tdd_and_reviewer_prompt_agree_on_test_naming_location() -> None:
    """tdd.md and reviewer-prompt.md must name the same two places a design
    names its tests (ACs and Test Strategy), not just one."""
    tdd_text = _text(ORCHESTRATE_TDD)
    reviewer_text = _text(IMPLEMENTATION_REVIEW_PROMPT)
    assert re.search(r"Acceptance Criteria", tdd_text)
    assert re.search(r"Test Strategy", tdd_text)
    assert re.search(r"Acceptance Criteria", reviewer_text)
    assert re.search(r"Test Strategy", reviewer_text)


def test_operational_lifecycle_placeholder_reframes_outcomes_as_fr_ac() -> None:
    """FR#4: the Operational Lifecycle placeholder's closing line says the
    section explains the model and each outcome is its own FR with ACs,
    in the define template.
    """
    text = _text(DEFINE_TEMPLATE)
    lifecycle = _section(text, "Operational Lifecycle")
    assert lifecycle is not None, (
        f"{DEFINE_TEMPLATE} has no '## Operational Lifecycle' section"
    )
    assert re.search(r"explains the model", lifecycle)
    assert re.search(r"its own FR#N with ACs", lifecycle)


def test_define_edge_cases_placeholder_holds_context_only() -> None:
    text = _text(DEFINE_TEMPLATE)
    edge_cases = _section(text, "Edge Cases")
    assert edge_cases is not None
    assert re.search(r"context only", edge_cases)
    assert re.search(r"becomes its own FR#N with ACs", edge_cases)


def test_define_architecture_and_replacement_targets_cite_changed_files() -> None:
    text = _text(DEFINE_TEMPLATE)
    architecture = _section(text, "Architecture")
    replacement_targets = _section(text, "Replacement Targets")
    assert architecture is not None
    assert replacement_targets is not None
    assert re.search(r"### Changed Files", architecture)
    assert re.search(r"### Changed Files", replacement_targets)


def test_sketch_ledger_has_no_fr_ac_content() -> None:
    """The ledger records decisions, not FR/AC lists, so no FR#N or AC#N
    identifier appears anywhere in the template."""
    text = _text(SKETCH_TEMPLATE)
    assert re.search(r"\b(FR|AC)#", text) is None


def test_sketch_excludes_define_only_sections() -> None:
    """The ledger has none of mine-define's requirement or architecture
    sections."""
    text = _text(SKETCH_TEMPLATE)
    for heading in (
        "## Functional Requirements",
        "## Operational Lifecycle",
        "## Approach",
        "## Changed Files",
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


def test_sketch_ledger_header_and_section_order() -> None:
    """Resume, the findings protocol, and the Addendum convention key on the
    `**Mode:** sketch` header and a `**Status:**` that starts as `draft`."""
    text = _text(SKETCH_TEMPLATE)
    assert re.search(r"^\*\*Mode:\*\* sketch$", text, re.MULTILINE)
    assert re.search(r"^\*\*Status:\*\* draft$", text, re.MULTILINE)
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    ledger = [
        h
        for h in headings
        if h in ("Summary", "Decisions", "Assumed", "Build", "Addendum")
    ]
    assert ledger == ["Summary", "Decisions", "Assumed", "Build", "Addendum"]


def test_sketch_decision_block_carries_the_rubric_and_pending_marker() -> None:
    """Each decision holds its own options, reasoning, and answer, and is
    created with the literal `**Ratified:** pending` marker resume matches.

    The ledger spells its fields as prose labels ("Deciding factor", "Pick B
    instead if"); the challenge findings format uses hyphenated keys
    ("Deciding-factor", "Pick-instead-if"). Both follow their own file's
    field convention, so the tests below pin each spelling separately."""
    text = _text(SKETCH_TEMPLATE)
    decisions = _section(text, "Decisions")
    assert decisions is not None
    assert re.search(r"^### D1: ", decisions, re.MULTILINE)
    for field in (
        r"\*\*Deciding factor:\*\*",
        r"^\| \| A: ",
        r"\*\*Recommendation:\*\*",
        r"\*\*Pick B instead if\*\*",
        r"\*\*Reversibility:\*\*",
        r"^\*\*Ratified:\*\* pending$",
    ):
        assert re.search(field, decisions, re.MULTILINE), field


def test_sketch_build_section_has_the_build_checklist() -> None:
    text = _text(SKETCH_TEMPLATE)
    build = _section(text, "Build")
    assert build is not None
    items = re.findall(r"^- \[ \] (.+)$", build, re.MULTILINE)
    assert items == [
        "Implementation and tests committed",
        "Docs",
        "Ship-time challenge",
    ]
    assert re.search(r"\*\*Calls made during the build:\*\*", build)


def test_sketch_content_rules_cite_the_rubric_without_restating_it() -> None:
    text = _text(SKETCH_TEMPLATE)
    content_rules = _section(text, "Content Rules")
    assert content_rules is not None
    assert re.search(CITES_PRESENTING_DECISIONS, content_rules)
    assert re.search(r"Behavior, not technique", content_rules)
    assert "Fill in the table before choosing" not in text


def test_challenge_questions_cite_the_rubric() -> None:
    """The rubric's second consumer: every User-directed and TENSION question
    in the challenge walkthrough shows the reasoning first."""
    assert (REPO_ROOT / PRESENTING_DECISIONS).is_file()
    flow = _section(_text(CHALLENGE_FINDINGS_PROTOCOL), "Inline Resolution Flow")
    assert flow is not None
    assert re.search(CITES_PRESENTING_DECISIONS, _text(CHALLENGE_FINDINGS_PROTOCOL))
    assert re.search(r"\*\*Criteria:\*\*", flow)
    assert re.search(r"TENSION", flow)


def test_challenge_synthesis_fills_the_table_before_recommending() -> None:
    """The table has to exist before the recommendation is chosen; synthesis
    is the only place that can do it in that order."""
    text = _text(CHALLENGE_SYNTHESIS_PROCEDURE)
    assert re.search(CITES_PRESENTING_DECISIONS, text)
    criteria = text.index("`criteria` table")
    recommendation = text.index("`recommendation`")
    assert criteria < recommendation
    protocol = _text(CHALLENGE_FINDINGS_PROTOCOL)
    for field in ("**Deciding-factor:**", "**Criteria:**", "**Pick-instead-if:**"):
        assert field in protocol, field


# AC#7: validator-prompt.md Step 1 describes a single extraction pass for FR
# and AC identifiers with no location field, and no longer contains "the
# section it appears in".
def test_validator_step1_describes_single_extraction_pass_with_no_location() -> None:
    text = _text(PLAN_VALIDATOR_PROMPT)
    step1 = _section(text, "Step 1: Extract Requirements from design.md")
    assert step1 is not None, (
        f"{PLAN_VALIDATOR_PROMPT} has no '## Step 1: Extract Requirements from design.md' section"
    )
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
    extract_section = _section(text, "Extract key information", level=3)
    assert extract_section is not None, (
        f"{PLAN_SKILL} has no '### Extract key information' section"
    )
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
    extract_section = _section(text, "Extract key information", level=3)
    assert extract_section is not None
    assert re.search(r"nested under", extract_section) is not None, (
        "SKILL.md's extraction list must describe ACs as nested under their FRs"
    )


# AC#9: the challenge's Inline Resolution Flow references the design
# template's Content Rules for design-doc targets.
def test_challenge_inline_resolution_references_design_template_content_rules() -> None:
    text = _text(CHALLENGE_FINDINGS_PROTOCOL)
    flow = _section(text, "Inline Resolution Flow")
    assert flow is not None, (
        f"{CHALLENGE_FINDINGS_PROTOCOL} has no '## Inline Resolution Flow' section"
    )
    assert re.search(r"design-doc", flow) is not None
    assert re.search(r"Content Rules", flow) is not None
    assert re.search(r"mine-sketch/design-template\.md", flow) is not None
    assert re.search(r"mine-define/design-template\.md", flow) is not None
    assert re.search(r"\*\*Mode:\*\* sketch", flow) is not None


# AC#10: the implementation reviewer's missing-test check names the design's
# ACs as a place tests are named, alongside Test Strategy.
def test_implementation_review_missing_test_check_names_acs() -> None:
    text = _text(IMPLEMENTATION_REVIEW_PROMPT)
    section = _section(text, "7. Test coverage", level=3)
    assert section is not None, (
        f"{IMPLEMENTATION_REVIEW_PROMPT} has no '### 7. Test coverage' section"
    )
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
    assert re.search(r"consolidating, not syncing", text) is not None


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
