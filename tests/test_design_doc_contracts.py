"""Contract guards for the decision-ledger template and its consumers.

Guards the `mine-sketch` ledger template (issue #605): no FR/AC content, one
`### D<n>` block per decision carrying the recommendation rubric and a
literal `**Ratified:** pending` marker, a `## Build` checklist for build mode,
and a citation of the shared rubric rather than a copy. Also guards the
challenge and comb files that consume the ledger.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SKETCH_TEMPLATE = "skills/mine-sketch/design-template.md"
PRESENTING_DECISIONS = "references/common/presenting-decisions.md"
CITES_PRESENTING_DECISIONS = re.escape(Path(PRESENTING_DECISIONS).name)
CHALLENGE_FINDINGS_PROTOCOL = "skills/mine-challenge/findings-protocol.md"
CHALLENGE_SYNTHESIS_PROCEDURE = "skills/mine-challenge/synthesis-procedure.md"
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


def test_sketch_ledger_has_no_fr_ac_content() -> None:
    """The ledger records decisions, not FR/AC lists, so no FR#N or AC#N
    identifier appears anywhere in the template."""
    text = _text(SKETCH_TEMPLATE)
    assert re.search(r"\b(FR|AC)#", text) is None


def test_sketch_excludes_define_only_sections() -> None:
    """The ledger has none of a requirements doc's requirement or
    architecture sections."""
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


# AC#9: the challenge's Inline Resolution Flow references the ledger
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
