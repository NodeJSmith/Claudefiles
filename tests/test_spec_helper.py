"""Tests for bin/spec-helper — validation and normalization functions."""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import frontmatter
import pytest

# ---------------------------------------------------------------------------
# Import spec-helper as a module (it's a script without .py extension)
# ---------------------------------------------------------------------------

_BIN = Path(__file__).resolve().parent.parent / "bin" / "spec-helper"
_loader = importlib.machinery.SourceFileLoader("spec_helper", str(_BIN))
_spec = importlib.util.spec_from_loader("spec_helper", _loader)
assert _spec and _spec.loader
spec_helper = importlib.util.module_from_spec(_spec)
sys.modules["spec_helper"] = spec_helper
_spec.loader.exec_module(spec_helper)


# ===================================================================
# validate_wp_metadata
# ===================================================================


class TestValidateWpMetadataValid:
    """Canonical schema passes with empty error list."""

    def test_valid_metadata_returns_no_errors(self):
        meta = {
            "work_package_id": "WP01",
            "title": "Some title",
            "lane": "planned",
            "depends_on": [],
        }
        errors = spec_helper.validate_wp_metadata(meta, "WP01.md")
        assert errors == []

    def test_valid_with_dependencies(self):
        meta = {
            "work_package_id": "WP03",
            "title": "Some title",
            "lane": "doing",
            "depends_on": ["WP01", "WP02"],
        }
        errors = spec_helper.validate_wp_metadata(meta, "WP03.md")
        assert errors == []

    def test_valid_all_lanes(self):
        for lane in ("planned", "doing", "for_review", "done"):
            meta = {
                "work_package_id": "WP01",
                "title": "T",
                "lane": lane,
                "depends_on": [],
            }
            assert spec_helper.validate_wp_metadata(meta, "WP01.md") == []


class TestValidateWpMetadataInvalidWpId:
    """Bad ID produces error."""

    def test_missing_wp_id(self):
        meta = {"title": "T", "lane": "planned", "depends_on": []}
        errors = spec_helper.validate_wp_metadata(meta, "WP01.md")
        assert any("work_package_id" in e for e in errors)

    def test_empty_wp_id(self):
        meta = {"work_package_id": "", "title": "T", "lane": "planned", "depends_on": []}
        errors = spec_helper.validate_wp_metadata(meta, "WP01.md")
        assert any("work_package_id" in e for e in errors)

    def test_bad_format_wp_id(self):
        meta = {"work_package_id": "wp1", "title": "T", "lane": "planned", "depends_on": []}
        errors = spec_helper.validate_wp_metadata(meta, "WP01.md")
        assert any("work_package_id" in e for e in errors)


class TestValidateWpMetadataInvalidLane:
    """Unrecognized lane produces error."""

    def test_invalid_lane(self):
        meta = {"work_package_id": "WP01", "title": "T", "lane": "in_progress", "depends_on": []}
        errors = spec_helper.validate_wp_metadata(meta, "WP01.md")
        assert any("lane" in e.lower() for e in errors)


class TestValidateWpMetadataInvalidDependency:
    """Malformed dep produces error."""

    def test_bad_dependency_format(self):
        meta = {"work_package_id": "WP01", "title": "T", "lane": "planned", "depends_on": ["bad"]}
        errors = spec_helper.validate_wp_metadata(meta, "WP01.md")
        assert any("dependency" in e.lower() for e in errors)


class TestValidateWpMetadataMissingTitle:
    """Empty/missing title produces error."""

    def test_missing_title(self):
        meta = {"work_package_id": "WP01", "lane": "planned", "depends_on": []}
        errors = spec_helper.validate_wp_metadata(meta, "WP01.md")
        assert any("title" in e.lower() for e in errors)

    def test_empty_title(self):
        meta = {"work_package_id": "WP01", "title": "", "lane": "planned", "depends_on": []}
        errors = spec_helper.validate_wp_metadata(meta, "WP01.md")
        assert any("title" in e.lower() for e in errors)


# ===================================================================
# normalize_wp_metadata
# ===================================================================


