"""Contract guards for the mandatory challenge invocations.

Guards the three call sites that must invoke the mandatory challenge gate
(mine-define, mine-sketch, mine-orchestrate), the shared challenge-gate.md
recipe, the `blocking`/`minor` key names it emits, the define Revise handler
(which re-combs but must not re-challenge), and the sketch upgrade-to-caliper
prompt's position relative to the challenge phase and handoff gate.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFINE_SKILL = "skills/mine-define/SKILL.md"
SKETCH_SKILL = "skills/mine-sketch/SKILL.md"
ORCHESTRATE_PIPELINE = "skills/mine-orchestrate/post-execution-pipeline.md"
CHALLENGE_GATE = "skills/mine-challenge/challenge-gate.md"
CHALLENGE_SKILL = "skills/mine-challenge/SKILL.md"


@pytest.mark.parametrize(
    ("relative_path", "required_anchors"),
    [
        (
            DEFINE_SKILL,
            [
                # FR#1: challenge phase between comb and sign-off
                ("define challenge phase heading", r"^## Phase 5\.5: Challenge$"),
                ("define challenge gate reference", r"challenge-gate\.md"),
                ("define challenge gate type", r"define-challenge"),
            ],
        ),
        (
            SKETCH_SKILL,
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
            ORCHESTRATE_PIPELINE,
            [
                # FR#7: Step 3.5 between Step 3 and Step 4
                ("orchestrate challenge step heading", r"^## Step 3\.5: Challenge$"),
                ("orchestrate challenge gate reference", r"challenge-gate\.md"),
                ("orchestrate challenge gate type", r"ship-challenge"),
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
                # invocation itself. All three callers delegate to this one
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
        # FR#2, AC#1: no "Challenge first" in mine-define sign-off
        (
            DEFINE_SKILL,
            r"Challenge first",
            "define has no Challenge first option",
        ),
        # FR#9, AC#1: no "Challenge first" in orchestrate shipping gate
        (
            ORCHESTRATE_PIPELINE,
            r"Challenge first",
            "orchestrate has no Challenge first option",
        ),
        # FR#16, AC#13: no challenge-results* detection in challenge SKILL.md
        (
            CHALLENGE_SKILL,
            r"challenge-results\*",
            "challenge has no file-based detection",
        ),
        # FR#8: orchestrate dispatches challenge itself rather than telling
        # the user to run it (the pre-feature anti-pattern this replaced).
        (
            ORCHESTRATE_PIPELINE,
            r"[Tt]ell the user to run",
            "orchestrate dispatches challenge itself, doesn't delegate to the user",
        ),
    ],
)
def test_challenge_mandate_negative(
    relative_path: str, forbidden_pattern: str, label: str
) -> None:
    text = (REPO_ROOT / relative_path).read_text()
    assert re.search(forbidden_pattern, text) is None, f"{relative_path}: {label}"


def test_define_challenge_between_comb_and_signoff() -> None:
    """FR#1, AC#2: Phase 5.5 sits between Phase 5 (comb) and Phase 6 (sign-off)."""
    text = (REPO_ROOT / DEFINE_SKILL).read_text()
    comb_pos = text.index("## Phase 5:")
    challenge_pos = text.index("## Phase 5.5: Challenge")
    signoff_pos = text.index("## Phase 6:")
    assert comb_pos < challenge_pos < signoff_pos


def test_sketch_challenge_between_comb_and_handoff() -> None:
    """FR#4, AC#3: Phase 4.5 sits between Phase 4 (comb) and Phase 5 (handoff)."""
    text = (REPO_ROOT / SKETCH_SKILL).read_text()
    comb_pos = text.index("## Phase 4:")
    challenge_pos = text.index("## Phase 4.5: Challenge")
    handoff_pos = text.index("## Phase 5:")
    assert comb_pos < challenge_pos < handoff_pos


def test_orchestrate_challenge_between_step3_and_step4() -> None:
    """FR#7, AC#4: Step 3.5 sits between Step 3 and Step 4."""
    text = (REPO_ROOT / ORCHESTRATE_PIPELINE).read_text()
    step3_pos = text.index("## Step 3:")
    challenge_pos = text.index("## Step 3.5: Challenge")
    step4_pos = text.index("## Step 4:")
    assert step3_pos < challenge_pos < step4_pos


def test_define_revise_recombs_without_rechallenge() -> None:
    """FR#3, AC#17: Revise re-runs the comb but does not invoke challenge."""
    text = (REPO_ROOT / DEFINE_SKILL).read_text()
    revise_start = text.index('### On "Revise"')
    next_section = text.index("###", revise_start + 1)
    revise_text = text[revise_start:next_section]
    assert re.search(r"[Cc]omb", revise_text), "Revise handler must mention comb"
    assert not re.search(r"challenge|Challenge", revise_text), (
        "Revise handler must not mention challenge"
    )


def test_sketch_upgrade_between_challenge_and_handoff() -> None:
    """FR#6, AC#18: Upgrade-to-caliper prompt sits between challenge phase and handoff gate.

    "Upgrade to full caliper" also appears earlier, in Phase 1's escalation
    check — search for the occurrence after the challenge phase heading, not
    the first occurrence in the file.
    """
    text = (REPO_ROOT / SKETCH_SKILL).read_text()
    challenge_pos = text.index("## Phase 4.5: Challenge")
    upgrade_pos = text.index("Upgrade to full caliper", challenge_pos)
    handoff_pos = text.index("## Phase 5:")
    assert challenge_pos < upgrade_pos < handoff_pos
