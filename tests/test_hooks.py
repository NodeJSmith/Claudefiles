"""Integration tests for hook scripts (tmux-drift, compaction, bash-history).

Each test crafts JSON input matching the PreToolUse/PostToolUse schema, invokes
the hook via subprocess.run, and asserts on exit code and stdout.
"""

import json
import os
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path

# Resolve hook paths relative to the repo root
REPO_ROOT = Path(__file__).parent.parent
COMPACTION_HOOK = REPO_ROOT / "scripts" / "hooks" / "subagent-compaction-check.sh"
BASH_HISTORY_HOOK = REPO_ROOT / "scripts" / "hooks" / "bash-history-capture.py"


def run_hook(
    script: Path,
    stdin: str,
    tmpdir: str,
    extra_env: dict | None = None,
    timeout: int = 5,
) -> subprocess.CompletedProcess:
    """Run a hook script with given stdin and CLAUDE_CODE_TMPDIR set to tmpdir."""
    env = os.environ.copy()
    env["CLAUDE_CODE_TMPDIR"] = tmpdir
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(script)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )


# ---------------------------------------------------------------------------
# tmux-drift-check.sh tests
# ---------------------------------------------------------------------------

DRIFT_CHECK_HOOK = REPO_ROOT / "scripts" / "hooks" / "tmux-drift-check.sh"


def _drift_session_id(test_name: str) -> str:
    return f"drift-test-{test_name}-{uuid.uuid4().hex[:8]}"


def _write_drift_counter(session_id: str, count: int) -> Path:
    p = Path(f"/tmp/claude-tmux-drift-{session_id}.txt")
    p.write_text(str(count))
    return p


def _read_drift_counter(session_id: str) -> int | None:
    p = Path(f"/tmp/claude-tmux-drift-{session_id}.txt")
    if not p.exists():
        return None
    text = p.read_text().strip()
    return int(text) if text else None


def _cleanup_drift(session_id: str) -> None:
    p = Path(f"/tmp/claude-tmux-drift-{session_id}.txt")
    if p.exists():
        p.unlink()


def _make_tmux_stub(tmpdir: Path, session_name: str) -> Path:
    """Write a tmux stub script that prints session_name for display-message."""
    stub = tmpdir / "tmux"
    stub.write_text(f'#!/usr/bin/env bash\necho "{session_name}"\n')
    stub.chmod(0o755)
    return stub


def _run_drift_check(
    session_id: str,
    session_name: str = "test-session",
    extra_env: dict[str, str] | None = None,
    tmux_stub_dir: Path | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["TMUX"] = "/tmp/tmux-stub,1,0"
    if tmux_stub_dir:
        env["PATH"] = str(tmux_stub_dir) + ":" + env.get("PATH", "")
        stub_ctx = None
    else:
        stub_ctx = tempfile.TemporaryDirectory()
        _td = Path(stub_ctx.name)
        _make_tmux_stub(_td, session_name)
        env["PATH"] = str(_td) + ":" + env.get("PATH", "")
    if extra_env:
        env.update(extra_env)
    try:
        return subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": session_id}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
    finally:
        if stub_ctx is not None:
            stub_ctx.cleanup()


class TestTmuxDriftCheckSilentBelowInterval:
    """Hook stays silent while counter is below the heartbeat interval."""

    def test_first_call_silent(self):
        sid = _drift_session_id("first_silent")
        try:
            result = _run_drift_check(sid)
            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_drift(sid)

    def test_below_interval_silent(self):
        sid = _drift_session_id("below_interval")
        try:
            _write_drift_counter(sid, 27)  # will become 28, threshold is 30
            result = _run_drift_check(
                sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "30"}
            )
            assert result.returncode == 0
            assert result.stdout.strip() == ""
            assert _read_drift_counter(sid) == 28
        finally:
            _cleanup_drift(sid)

    def test_counter_increments_each_call(self):
        sid = _drift_session_id("increments")
        try:
            _write_drift_counter(sid, 5)
            _run_drift_check(sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "30"})
            assert _read_drift_counter(sid) == 6
        finally:
            _cleanup_drift(sid)


class TestTmuxDriftCheckEmitsAtThreshold:
    """Hook emits session name context at the heartbeat threshold."""

    def test_emits_at_threshold(self):
        sid = _drift_session_id("at_threshold")
        try:
            _write_drift_counter(sid, 29)  # will become 30, fires
            result = _run_drift_check(
                sid,
                session_name="myapp-feature",
                extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "30"},
            )
            assert result.returncode == 0
            output = json.loads(result.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            assert "myapp-feature" in context
            assert "claude-tmux rename" in context
        finally:
            _cleanup_drift(sid)

    def test_counter_resets_after_firing(self):
        sid = _drift_session_id("resets")
        try:
            _write_drift_counter(sid, 29)
            _run_drift_check(sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "30"})
            assert _read_drift_counter(sid) == 0
        finally:
            _cleanup_drift(sid)

    def test_custom_heartbeat_interval(self):
        sid = _drift_session_id("custom_interval")
        try:
            _write_drift_counter(sid, 4)  # will become 5, fires at interval=5
            result = _run_drift_check(
                sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "5"}
            )
            assert result.returncode == 0
            assert result.stdout.strip() != ""
        finally:
            _cleanup_drift(sid)