class TestNormalizeDependsString:
    """depends: WP02 becomes depends_on: ["WP02"]."""

    def test_string_dep_becomes_list(self):
        raw = {"depends": "WP02", "title": "T", "lane": "planned"}
        result = spec_helper.normalize_wp_metadata(raw, "WP01.md")
        assert result["depends_on"] == ["WP02"]
        assert "depends" not in result


class TestNormalizeDependsList:
    """depends: ["WP01"] becomes depends_on: ["WP01"]."""

    def test_list_dep_stays_list(self):
        raw = {"depends": ["WP01"], "title": "T", "lane": "planned"}
        result = spec_helper.normalize_wp_metadata(raw, "WP01.md")
        assert result["depends_on"] == ["WP01"]
        assert "depends" not in result


class TestNormalizeDependsEmpty:
    """depends: (empty) becomes depends_on: []."""

    def test_empty_dep_becomes_empty_list(self):
        raw = {"depends": None, "title": "T", "lane": "planned"}
        result = spec_helper.normalize_wp_metadata(raw, "WP01.md")
        assert result["depends_on"] == []
        assert "depends" not in result

    def test_empty_string_dep_becomes_empty_list(self):
        raw = {"depends": "", "title": "T", "lane": "planned"}
        result = spec_helper.normalize_wp_metadata(raw, "WP01.md")
        assert result["depends_on"] == []
        assert "depends" not in result


class TestNormalizeMissingWpId:
    """Derives from filename WP03.md -> work_package_id: "WP03"."""

    def test_derives_wp_id_from_filename(self):
        raw = {"title": "T", "lane": "planned", "depends_on": []}
        result = spec_helper.normalize_wp_metadata(raw, "WP03.md")
        assert result["work_package_id"] == "WP03"

    def test_does_not_override_existing_wp_id(self):
        raw = {"work_package_id": "WP05", "title": "T", "lane": "planned", "depends_on": []}
        result = spec_helper.normalize_wp_metadata(raw, "WP03.md")
        assert result["work_package_id"] == "WP05"


class TestNormalizePreservesUnknownFields:
    """issue field survives normalization."""

    def test_unknown_field_preserved(self):
        raw = {
            "work_package_id": "WP01",
            "title": "T",
            "lane": "done",
            "depends_on": [],
            "issue": "#117",
        }
        result = spec_helper.normalize_wp_metadata(raw, "WP01.md")
        assert result["issue"] == "#117"

    def test_depends_normalization_preserves_issue(self):
        raw = {
            "title": "T",
            "lane": "done",
            "depends": "WP02",
            "issue": "#117",
        }
        result = spec_helper.normalize_wp_metadata(raw, "WP01.md")
        assert result["issue"] == "#117"
        assert result["depends_on"] == ["WP02"]


# ===================================================================
# Round-trip: load -> modify -> dump -> reload
# ===================================================================


# ===================================================================
# find_repo_root
# ===================================================================


