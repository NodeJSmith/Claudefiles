"""Tests for claude_memory.session_tail — prior-session tail recovery."""

import json
import os

from claude_memory.session_tail import (
    build_tail,
    find_pending_question,
    format_pending_block,
    last_typed_instruction,
    load_tail_entries,
    resolve_target,
    transcript_dir,
    typed_instruction,
)

# --- entry builders (mirror the real transcript shapes) ---

_counter = [0]


def _uuid() -> str:
    _counter[0] += 1
    return f"uuid-{_counter[0]:04d}"


def user_text(text: str, sidechain: bool = False) -> dict:
    return {
        "type": "user",
        "message": {"role": "user", "content": text},
        "uuid": _uuid(),
        "isSidechain": sidechain,
    }


def user_tool_result(tool_id: str, content) -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": content}
            ],
        },
        "uuid": _uuid(),
    }


def assistant_text(text: str) -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        "uuid": _uuid(),
    }


def ask_question(tool_id: str, question: str, options, sidechain: bool = False) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": "AskUserQuestion",
                    "input": {
                        "questions": [{"question": question, "options": options}]
                    },
                }
            ],
        },
        "uuid": _uuid(),
        "isSidechain": sidechain,
    }


OPTS = [
    {"label": "Ship it", "description": "commit and PR"},
    {"label": "Wait", "description": "hold"},
]
ANSWERED = 'Your questions have been answered: "How do you want to proceed?"="Ship it"'
REJECTED = (
    "The user doesn't want to proceed with this tool use. The tool use was rejected."
)
INTERRUPT = "[Request interrupted by user for tool use]"


class TestFindPendingQuestion:
    def test_asked_no_result_is_pending(self):
        entries = [user_text("do the thing"), ask_question("t1", "proceed?", OPTS)]
        payload = find_pending_question(entries)
        assert payload is not None
        assert payload["questions"][0]["question"] == "proceed?"

    def test_asked_then_rejected_is_pending(self):
        entries = [
            ask_question("t1", "proceed?", OPTS),
            user_tool_result("t1", REJECTED),
        ]
        assert find_pending_question(entries) is not None

    def test_asked_then_interrupted_is_pending(self):
        entries = [
            ask_question("t1", "proceed?", OPTS),
            user_tool_result("t1", INTERRUPT),
        ]
        assert find_pending_question(entries) is not None

    def test_asked_then_answered_is_not_pending(self):
        entries = [
            ask_question("t1", "proceed?", OPTS),
            user_tool_result("t1", ANSWERED),
        ]
        assert find_pending_question(entries) is None

    def test_no_question_is_not_pending(self):
        entries = [user_text("hi"), assistant_text("hello")]
        assert find_pending_question(entries) is None

    def test_sidechain_question_ignored(self):
        entries = [ask_question("t1", "subagent ask?", OPTS, sidechain=True)]
        assert find_pending_question(entries) is None

    def test_only_last_question_matters(self):
        # Earlier question answered, later one left open -> pending on the later.
        entries = [
            ask_question("t1", "first?", OPTS),
            user_tool_result("t1", ANSWERED),
            ask_question("t2", "second?", OPTS),
        ]
        payload = find_pending_question(entries)
        assert payload["questions"][0]["question"] == "second?"

    def test_last_answered_after_earlier_open(self):
        # Later question answered -> not pending even if an earlier one looked open.
        entries = [
            ask_question("t1", "first?", OPTS),
            ask_question("t2", "second?", OPTS),
            user_tool_result("t2", ANSWERED),
        ]
        assert find_pending_question(entries) is None

    def test_result_as_list_content(self):
        # Real transcripts sometimes store tool_result content as a list of blocks;
        # the answer marker must be read from the extracted text, not str(list).
        listed = [{"type": "text", "text": ANSWERED}]
        entries = [ask_question("t1", "proceed?", OPTS), user_tool_result("t1", listed)]
        assert find_pending_question(entries) is None

    def test_list_result_without_marker_is_pending(self):
        # A non-answer delivered as list-of-blocks must not be read as answered.
        listed = [{"type": "text", "text": "user chose to stop"}]
        entries = [ask_question("t1", "proceed?", OPTS), user_tool_result("t1", listed)]
        assert find_pending_question(entries) is not None


