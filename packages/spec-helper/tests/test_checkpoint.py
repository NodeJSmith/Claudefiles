"""Tests for checkpoint module — visual_mode and current_wp_status handling."""

from pathlib import Path

import pytest

from typing import Any

from spec_helper.checkpoint import (
    CHECKPOINT_VERSION,
    VALID_CURRENT_WP_STATUSES,
    VALID_VISUAL_MODES,
    CheckpointState,
    Verdict,
    add_verdict,
    read_checkpoint,
    state_to_dict,
    update_header,
    write_checkpoint,
)


@pytest.fixture
def checkpoint_dir(tmp_path: Path) -> Path:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    return tasks


def _make_state(**overrides: Any) -> CheckpointState:
    defaults: dict[str, Any] = {
        "feature_dir": "design/specs/001-test",
        "tmpdir": "/tmp/claude-test",
        "visual_mode": "enabled",
        "dev_server_url": "http://localhost:3000",
        "last_completed_wp": "none",
        "started_at": "2026-04-06T10:00:00Z",
        "base_commit": "abc1234",
    }
    defaults.update(overrides)
    return CheckpointState(**defaults)


class TestVisualMode:
    """visual_mode is a tri-state string, not a boolean."""

    @pytest.mark.parametrize("mode", sorted(VALID_VISUAL_MODES))
    def test_round_trip_all_modes(self, checkpoint_dir: Path, mode: str) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(visual_mode=mode)
        write_checkpoint(state, path)
        restored = read_checkpoint(path)
        assert restored.visual_mode == mode

    def test_state_to_dict_uses_visual_mode_key(self) -> None:
        state = _make_state(visual_mode="skipped_no_server")
        d = state_to_dict(state)
        assert "visual_mode" in d
        assert "visual_skip" not in d
        assert d["visual_mode"] == "skipped_no_server"

    def test_invalid_visual_mode_rejected(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(visual_mode="enabled")
        write_checkpoint(state, path)
        # Manually corrupt the file
        text = path.read_text().replace("visual_mode: enabled", "visual_mode: bogus")
        path.write_text(text)
        with pytest.raises(ValueError, match="Invalid visual_mode"):
            read_checkpoint(path)

    def test_update_visual_mode(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(visual_mode="enabled")
        write_checkpoint(state, path)
        update_header(path, visual_mode="skipped_no_server")
        restored = read_checkpoint(path)
        assert restored.visual_mode == "skipped_no_server"


class TestCurrentWpStatus:
    """current_wp_status accepts executing and warn_retry in addition to original values."""

    @pytest.mark.parametrize("status", sorted(VALID_CURRENT_WP_STATUSES))
    def test_round_trip_all_statuses(self, checkpoint_dir: Path, status: str) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp="WP01", current_wp_status=status)
        write_checkpoint(state, path)
        restored = read_checkpoint(path)
        assert restored.current_wp_status == status

    def test_executing_status(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state()
        write_checkpoint(state, path)
        update_header(path, current_wp="WP01", current_wp_status="executing")
        restored = read_checkpoint(path)
        assert restored.current_wp_status == "executing"

    def test_warn_retry_status(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state()
        write_checkpoint(state, path)
        update_header(path, current_wp="WP01", current_wp_status="warn_retry")
        restored = read_checkpoint(path)
        assert restored.current_wp_status == "warn_retry"

    def test_clear_status(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp="WP01", current_wp_status="executing")
        write_checkpoint(state, path)
        update_header(path, current_wp="", current_wp_status="")
        restored = read_checkpoint(path)
        assert restored.current_wp == ""
        assert restored.current_wp_status == ""


class TestCheckpointRoundTrip:
    """Full checkpoint write → read preserves all fields."""

    def test_full_round_trip(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(
            visual_mode="skipped_no_vision",
            current_wp="WP03",
            current_wp_status="blocked",
        )
        write_checkpoint(state, path)
        restored = read_checkpoint(path)
        assert restored.feature_dir == state.feature_dir
        assert restored.tmpdir == state.tmpdir
        assert restored.visual_mode == state.visual_mode
        assert restored.dev_server_url == state.dev_server_url
        assert restored.base_commit == state.base_commit
        assert restored.current_wp == state.current_wp
        assert restored.current_wp_status == state.current_wp_status


class TestLegacyCheckpointVersion:
    """Old checkpoints with visual_skip are rejected with a version error."""

    def test_legacy_visual_skip_rejected(self, checkpoint_dir: Path) -> None:
        """A v1 checkpoint with visual_skip instead of visual_mode fails on read."""
        path = checkpoint_dir / ".orchestrate-state.md"
        path.write_text(
            "# Orchestration State\n\n"
            "version: 1\n"
            "feature_dir: design/specs/001-test\n"
            "tmpdir: /tmp/test\n"
            "visual_skip: false\n"
            "dev_server_url: none\n"
            "last_completed_wp: none\n"
            "started_at: 2026-04-06T10:00:00Z\n"
            "base_commit: abc1234\n\n"
            "## Verdicts\n"
        )
        with pytest.raises(ValueError, match="missing required fields.*visual_mode"):
            read_checkpoint(path)

    def test_version_bump_prevents_old_format(self) -> None:
        """CHECKPOINT_VERSION is 2, signaling the visual_skip→visual_mode break."""
        assert CHECKPOINT_VERSION == 2


class TestWriteValidation:
    """write_checkpoint validates state before persisting."""

    def test_invalid_visual_mode_rejected_on_write(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(visual_mode="bogus")
        with pytest.raises(ValueError, match="Invalid visual_mode"):
            write_checkpoint(state, path)

    def test_invalid_status_rejected_on_write(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp="WP01", current_wp_status="invalid")
        with pytest.raises(ValueError, match="Invalid current_wp_status"):
            write_checkpoint(state, path)

    def test_status_without_wp_rejected_on_write(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp_status="executing")
        with pytest.raises(ValueError, match="current_wp_status requires current_wp"):
            write_checkpoint(state, path)

    def test_invalid_visual_mode_via_update_header(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        write_checkpoint(_make_state(), path)
        with pytest.raises(ValueError, match="Invalid visual_mode"):
            update_header(path, visual_mode="bogus")

    def test_status_without_wp_via_update_header(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        write_checkpoint(_make_state(), path)
        with pytest.raises(ValueError, match="current_wp_status requires current_wp"):
            update_header(path, current_wp_status="executing")

    def test_clear_status_omits_fields_from_file(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp="WP01", current_wp_status="executing")
        write_checkpoint(state, path)
        update_header(path, current_wp="", current_wp_status="")
        text = path.read_text()
        assert "current_wp:" not in text
        assert "current_wp_status:" not in text

    def test_empty_visual_mode_rejected_on_read(self, checkpoint_dir: Path) -> None:
        """An empty visual_mode value should not pass validation."""
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state()
        write_checkpoint(state, path)
        text = path.read_text().replace("visual_mode: enabled", "visual_mode: ")
        path.write_text(text)
        with pytest.raises(ValueError, match="Invalid visual_mode"):
            read_checkpoint(path)


class TestAddVerdict:
    """add_verdict round-trip, duplicate detection, and validation."""

    def test_add_verdict_round_trip(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp="WP01", current_wp_status="executing")
        write_checkpoint(state, path)
        verdict = Verdict(
            wp_id="WP01", title="Set up model", verdict="PASS", commit="abc123"
        )
        add_verdict(path, verdict)
        restored = read_checkpoint(path)
        assert len(restored.verdicts) == 1
        assert restored.verdicts[0].wp_id == "WP01"
        assert restored.verdicts[0].verdict == "PASS"

    def test_add_verdict_duplicate_raises(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp="WP01", current_wp_status="executing")
        write_checkpoint(state, path)
        verdict = Verdict(
            wp_id="WP01", title="Set up model", verdict="PASS", commit="abc123"
        )
        add_verdict(path, verdict)
        with pytest.raises(ValueError, match="already exists"):
            add_verdict(path, verdict)

    def test_add_verdict_missing_checkpoint_raises(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        verdict = Verdict(wp_id="WP01", title="Test", verdict="PASS", commit="abc123")
        with pytest.raises(FileNotFoundError):
            add_verdict(path, verdict)

    def test_empty_commit_rejected(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp="WP01", current_wp_status="executing")
        write_checkpoint(state, path)
        verdict = Verdict(wp_id="WP01", title="Test", verdict="PASS", commit="")
        with pytest.raises(ValueError, match="commit field is required"):
            add_verdict(path, verdict)


class TestMalformedVerdictBlock:
    """Malformed verdict blocks raise instead of being silently dropped."""

    def test_malformed_title_raises(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state()
        write_checkpoint(state, path)
        text = path.read_text() + "\n### GARBAGE LINE\nverdict: PASS\ncommit: abc\n"
        path.write_text(text)
        with pytest.raises(ValueError, match="Malformed verdict block header"):
            read_checkpoint(path)


class TestImmutableFields:
    """Immutable fields cannot be changed via update_header."""

    def test_version_immutable(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        write_checkpoint(_make_state(), path)
        with pytest.raises(ValueError, match="immutable"):
            update_header(path, version=1)

    def test_feature_dir_immutable(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        write_checkpoint(_make_state(), path)
        with pytest.raises(ValueError, match="immutable"):
            update_header(path, feature_dir="other")


class TestAutoClearStatus:
    """Clearing current_wp auto-clears current_wp_status."""

    def test_clear_wp_alone_auto_clears_status(self, checkpoint_dir: Path) -> None:
        path = checkpoint_dir / ".orchestrate-state.md"
        state = _make_state(current_wp="WP01", current_wp_status="executing")
        write_checkpoint(state, path)
        update_header(path, current_wp="")
        restored = read_checkpoint(path)
        assert restored.current_wp == ""
        assert restored.current_wp_status == ""

    def test_wp_requires_status(self, checkpoint_dir: Path) -> None:
        """Setting current_wp without current_wp_status raises."""
        path = checkpoint_dir / ".orchestrate-state.md"
        write_checkpoint(_make_state(), path)
        with pytest.raises(ValueError, match="current_wp requires current_wp_status"):
            update_header(path, current_wp="WP01")