class TestFindRepoRootWithGitAndSpecs:
    """Returns correct root when both .git and design/specs/ exist."""

    def test_finds_root_with_git_and_specs(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        result = spec_helper.find_repo_root()
        assert result == tmp_path

    def test_finds_root_from_subdirectory(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        sub = tmp_path / "a" / "b" / "c"
        sub.mkdir(parents=True)
        monkeypatch.chdir(sub)
        result = spec_helper.find_repo_root()
        assert result == tmp_path


class TestFindRepoRootNoGitDies:
    """Dies when no .git in ancestry."""

    def test_no_git_dies(self, tmp_path, monkeypatch):
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            spec_helper.find_repo_root()


# ===================================================================
# list_features — digit width
# ===================================================================


# ===================================================================
# Slug sanitization
# ===================================================================


class TestSlugSanitizationDoubleHyphens:
    """Double hyphens are collapsed to single."""

    def test_double_hyphens_collapsed(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="auth--flow", json=False)
        spec_helper.cmd_init(args)

        created = list((tmp_path / "design" / "specs").iterdir())
        assert len(created) == 1
        assert created[0].name == "001-auth-flow"


class TestSlugSanitizationTrailingHyphen:
    """Trailing hyphens are stripped."""

    def test_trailing_hyphen_stripped(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="auth-", json=False)
        spec_helper.cmd_init(args)

        created = list((tmp_path / "design" / "specs").iterdir())
        assert len(created) == 1
        assert created[0].name == "001-auth"


class TestListFeaturesAnyDigitWidth:
    """Recognizes directories with any digit-width prefix."""

    def test_any_digit_width(self, tmp_path):
        sd = tmp_path / "design" / "specs"
        sd.mkdir(parents=True)
        (sd / "01-foo").mkdir()
        (sd / "001-bar").mkdir()
        (sd / "1000-baz").mkdir()
        (sd / "not-a-feature").mkdir()  # should be excluded

        features = spec_helper.list_features(tmp_path)
        names = [f.name for f in features]
        assert "01-foo" in names
        assert "001-bar" in names
        assert "1000-baz" in names
        assert "not-a-feature" not in names
        assert len(names) == 3


# ===================================================================
# --auto flag (find_feature_dir)
# ===================================================================


class TestFindFeatureDirAuto:
    """--auto returns the most recently modified feature directory."""

    def test_auto_returns_most_recent(self, tmp_path):
        import time

        sd = tmp_path / "design" / "specs"
        sd.mkdir(parents=True)

        # Create two features with different modification times
        old = sd / "001-old-feature"
        old.mkdir()
        (old / "spec.md").write_text("old")

        # Ensure measurable time gap
        time.sleep(0.05)

        new = sd / "002-new-feature"
        new.mkdir()
        (new / "spec.md").write_text("new")

        result = spec_helper.find_feature_dir_auto(tmp_path)
        assert result == new

    def test_auto_no_features_dies(self, tmp_path):
        sd = tmp_path / "design" / "specs"
        sd.mkdir(parents=True)

        with pytest.raises(SystemExit):
            spec_helper.find_feature_dir_auto(tmp_path)


# ===================================================================
# find_feature_dir — multi-format resolution
# ===================================================================


class TestFindFeatureDirResolution:
    """find_feature_dir resolves 7, 007, 007-spec, 007-spec-helper-v2 to same dir."""

    @pytest.fixture()
    def feature_root(self, tmp_path):
        sd = tmp_path / "design" / "specs"
        sd.mkdir(parents=True)
        target = sd / "007-spec-helper-v2"
        target.mkdir()
        return tmp_path

    def test_resolves_bare_number(self, feature_root):
        result = spec_helper.find_feature_dir(feature_root, "7")
        assert result.name == "007-spec-helper-v2"

    def test_resolves_padded_number(self, feature_root):
        result = spec_helper.find_feature_dir(feature_root, "007")
        assert result.name == "007-spec-helper-v2"

    def test_resolves_number_prefix_with_partial_slug(self, feature_root):
        result = spec_helper.find_feature_dir(feature_root, "007-spec")
        assert result.name == "007-spec-helper-v2"

    def test_resolves_exact_name(self, feature_root):
        result = spec_helper.find_feature_dir(feature_root, "007-spec-helper-v2")
        assert result.name == "007-spec-helper-v2"


class TestFindRepoRootNoSpecsDies:
    """Dies when .git exists but no design/specs/."""

    def test_no_specs_dies(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            spec_helper.find_repo_root()


# ===================================================================
# Round-trip: load -> modify -> dump -> reload
# ===================================================================


class TestRoundtripPreservesUnknownFields:
    """Load a WP file with issue field, modify lane, dump, reload — issue survives."""

    def test_roundtrip_with_issue_field(self, tmp_path):
        wp_content = """\
---
lane: done
title: Delete permissions subsystem
issue: '#117'
depends_on: []
---

# WP01: Delete permissions subsystem

## Activity Log

- 2026-03-20T10:00:00Z — system — lane=planned — WP created
"""
        wp_file = tmp_path / "WP01.md"
        wp_file.write_text(wp_content)

        # Load
        post = frontmatter.load(str(wp_file))

        # Modify lane via direct mutation (the pattern from design.md)
        post.metadata["lane"] = "for_review"

        # Dump to a new file
        out_file = tmp_path / "WP01_out.md"
        with open(out_file, "wb") as f:
            frontmatter.dump(post, f)

        # Reload and verify
        reloaded = frontmatter.load(str(out_file))
        assert reloaded["lane"] == "for_review"
        assert reloaded["issue"] == "#117"
        assert reloaded["title"] == "Delete permissions subsystem"
        assert "Activity Log" in reloaded.content

    def test_roundtrip_real_006_format(self, tmp_path):
        """Mimics the real 006 WP format with depends (old key) and issue."""
        wp_content = """\
---
lane: done
title: Delete permissions subsystem
issue: '#117'
depends:
---

# WP01: Delete permissions subsystem

## Activity Log

- 2026-03-20T10:00:00Z — system — lane=planned — WP created
"""
        wp_file = tmp_path / "WP01.md"
        wp_file.write_text(wp_content)

        # Load and normalize
        post = frontmatter.load(str(wp_file))
        raw = spec_helper.normalize_wp_metadata(dict(post.metadata), "WP01.md")

        # Verify normalization
        assert raw["depends_on"] == []
        assert "depends" not in raw
        assert raw["issue"] == "#117"
        assert raw["work_package_id"] == "WP01"

        # Modify lane
        post.metadata["lane"] = "for_review"

        # Dump and reload
        out_file = tmp_path / "WP01_out.md"
        with open(out_file, "wb") as f:
            frontmatter.dump(post, f)

        reloaded = frontmatter.load(str(out_file))
        assert reloaded.metadata["lane"] == "for_review"
        assert reloaded.metadata["issue"] == "#117"


# ===================================================================
# wp-move — WP03 tests
# ===================================================================


def _make_wp_file(tmp_path, content, *, feature="001-test", filename="WP01.md"):
    """Helper: create a WP file inside a feature/tasks/ directory."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    tasks = root / "design" / "specs" / feature / "tasks"
    tasks.mkdir(parents=True)
    wp_file = tasks / filename
    wp_file.write_text(content)
    return root, wp_file


class TestWpMoveChangesLane:
    """Lane field updated in file after wp-move."""

    def test_wp_move_changes_lane(self, tmp_path, monkeypatch):
        content = """\
---
work_package_id: WP01
title: Test task
lane: planned
depends_on: []
---

## Subtasks

- Do something

## Activity Log

- 2026-01-01T00:00:00Z — system — lane=planned — WP created
"""
        root, wp_file = _make_wp_file(tmp_path, content)
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", wp_id="WP01", lane="doing",
            auto=False, json=False,
        )
        spec_helper.cmd_wp_move(args)

        reloaded = frontmatter.load(str(wp_file))
        assert reloaded.metadata["lane"] == "doing"


class TestWpMovePreservesUnknownFields:
    """Unknown fields like 'issue' survive wp-move."""

    def test_wp_move_preserves_unknown_fields(self, tmp_path, monkeypatch):
        content = """\
---
work_package_id: WP01
title: Test task
lane: planned
depends_on: []
issue: '#117'
custom_field: some_value
---

## Activity Log

- 2026-01-01T00:00:00Z — system — lane=planned — WP created
"""
        root, wp_file = _make_wp_file(tmp_path, content)
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", wp_id="WP01", lane="doing",
            auto=False, json=False,
        )
        spec_helper.cmd_wp_move(args)

        reloaded = frontmatter.load(str(wp_file))
        assert reloaded.metadata["lane"] == "doing"
        assert reloaded.metadata["issue"] == "#117"
        assert reloaded.metadata["custom_field"] == "some_value"


class TestWpMoveAtomicWrite:
    """Verify temp file created in same directory as WP file."""

    def test_wp_move_atomic_write(self, tmp_path, monkeypatch):
        content = """\
---
work_package_id: WP01
title: Test task
lane: planned
depends_on: []
---

## Activity Log

- 2026-01-01T00:00:00Z — system — lane=planned — WP created
"""
        root, wp_file = _make_wp_file(tmp_path, content)
        monkeypatch.chdir(root)

        # Track NamedTemporaryFile calls to verify dir= parameter
        import tempfile as _tempfile
        captured_dirs = []
        _original_ntf = _tempfile.NamedTemporaryFile

        def _tracking_ntf(*a, **kw):
            captured_dirs.append(kw.get("dir"))
            return _original_ntf(*a, **kw)

        monkeypatch.setattr(_tempfile, "NamedTemporaryFile", _tracking_ntf)

        args = argparse.Namespace(
            feature="001-test", wp_id="WP01", lane="doing",
            auto=False, json=False,
        )
        spec_helper.cmd_wp_move(args)

        # Temp file should have been created in the same directory as the WP file
        assert len(captured_dirs) == 1
        assert captured_dirs[0] == wp_file.parent


class TestActivityLogInsertBeforeNextHeading:
    """Activity Log is NOT the last section; entry inserted before next ## heading."""

    def test_activity_log_insert_before_next_heading(self, tmp_path, monkeypatch):
        content = """\
---
work_package_id: WP01
title: Test task
lane: planned
depends_on: []
---

## Activity Log

- 2026-01-01T00:00:00Z — system — lane=planned — WP created

## Review Guidance

- Check things
"""
        root, wp_file = _make_wp_file(tmp_path, content)
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", wp_id="WP01", lane="doing",
            auto=False, json=False,
        )
        spec_helper.cmd_wp_move(args)

        text = wp_file.read_text()
        # The new log entry should appear BEFORE ## Review Guidance
        log_idx = text.index("lane=doing — moved from planned")
        review_idx = text.index("## Review Guidance")
        assert log_idx < review_idx

        # ## Review Guidance content should still be present
        assert "- Check things" in text


class TestActivityLogInsertAtEof:
    """Activity Log is last section; entry appended at end."""

    def test_activity_log_insert_at_eof(self, tmp_path, monkeypatch):
        content = """\
---
work_package_id: WP01
title: Test task
lane: planned
depends_on: []
---

## Subtasks

- Do something

## Activity Log

- 2026-01-01T00:00:00Z — system — lane=planned — WP created
"""
        root, wp_file = _make_wp_file(tmp_path, content)
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", wp_id="WP01", lane="doing",
            auto=False, json=False,
        )
        spec_helper.cmd_wp_move(args)

        text = wp_file.read_text()
        # New entry should be after the original log entry
        assert "lane=doing — moved from planned" in text
        lines = text.strip().splitlines()
        # The last non-empty line should be the new log entry
        assert "lane=doing — moved from planned" in lines[-1]


class TestActivityLogCreatedWhenMissing:
    """No Activity Log section; one created at EOF."""

    def test_activity_log_created_when_missing(self, tmp_path, monkeypatch):
        content = """\
---
work_package_id: WP01
title: Test task
lane: planned
depends_on: []
---

## Subtasks

- Do something
"""
        root, wp_file = _make_wp_file(tmp_path, content)
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", wp_id="WP01", lane="doing",
            auto=False, json=False,
        )
        spec_helper.cmd_wp_move(args)

        text = wp_file.read_text()
        assert "## Activity Log" in text
        assert "lane=doing — moved from planned" in text
        # Activity Log section should appear after Subtasks
        subtasks_idx = text.index("## Subtasks")
        activity_idx = text.index("## Activity Log")
        assert activity_idx > subtasks_idx


