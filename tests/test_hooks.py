"""Integration tests for hook scripts (pytest-guard, context-tier, tmux-drift, compaction).

Each test crafts JSON input matching the PreToolUse/PostToolUse schema, invokes
the hook via subprocess.run, and asserts on exit code and stdout.
"""

import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

# Resolve hook paths relative to the repo root
REPO_ROOT = Path(__file__).parent.parent
COMPACTION_HOOK = REPO_ROOT / "scripts" / "hooks" / "subagent-compaction-check.sh"
GUARD_HOOK = REPO_ROOT / "scripts" / "hooks" / "pytest-guard.sh"


def run_hook(
    script: Path,
    stdin: str,
    tmpdir: str,
    extra_env: dict | None = None,
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
    )


# ---------------------------------------------------------------------------
# context-tier.sh tests
# ---------------------------------------------------------------------------

CONTEXT_TIER_HOOK = REPO_ROOT / "scripts" / "hooks" / "context-tier.sh"


def _context_tier_session_id(test_name: str) -> str:
    """Generate a unique session ID for a context-tier test to avoid cross-talk."""
    return f"ct-test-{test_name}-{uuid.uuid4().hex[:8]}"


def _write_sidecar(session_id: str, percent: str) -> Path:
    """Write the sidecar file that claude-context-writer would produce."""
    p = Path(f"/tmp/claude-context-{session_id}.txt")
    p.write_text(percent)
    return p


def _read_tier(session_id: str) -> str | None:
    """Read the tier state file; returns None if absent."""
    p = Path(f"/tmp/claude-context-tier-{session_id}.txt")
    if not p.exists():
        return None
    return p.read_text().strip()


def _write_tier(session_id: str, tier: str) -> Path:
    """Pre-seed the tier state file to simulate a prior call."""
    p = Path(f"/tmp/claude-context-tier-{session_id}.txt")
    p.write_text(tier)
    return p


def _cleanup_context_tier(session_id: str) -> None:
    """Remove sidecar, tier, and counter files for a session."""
    for pattern in (
        f"/tmp/claude-context-{session_id}.txt",
        f"/tmp/claude-context-tier-{session_id}.txt",
        f"/tmp/claude-context-calls-{session_id}.txt",
    ):
        p = Path(pattern)
        if p.exists():
            p.unlink()


def _write_counter(session_id: str, count: int) -> Path:
    """Pre-seed the heartbeat counter file."""
    p = Path(f"/tmp/claude-context-calls-{session_id}.txt")
    p.write_text(str(count))
    return p


def _read_counter(session_id: str) -> int | None:
    """Read the heartbeat counter; returns None if absent."""
    p = Path(f"/tmp/claude-context-calls-{session_id}.txt")
    if not p.exists():
        return None
    text = p.read_text().strip()
    return int(text) if text else None


def _make_context_tier_input(session_id: str) -> str:
    """Build JSON stdin for the context-tier hook."""
    return json.dumps({"session_id": session_id})


def _run_context_tier(
    session_id: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run the context-tier hook with the given session_id."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(CONTEXT_TIER_HOOK)],
        input=_make_context_tier_input(session_id),
        capture_output=True,
        text=True,
        env=env,
    )


class TestContextTierFirstCallEmits:
    """First call (no prior tier state) emits a tier message."""

    def test_context_tier_first_call_emits_low(self):
        sid = _context_tier_session_id("first_low")
        try:
            _write_sidecar(sid, "10")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "low usage (10%)" in result.stdout
            assert _read_tier(sid) == "low"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_first_call_emits_critical(self):
        sid = _context_tier_session_id("first_crit")
        try:
            _write_sidecar(sid, "90")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "critical usage (90%)" in result.stdout
            assert _read_tier(sid) == "critical"
        finally:
            _cleanup_context_tier(sid)


class TestContextTierSameTierSuppressed:
    """Repeat call at the same tier is suppressed (until heartbeat threshold)."""

    def test_context_tier_same_tier_silent(self):
        sid = _context_tier_session_id("same_tier")
        try:
            _write_sidecar(sid, "15")
            _write_tier(sid, "low")  # already at low

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_same_tier_moderate_silent(self):
        sid = _context_tier_session_id("same_mod")
        try:
            _write_sidecar(sid, "50")
            _write_tier(sid, "moderate")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)


