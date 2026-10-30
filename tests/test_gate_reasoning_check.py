"""Integration tests for gate-reasoning-check.py (PostToolUse, PostToolUseFailure: AskUserQuestion).

Drives the hook as a subprocess against written transcripts, the same path Claude Code uses.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HOOK = REPO_ROOT / "scripts" / "hooks" / "gate-reasoning-check.py"
CALL_ID = "toolu_current"
RUBRIC = "**Situation:** today the cache reads the flag separately. " + "x" * 200


def text(body: str) -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": body}]},
    }


def tool(name: str, call_id: str = "toolu_other") -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": call_id, "name": name, "input": {}}],
        },
    }


def result(call_id: str = "toolu_other") -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": call_id, "content": "ok"}
            ],
        },
    }


def user(body: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": body}}


def write_transcript(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def run_hook(
    tmp_path: Path,
    records: list[dict],
    question: str = "Decision 2 of 4: Which one?",
    header: str = "D2",
) -> dict:
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [*records, tool("AskUserQuestion", CALL_ID)])
    return invoke(tmp_path, transcript, question, header)


def invoke(
    tmp_path: Path, transcript: Path, question: str | list[dict], header: str = "D2"
) -> dict:
    questions = (
        question
        if isinstance(question, list)
        else [{"question": question, "header": header, "options": []}]
    )
    payload = {
        "tool_name": "AskUserQuestion",
        "tool_use_id": CALL_ID,
        "transcript_path": str(transcript),
        "session_id": "s",
        "hook_event_name": "PostToolUse",
        "tool_input": {"questions": questions},
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
        timeout=10,
        check=True,
    )
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def reminded(output: dict) -> bool:
    return "additionalContext" in output.get("hookSpecificOutput", {})


def test_decision_with_no_text_is_reminded(tmp_path):
    assert reminded(run_hook(tmp_path, [tool("Edit"), result()]))


def test_decision_with_rubric_stays_silent(tmp_path):
    assert not reminded(run_hook(tmp_path, [tool("Edit"), result(), text(RUBRIC)]))


def test_finding_and_rare_batch_questions_are_gates(tmp_path):
    assert reminded(
        run_hook(
            tmp_path, [], "[Context: 28%] Finding 4/8: Ordering (TENSION)", "senior-eng"
        )
    )
    assert reminded(
        run_hook(
            tmp_path,
            [],
            "[Context: 29%] 2 rare-case findings: accept the recommendations?",
            "Rare cases",
        )
    )


def test_non_gate_question_is_ignored(tmp_path):
    assert not reminded(
        run_hook(tmp_path, [], "Does this posture fit the change?", "Posture")
    )


def test_followup_rare_question_is_ignored(tmp_path):
    assert not reminded(
        run_hook(
            tmp_path,
            [],
            "Which rare-case findings (1-6) do you want to walk?",
            "Rare cases",
        )
    )


def test_text_before_the_previous_question_does_not_count(tmp_path):
    records = [text(RUBRIC), tool("AskUserQuestion"), result()]
    assert reminded(run_hook(tmp_path, records))


def test_reask_after_a_user_question_needs_new_text(tmp_path):
    records = [text(RUBRIC), user("what is the difference between the first two?")]
    assert reminded(run_hook(tmp_path, records))


def test_status_lines_split_by_tools_do_not_add_up(tmp_path):
    line = (
        "Applied that fix. Moving on to the next item now, then the rest of the list. "
        * 2
    )
    records = [
        text(line),
        tool("Edit"),
        result(),
        text(line),
        tool("Edit"),
        result(),
        text(line),
    ]
    assert reminded(run_hook(tmp_path, records))


def test_rubric_followed_by_a_tool_still_counts(tmp_path):
    assert not reminded(run_hook(tmp_path, [text(RUBRIC), tool("Bash"), result()]))


def test_subagent_text_does_not_count(tmp_path):
    assert reminded(run_hook(tmp_path, [{**text(RUBRIC), "isSidechain": True}]))


def test_rubric_in_the_same_record_as_the_call_counts(tmp_path):
    transcript = tmp_path / "t.jsonl"
    mixed = tool("AskUserQuestion", CALL_ID)
    mixed["message"]["content"].insert(0, {"type": "text", "text": RUBRIC})
    write_transcript(transcript, [mixed])
    assert not reminded(invoke(tmp_path, transcript, "Decision 1 of 2: Which?"))


def test_batched_questions_need_reasoning_for_each(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [text(RUBRIC), tool("AskUserQuestion", CALL_ID)])
    questions = [
        {"question": f"Finding {n}: which?", "header": "F", "options": []}
        for n in (2, 3)
    ]
    assert reminded(invoke(tmp_path, transcript, questions))
    write_transcript(transcript, [text(RUBRIC * 2), tool("AskUserQuestion", CALL_ID)])
    assert not reminded(invoke(tmp_path, transcript, questions))


def test_triggers_match_the_question_wording_in_the_skills():
    """A rewording in a skill would otherwise switch the hook off silently."""
    sketch = (REPO_ROOT / "skills/mine-sketch/SKILL.md").read_text()
    protocol = (REPO_ROOT / "skills/mine-challenge/findings-protocol.md").read_text()
    assert 'question: "Decision <N> of <M>:' in sketch
    assert 'header: "D<n>"' in sketch
    assert 'Finding N/{total}: <title> (<severity>)"' in protocol
    assert "Finding N/{total}: <title> (TENSION)" in protocol
    assert '{count} rare-case findings: accept the recommendations?"' in protocol


def test_waits_for_the_call_to_reach_the_transcript(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [text(RUBRIC)])

    def flush_later() -> None:
        time.sleep(0.4)
        write_transcript(transcript, [text(RUBRIC), tool("AskUserQuestion", CALL_ID)])

    writer = threading.Thread(target=flush_later)
    writer.start()
    output = invoke(tmp_path, transcript, "Decision 1 of 2: Which?")
    writer.join()
    assert not reminded(output)
    assert (
        "shown"
        in (tmp_path / ".local/share/claudefiles/gate-reasoning-check.log").read_text()
    )


def test_stays_silent_when_the_call_never_appears(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [])
    assert not reminded(invoke(tmp_path, transcript, "Decision 1 of 2: Which?"))
    assert (
        "transcript"
        in (tmp_path / ".local/share/claudefiles/gate-reasoning-check.log").read_text()
    )


def test_stays_silent_when_the_transcript_is_missing(tmp_path):
    assert not reminded(
        invoke(tmp_path, tmp_path / "missing.jsonl", "Decision 1 of 2: Which?")
    )
    assert (
        "transcript"
        in (tmp_path / ".local/share/claudefiles/gate-reasoning-check.log").read_text()
    )