class TestWpMoveNoopWarns:
    """Same lane produces stderr warning."""

    def test_wp_move_noop_warns(self, tmp_path, monkeypatch, capsys):
        content = """\
---
work_package_id: WP01
title: Test task
lane: doing
depends_on: []
---

## Activity Log

- 2026-01-01T00:00:00Z — system — lane=doing — WP created
"""
        root, wp_file = _make_wp_file(tmp_path, content)
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", wp_id="WP01", lane="doing",
            auto=False, json=False,
        )
        spec_helper.cmd_wp_move(args)

        captured = capsys.readouterr()
        assert "already in lane" in captured.err
        assert "no change" in captured.err

        # File should be unmodified — no new activity log entry
        text = wp_file.read_text()
        assert text.count("lane=doing") == 1  # only the original entry


class TestWpMoveInvalidMetadataWarns:
    """Bad wp_id produces stderr warning but move succeeds."""

    def test_wp_move_invalid_metadata_warns(self, tmp_path, monkeypatch, capsys):
        content = """\
---
work_package_id: bad_id
title: Test task
lane: planned
depends_on: []
---

## Activity Log

- 2026-01-01T00:00:00Z — system — lane=planned — WP created
"""
        root, wp_file = _make_wp_file(tmp_path, content)
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", wp_id="WP01", lane="doing",
            auto=False, json=False,
        )
        spec_helper.cmd_wp_move(args)

        captured = capsys.readouterr()
        # Should warn about invalid work_package_id
        assert "warning" in captured.err.lower()
        assert "work_package_id" in captured.err

        # But the move should still succeed
        reloaded = frontmatter.load(str(wp_file))
        assert reloaded.metadata["lane"] == "doing"