class TestContextTierTransitionEmits:
    """Tier change emits a new message and updates the state file."""

    def test_context_tier_low_to_low_mid(self):
        sid = _context_tier_session_id("low_lowmid")
        try:
            _write_sidecar(sid, "30")
            _write_tier(sid, "low")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "Plenty of room" in result.stdout
            assert _read_tier(sid) == "low-mid"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_low_mid_to_moderate(self):
        sid = _context_tier_session_id("lowmid_mod")
        try:
            _write_sidecar(sid, "45")
            _write_tier(sid, "low-mid")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "moderate usage (45%)" in result.stdout
            assert _read_tier(sid) == "moderate"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_moderate_to_high(self):
        sid = _context_tier_session_id("mod_high")
        try:
            _write_sidecar(sid, "70")
            _write_tier(sid, "moderate")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "high usage (70%)" in result.stdout
            assert _read_tier(sid) == "high"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_high_to_critical(self):
        sid = _context_tier_session_id("high_crit")
        try:
            _write_sidecar(sid, "85")
            _write_tier(sid, "high")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "critical usage (85%)" in result.stdout
            assert _read_tier(sid) == "critical"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_full_escalation_sequence(self):
        """Walk through all five tiers in sequence."""
        sid = _context_tier_session_id("full_seq")
        try:
            # low (first call)
            _write_sidecar(sid, "5")
            result = _run_context_tier(sid)
            assert "low usage (5%)" in result.stdout
            assert _read_tier(sid) == "low"

            # low → low-mid
            _write_sidecar(sid, "30")
            result = _run_context_tier(sid)
            assert "Plenty of room" in result.stdout
            assert _read_tier(sid) == "low-mid"

            # low-mid → moderate
            _write_sidecar(sid, "50")
            result = _run_context_tier(sid)
            assert "moderate usage (50%)" in result.stdout
            assert _read_tier(sid) == "moderate"

            # moderate → high
            _write_sidecar(sid, "65")
            result = _run_context_tier(sid)
            assert "high usage (65%)" in result.stdout
            assert _read_tier(sid) == "high"

            # high → critical
            _write_sidecar(sid, "80")
            result = _run_context_tier(sid)
            assert "critical usage (80%)" in result.stdout
            assert _read_tier(sid) == "critical"
        finally:
            _cleanup_context_tier(sid)


class TestContextTierMissingSidecar:
    """Missing sidecar file is a no-op."""

    def test_context_tier_missing_sidecar_exits_zero(self):
        sid = _context_tier_session_id("no_sidecar")
        try:
            # Do NOT create a sidecar file
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)


class TestContextTierInvalidSidecar:
    """Invalid or non-numeric sidecar content is a no-op."""

    def test_context_tier_empty_sidecar(self):
        sid = _context_tier_session_id("empty_sc")
        try:
            _write_sidecar(sid, "")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_non_numeric_sidecar(self):
        sid = _context_tier_session_id("nonnumeric")
        try:
            _write_sidecar(sid, "abc")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_negative_number_sidecar(self):
        sid = _context_tier_session_id("negative")
        try:
            _write_sidecar(sid, "-5")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_float_sidecar(self):
        sid = _context_tier_session_id("float")
        try:
            _write_sidecar(sid, "42.5")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)