class TestTmuxDriftCheckNoTmux:
    """Hook exits silently when not inside tmux."""

    def test_no_tmux_env_silent(self):
        sid = _drift_session_id("no_tmux")
        env = os.environ.copy()
        env.pop("TMUX", None)
        result = subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": sid}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestTmuxDriftCheckInvalidSessionId:
    """Hook rejects session IDs with path-unsafe characters."""

    def test_slash_in_session_id_silent(self):
        env = os.environ.copy()
        env["TMUX"] = "/tmp/tmux-stub,1,0"
        result = subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": "foo/bar"}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_dot_in_session_id_silent(self):
        env = os.environ.copy()
        env["TMUX"] = "/tmp/tmux-stub,1,0"
        result = subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": "foo.bar"}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_session_id_silent(self):
        env = os.environ.copy()
        env["TMUX"] = "/tmp/tmux-stub,1,0"
        result = subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": ""}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestTmuxDriftCheckHeartbeatConfig:
    """Heartbeat interval env var edge cases."""

    def test_zero_interval_falls_back_to_default(self):
        # CLAUDE_TMUX_DRIFT_HEARTBEAT=0 is rejected; the hook falls back to 30.
        # With counter at 29, the next call brings it to 30 (>= 30), so the hook fires.
        sid = _drift_session_id("zero_interval")
        try:
            _write_drift_counter(sid, 29)
            result = _run_drift_check(
                sid,
                session_name="zero-fallback-session",
                extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "0"},
            )
            assert result.returncode == 0
            output = json.loads(result.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            assert "zero-fallback-session" in context
            assert _read_drift_counter(sid) == 0
        finally:
            _cleanup_drift(sid)

    def test_invalid_interval_falls_back_to_default(self):
        sid = _drift_session_id("invalid_interval")
        try:
            _write_drift_counter(sid, 5)
            result = _run_drift_check(
                sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "abc"}
            )
            assert result.returncode == 0
            assert result.stdout.strip() == ""  # 6 < 30 default
        finally:
            _cleanup_drift(sid)


def _make_compaction_input(session_id: str, transcript_path: str) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "transcript_path": transcript_path,
            "tool_input": {"description": "test agent"},
            "tool_response": {},
        }
    )


def _write_compact_boundary(jsonl_path: Path, pre: int, post: int) -> None:
    entry = {
        "type": "system",
        "subtype": "compact_boundary",
        "compactMetadata": {
            "trigger": "auto",
            "preTokens": pre,
            "postTokens": post,
            "durationMs": 5000,
        },
    }
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _write_agent_meta(meta_path: Path, description: str) -> None:
    meta = {
        "agentType": "general-purpose",
        "description": description,
        "toolUseId": "toolu_test",
    }
    meta_path.write_text(json.dumps(meta))


def _compaction_fixture(tmpdir: str) -> tuple[str, str, Path]:
    """Create a session transcript and subagent directory. Returns (sid, transcript_path, subagent_dir)."""
    sid = f"compaction-{uuid.uuid4().hex[:8]}"
    transcript = Path(tmpdir) / "session.jsonl"
    transcript.write_text("")
    subagent_dir = Path(tmpdir) / "session" / "subagents"
    subagent_dir.mkdir(parents=True)
    return sid, str(transcript), subagent_dir


class TestCompactionHookDetectsCompaction:
    """Hook detects compact_boundary events and emits a warning."""

    def test_compaction_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)
            _write_agent_meta(subagent_dir / "agent-abc123.meta.json", "T01 executor")

            stdin = _make_compaction_input(sid, transcript_path)
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert "Subagent compaction detected" in result.stdout
            assert "T01 executor" in result.stdout
            assert "170,000" in result.stdout
            assert "8,000" in result.stdout


class TestCompactionHookNoCompaction:
    """Hook exits silently when no compaction events are present."""

    def test_no_compaction_silent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            agent_jsonl.write_text('{"type":"assistant","content":"hello"}\n')

            stdin = _make_compaction_input(sid, transcript_path)
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


class TestCompactionHookDedup:
    """Hook deduplicates — second call for same session is silent."""

    def test_dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)

            stdin = _make_compaction_input(sid, transcript_path)

            result1 = run_hook(COMPACTION_HOOK, stdin, tmpdir)
            assert "Subagent compaction detected" in result1.stdout

            result2 = run_hook(COMPACTION_HOOK, stdin, tmpdir)
            assert result2.stdout.strip() == ""