class TestTypedInstruction:
    def test_real_text(self):
        assert typed_instruction(user_text("ship the feature")) == "ship the feature"

    def test_tool_result_filtered(self):
        assert typed_instruction(user_tool_result("t1", "output")) is None

    def test_interrupt_filtered(self):
        assert typed_instruction(user_text(INTERRUPT)) is None

    def test_task_notification_filtered(self):
        assert (
            typed_instruction(
                user_text("<task-notification>\ndone\n</task-notification>")
            )
            is None
        )

    def test_system_reminder_filtered(self):
        assert (
            typed_instruction(user_text("<system-reminder>be good</system-reminder>"))
            is None
        )

    def test_skill_body_filtered(self):
        assert (
            typed_instruction(user_text("Base directory for this skill: /x\n# Foo"))
            is None
        )

    def test_command_wrapper_stripped_to_empty(self):
        entry = user_text(
            "<command-message>x</command-message><command-name>/x</command-name>"
        )
        assert typed_instruction(entry) is None

    def test_last_typed_instruction_skips_trailing_noise(self):
        entries = [
            user_text("the real instruction"),
            assistant_text("working"),
            user_tool_result("t1", "out"),
            user_text("<task-notification>done</task-notification>"),
        ]
        assert last_typed_instruction(entries) == "the real instruction"


class TestBuildTail:
    def test_orders_and_limits(self):
        entries = [
            user_text("u1"),
            assistant_text("a1"),
            ask_question("t1", "q?", OPTS),
            user_tool_result("t1", "out"),
        ]
        tail = build_tail(entries, 8)
        assert tail[0] == ("user", "u1")
        assert tail[1] == ("assistant", "a1")
        assert ("tool", "AskUserQuestion") in tail

    def test_respects_k(self):
        entries = [user_text(f"u{i}") for i in range(20)]
        assert len(build_tail(entries, 5)) == 5

    def test_non_positive_k_returns_empty(self):
        entries = [user_text("u1"), assistant_text("a1")]
        assert build_tail(entries, 0) == []
        assert build_tail(entries, -1) == []


class TestTranscriptDir:
    def test_worktree_path_not_normalized(self):
        # The transcript lives in the RAW-cwd dir, worktree segment included.
        cwd = "/home/j/source/hassette/.claude/worktrees/959"
        assert (
            transcript_dir(cwd).name == "-home-j-source-hassette--claude-worktrees-959"
        )

    def test_plain_path(self):
        assert transcript_dir("/home/j/repo").name == "-home-j-repo"

    def test_dots_become_dashes(self):
        assert transcript_dir("/home/j/.config/app").name == "-home-j--config-app"


class TestResolveTarget:
    def _write(self, path, stem):
        f = path / f"{stem}.jsonl"
        f.write_text(json.dumps({"type": "user", "uuid": "u", "message": {}}) + "\n")
        return f

    def test_picks_second_newest(self, tmp_path):
        older = self._write(tmp_path, "older")
        newer = self._write(tmp_path, "newer")  # current/live session
        os.utime(older, (1000, 1000))
        os.utime(newer, (2000, 2000))
        assert resolve_target(tmp_path, None) == older

    def test_selector_substring(self, tmp_path):
        self._write(tmp_path, "aaaa-1111")
        self._write(tmp_path, "bbbb-2222")
        assert resolve_target(tmp_path, "bbbb").stem == "bbbb-2222"

    def test_single_session_returns_none(self, tmp_path):
        self._write(tmp_path, "only")
        assert resolve_target(tmp_path, None) is None


class TestLoadTailEntries:
    def test_reads_only_tail(self, tmp_path):
        f = tmp_path / "s.jsonl"
        lines = [
            json.dumps({"uuid": f"u{i}", "type": "user", "message": {}})
            for i in range(50)
        ]
        f.write_text("\n".join(lines) + "\n")
        entries = load_tail_entries(f, tail_lines=10)
        assert len(entries) == 10
        assert entries[-1]["uuid"] == "u49"

    def test_skips_lines_without_uuid(self, tmp_path):
        f = tmp_path / "s.jsonl"
        f.write_text(
            json.dumps({"type": "file-history-snapshot"})
            + "\n"
            + json.dumps({"uuid": "u1", "type": "user", "message": {}})
            + "\n"
        )
        assert [e["uuid"] for e in load_tail_entries(f, tail_lines=10)] == ["u1"]


class TestFormatPendingBlock:
    def test_injection_format_has_question_and_options(self):
        payload = {"questions": [{"question": "proceed?", "options": OPTS}]}
        out = format_pending_block(payload, for_injection=True)
        assert "Unresolved Decision" in out
        assert "proceed?" in out
        assert "Ship it" in out

    def test_cli_format_numbers_options(self):
        payload = {"questions": [{"question": "proceed?", "options": OPTS}]}
        out = format_pending_block(payload)
        assert "PENDING QUESTION" in out
        assert "1. Ship it" in out
