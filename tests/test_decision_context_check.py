"""Tests for scripts/hooks/decision-context-check.py."""

import importlib.util
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
HOOK = REPO_ROOT / "scripts" / "hooks" / "decision-context-check.py"
TOOL_USE_ID = "toolu_decision_probe"
RUBRIC = (
    "**Deciding factor:** fewest moving parts\n\n"
    "| | A | B |\n|---|---|---|\n| cost | low | high |\n\n"
    "**Recommendation:** A, because it is simpler.\n**Pick B instead if** you need X."
)
FINDING_QUESTION = "[Context: 43%] Finding 7/10: UnknownValue short-circuit (MEDIUM)"
FINDING_RUBRIC = (
    "**Deciding-factor:** fewer code paths\n\n"
    "**Criteria:**\n| | A | B |\n|---|---|---|\n| paths | 1 | 2 |\n\n"
    "**Pick-instead-if:** B if identity must survive revalidation."
)
FINDING_FALLBACK = (
    "**Deciding-factor:** not recorded\n**Pick-instead-if:** not recorded\n\n"
    "Why it matters: ..."
)

_spec = importlib.util.spec_from_file_location("decision_context_check", HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    return tmp_path / "t.jsonl"


def user_prompt(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool_result(tool_use_id: str) -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_use_id}],
        },
    }


def skill_meta(text: str) -> dict:
    return {
        "type": "user",
        "isMeta": True,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def assistant_text(text: str) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def assistant_tool_use(tool_use_id: str, name: str, tool_input: dict) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": name,
                    "input": tool_input,
                }
            ]
        },
    }


def question_input(
    question: str = "Decision 3 of 14: What shape is a cadence policy?",
) -> dict:
    return {
        "questions": [
            {"question": question, "header": "Q", "multiSelect": False, "options": []}
        ]
    }


def ask(tool_input: dict) -> dict:
    return assistant_tool_use(TOOL_USE_ID, "AskUserQuestion", tool_input)


