"""Tests for bin/skill-census."""

import json
import runpy
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "bin" / "skill-census"
count_invocations = runpy.run_path(str(SCRIPT))["count_invocations"]


def user(content) -> dict:
    return {"type": "user", "message": {"content": content}}


def skill_call(name: str) -> dict:
    block = {"type": "tool_use", "name": "Skill", "input": {"skill": name}}
    return {"type": "assistant", "message": {"content": [block]}}


def tool_result(text: str) -> dict:
    return user([{"type": "tool_result", "content": text}])


def slash(name: str) -> dict:
    return user(f"<command-name>/{name}</command-name>")


def skill_body() -> dict:
    return {**user("skill instructions"), "isMeta": True}


def transcript(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


def test_slash_followed_by_tool_call_counts_once_in_total(tmp_path: Path) -> None:
    path = transcript(
        tmp_path, [slash("mine-sketch"), skill_body(), skill_call("mine-sketch")]
    )

    total, tool, slash_counts = count_invocations([path])

    assert total["mine-sketch"] == 1
    assert tool["mine-sketch"] == 1
    assert slash_counts["mine-sketch"] == 1


def test_same_skill_in_separate_turns_counts_each(tmp_path: Path) -> None:
    path = transcript(
        tmp_path,
        [
            slash("mine-sketch"),
            skill_call("mine-sketch"),
            tool_result("ok"),
            user("next request"),
            skill_call("mine-sketch"),
        ],
    )

    total, _, _ = count_invocations([path])

    assert total["mine-sketch"] == 2


def test_tool_result_quoting_an_invocation_is_not_counted(tmp_path: Path) -> None:
    path = transcript(
        tmp_path, [tool_result("<command-name>/mine-sketch</command-name>")]
    )

    total, tool, slash_counts = count_invocations([path])

    assert not total
    assert not tool
    assert not slash_counts