# ===================================================================
# Helper: create a feature with multiple WP files
# ===================================================================


def _make_feature(tmp_path, wps, *, feature="001-test", design_md=None):
    """Helper: create a feature dir with multiple WP files and optional design.md.

    wps is a dict of {filename: frontmatter_content_string}.
    Returns (root, feature_dir).
    """
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    feature_dir = root / "design" / "specs" / feature
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True)
    for filename, content in wps.items():
        (tasks / filename).write_text(content)
    if design_md is not None:
        (feature_dir / "design.md").write_text(design_md)
    return root, feature_dir


# ===================================================================
# wp-validate — WP04 tests
# ===================================================================


_VALID_WP01 = """\
---
work_package_id: WP01
title: First task
lane: planned
depends_on: []
---

## Subtasks

- Do something
"""

_VALID_WP02 = """\
---
work_package_id: WP02
title: Second task
lane: doing
depends_on:
- WP01
---

## Subtasks

- Do something else
"""


class TestWpValidateAllValid:
    """Canonical WPs pass with no errors."""

    def test_wp_validate_all_valid(self, tmp_path, monkeypatch, capsys):
        root, _ = _make_feature(tmp_path, {
            "WP01.md": _VALID_WP01,
            "WP02.md": _VALID_WP02,
        })
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", auto=False, json=False, fix=False,
        )
        spec_helper.cmd_wp_validate(args)

        captured = capsys.readouterr()
        assert "2 files validated" in captured.out
        assert "0 errors" in captured.out

    def test_wp_validate_all_valid_json(self, tmp_path, monkeypatch, capsys):
        root, _ = _make_feature(tmp_path, {
            "WP01.md": _VALID_WP01,
            "WP02.md": _VALID_WP02,
        })
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", auto=False, json=True, fix=False,
        )
        spec_helper.cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["valid"] is True
        assert result["files"] == 2
        assert result["errors"] == []


