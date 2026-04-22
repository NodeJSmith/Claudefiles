"""Tests for merge-settings hook merging and promotion logic."""

from pathlib import Path
from typing import Any

import pytest

from merge_settings.merge import (
    compute_additions,
    concat_unique,
    load_json,
    merge_hook_entries,
    merger,
    write_json,
)


# ---------------------------------------------------------------------------
# merge_hook_entries
# ---------------------------------------------------------------------------


class TestMergeHookEntries:
    def test_same_matcher_merges_inner_hooks(self) -> None:
        base = [{"hooks": [{"type": "command", "command": "hook-a"}]}]
        nxt = [{"hooks": [{"type": "command", "command": "hook-b"}]}]
        result = merge_hook_entries(base, nxt)
        assert len(result) == 1
        assert len(result[0]["hooks"]) == 2
        cmds = [h["command"] for h in result[0]["hooks"]]
        assert cmds == ["hook-a", "hook-b"]

    def test_different_matchers_kept_separate(self) -> None:
        base = [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "hook-a"}]}
        ]
        nxt = [
            {"matcher": "Edit", "hooks": [{"type": "command", "command": "hook-b"}]}
        ]
        result = merge_hook_entries(base, nxt)
        assert len(result) == 2
        assert result[0]["matcher"] == "Bash"
        assert result[1]["matcher"] == "Edit"

    def test_same_explicit_matcher_merges(self) -> None:
        base = [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "hook-a"}]}
        ]
        nxt = [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "hook-b"}]}
        ]
        result = merge_hook_entries(base, nxt)
        assert len(result) == 1
        assert result[0]["matcher"] == "Bash"
        assert len(result[0]["hooks"]) == 2

    def test_duplicate_inner_hooks_deduplicated(self) -> None:
        hook = {"type": "command", "command": "hook-a"}
        base = [{"hooks": [hook]}]
        nxt = [{"hooks": [hook]}]
        result = merge_hook_entries(base, nxt)
        assert len(result) == 1
        assert len(result[0]["hooks"]) == 1

    def test_preserves_order_base_then_nxt(self) -> None:
        base = [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "a"}]},
            {"matcher": "Edit", "hooks": [{"type": "command", "command": "b"}]},
        ]
        nxt = [
            {"matcher": "Write", "hooks": [{"type": "command", "command": "c"}]},
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "d"}]},
        ]
        result = merge_hook_entries(base, nxt)
        matchers = [e.get("matcher") for e in result]
        assert matchers == ["Bash", "Edit", "Write"]
        bash_cmds = [h["command"] for h in result[0]["hooks"]]
        assert bash_cmds == ["a", "d"]

    def test_no_matcher_and_with_matcher_kept_separate(self) -> None:
        base = [{"hooks": [{"type": "command", "command": "no-matcher"}]}]
        nxt = [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "with-matcher"}],
            }
        ]
        result = merge_hook_entries(base, nxt)
        assert len(result) == 2
        assert result[0].get("matcher") is None
        assert result[1]["matcher"] == "Bash"

    def test_real_scenario_session_start_duplicate(self) -> None:
        """The exact bug: Claudefiles has SessionStart with 6 hooks, machine
        has SessionStart with 1 hook (tmux-remind.sh) that's already in
        Claudefiles.  Should merge into one entry with 6 hooks (deduped)."""
        claudefiles_entry = {
            "hooks": [
                {"type": "command", "command": "uuidgen", "timeout": 2000},
                {"type": "command", "command": "tmux-remind.sh", "timeout": 5000},
                {"type": "command", "command": "cm-memory-setup", "timeout": 10000},
                {"type": "command", "command": "cm-onboarding", "timeout": 10000},
                {"type": "command", "command": "cm-memory-context", "timeout": 10000},
                {
                    "type": "command",
                    "command": "cm-consolidation-check",
                    "timeout": 10000,
                },
            ]
        }
        machine_entry = {
            "hooks": [
                {"type": "command", "command": "tmux-remind.sh", "timeout": 5000},
            ]
        }
        result = merge_hook_entries([claudefiles_entry], [machine_entry])
        assert len(result) == 1
        assert len(result[0]["hooks"]) == 6


# ---------------------------------------------------------------------------
# Full merger integration (hooks path through _list_strategy)
# ---------------------------------------------------------------------------


