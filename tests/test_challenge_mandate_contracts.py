"""Contract guards for the mandatory challenge invocations.

Guards mine-sketch's two mandatory challenge call sites (sketch time and
build-mode ship time), the shared challenge-gate.md recipe, the
`blocking`/`minor` key names it emits, and the challenge phase's position
between ratification and the comb.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

SKETCH_SKILL = "skills/mine-sketch/SKILL.md"
CHALLENGE_GATE = "skills/mine-challenge/challenge-gate.md"
CHALLENGE_SKILL = "skills/mine-challenge/SKILL.md"

SKETCH_RATIFY_HEADING = "## Phase 3: Ratify"
SKETCH_CHALLENGE_HEADING = "## Phase 4: Challenge"
SKETCH_COMB_HEADING = "## Phase 5: Comb"
SKETCH_GATE_HEADING = "## Phase 6:"


@pytest.mark.parametrize(
    ("relative_path", "required_anchors"),
    [
        (
            SKETCH_SKILL,
            [
                # FR#4: challenge phase between ratify and comb
                (
                    "sketch challenge phase heading",
                    rf"^{re.escape(SKETCH_CHALLENGE_HEADING)}$",
                ),
                ("sketch challenge gate reference", r"challenge-gate\.md"),
                ("sketch challenge gate type", r"sketch-challenge"),
                # FR#5: --critics=2
                ("sketch critics pinned", r"--critics=2"),
                # Build mode's ship-time challenge against the ledger
                ("sketch build ship challenge", r"ship-challenge"),
            ],
        ),
        (
            CHALLENGE_GATE,
            [
                # FR#24: challenge-gate.md exists with parameter block
                ("gate recipe heading", r"^# Challenge Gate$"),
                ("gate parameters section", r"^## Parameters the caller supplies$"),
                ("gate sequence section", r"^## The sequence$"),
                # FR#24, FR#8: the literal, non-declinable /mine-challenge
                # invocation itself. Both call sites delegate to this one
                # line rather than repeating the invocation, so this is the
                # only place a "silently deleted the mandatory call" mutation
                # can be caught.
                ("challenge invocation command", r"Invoke `/mine-challenge"),
                # FR#11, AC#16: blocking and minor key names
                ("blocking key in data", r'"blocking"'),
                ("minor key in data", r'"minor"'),
            ],
        ),
    ],
)
def test_challenge_mandate_file_contains_required_anchors(
    relative_path: str, required_anchors: list[tuple[str, str]]
) -> None:
    text = (REPO_ROOT / relative_path).read_text()
    missing = [
        label
        for label, pattern in required_anchors
        if re.search(pattern, text, re.MULTILINE) is None
    ]
    assert missing == [], f"{relative_path} is missing contract anchor(s): {missing}"


@pytest.mark.parametrize(
    ("relative_path", "forbidden_pattern", "label"),
    [
        # FR#16, AC#13: no challenge-results* detection in challenge SKILL.md
        (
            CHALLENGE_SKILL,
            r"challenge-results\*",
            "challenge has no file-based detection",
        ),
        # Spec 1015 D2: scope, structure, and session-size concerns come up in
        # conversation, so sketch carries no escalation prompt.
        (
            SKETCH_SKILL,
            r'header: "Escalate\?"|header: "Too big\?"',
            "sketch has no escalation prompt",
        ),
    ],
)
def test_challenge_mandate_negative(
    relative_path: str, forbidden_pattern: str, label: str
) -> None:
    text = (REPO_ROOT / relative_path).read_text()
    assert re.search(forbidden_pattern, text) is None, f"{relative_path}: {label}"


def test_sketch_challenge_between_ratify_and_comb() -> None:
    """FR#4, AC#3: the challenge runs after ratification and before the single
    comb, which runs once so it also catches inconsistency the challenge's
    edits introduced. The ledger gate comes last."""
    text = (REPO_ROOT / SKETCH_SKILL).read_text()
    ratify_pos = text.index(SKETCH_RATIFY_HEADING)
    challenge_pos = text.index(SKETCH_CHALLENGE_HEADING)
    comb_pos = text.index(SKETCH_COMB_HEADING)
    gate_pos = text.index(SKETCH_GATE_HEADING)
    assert ratify_pos < challenge_pos < comb_pos < gate_pos