class TestWpValidateMissingField:
    """WP without title reports error."""

    def test_wp_validate_missing_title(self, tmp_path, monkeypatch, capsys):
        no_title = """\
---
work_package_id: WP01
lane: planned
depends_on: []
---

Body text.
"""
        root, _ = _make_feature(tmp_path, {"WP01.md": no_title})
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", auto=False, json=True, fix=False,
        )
        with pytest.raises(SystemExit, match="1"):
            spec_helper.cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["valid"] is False
        assert any("title" in e["message"].lower() for e in result["errors"])


class TestWpValidateBrokenDependency:
    """depends_on references non-existent WP."""

    def test_wp_validate_broken_dependency(self, tmp_path, monkeypatch, capsys):
        broken_dep = """\
---
work_package_id: WP01
title: First task
lane: planned
depends_on:
- WP99
---

Body text.
"""
        root, _ = _make_feature(tmp_path, {"WP01.md": broken_dep})
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", auto=False, json=True, fix=False,
        )
        with pytest.raises(SystemExit, match="1"):
            spec_helper.cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["valid"] is False
        assert any("WP99" in e["message"] for e in result["errors"])


class TestWpValidatePlanSectionMismatch:
    """plan_section not in design.md headers produces warning."""

    def test_wp_validate_plan_section_mismatch(self, tmp_path, monkeypatch, capsys):
        wp_with_section = """\
---
work_package_id: WP01
title: First task
lane: planned
depends_on: []
plan_section: Nonexistent Section
---

Body text.
"""
        design = """\
# Design

## Architecture

Some text.

## Command Surface

More text.
"""
        root, _ = _make_feature(
            tmp_path,
            {"WP01.md": wp_with_section},
            design_md=design,
        )
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", auto=False, json=True, fix=False,
        )
        spec_helper.cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert any("plan_section" in w["message"].lower() or "Nonexistent Section" in w["message"]
                    for w in result["warnings"])


