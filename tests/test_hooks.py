"""Integration tests for hook scripts (tmux-drift, claude-status-writer,
compaction, bash-history).

Each test crafts JSON input matching the PreToolUse/PostToolUse schema, invokes
the hook via subprocess.run, and asserts on exit code and stdout.
"""

import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path

# Resolve hook paths relative to the repo root
REPO_ROOT = Path(__file__).parent.parent
COMPACTION_HOOK = REPO_ROOT / "scripts" / "hooks" / "subagent-compaction-check.sh"
BASH_HISTORY_HOOK = REPO_ROOT / "scripts" / "hooks" / "bash-history-capture.py"
DOCS_CHECK_HOOK = REPO_ROOT / "scripts" / "hooks" / "project-docs-check.sh"


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
# project-docs-check.sh tests
# ---------------------------------------------------------------------------


def _git_init(path: Path) -> None:
    # Strip GIT_* vars (GIT_DIR, GIT_WORK_TREE, ...) so these commands always
    # target the temp repo at `path` regardless of the ambient invocation
    # context. Without this, running the suite from inside a git hook (e.g.
    # prek's pre-push hook, which sets GIT_DIR for its own invocation) makes
    # git resolve GIT_DIR instead of `cwd` and silently commit into the real
    # outer repo.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, env=env)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        check=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=path, check=True, env=env
    )
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init", "--allow-empty"],
        cwd=path,
        check=True,
        env=env,
    )


def test_git_init_ignores_leaked_git_dir_env() -> None:
    """A leaked GIT_DIR/GIT_WORK_TREE (e.g. this suite running inside prek's
    pre-push hook, which sets GIT_DIR for its own invocation) must not make
    _git_init operate on that outer repo instead of its intended `path`."""
    with (
        tempfile.TemporaryDirectory() as outer,
        tempfile.TemporaryDirectory() as target,
    ):
        outer_path = Path(outer).resolve()
        target_path = Path(target).resolve()
        # Verification queries below must resolve `outer_path` regardless of
        # ambient GIT_* pollution too — otherwise, run for real inside a git
        # hook, both queries would read the *ambient* repo's HEAD instead of
        # outer_path's, making the before/after comparison trivially equal
        # (and the test worthless) whether or not the fix under test works.
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

        _git_init(outer_path)
        outer_head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=outer_path,
            check=True,
            capture_output=True,
            text=True,
            env=clean_env,
        ).stdout.strip()

        saved = {k: os.environ.get(k) for k in ("GIT_DIR", "GIT_WORK_TREE")}
        try:
            os.environ["GIT_DIR"] = str(outer_path / ".git")
            os.environ["GIT_WORK_TREE"] = str(outer_path)
            _git_init(target_path)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        outer_head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=outer_path,
            check=True,
            capture_output=True,
            text=True,
            env=clean_env,
        ).stdout.strip()

        assert outer_head_after == outer_head_before
        assert (target_path / ".git").is_dir()


def _make_docs_check_input(session_id: str, file_path: Path) -> str:
    return json.dumps(
        {"session_id": session_id, "tool_input": {"file_path": str(file_path)}}
    )


def _run_docs_check(
    session_id: str,
    file_path: Path,
    tmpdir: str,
    config_dir: str,
    timeout: int = 6,
) -> subprocess.CompletedProcess:
    return run_hook(
        DOCS_CHECK_HOOK,
        _make_docs_check_input(session_id, file_path),
        tmpdir,
        extra_env={"CLAUDE_CONFIG_DIR": config_dir},
        timeout=timeout,
    )


class TestDocsCheckPromptsWhenMissing:
    """Hook prompts when a touched project has no docs/ directory."""

    def test_prompts_for_undocumented_project(self):
        with (
            tempfile.TemporaryDirectory() as repo,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
        ):
            repo = Path(repo).resolve()
            project = repo / "services" / "api"
            project.mkdir(parents=True)
            (project / "package.json").write_text("{}")
            _git_init(repo)

            sid = f"docs-{uuid.uuid4().hex[:8]}"
            file_path = project / "main.py"
            file_path.write_text("")

            result = _run_docs_check(sid, file_path, tmpdir, config_dir)

            assert result.returncode == 0
            assert "AskUserQuestion" in result.stdout
            assert str(project) in result.stdout


