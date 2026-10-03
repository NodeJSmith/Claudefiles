"""Tests for scripts/hooks/decision-context-check.py."""

import json
import os
import subprocess
import threading
import time
from pathlib import Path

HOOK = Path(__file__).parent.parent / "scripts" / "hooks" / "decision-context-check.py"
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


def decision_input(
    question: str = "Decision 3 of 14: What shape is a cadence policy?",
) -> dict:
    return {
        "questions": [
            {"question": question, "header": "D3", "multiSelect": False, "options": []}
        ]
    }


def ask(tool_input: dict | None = None) -> dict:
    return assistant_tool_use(
        TOOL_USE_ID, "AskUserQuestion", tool_input or decision_input()
    )


def write_transcript(path: Path, entries: list[dict]) -> None:
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def run_hook(
    tmp_path: Path,
    transcript: Path,
    tool_name: str = "AskUserQuestion",
    tool_input: dict | None = None,
):
    payload = {
        "tool_name": tool_name,
        "tool_input": tool_input or decision_input(),
        "tool_use_id": TOOL_USE_ID,
        "transcript_path": str(transcript),
        "hook_event_name": "PreToolUse",
    }
    return subprocess.run(
        [str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
        timeout=10,
        check=False,
    )


def decision(result: subprocess.CompletedProcess) -> str | None:
    assert result.returncode == 0, result.stderr
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def test_other_tools_pass_through(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [user_prompt("hi")])
    assert (
        decision(
            run_hook(
                tmp_path, transcript, tool_name="Bash", tool_input={"command": "ls"}
            )
        )
        is None
    )


def test_non_decision_question_passes_through(tmp_path):
    transcript = tmp_path / "t.jsonl"
    plain = {
        "questions": [
            {
                "question": "Ship it?",
                "header": "Ship",
                "multiSelect": False,
                "options": [],
            }
        ]
    }
    write_transcript(
        transcript,
        [user_prompt("go"), assistant_tool_use(TOOL_USE_ID, "AskUserQuestion", plain)],
    )
    assert decision(run_hook(tmp_path, transcript, tool_input=plain)) is None


def test_rubric_in_reply_text_is_allowed(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript, [tool_result("toolu_prev"), assistant_text(RUBRIC), ask()]
    )
    assert decision(run_hook(tmp_path, transcript)) is None


def test_rubric_only_in_written_file_is_denied(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript,
        [
            user_prompt("sketch it"),
            assistant_text("The ledger has 13 decisions. I'm writing it now."),
            assistant_tool_use(
                "toolu_write", "Write", {"file_path": "design.md", "content": RUBRIC}
            ),
            tool_result("toolu_write"),
            ask(),
        ],
    )
    result = run_hook(tmp_path, transcript)
    assert decision(result) == "deny"
    assert (
        "Deciding factor"
        in json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_rubric_before_an_intervening_tool_call_is_denied(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript,
        [
            assistant_text(RUBRIC),
            assistant_tool_use("toolu_edit", "Edit", {"file_path": "design.md"}),
            tool_result("toolu_edit"),
            ask(),
        ],
    )
    assert decision(run_hook(tmp_path, transcript)) == "deny"


def test_context_prefixed_question_still_triggers(tmp_path):
    transcript = tmp_path / "t.jsonl"
    tool_input = decision_input("[Context: 40%] Decision 5 of 7, 2 new: Which key?")
    write_transcript(transcript, [tool_result("toolu_prev"), ask(tool_input)])
    assert decision(run_hook(tmp_path, transcript, tool_input=tool_input)) == "deny"


def test_meta_entry_does_not_end_the_reply_span(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(
        transcript,
        [
            user_prompt("go"),
            assistant_text(RUBRIC),
            skill_meta("Base directory for this skill: ..."),
            ask(),
        ],
    )
    assert decision(run_hook(tmp_path, transcript)) is None


def test_waits_for_the_tool_use_line_to_land(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [tool_result("toolu_prev")])

    def append_turn_late():
        time.sleep(0.3)
        with transcript.open("a") as f:
            f.write(json.dumps(assistant_text("No rubric here.")) + "\n")
            f.write(json.dumps(ask()) + "\n")

    writer = threading.Thread(target=append_turn_late)
    writer.start()
    result = run_hook(tmp_path, transcript)
    writer.join()
    assert decision(result) == "deny"


def test_allows_when_tool_use_never_lands(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [tool_result("toolu_prev")])
    assert decision(run_hook(tmp_path, transcript)) is None


def test_challenge_finding_with_rubric_is_allowed(tmp_path):
    transcript = tmp_path / "t.jsonl"
    tool_input = decision_input(FINDING_QUESTION)
    write_transcript(
        transcript,
        [tool_result("toolu_prev"), assistant_text(FINDING_RUBRIC), ask(tool_input)],
    )
    assert decision(run_hook(tmp_path, transcript, tool_input=tool_input)) is None


def test_challenge_finding_without_rubric_is_denied(tmp_path):
    transcript = tmp_path / "t.jsonl"
    tool_input = decision_input(FINDING_QUESTION)
    write_transcript(
        transcript,
        [
            assistant_tool_use("toolu_edit", "Edit", {"file_path": "findings.md"}),
            tool_result("toolu_edit"),
            ask(tool_input),
        ],
    )
    assert decision(run_hook(tmp_path, transcript, tool_input=tool_input)) == "deny"


def test_challenge_finding_with_not_recorded_fallback_is_allowed(tmp_path):
    transcript = tmp_path / "t.jsonl"
    tool_input = decision_input(FINDING_QUESTION)
    fallback = "**Deciding-factor:** not recorded\n**Pick-instead-if:** not recorded\n\nWhy it matters: ..."
    write_transcript(
        transcript,
        [tool_result("toolu_prev"), assistant_text(fallback), ask(tool_input)],
    )
    assert decision(run_hook(tmp_path, transcript, tool_input=tool_input)) is None