class TestWpValidateUnknownFieldWarning:
    """Unknown field 'issue' reported as warning, not error."""

    def test_wp_validate_unknown_field_warning(self, tmp_path, monkeypatch, capsys):
        wp_with_issue = """\
---
work_package_id: WP01
title: First task
lane: planned
depends_on: []
issue: '#117'
---

Body text.
"""
        root, _ = _make_feature(tmp_path, {"WP01.md": wp_with_issue})
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", auto=False, json=True, fix=False,
        )
        spec_helper.cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        # Should be valid (unknown fields are warnings, not errors)
        assert result["valid"] is True
        assert any("issue" in w["message"] for w in result["warnings"])


class TestWpValidateFixNormalizes:
    """--fix rewrites file: 'depends' becomes 'depends_on'."""

    def test_wp_validate_fix_normalizes(self, tmp_path, monkeypatch):
        old_schema = """\
---
title: First task
lane: planned
depends: WP02
---

Body text.
"""
        wp02 = """\
---
work_package_id: WP02
title: Second task
lane: planned
depends_on: []
---

Body.
"""
        root, feature_dir = _make_feature(tmp_path, {
            "WP01.md": old_schema,
            "WP02.md": wp02,
        })
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", auto=False, json=False, fix=True,
        )
        spec_helper.cmd_wp_validate(args)

        # Reload and verify normalization was persisted
        wp_file = feature_dir / "tasks" / "WP01.md"
        reloaded = frontmatter.load(str(wp_file))
        assert "depends" not in reloaded.metadata
        assert reloaded.metadata["depends_on"] == ["WP02"]
        assert reloaded.metadata["work_package_id"] == "WP01"


class TestWpValidateFixPreservesUnknown:
    """--fix keeps 'issue' field."""

    def test_wp_validate_fix_preserves_unknown(self, tmp_path, monkeypatch):
        wp_with_issue = """\
---
title: First task
lane: planned
depends: WP02
issue: '#117'
---

Body text.
"""
        wp02 = """\
---
work_package_id: WP02
title: Second task
lane: planned
depends_on: []
---

Body.
"""
        root, feature_dir = _make_feature(tmp_path, {
            "WP01.md": wp_with_issue,
            "WP02.md": wp02,
        })
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test", auto=False, json=False, fix=True,
        )
        spec_helper.cmd_wp_validate(args)

        wp_file = feature_dir / "tasks" / "WP01.md"
        reloaded = frontmatter.load(str(wp_file))
        assert reloaded.metadata["issue"] == "#117"
        assert reloaded.metadata["depends_on"] == ["WP02"]
        assert reloaded.metadata["work_package_id"] == "WP01"


# ===================================================================
# wp-list — WP04 tests
# ===================================================================