class TestDocsCheckSilentWhenDocsPresent:
    """Hook is silent when the project already has a non-empty docs/ directory."""

    def test_silent_when_documented(self):
        with (
            tempfile.TemporaryDirectory() as repo,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
        ):
            repo = Path(repo)
            project = repo / "services" / "web"
            (project / "docs").mkdir(parents=True)
            (project / "package.json").write_text("{}")
            (project / "docs" / "overview.md").write_text("# Web docs")
            _git_init(repo)

            sid = f"docs-{uuid.uuid4().hex[:8]}"
            file_path = project / "index.js"
            file_path.write_text("")

            result = _run_docs_check(sid, file_path, tmpdir, config_dir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


class TestDocsCheckDedup:
    """Second touch of the same project in the same session stays silent."""

    def test_dedup_within_session(self):
        with (
            tempfile.TemporaryDirectory() as repo,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
        ):
            repo = Path(repo).resolve()
            project = repo / "services" / "api"
            project.mkdir(parents=True)
            (project / "package.json").write_text("{}")
            _git_init(repo)

            sid = f"docs-{uuid.uuid4().hex[:8]}"
            file_a = project / "a.py"
            file_a.write_text("")
            file_b = project / "b.py"
            file_b.write_text("")

            result1 = _run_docs_check(sid, file_a, tmpdir, config_dir)
            assert "AskUserQuestion" in result1.stdout

            result2 = _run_docs_check(sid, file_b, tmpdir, config_dir)
            assert result2.stdout.strip() == ""


class TestDocsCheckSuppressedState:
    """Hook stays silent once a project's state file is suppressed."""

    def test_silent_when_suppressed(self):
        with (
            tempfile.TemporaryDirectory() as repo,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
        ):
            repo = Path(repo).resolve()
            project = repo / "services" / "api"
            project.mkdir(parents=True)
            (project / "package.json").write_text("{}")
            _git_init(repo)

            encoded = str(project).replace("/", "-").replace(".", "-")
            state_dir = Path(config_dir) / "projects" / encoded
            state_dir.mkdir(parents=True)
            (state_dir / "docs-check.json").write_text(
                json.dumps({"status": "suppressed"})
            )

            sid = f"docs-{uuid.uuid4().hex[:8]}"
            file_path = project / "main.py"
            file_path.write_text("")

            result = _run_docs_check(sid, file_path, tmpdir, config_dir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""

    def test_silent_when_deferred_with_future_prompt_after(self):
        with (
            tempfile.TemporaryDirectory() as repo,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
        ):
            repo = Path(repo).resolve()
            project = repo / "services" / "api"
            project.mkdir(parents=True)
            (project / "package.json").write_text("{}")
            _git_init(repo)

            encoded = str(project).replace("/", "-").replace(".", "-")
            state_dir = Path(config_dir) / "projects" / encoded
            state_dir.mkdir(parents=True)
            future = subprocess.run(
                ["date", "-d", "+1 day", "+%Y-%m-%d"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (state_dir / "docs-check.json").write_text(
                json.dumps({"status": "deferred", "tier": 1, "prompt_after": future})
            )

            sid = f"docs-{uuid.uuid4().hex[:8]}"
            file_path = project / "main.py"
            file_path.write_text("")

            result = _run_docs_check(sid, file_path, tmpdir, config_dir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""

    def test_prompts_when_deferred_with_past_prompt_after(self):
        with (
            tempfile.TemporaryDirectory() as repo,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
        ):
            repo = Path(repo).resolve()
            project = repo / "services" / "api"
            project.mkdir(parents=True)
            (project / "package.json").write_text("{}")
            _git_init(repo)

            encoded = str(project).replace("/", "-").replace(".", "-")
            state_dir = Path(config_dir) / "projects" / encoded
            state_dir.mkdir(parents=True)
            past = subprocess.run(
                ["date", "-d", "-1 day", "+%Y-%m-%d"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (state_dir / "docs-check.json").write_text(
                json.dumps({"status": "deferred", "tier": 1, "prompt_after": past})
            )

            sid = f"docs-{uuid.uuid4().hex[:8]}"
            file_path = project / "main.py"
            file_path.write_text("")

            result = _run_docs_check(sid, file_path, tmpdir, config_dir)

            assert result.returncode == 0
            assert "AskUserQuestion" in result.stdout


class TestDocsCheckSymlinkNoHang:
    """Regression: touching a project through a symlinked path must not hang.

    The walk-up loop previously compared a logical path (preserving symlinks)
    against `git rev-parse --show-toplevel`'s physically-resolved output —
    when a symlink sat above the repo with no project marker in between, the
    two never matched and the loop spun until the hook's external timeout.
    """

    def test_symlinked_path_does_not_hang(self):
        with (
            tempfile.TemporaryDirectory() as real_base,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
        ):
            real_base = Path(real_base).resolve()
            repo = real_base / "repo"
            (repo / "sub" / "proj").mkdir(parents=True)
            _git_init(repo)

            linked_base = real_base.parent / f"linked-{uuid.uuid4().hex[:8]}"
            linked_base.symlink_to(real_base)
            try:
                sid = f"docs-{uuid.uuid4().hex[:8]}"
                (repo / "sub" / "proj" / "f.py").write_text("")
                file_path = linked_base / "repo" / "sub" / "proj" / "f.py"

                result = _run_docs_check(sid, file_path, tmpdir, config_dir, timeout=6)

                assert result.returncode == 0
                message = json.loads(result.stdout)["hookSpecificOutput"][
                    "additionalContext"
                ]
                # The canonicalized (physical) path is used, not the symlinked one —
                # proves the walk-up loop terminated against the same path git did,
                # and the state key wasn't built by concatenating the two.
                assert str(repo) in message
                assert str(linked_base) not in message
            finally:
                linked_base.unlink()


class TestDocsCheckStateKeyReanchorsThroughSymlinkedWorktree:
    """Coverage: the defer/suppress state file for a project touched inside a
    worktree — reached through a symlinked path segment — must key on the
    main repo's stable path, not the worktree's own (deleted-on-cleanup) path.

    No prior test exercised the worktree re-anchoring branch under a symlink
    at all (TestDocsCheckSymlinkNoHang only covers the walk-up loop's own
    termination, not this state-key computation). This pins the intended
    behavior of the `git rev-parse --show-prefix`-based re-anchor.
    """

    def test_state_key_uses_main_repo_not_worktree(self):
        with (
            tempfile.TemporaryDirectory() as real_base,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
        ):
            real_base = Path(real_base).resolve()
            main_repo = real_base / "mainrepo"
            main_repo.mkdir()
            _git_init(main_repo)

            worktree = real_base / "mainrepo-wt"
            subprocess.run(
                ["git", "worktree", "add", "-q", "-b", "wtbranch", str(worktree)],
                cwd=main_repo,
                check=True,
                env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            )

            linked_base = real_base.parent / f"linked-{uuid.uuid4().hex[:8]}"
            linked_base.symlink_to(real_base)
            try:
                sid = f"docs-{uuid.uuid4().hex[:8]}"
                file_path = linked_base / "mainrepo-wt" / "f.py"
                (worktree / "f.py").write_text("")

                result = _run_docs_check(sid, file_path, tmpdir, config_dir)

                assert result.returncode == 0
                message = json.loads(result.stdout)["hookSpecificOutput"][
                    "additionalContext"
                ]
                # state_file lives under the main repo's project directory,
                # not the worktree's — and never under the symlinked path.
                assert "docs-check.json" in message
                assert str(main_repo).replace("/", "-").replace(".", "-") in message
                assert str(worktree).replace("/", "-").replace(".", "-") not in message
                assert str(linked_base) not in message
            finally:
                linked_base.unlink()


def _make_git_shim(
    shim_dir: Path, real_git: str, physical_toplevel: str, alias_toplevel: str
) -> Path:
    """Write a git shim that lies about `--show-toplevel` for one specific
    physical path, returning a textually different (but same-target) alias
    path instead. Every other invocation execs the real git unchanged.

    This manufactures the exact divergence the old state-key computation was
    vulnerable to (comparing --show-toplevel's raw output against a pwd -P'd
    path) without relying on a symlinked *file path*, which the hook's own
    `pwd -P` canonicalization of `dir` neutralizes before git ever runs.
    """
    shim = shim_dir / "git"
    shim.write_text(
        f"""#!/usr/bin/env bash
REAL_GIT={shlex.quote(real_git)}
PHYSICAL={shlex.quote(physical_toplevel)}
ALIAS={shlex.quote(alias_toplevel)}

has_rev_parse=0
has_show_toplevel=0
for arg in "$@"; do
  case "$arg" in
    rev-parse) has_rev_parse=1 ;;
    --show-toplevel) has_show_toplevel=1 ;;
  esac
done

if [ "$has_rev_parse" = 1 ] && [ "$has_show_toplevel" = 1 ]; then
  real_answer="$("$REAL_GIT" "$@")"
  rc=$?
  if [ "$real_answer" = "$PHYSICAL" ]; then
    printf '%s\\n' "$ALIAS"
    exit 0
  fi
  printf '%s\\n' "$real_answer"
  exit $rc
fi

exec "$REAL_GIT" "$@"
"""
    )
    shim.chmod(0o755)
    return shim


def _make_show_prefix_failure_shim(
    shim_dir: Path, real_git: str, target_cwd: str
) -> Path:
    """Write a git shim that makes `git rev-parse --show-prefix` fail (no
    output, nonzero exit) when invoked with cwd == target_cwd. Every other
    invocation — including --show-prefix run from anywhere else, and
    --show-toplevel / --git-common-dir from target_cwd itself — execs the
    real git unchanged.

    Manufactures the exact failure the guard in project-docs-check.sh
    (~lines 130-141) exists to handle: an empty/failed --show-prefix result
    for a project_root that is a subproject, not the repo root.
    """
    shim = shim_dir / "git"
    shim.write_text(
        f"""#!/usr/bin/env bash
REAL_GIT={shlex.quote(real_git)}
TARGET_CWD={shlex.quote(target_cwd)}

has_rev_parse=0
has_show_prefix=0
for arg in "$@"; do
  case "$arg" in
    rev-parse) has_rev_parse=1 ;;
    --show-prefix) has_show_prefix=1 ;;
  esac
done

if [ "$has_rev_parse" = 1 ] && [ "$has_show_prefix" = 1 ] && [ "$(pwd -P)" = "$TARGET_CWD" ]; then
  exit 1
fi

exec "$REAL_GIT" "$@"
"""
    )
    shim.chmod(0o755)
    return shim


class TestDocsCheckStateKeyShowPrefixFailureFallsBackToUnanchoredKey:
    """Regression: when `git rev-parse --show-prefix` fails or returns empty
    for a subproject (project_root != repo_root), the guard added in
    project-docs-check.sh (~lines 130-141) must fall back to the unanchored
    project_root key.

    Without the guard, an empty `rel` collapses
    `state_key="${main_repo_root}${rel:+/${rel%/}}"` to exactly
    main_repo_root — silently aliasing this subproject's defer/suppress
    state onto the repo root's own state file, and colliding with any other
    subproject that hits the same failure. The guard's `else` branch instead
    falls back to `state_key="$project_root"`, keeping the subproject's
    state file distinct.
    """

    def test_show_prefix_failure_falls_back_to_project_root_key(self):
        with (
            tempfile.TemporaryDirectory() as repo_base,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
            tempfile.TemporaryDirectory() as shim_base,
        ):
            repo = (Path(repo_base).resolve()) / "repo"
            repo.mkdir()
            _git_init(repo)

            # project_root resolves to this subproject via the marker walk-up
            # loop (package.json found immediately) — it is NOT repo_root, so
            # the guard's `[ "$project_root" = "$repo_root" ]` escape hatch
            # does not apply and the empty-`rel` fallback is the only thing
            # standing between this and a collapsed state key.
            sub_proj = repo / "sub" / "proj"
            sub_proj.mkdir(parents=True)
            (sub_proj / "package.json").write_text("{}")
            (sub_proj / "f.py").write_text("")

            real_git = shutil.which("git")
            assert real_git is not None, "git must be on PATH to build the shim"

            shim_dir = Path(shim_base)
            _make_show_prefix_failure_shim(shim_dir, real_git, str(sub_proj))

            sid = f"docs-{uuid.uuid4().hex[:8]}"
            file_path = sub_proj / "f.py"

            env = os.environ.copy()
            env["PATH"] = str(shim_dir) + ":" + env.get("PATH", "")
            env["CLAUDE_CODE_TMPDIR"] = tmpdir
            env["CLAUDE_CONFIG_DIR"] = str(config_dir)

            result = subprocess.run(
                [str(DOCS_CHECK_HOOK)],
                input=_make_docs_check_input(sid, file_path),
                capture_output=True,
                text=True,
                env=env,
                timeout=6,
                check=False,
            )

            assert result.returncode == 0
            message = json.loads(result.stdout)["hookSpecificOutput"][
                "additionalContext"
            ]

            # New (guarded) code: rel is empty and project_root != repo_root,
            # so state_key falls back to the unanchored project_root — the
            # full sub/proj path is encoded into the state file's directory.
            unanchored_state_file = str(
                Path(config_dir)
                / "projects"
                / str(sub_proj).replace("/", "-").replace(".", "-")
                / "docs-check.json"
            )
            # Old (unconditional) code: state_key collapses to bare
            # main_repo_root ("${rel:+...}" contributes nothing when rel is
            # empty) — the state file directory would encode only the repo
            # root, dropping the sub/proj offset entirely.
            anchored_state_file = str(
                Path(config_dir)
                / "projects"
                / str(repo).replace("/", "-").replace(".", "-")
                / "docs-check.json"
            )

            assert unanchored_state_file in message
            assert anchored_state_file not in message


class TestDocsCheckStateKeyMismatchedToplevelFormatting:
    """Regression: the state-key computation must not depend on
    `git rev-parse --show-toplevel`'s raw output textually matching the
    pwd -P'd project_root.

    TestDocsCheckStateKeyReanchorsThroughSymlinkedWorktree places a symlink
    above the worktree, but the hook canonicalizes the touched file's
    directory with `pwd -P` *before* invoking git — so `--show-toplevel`,
    run from that already-physical cwd, returns the same physical path on
    both the old and new code. No textual divergence occurs, so that test
    cannot distinguish the two implementations (it passes unchanged against
    the pre-fix script).

    This test manufactures the divergence directly with a git shim that
    returns a textually different (but same-target) toplevel path — the
    exact scenario `--show-prefix` was introduced to be immune to, since it
    never compares against `--show-toplevel`'s output at all.
    """

    def test_state_key_survives_toplevel_alias_mismatch(self):
        with (
            tempfile.TemporaryDirectory() as real_base,
            tempfile.TemporaryDirectory() as tmpdir,
            tempfile.TemporaryDirectory() as config_dir,
            tempfile.TemporaryDirectory() as shim_base,
        ):
            real_base = Path(real_base).resolve()
            main_repo = real_base / "mainrepo"
            main_repo.mkdir()
            _git_init(main_repo)

            worktree = real_base / "mainrepo-wt"
            subprocess.run(
                ["git", "worktree", "add", "-q", "-b", "wtbranch", str(worktree)],
                cwd=main_repo,
                check=True,
                env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            )

            # project_root resolves via the marker branch of the walk-up
            # loop (package.json found immediately), independent of
            # repo_root's value.
            sub_proj = worktree / "sub" / "proj"
            sub_proj.mkdir(parents=True)
            (sub_proj / "package.json").write_text("{}")
            (sub_proj / "f.py").write_text("")

            # A plausible alternate alias path for the worktree — not the
            # physical path git or pwd -P would ever report.
            linked_base = real_base.parent / f"linked-{uuid.uuid4().hex[:8]}"
            linked_base.symlink_to(real_base)
            try:
                real_git = shutil.which("git")
                assert real_git is not None, "git must be on PATH to build the shim"

                shim_dir = Path(shim_base)
                alias_worktree = linked_base / "mainrepo-wt"
                _make_git_shim(shim_dir, real_git, str(worktree), str(alias_worktree))

                sid = f"docs-{uuid.uuid4().hex[:8]}"
                file_path = sub_proj / "f.py"

                env = os.environ.copy()
                env["PATH"] = str(shim_dir) + ":" + env.get("PATH", "")
                env["CLAUDE_CODE_TMPDIR"] = tmpdir
                env["CLAUDE_CONFIG_DIR"] = str(config_dir)

                result = subprocess.run(
                    [str(DOCS_CHECK_HOOK)],
                    input=_make_docs_check_input(sid, file_path),
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=6,
                    check=False,
                )

                assert result.returncode == 0
                message = json.loads(result.stdout)["hookSpecificOutput"][
                    "additionalContext"
                ]

                # New code: state_key = main_repo_root + the sub/proj offset,
                # computed via --show-prefix — immune to the shimmed
                # --show-toplevel value.
                reanchored_key = str(main_repo / "sub" / "proj")
                reanchored_fragment = reanchored_key.replace("/", "-").replace(".", "-")
                # Old code: the textual case-match against the shimmed
                # (alias) --show-toplevel value fails, so it falls through
                # to the worktree-local, session-ephemeral key instead.
                worktree_fragment = str(sub_proj).replace("/", "-").replace(".", "-")

                assert reanchored_fragment in message
                assert worktree_fragment not in message
                assert str(alias_worktree) not in message
            finally:
                linked_base.unlink()


# ---------------------------------------------------------------------------
# bash-history-capture.py tests
# ---------------------------------------------------------------------------


def _fake_tool_use_id() -> str:
    return f"toolu_{uuid.uuid4().hex[:12]}"


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
            "tool_use_id": tool_use_id or _fake_tool_use_id(),
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
            fixed_id = _fake_tool_use_id()
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

    def test_captures_failed_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = json.dumps(
                {
                    "session_id": "test-session",
                    "tool_use_id": _fake_tool_use_id(),
                    "cwd": "/tmp",
                    "hook_event_name": "PostToolUseFailure",
                    "tool_input": {
                        "command": "bad-command",
                        "description": "Run bad command",
                    },
                    "error": "command not found: bad-command",
                    "is_interrupt": False,
                    "duration_ms": 42,
                }
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
            assert row["command"] == "bad-command"
            assert row["status"] == "error"
            assert "command not found" in row["output_preview"]
            assert row["hook_event"] == "PostToolUseFailure"
            assert row["duration_ms"] == 42
            assert row["is_interrupt"] == 0

    def test_captures_interrupted_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = json.dumps(
                {
                    "session_id": "test-session",
                    "tool_use_id": _fake_tool_use_id(),
                    "cwd": "/tmp",
                    "hook_event_name": "PostToolUseFailure",
                    "tool_input": {"command": "sleep 999"},
                    "error": "interrupted",
                    "is_interrupt": True,
                    "duration_ms": 1500,
                }
            )
            run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            rows = _query_db(db_path, "SELECT * FROM commands")
            assert len(rows) == 1
            assert rows[0]["is_interrupt"] == 1
            assert rows[0]["duration_ms"] == 1500

    def test_captures_duration_on_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = json.dumps(
                {
                    "session_id": "test-session",
                    "tool_use_id": _fake_tool_use_id(),
                    "cwd": "/tmp",
                    "hook_event_name": "PostToolUse",
                    "tool_input": {"command": "echo hi"},
                    "tool_response": {"stdout": "hi\n"},
                    "duration_ms": 85,
                }
            )
            run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            rows = _query_db(db_path, "SELECT * FROM commands")
            assert len(rows) == 1
            assert rows[0]["hook_event"] == "PostToolUse"
            assert rows[0]["duration_ms"] == 85
            assert rows[0]["is_interrupt"] == 0

    def test_migrates_existing_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            conn = sqlite3.connect(db_path)
            conn.executescript(
                """
                CREATE TABLE commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    session_id TEXT NOT NULL,
                    tool_use_id TEXT NOT NULL UNIQUE,
                    cwd TEXT,
                    transcript_path TEXT,
                    project_slug TEXT,
                    command TEXT NOT NULL,
                    description TEXT,
                    timeout_ms INTEGER,
                    is_background INTEGER NOT NULL DEFAULT 0,
                    status TEXT,
                    output_length INTEGER,
                    output_preview TEXT
                );
                """
            )
            conn.close()
            stdin = _make_bash_history_payload()
            run_hook(
                BASH_HISTORY_HOOK,
                stdin,
                tmpdir,
                extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
            )
            rows = _query_db(
                db_path, "SELECT hook_event, duration_ms, is_interrupt FROM commands"
            )
            assert len(rows) == 1
            assert rows[0]["is_interrupt"] == 0

    def test_skips_non_dict_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            for payload in ["null", "[]", "42", '"a string"']:
                result = run_hook(
                    BASH_HISTORY_HOOK,
                    payload,
                    tmpdir,
                    extra_env={"CLAUDE_BASH_HISTORY_DB": db_path},
                )
                assert result.returncode == 0
            assert not os.path.exists(db_path)

    def test_skips_missing_session_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = json.dumps(
                {
                    "tool_use_id": _fake_tool_use_id(),
                    "tool_input": {"command": "ls"},
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

    def test_skips_missing_tool_use_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            stdin = json.dumps(
                {
                    "session_id": "test-session",
                    "tool_input": {"command": "ls"},
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