class TestContextTierHeartbeat:
    """Heartbeat re-injects the message every N calls even without a tier change."""

    def test_heartbeat_fires_at_threshold(self):
        sid = _context_tier_session_id("hb_fire")
        try:
            _write_sidecar(sid, "15")
            # First call emits (tier change from empty → low), resets counter to 0
            result = _run_context_tier(sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "5"})
            assert "low usage (15%)" in result.stdout

            # Calls 2-5: suppressed (counter 1-4)
            for _ in range(4):
                result = _run_context_tier(
                    sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "5"}
                )
                assert result.stdout.strip() == ""

            # Call 6: heartbeat fires (counter hits 5)
            result = _run_context_tier(sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "5"})
            assert "low usage (15%)" in result.stdout
            assert _read_counter(sid) == 0
        finally:
            _cleanup_context_tier(sid)

    def test_tier_change_resets_counter(self):
        sid = _context_tier_session_id("hb_reset")
        try:
            _write_sidecar(sid, "15")
            _write_tier(sid, "low")
            _write_counter(sid, 20)

            # Tier change (low → moderate) should emit and reset counter
            _write_sidecar(sid, "45")
            result = _run_context_tier(sid)
            assert "moderate usage (45%)" in result.stdout
            assert _read_counter(sid) == 0
        finally:
            _cleanup_context_tier(sid)

    def test_non_numeric_env_falls_back_to_default(self):
        sid = _context_tier_session_id("hb_badenv")
        try:
            _write_sidecar(sid, "15")
            _write_tier(sid, "low")
            _write_counter(sid, 23)

            # With bad env, interval falls back to 25; counter 23+1=24 < 25
            result = _run_context_tier(
                sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "off"}
            )
            assert result.stdout.strip() == ""
            assert _read_counter(sid) == 24
        finally:
            _cleanup_context_tier(sid)

    def test_zero_env_falls_back_to_default(self):
        sid = _context_tier_session_id("hb_zero")
        try:
            _write_sidecar(sid, "15")
            _write_tier(sid, "low")
            _write_counter(sid, 23)

            result = _run_context_tier(sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "0"})
            assert result.stdout.strip() == ""
            assert _read_counter(sid) == 24
        finally:
            _cleanup_context_tier(sid)


class TestContextTierMissingSessionId:
    """Missing session_id in input is a no-op."""

    def test_context_tier_no_session_id_field(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"tool_name": "Bash"}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_empty_session_id(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"session_id": ""}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestContextTierPathTraversal:
    """Session IDs with path traversal characters are rejected."""

    def test_context_tier_slash_in_session_id(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"session_id": "../etc/passwd"}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_dot_in_session_id(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"session_id": "foo.bar"}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_dotdot_in_session_id(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"session_id": ".."}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""


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
# pytest-guard.sh escape-hatch tests
# ---------------------------------------------------------------------------


def _guard_input(command: str) -> str:
    """Build a PreToolUse JSON payload for the pytest guard (cwd avoids per-repo config)."""
    return json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/tmp"}
    )


def _guard_decision(result: subprocess.CompletedProcess) -> str | None:
    """The permissionDecision from a deny, or None if the hook passed silently."""
    out = result.stdout.strip()
    if not out:
        return None
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


class TestPytestGuardOverride:
    """PYTEST_GUARD_OFF="reason" prefix opts out of the timeout requirement."""

    def test_valid_reason_allows_bare_pytest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = _guard_input('PYTEST_GUARD_OFF="under a debugger" pytest tests/')
            result = run_hook(GUARD_HOOK, inp, tmpdir)
            assert result.returncode == 0
            assert _guard_decision(result) is None
            # the reason is echoed to stderr so the bypass stays auditable
            assert "under a debugger" in result.stderr

    def test_single_quoted_reason_allows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = _guard_input("PYTEST_GUARD_OFF='under a debugger' pytest tests/")
            result = run_hook(GUARD_HOOK, inp, tmpdir)
            assert _guard_decision(result) is None
            assert "under a debugger" in result.stderr

    def test_bare_word_reason_allows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = _guard_input("PYTEST_GUARD_OFF=ci pytest tests/")
            result = run_hook(GUARD_HOOK, inp, tmpdir)
            assert _guard_decision(result) is None
            assert "ci" in result.stderr

    def test_empty_reason_denied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = _guard_input('PYTEST_GUARD_OFF="" pytest tests/')
            result = run_hook(GUARD_HOOK, inp, tmpdir)
            assert _guard_decision(result) == "deny"

    def test_placeholder_reason_denied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = _guard_input('PYTEST_GUARD_OFF="<reason>" pytest tests/')
            result = run_hook(GUARD_HOOK, inp, tmpdir)
            assert _guard_decision(result) == "deny"

    def test_timeout_deny_advertises_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = _guard_input("pytest tests/")
            result = run_hook(GUARD_HOOK, inp, tmpdir)
            reason = json.loads(result.stdout)["hookSpecificOutput"][
                "permissionDecisionReason"
            ]
            assert "PYTEST_GUARD_OFF" in reason