class TestWpListJsonOutput:
    """Returns valid JSON array with expected fields."""

    def test_wp_list_json_output(self, tmp_path, monkeypatch, capsys):
        root, _ = _make_feature(tmp_path, {
            "WP01.md": _VALID_WP01,
            "WP02.md": _VALID_WP02,
        })
        monkeypatch.chdir(root)

        args = argparse.Namespace(feature="001-test", auto=False)
        spec_helper.cmd_wp_list(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert isinstance(result, list)
        assert len(result) == 2

        # Verify expected fields on first item
        item = result[0]
        assert "wp_id" in item
        assert "title" in item
        assert "lane" in item
        assert "depends_on" in item
        assert "path" in item


class TestWpListIncludesAllWps:
    """All WP files in feature appear in output."""

    def test_wp_list_includes_all_wps(self, tmp_path, monkeypatch, capsys):
        wp03 = """\
---
work_package_id: WP03
title: Third task
lane: done
depends_on:
- WP01
- WP02
---

Body.
"""
        root, _ = _make_feature(tmp_path, {
            "WP01.md": _VALID_WP01,
            "WP02.md": _VALID_WP02,
            "WP03.md": wp03,
        })
        monkeypatch.chdir(root)

        args = argparse.Namespace(feature="001-test", auto=False)
        spec_helper.cmd_wp_list(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        wp_ids = [item["wp_id"] for item in result]
        assert "WP01" in wp_ids
        assert "WP02" in wp_ids
        assert "WP03" in wp_ids


# ===================================================================
# WP05 — init creates directory only
# ===================================================================


class TestInitCreatesDirectoryOnly:
    """init creates only the feature directory — no spec.md or tasks/."""

    def test_init_creates_directory_only(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="user-auth", json=False)
        spec_helper.cmd_init(args)

        feature_dir = tmp_path / "design" / "specs" / "001-user-auth"
        assert feature_dir.is_dir()
        assert not (feature_dir / "spec.md").exists()
        assert not (feature_dir / "tasks").exists()


class TestInitJsonOutput:
    """JSON output has feature_number, slug, feature_dir keys."""

    def test_init_json_output(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="user-auth", json=True)
        spec_helper.cmd_init(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["feature_number"] == "001"
        assert result["slug"] == "user-auth"
        assert result["feature_dir"] == "design/specs/001-user-auth"


class TestInitHumanOutput:
    """Human output starts with 'Created:'."""

    def test_init_human_output(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="user-auth", json=False)
        spec_helper.cmd_init(args)

        captured = capsys.readouterr()
        assert captured.out.startswith("Created:")


# ===================================================================
# WP05 — structured error output
# ===================================================================


class TestErrorJsonFormat:
    """JSON mode error has 'error' and 'code' keys on stdout."""

    def test_error_json_format(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        # Simulate --json in sys.argv for die() to detect
        monkeypatch.setattr(sys, "argv", ["spec-helper", "--json", "init", "test"])

        with pytest.raises(SystemExit, match="1"):
            spec_helper.die("something went wrong", code="not_found")

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "error" in result
        assert "code" in result
        assert result["error"] == "something went wrong"
        assert result["code"] == "not_found"


class TestErrorHumanFormat:
    """Human mode error goes to stderr."""

    def test_error_human_format(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["spec-helper", "init", "test"])

        with pytest.raises(SystemExit, match="1"):
            spec_helper.die("something went wrong")

        captured = capsys.readouterr()
        assert "something went wrong" in captured.err
        assert captured.out == ""


# ===================================================================
# WP05 — status warns on invalid lane
# ===================================================================


class TestStatusWarnsOnInvalidLane:
    """stderr contains warning, WP still appears in 'planned'."""

    def test_status_warns_on_invalid_lane(self, tmp_path, monkeypatch, capsys):
        bad_lane_wp = """\
---
work_package_id: WP01
title: Bad lane task
lane: in_progress
depends_on: []
---

Body.
"""
        root, _ = _make_feature(tmp_path, {"WP01.md": bad_lane_wp})
        monkeypatch.chdir(root)

        args = argparse.Namespace(feature="001-test", auto=False, json=True)
        spec_helper.cmd_status(args)

        captured = capsys.readouterr()

        # Check stderr warning
        assert "warning" in captured.err.lower()
        assert "in_progress" in captured.err
        assert "WP01.md" in captured.err

        # Check WP bucketed as planned in JSON output
        result = json.loads(captured.out)
        assert "WP01" in result[0]["lanes"]["planned"]