class TestCompactionHookMissingPostTokens:
    """Hook handles missing postTokens gracefully."""

    def test_missing_post_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            entry = {
                "type": "system",
                "subtype": "compact_boundary",
                "compactMetadata": {"trigger": "auto", "preTokens": 175000},
            }
            agent_jsonl.write_text(json.dumps(entry) + "\n")

            stdin = _make_compaction_input(sid, transcript_path)
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert "175,000" in result.stdout
            assert "not recorded" in result.stdout
            assert "0%" not in result.stdout


class TestCompactionHookMultipleEvents:
    """Hook reports all compaction events for an agent that compacted twice."""

    def test_multiple_compactions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)
            _write_compact_boundary(agent_jsonl, 165000, 9000)

            stdin = _make_compaction_input(sid, transcript_path)
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert "170,000" in result.stdout
            assert "165,000" in result.stdout


class TestCompactionHookNoSubagentDir:
    """Hook exits silently when no subagent directory exists."""

    def test_no_subagent_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid = f"compaction-{uuid.uuid4().hex[:8]}"
            transcript = Path(tmpdir) / "session.jsonl"
            transcript.write_text("")

            stdin = _make_compaction_input(sid, str(transcript))
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# bash-history-capture.py tests
# ---------------------------------------------------------------------------


def _make_bash_history_payload(
    session_id: str = "test-session",
    tool_use_id: str | None = None,
    command: str = "ls -la",
    description: str | None = "List files",
    cwd: str = "/tmp",
    transcript_path: str | None = None,
    status: str = "success",
    output_field: str = "stdout",
    output_text: str = "file1\nfile2\n",
    is_background: bool = False,
) -> str:
    tool_response = {"status": status}
    if output_text:
        tool_response[output_field] = output_text

    return json.dumps(
        {
            "session_id": session_id,
            "tool_use_id": tool_use_id or f"toolu_{uuid.uuid4().hex[:12]}",
            "cwd": cwd,
            "transcript_path": transcript_path,
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": command,
                "description": description,
                "timeout": 120000,
                "run_in_background": is_background,
            },
            "tool_response": tool_response,
        }
    )


def _query_db(db_path: str, query: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query).fetchall()
    conn.close()
    return rows


class TestBashHistoryCapture:
    def test_captures_basic_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = _make_bash_history_payload(
                command="find . -name '*.py'",
                description="Find Python files",
                transcript_path="/home/user/.claude/projects/-home-user-myapp/abc.jsonl",
            )
            result = run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            assert result.returncode == 0

            rows = _query_db(db_path, "SELECT * FROM commands")
            assert len(rows) == 1
            row = rows[0]
            assert row["command"] == "find . -name '*.py'"
            assert row["description"] == "Find Python files"
            assert row["project_slug"] == "-home-user-myapp"
            assert row["output_length"] > 0
            assert row["output_preview"] is not None
            assert row["is_background"] == 0

    def test_handles_stdout_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = _make_bash_history_payload(
                output_field="stdout",
                output_text="hello world",
            )
            result = run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            assert result.returncode == 0
            rows = _query_db(
                db_path, "SELECT output_length, output_preview FROM commands"
            )
            assert rows[0]["output_length"] == 11
            assert rows[0]["output_preview"] == "hello world"

    def test_handles_text_field_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = _make_bash_history_payload(
                output_field="text",
                output_text="fallback output",
            )
            result = run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            assert result.returncode == 0
            rows = _query_db(
                db_path, "SELECT output_length, output_preview FROM commands"
            )
            assert rows[0]["output_length"] == 15
            assert rows[0]["output_preview"] == "fallback output"

    def test_deduplicates_by_tool_use_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            fixed_id = f"toolu_{uuid.uuid4().hex[:12]}"
            for cmd in ["first", "second"]:
                stdin = _make_bash_history_payload(
                    tool_use_id=fixed_id,
                    command=cmd,
                )
                run_hook(
                    BASH_HISTORY_HOOK,
                    stdin,
                    tmpdir,
                    extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
                )
            rows = _query_db(db_path, "SELECT command FROM commands")
            assert len(rows) == 1
            assert rows[0]["command"] == "first"

    def test_skips_empty_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = json.dumps(
                {
                    "session_id": "s1",
                    "tool_use_id": "t1",
                    "tool_input": {},
                    "tool_response": {},
                }
            )
            result = run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            assert result.returncode == 0
            assert not os.path.exists(db_path)

    def test_skips_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            result = run_hook(
                BASH_HISTORY_HOOK,
                "not json",
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            assert result.returncode == 0
            assert not os.path.exists(db_path)

    def test_captures_background_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = _make_bash_history_payload(is_background=True)
            run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            rows = _query_db(db_path, "SELECT is_background FROM commands")
            assert rows[0]["is_background"] == 1

    def test_db_file_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "subdir", "test.db")
            stdin = _make_bash_history_payload()
            run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            assert os.path.exists(db_path)
            mode = os.stat(db_path).st_mode & 0o777
            assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
