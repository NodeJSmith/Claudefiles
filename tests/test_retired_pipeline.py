"""Contract guards for retired components: spec 1015 retired define → plan →
orchestrate, and cfl followed once mine-sketch no longer needed it.

No installed instruction file may name a deleted component, since a skill or
rule that routes to a missing skill fails only when someone follows it.
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
    "cfl",
    "dispatch-stats",
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
