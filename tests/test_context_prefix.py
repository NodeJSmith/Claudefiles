"""Integration tests for the context-prefix.sh PreToolUse hook on AskUserQuestion.

Each test feeds the hook a PreToolUse payload and asserts on the
updatedInput it returns: the first question gets "[Context: N%] " from the
claude-context-writer sidecar, and any prefix the model wrote is stripped.
"""

import json
import subprocess
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
HOOK = REPO_ROOT / "scripts" / "hooks" / "context-prefix.sh"


@pytest.fixture
def session_id():
    sid = f"cp-test-{uuid.uuid4().hex[:8]}"
    yield sid
    Path(f"/tmp/claude-context-{sid}.meta").unlink(missing_ok=True)


def write_sidecar(session_id: str, pct: str) -> None:
    Path(f"/tmp/claude-context-{session_id}.meta").write_text(
        f"pct={pct}\ncwd=/home/user/a=b\n"  # "=" in cwd: parser must anchor on pct=
    )


def question(text: str) -> dict:
    return {
        "question": text,
        "header": "Ship",
        "options": [
            {"label": "Yes", "description": "d"},
            {"label": "No", "description": "d"},
        ],
        "multiSelect": False,
    }


def run_hook(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5,
    )


def updated_questions(session_id: str, *texts: str) -> list[str]:
    payload = {
        "session_id": session_id,
        "hook_event_name": "PreToolUse",
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": [question(t) for t in texts]},
    }
    result = run_hook(payload)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in out["hookSpecificOutput"]
    return [
        q["question"] for q in out["hookSpecificOutput"]["updatedInput"]["questions"]
    ]


def test_prefixes_first_question_from_sidecar(session_id):
    write_sidecar(session_id, "26")
    assert updated_questions(session_id, "Ship it?", "And this?") == [
        "[Context: 26%] Ship it?",
        "And this?",
    ]


def test_replaces_model_written_prefix_with_measured_value(session_id):
    write_sidecar(session_id, "26")
    assert updated_questions(session_id, "[Context: 41%] Ship it?") == [
        "[Context: 26%] Ship it?"
    ]


def test_strips_model_prefix_from_every_question(session_id):
    write_sidecar(session_id, "5")
    assert updated_questions(session_id, "A?", "  [Context:9%]  B?") == [
        "[Context: 5%] A?",
        "B?",
    ]


def test_preserves_other_question_fields(session_id):
    write_sidecar(session_id, "30")
    payload = {"session_id": session_id, "tool_input": {"questions": [question("Q?")]}}
    out = json.loads(run_hook(payload).stdout)
    q = out["hookSpecificOutput"]["updatedInput"]["questions"][0]
    assert {k: v for k, v in q.items() if k != "question"} == {
        k: v for k, v in question("Q?").items() if k != "question"
    }


def test_no_sidecar_means_no_prefix(session_id):
    assert updated_questions(session_id, "[Context: 41%] Ship it?") == ["Ship it?"]


@pytest.mark.parametrize("pct", ["", "42.5", "-5", "abc"])
def test_garbled_sidecar_means_no_prefix(session_id, pct):
    write_sidecar(session_id, pct)
    assert updated_questions(session_id, "Ship it?") == ["Ship it?"]


@pytest.mark.parametrize("bad_sid", ["", "../etc", "a.b"])
def test_unsafe_session_id_skips_sidecar(bad_sid):
    assert updated_questions(bad_sid, "Ship it?") == ["Ship it?"]


@pytest.mark.parametrize("tool_input", [{}, {"questions": []}, {"questions": "nope"}])
def test_leaves_input_without_questions_untouched(tool_input):
    result = run_hook({"session_id": "x", "tool_input": tool_input})
    assert result.returncode == 0
    assert result.stdout == ""


def test_invalid_json_exits_cleanly():
    result = subprocess.run(
        [str(HOOK)], input="not json", capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0
    assert result.stdout == ""
