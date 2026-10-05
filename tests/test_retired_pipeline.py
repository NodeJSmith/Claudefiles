"""Contract guards for spec 1015, which retired define → plan → orchestrate.

Decision numbers (D3, D9, D10) refer to the ledger at
design/specs/1015-retire-heavy-pipeline/design.md.

Two kinds of pins. First, no installed instruction file names a deleted
component, since a skill or rule that routes to a missing skill fails only
when someone follows it. Second, the behavior mine-sketch took over: reading
a named brief as prior work, no legacy routing, and the known-issues protocol
in build mode.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

INSTRUCTION_DIRS = ("skills", "commands", "agents", "rules", "references")
INSTRUCTION_SUFFIXES = (".md", ".sh", ".py")
# Scanned regardless of suffix: scripts often have none.
SCRIPT_DIRS = ("bin", "scripts")
# CHANGELOG.md is history and keeps the retired names on purpose.
ROOT_FILES = ("README.md", "REFERENCE.md", "ONBOARDING.md", "CLAUDE.md", "install.py")

SKETCH_SKILL = "skills/mine-sketch/SKILL.md"
KNOWN_ISSUES = "skills/mine-sketch/known-issues.md"

# Skill, agent, script and file names, plus one sentinel token and one
# subcommand. Each is matched on word boundaries in every scanned file.
RETIRED = [
    "mine-define",
    "mine-plan",
    "mine-orchestrate",
    "mine-implementation-review",
    "mine-build",
    "spec-reviewer",
    "orchestrate-cost",
    "verdict-line-format",
    "lint-verdict-line",
    "orchestrate-concise-probe",
    "CONCISE-RETURN-MODE",
    "implementer-prompt.md",
    "staleness-preflight",
    "cfl archive",
    "caliper",
    "known-issues-protocol",
    "design-doc-format",
    "post-execution-pipeline",
    "wip-commit-protocol",
    "visual-reviewer",
    "retry-prompt",
    "agent-stats",
]

# The pipeline described in prose rather than by skill name.
RETIRED_PROSE = re.compile(r"define\s*(?:→|->)\s*plan")


def _scanned_files() -> list[Path]:
    instruction = [
        path
        for name in INSTRUCTION_DIRS
        for path in (REPO_ROOT / name).rglob("*")
        if path.is_file() and path.suffix in INSTRUCTION_SUFFIXES
    ]
    scripts = [
        path
        for name in SCRIPT_DIRS
        for path in (REPO_ROOT / name).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    return instruction + scripts + [REPO_ROOT / name for name in ROOT_FILES]


def _text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text()


def _between(text: str, start: str, end: str | None = None) -> str:
    """The text after heading `start`, up to heading `end` (or end of file).
    Fails with the missing heading's name rather than an IndexError."""
    assert start in text, f"heading {start!r} not found"
    body = text.split(start, 1)[1]
    if end is None:
        return body
    assert end in body, f"heading {end!r} not found after {start!r}"
    return body.split(end, 1)[0]


@pytest.mark.parametrize("name", RETIRED)
def test_no_scanned_file_names_a_retired_component(name: str) -> None:
    hits = [
        str(path.relative_to(REPO_ROOT))
        for path in _scanned_files()
        if re.search(
            rf"(?<![\w-]){re.escape(name)}(?![\w-])", path.read_text(errors="replace")
        )
    ]
    assert hits == [], f"{name} is retired but still named in: {hits}"


def test_no_scanned_file_describes_the_retired_pipeline() -> None:
    hits = [
        str(path.relative_to(REPO_ROOT))
        for path in _scanned_files()
        if RETIRED_PROSE.search(path.read_text(errors="replace"))
    ]
    assert hits == [], f"the define → plan pipeline is still described in: {hits}"


def test_sketch_reads_a_named_brief_as_prior_work() -> None:
    """D3: grill and research hand their brief to sketch, so Phase 1 reads it."""
    scope = _between(_text(SKETCH_SKILL), "## Phase 1: Scope", "## Phase 2:")
    assert re.search(r"names a brief or research file.*read it first", scope, re.DOTALL)


def test_sketch_routing_has_no_legacy_row() -> None:
    """D9: a doc without `**Mode:** sketch` gets no special routing."""
    routing = _between(_text(SKETCH_SKILL), "## Routing", "## Phase 1")
    legacy_row = "| No `**Mode:** sketch` |"
    assert legacy_row not in routing


def test_build_mode_records_and_walks_known_issues() -> None:
    """D10: deferrals in Steps 2-3 go through the protocol, and Step 4 walks
    this build's open entries before the Ship? gate."""
    text = _text(SKETCH_SKILL)
    implement = _between(text, "### Step 2: Implement", "### Step 3")
    finish = _between(text, "### Step 4: Finish")
    assert "known-issues.md" in implement
    walkthrough_pos = finish.index("known-issues.md")
    ship_gate_pos = finish.index('header: "Ship?"')
    assert walkthrough_pos < ship_gate_pos, (
        "known issues are walked before the Ship? gate"
    )
    # Every open entry is walked; a branch filter silently skips entries from
    # a build resumed on another branch.
    assert "walk all of them" in finish
    assert "on this branch" not in finish
    # The Severity Gate question is only for deferrals the user hasn't seen.
    assert "deferring it on your own" in implement
    assert "needs no second question" in _text(KNOWN_ISSUES)


def test_known_issues_protocol_shape() -> None:
    """D10: qualifying rules, the Severity Gate, and an entry schema keyed by
    date and branch instead of a cfl run id."""
    text = _text(KNOWN_ISSUES)
    assert re.search(r"^## What Qualifies$", text, re.MULTILINE)
    assert re.search(r"^## Severity Gate$", text, re.MULTILINE)
    assert re.search(r"^Recorded: <YYYY-MM-DD> \(<branch>\)$", text, re.MULTILINE)
    assert re.search(r"^Run: ", text, re.MULTILINE) is None
    assert "rated it CRITICAL or HIGH" in text
    for label in ("Fix now", "Stop here", "Ship anyway"):
        assert f'label: "{label}"' in text


def test_sketch_adopts_a_grill_brief_directory() -> None:
    """D3: a directory holding grill's brief.md becomes the ledger's home, and
    setup checks the existing spec instead of creating a second one."""
    text = _text(SKETCH_SKILL)
    routing = _between(text, "## Routing", "## Phase 1")
    assert re.search(r"^\| No `design\.md`, but a `brief\.md`", routing, re.MULTILINE)
    cfl_setup = _between(text, "### Initialize CFL tracking", "### Start run")
    assert re.search(r"feature directory with a brief, skip `cfl spec init`", cfl_setup)
    assert "spec_not_found" in cfl_setup