class TestMergerHooksIntegration:
    def test_merging_two_layers_with_overlapping_session_start(self) -> None:
        layer1 = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "hook-a"}]}
                ]
            }
        }
        layer2 = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {"type": "command", "command": "hook-a"},
                            {"type": "command", "command": "hook-b"},
                        ]
                    }
                ]
            }
        }
        merged: dict[str, Any] = {}
        merger.merge(merged, layer1)
        merger.merge(merged, layer2)
        entries = merged["hooks"]["SessionStart"]
        assert len(entries) == 1
        cmds = [h["command"] for h in entries[0]["hooks"]]
        assert cmds == ["hook-a", "hook-b"]

    def test_merging_preserves_different_hook_types(self) -> None:
        layer1 = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "a"}],
                    }
                ],
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "b"}]}
                ],
            }
        }
        layer2 = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "c"}],
                    }
                ],
            }
        }
        merged: dict[str, Any] = {}
        merger.merge(merged, layer1)
        merger.merge(merged, layer2)
        assert len(merged["hooks"]["PreToolUse"]) == 1
        assert len(merged["hooks"]["PreToolUse"][0]["hooks"]) == 2
        assert len(merged["hooks"]["SessionStart"]) == 1

    def test_three_layer_merge(self) -> None:
        """Simulate the real scenario: Claudefiles + Dotfiles + Machine."""
        claudefiles = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {"type": "command", "command": "a"},
                            {"type": "command", "command": "b"},
                        ]
                    }
                ]
            }
        }
        dotfiles = {
            "hooks": {
                "Notification": [
                    {
                        "matcher": "permission_prompt",
                        "hooks": [{"type": "command", "command": "notify.sh"}],
                    }
                ]
            }
        }
        machine = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "b"}]}
                ]
            }
        }
        merged: dict[str, Any] = {}
        merger.merge(merged, claudefiles)
        merger.merge(merged, dotfiles)
        merger.merge(merged, machine)
        assert len(merged["hooks"]["SessionStart"]) == 1
        assert len(merged["hooks"]["SessionStart"][0]["hooks"]) == 2
        assert len(merged["hooks"]["Notification"]) == 1


# ---------------------------------------------------------------------------
# Promotion: compute_additions with snapshot baseline
# ---------------------------------------------------------------------------


class TestPromotionSnapshot:
    def test_removed_item_not_flagged_when_snapshot_exists(self) -> None:
        """If a hook was in the last merge output and is still in runtime
        settings.json, but was removed from a layer, it should NOT be flagged
        as a runtime addition — the snapshot already accounts for it."""
        removed_hook = {"type": "command", "command": "removed.sh", "timeout": 5000}
        kept_hook = {"type": "command", "command": "kept.sh", "timeout": 5000}

        last_merge = {
            "hooks": {"SessionStart": [{"hooks": [removed_hook, kept_hook]}]}
        }
        runtime = {
            "hooks": {"SessionStart": [{"hooks": [removed_hook, kept_hook]}]}
        }
        additions = compute_additions(runtime, last_merge)
        assert additions == {}

    def test_genuine_runtime_addition_detected(self) -> None:
        last_merge = {"permissions": {"allow": ["Bash(git:*)"]}}
        runtime = {"permissions": {"allow": ["Bash(git:*)", "Bash(docker:*)"]}}
        additions = compute_additions(runtime, last_merge)
        assert additions == {"permissions": {"allow": ["Bash(docker:*)"]}}

    def test_falls_back_to_merged_when_no_snapshot(self) -> None:
        """First run: no snapshot file exists.  The code falls back to the
        freshly merged result as baseline."""
        merged = {"permissions": {"allow": ["Bash(git:*)"]}}
        runtime = {"permissions": {"allow": ["Bash(git:*)"]}}
        additions = compute_additions(runtime, merged)
        assert additions == {}

    def test_snapshot_written_and_used(self, tmp_path: Path) -> None:
        """End-to-end: write a snapshot, simulate a layer removal, and verify
        the removed item is not flagged."""
        snapshot_path = tmp_path / ".settings.last-merge.json"
        output_path = tmp_path / "settings.json"

        hook_a = {"type": "command", "command": "a.sh"}
        hook_b = {"type": "command", "command": "b.sh"}

        first_merge = {"hooks": {"SessionStart": [{"hooks": [hook_a, hook_b]}]}}
        write_json(snapshot_path, first_merge)
        write_json(output_path, first_merge)

        fresh_merge = {"hooks": {"SessionStart": [{"hooks": [hook_a]}]}}

        runtime = load_json(output_path)
        last_merge = load_json(snapshot_path)
        baseline = last_merge if last_merge is not None else fresh_merge

        additions = compute_additions(runtime, baseline)
        assert additions == {}, (
            "hook_b was in the last merge snapshot so it shouldn't be flagged"
        )


# ---------------------------------------------------------------------------
# concat_unique
# ---------------------------------------------------------------------------


class TestConcatUnique:
    def test_deduplicates_strings(self) -> None:
        assert concat_unique(["a", "b"], ["b", "c"]) == ["a", "b", "c"]

    def test_deduplicates_dicts(self) -> None:
        d = {"x": 1}
        assert concat_unique([d], [d, {"y": 2}]) == [d, {"y": 2}]

    def test_preserves_order(self) -> None:
        assert concat_unique(["c", "a"], ["b", "a"]) == ["c", "a", "b"]


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------


class TestLoadJson:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert load_json(tmp_path / "nope.json") is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.json"
        p.write_text("")
        assert load_json(p) is None

    def test_valid_dict(self, tmp_path: Path) -> None:
        p = tmp_path / "ok.json"
        p.write_text('{"a": 1}')
        assert load_json(p) == {"a": 1}

    def test_invalid_json_raises_value_error(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{bad json}")
        with pytest.raises(ValueError, match="invalid JSON"):
            load_json(p)

    def test_non_dict_json_raises_value_error(self, tmp_path: Path) -> None:
        p = tmp_path / "list.json"
        p.write_text("[1, 2, 3]")
        with pytest.raises(ValueError, match="must contain a JSON object"):
            load_json(p)