def write_transcript(path: Path, entries: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")


def run_hook(
    transcript: Path, tool_input: dict, tool_name: str = "AskUserQuestion"
) -> subprocess.CompletedProcess:
    payload = {
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_use_id": TOOL_USE_ID,
        "transcript_path": str(transcript),
        "hook_event_name": "PreToolUse",
    }
    return subprocess.run(
        [str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(transcript.parent)},
        timeout=10,
        check=False,
    )


def permission_decision(result: subprocess.CompletedProcess) -> str | None:
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def check(
    transcript: Path, entries: list[dict], tool_input: dict
) -> subprocess.CompletedProcess:
    """Write entries ending in an AskUserQuestion for tool_input, then run the hook."""
    write_transcript(transcript, [*entries, ask(tool_input)])
    return run_hook(transcript, tool_input)


def test_other_tools_pass_through(transcript):
    write_transcript(transcript, [user_prompt("hi")])
    result = run_hook(transcript, {"command": "ls"}, tool_name="Bash")
    assert permission_decision(result) is None


def test_non_decision_question_passes_through(transcript):
    result = check(transcript, [user_prompt("go")], question_input("Ship it?"))
    assert permission_decision(result) is None


def test_rubric_in_reply_text_is_allowed(transcript):
    result = check(
        transcript,
        [tool_result("toolu_prev"), assistant_text(RUBRIC)],
        question_input(),
    )
    assert permission_decision(result) is None


def test_rubric_only_in_written_file_is_denied(transcript):
    entries = [
        user_prompt("sketch it"),
        assistant_text("The ledger has 13 decisions. I'm writing it now."),
        assistant_tool_use(
            "toolu_write", "Write", {"file_path": "design.md", "content": RUBRIC}
        ),
        tool_result("toolu_write"),
    ]
    result = check(transcript, entries, question_input())
    assert permission_decision(result) == "deny"
    reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Deciding factor" in reason


def test_rubric_before_an_intervening_tool_call_is_denied(transcript):
    entries = [
        assistant_text(RUBRIC),
        assistant_tool_use("toolu_edit", "Edit", {"file_path": "design.md"}),
        tool_result("toolu_edit"),
    ]
    assert permission_decision(check(transcript, entries, question_input())) == "deny"


def test_context_prefixed_question_still_triggers(transcript):
    tool_input = question_input("[Context: 40%] Decision 5 of 7, 2 new: Which key?")
    result = check(transcript, [tool_result("toolu_prev")], tool_input)
    assert permission_decision(result) == "deny"


def test_meta_entry_does_not_end_the_reply_span(transcript):
    entries = [
        user_prompt("go"),
        assistant_text(RUBRIC),
        skill_meta("Base directory for this skill: ..."),
    ]
    assert permission_decision(check(transcript, entries, question_input())) is None


def test_waits_for_the_tool_use_line_to_land(transcript):
    write_transcript(transcript, [tool_result("toolu_prev")])

    def append_turn_late():
        time.sleep(0.3)
        with transcript.open("a", encoding="utf-8") as f:
            f.write(json.dumps(assistant_text("No rubric here.")) + "\n")
            f.write(json.dumps(ask(question_input())) + "\n")

    writer = threading.Thread(target=append_turn_late)
    writer.start()
    result = run_hook(transcript, question_input())
    writer.join()
    assert permission_decision(result) == "deny"


def test_allows_when_tool_use_never_lands(transcript):
    write_transcript(transcript, [tool_result("toolu_prev")])
    assert permission_decision(run_hook(transcript, question_input())) is None


def test_challenge_finding_with_rubric_is_allowed(transcript):
    result = check(
        transcript,
        [tool_result("toolu_prev"), assistant_text(FINDING_RUBRIC)],
        question_input(FINDING_QUESTION),
    )
    assert permission_decision(result) is None


def test_challenge_finding_without_rubric_is_denied(transcript):
    entries = [
        assistant_tool_use("toolu_edit", "Edit", {"file_path": "findings.md"}),
        tool_result("toolu_edit"),
    ]
    result = check(transcript, entries, question_input(FINDING_QUESTION))
    assert permission_decision(result) == "deny"


def test_challenge_finding_with_not_recorded_fallback_is_allowed(transcript):
    result = check(
        transcript,
        [tool_result("toolu_prev"), assistant_text(FINDING_FALLBACK)],
        question_input(FINDING_QUESTION),
    )
    assert permission_decision(result) is None


@pytest.mark.parametrize(
    ("kind_name", "question_template", "rubric_doc"),
    [
        (
            "mine-sketch decision",
            REPO_ROOT / "skills" / "mine-sketch" / "SKILL.md",
            REPO_ROOT / "references" / "common" / "presenting-decisions.md",
        ),
        (
            "mine-challenge finding",
            REPO_ROOT / "skills" / "mine-challenge" / "findings-protocol.md",
            REPO_ROOT / "skills" / "mine-challenge" / "findings-protocol.md",
        ),
    ],
)
def test_hook_matches_the_skill_docs(kind_name, question_template, rubric_doc):
    """A renamed label or question format in a skill doc would make the hook deny or
    ignore every question of that kind; fail here instead."""
    kind = next(k for k in hook.QUESTION_KINDS if k.name == kind_name)
    template = question_template.read_text(encoding="utf-8")
    rendered = template.replace("<N> of <M>", "3 of 14").replace("N/{total}", "7/10")
    assert kind.trigger.search(rendered), (
        f"{kind_name} trigger not in {question_template}"
    )
    # Only the format template's label lines (`**Label:** ...`), not prose that
    # mentions the labels in backticks — prose would keep this passing after the
    # template itself changed.
    label_lines = "\n".join(
        line
        for line in rubric_doc.read_text(encoding="utf-8").splitlines()
        if line.startswith("**")
    )
    for label, pattern in kind.markers.items():
        assert pattern.search(label_lines), f"{label} label line not in {rubric_doc}"
