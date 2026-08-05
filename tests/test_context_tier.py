"""Integration tests for the context-tier.sh PreToolUse hook and its producer,
claude-context-writer (statusLine).

Each test crafts JSON input matching the PreToolUse/statusLine schema, invokes
the script via subprocess.run, and asserts on exit code and stdout. The
consumer hook reads a sidecar file written by the producer and emits tier
guidance when the tier changes or a heartbeat fires.
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

# Resolve hook paths relative to the repo root
REPO_ROOT = Path(__file__).parent.parent
CONTEXT_TIER_HOOK = REPO_ROOT / "scripts" / "hooks" / "context-tier.sh"
CONTEXT_WRITER = REPO_ROOT / "scripts" / "hooks" / "claude-context-writer"


def _context_tier_session_id(test_name: str) -> str:
    """Generate a unique session ID for a context-tier test to avoid cross-talk."""
    return f"ct-test-{test_name}-{uuid.uuid4().hex[:8]}"


def _write_sidecar(session_id: str, percent: str) -> Path:
    """Write the .meta sidecar that claude-context-writer would produce.

    `percent` is embedded verbatim as the pct= value, so the invalid-content
    tests (e.g. "-5", "42.5", "") exercise the hook's numeric guard the same
    way a real garbled sidecar would.
    """
    p = Path(f"/tmp/claude-context-{session_id}.meta")
    p.write_text(f"pct={percent}\ncwd=/home/jessica/work\n")
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
        f"/tmp/claude-context-{session_id}.meta",
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
    timeout: int = 5,
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
        timeout=timeout,
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
    """A .meta whose pct= value is empty or non-numeric is a no-op."""

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

    def test_context_tier_heartbeat_fires_at_threshold(self):
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

    def test_context_tier_heartbeat_resets_on_tier_change(self):
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

    def test_context_tier_heartbeat_non_numeric_env_falls_back_to_default(self):
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

    def test_context_tier_heartbeat_zero_env_falls_back_to_default(self):
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
            timeout=5,
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_empty_session_id(self):
        result = _run_context_tier("")

        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestContextTierPathTraversal:
    """Session IDs with path traversal characters are rejected."""

    def test_context_tier_slash_in_session_id(self):
        result = _run_context_tier("../etc/passwd")

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_dot_in_session_id(self):
        result = _run_context_tier("foo.bar")

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_dotdot_in_session_id(self):
        result = _run_context_tier("..")

        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestContextTierMalformedMeta:
    """A pct-less or garbled .meta is a no-op; a cwd with '=' doesn't corrupt the pct parse."""

    def test_context_tier_meta_without_pct_line(self):
        sid = _context_tier_session_id("no_pct")
        try:
            Path(f"/tmp/claude-context-{sid}.meta").write_text(
                "cwd=/home/jessica/work\n"
            )
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_garbage_meta(self):
        sid = _context_tier_session_id("garbage")
        try:
            Path(f"/tmp/claude-context-{sid}.meta").write_text(
                "not a valid sidecar at all\n"
            )
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_cwd_with_equals_preserves_pct(self):
        """A cwd path containing '=' must not corrupt the anchored pct extraction."""
        sid = _context_tier_session_id("cwd_eq")
        try:
            Path(f"/tmp/claude-context-{sid}.meta").write_text(
                "pct=50\ncwd=/home/jessica/a=b/work\n"
            )
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "moderate usage (50%)" in result.stdout
            assert _read_tier(sid) == "moderate"
        finally:
            _cleanup_context_tier(sid)


class TestContextWriterProducer:
    """claude-context-writer writes only the .meta sidecar — never the legacy .txt (AC#1)."""

    def test_context_writer_writes_meta_not_txt(self):
        sid = _context_tier_session_id("producer")
        try:
            payload = json.dumps(
                {
                    "session_id": sid,
                    "context_window": {
                        "current_usage": {
                            "input_tokens": 10000,
                            "cache_creation_input_tokens": 5000,
                            "cache_read_input_tokens": 5000,
                        },
                        "context_window_size": 200000,
                    },
                    "workspace": {"current_dir": "/home/jessica/work"},
                }
            )
            result = subprocess.run(
                [str(CONTEXT_WRITER)],
                input=payload,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
                timeout=5,
            )

            assert result.returncode == 0
            meta = Path(f"/tmp/claude-context-{sid}.meta")
            txt = Path(f"/tmp/claude-context-{sid}.txt")
            assert meta.exists()
            content = meta.read_text()
            assert "pct=10\n" in content  # 20000 / 200000 = 10%
            assert "cwd=/home/jessica/work" in content
            assert not txt.exists()
        finally:
            _cleanup_context_tier(sid)
