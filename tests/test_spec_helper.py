"""Tests for spec-helper package."""

import argparse
import json
import sys

import frontmatter
import pytest

from spec_helper.validation import validate_wp_metadata, normalize_wp_metadata
from spec_helper.filesystem import (
    find_feature_dir,
    find_feature_dir_auto,
    find_repo_root,
    find_wp_file,
    list_features,
)
from spec_helper.errors import die
from spec_helper.commands import (
    cmd_init,
    cmd_wp_move,
    cmd_wp_validate,
    cmd_wp_list,
    cmd_status,
)
from spec_helper.cli import build_parser


# ===================================================================
# CLI parsing smoke tests (challenge finding #1 and #2)
# ===================================================================


class TestCLIParsing:
    """Verify argparse accepts the actual command patterns callers use."""

    def test_init_with_json_after_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["init", "user-auth", "--json"])
        assert args.command == "init"
        assert args.json is True
        assert args.slug == "user-auth"

    def test_init_with_json_before_subcommand(self):
        """--json before subcommand is accepted but overridden by subparser default.
        Callers should always put --json after the subcommand."""
        parser = build_parser()
        # This parses without error — the flag is accepted
        args = parser.parse_args(["--json", "init", "user-auth"])
        # Note: argparse subparser default overrides parent's value
        # Callers use `spec-helper init slug --json` (after subcommand)
        assert args.command == "init"

    def test_wp_move_basic(self):
        parser = build_parser()
        args = parser.parse_args(["wp-move", "007-auth", "WP01", "doing"])
        assert args.command == "wp-move"
        assert args.feature == "007-auth"
        assert args.wp_id == "WP01"
        assert args.lane == "doing"

    def test_wp_move_with_auto(self):
        parser = build_parser()
        args = parser.parse_args(["wp-move", "--auto", "WP01", "doing"])
        assert args.auto is True
        assert args.feature is None

    def test_status_no_args(self):
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"
        assert args.feature is None

    def test_status_with_json(self):
        parser = build_parser()
        args = parser.parse_args(["status", "007-auth", "--json"])
        assert args.json is True

    def test_wp_validate_with_fix(self):
        parser = build_parser()
        args = parser.parse_args(["wp-validate", "--fix"])
        assert args.fix is True
        assert args.feature is None

    def test_wp_validate_feature_with_json(self):
        parser = build_parser()
        args = parser.parse_args(["wp-validate", "007-auth", "--json"])
        assert args.json is True
        assert args.feature == "007-auth"

    def test_wp_list_with_auto(self):
        parser = build_parser()
        args = parser.parse_args(["wp-list", "--auto"])
        assert args.auto is True

    def test_next_number(self):
        parser = build_parser()
        args = parser.parse_args(["next-number"])
        assert args.command == "next-number"

    def test_next_number_with_json(self):
        parser = build_parser()
        args = parser.parse_args(["next-number", "--json"])
        assert args.json is True

    def test_json_before_subcommand_is_accepted(self):
        """--json before subcommand parses without error."""
        parser = build_parser()
        args = parser.parse_args(["--json", "status"])
        assert args.command == "status"


# ===================================================================
# validate_wp_metadata
# ===================================================================


class TestValidateWpMetadataValid:
    """Canonical schema passes with empty error list."""

    def test_valid_metadata(self):
        meta = {
            "work_package_id": "WP01",
            "title": "Test task",
            "lane": "planned",
            "depends_on": [],
        }
        assert validate_wp_metadata(meta, "WP01.md") == []

    def test_valid_with_dependencies(self):
        meta = {
            "work_package_id": "WP03",
            "title": "Integration",
            "lane": "doing",
            "depends_on": ["WP01", "WP02"],
        }
        assert validate_wp_metadata(meta, "WP03.md") == []


class TestValidateWpMetadataInvalidWpId:
    def test_empty_wp_id(self):
        meta = {"work_package_id": "", "title": "Test", "lane": "planned"}
        errors = validate_wp_metadata(meta, "WP01.md")
        assert any("work_package_id" in e for e in errors)

    def test_bad_format_wp_id(self):
        meta = {"work_package_id": "bad_id", "title": "Test", "lane": "planned"}
        errors = validate_wp_metadata(meta, "WP01.md")
        assert any("work_package_id" in e for e in errors)


class TestValidateWpMetadataInvalidLane:
    def test_invalid_lane(self):
        meta = {"work_package_id": "WP01", "title": "Test", "lane": "review"}
        errors = validate_wp_metadata(meta, "WP01.md")
        assert any("lane" in e for e in errors)


class TestValidateWpMetadataInvalidDependency:
    def test_bad_dependency_format(self):
        meta = {
            "work_package_id": "WP01",
            "title": "Test",
            "lane": "planned",
            "depends_on": ["bad"],
        }
        errors = validate_wp_metadata(meta, "WP01.md")
        assert any("dependency" in e.lower() for e in errors)


class TestValidateWpMetadataMissingTitle:
    def test_missing_title(self):
        meta = {"work_package_id": "WP01", "lane": "planned"}
        errors = validate_wp_metadata(meta, "WP01.md")
        assert any("title" in e.lower() for e in errors)

    def test_empty_title(self):
        meta = {"work_package_id": "WP01", "title": "", "lane": "planned"}
        errors = validate_wp_metadata(meta, "WP01.md")
        assert any("title" in e.lower() for e in errors)


# ===================================================================
# normalize_wp_metadata
# ===================================================================


class TestNormalizeDependsString:
    def test_string_dep_becomes_list(self):
        raw = {"depends": "WP02", "lane": "planned"}
        result = normalize_wp_metadata(raw, "WP03.md")
        assert result["depends_on"] == ["WP02"]
        assert "depends" not in result


class TestNormalizeDependsList:
    def test_list_dep_stays_list(self):
        raw = {"depends": ["WP01", "WP02"], "lane": "planned"}
        result = normalize_wp_metadata(raw, "WP03.md")
        assert result["depends_on"] == ["WP01", "WP02"]


class TestNormalizeDependsEmpty:
    def test_empty_dep_becomes_empty_list(self):
        raw = {"depends": None, "lane": "planned"}
        result = normalize_wp_metadata(raw, "WP01.md")
        assert result["depends_on"] == []

    def test_empty_string_dep_becomes_empty_list(self):
        raw = {"depends": "", "lane": "planned"}
        result = normalize_wp_metadata(raw, "WP01.md")
        assert result["depends_on"] == []


class TestNormalizeMissingWpId:
    def test_derives_wp_id_from_filename(self):
        raw = {"title": "Test", "lane": "planned"}
        result = normalize_wp_metadata(raw, "WP03.md")
        assert result["work_package_id"] == "WP03"

    def test_does_not_override_existing_wp_id(self):
        raw = {"work_package_id": "WP01", "title": "Test", "lane": "planned"}
        result = normalize_wp_metadata(raw, "WP99.md")
        assert result["work_package_id"] == "WP01"


class TestNormalizePreservesUnknownFields:
    def test_unknown_field_preserved(self):
        raw = {
            "work_package_id": "WP01",
            "title": "Test",
            "lane": "planned",
            "issue": "#117",
        }
        result = normalize_wp_metadata(raw, "WP01.md")
        assert result["issue"] == "#117"

    def test_depends_normalization_preserves_issue(self):
        raw = {"depends": "WP02", "issue": "#117", "lane": "planned"}
        result = normalize_wp_metadata(raw, "WP01.md")
        assert result["issue"] == "#117"
        assert result["depends_on"] == ["WP02"]


class TestNormalizeDoesNotShareReferences:
    """Shallow copy must not share mutable list values with the original."""

    def test_list_not_shared(self):
        original = {
            "depends_on": ["WP01"],
            "lane": "planned",
            "work_package_id": "WP02",
            "title": "Test",
        }
        result = normalize_wp_metadata(original, "WP02.md")
        result["depends_on"].append("WP03")
        assert original["depends_on"] == ["WP01"]


# ===================================================================
# find_repo_root
# ===================================================================


class TestFindRepoRootWithGitAndSpecs:
    def test_finds_root_with_git_and_specs(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        assert find_repo_root() == tmp_path

    def test_finds_root_from_subdirectory(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        sub = tmp_path / "some" / "deep" / "dir"
        sub.mkdir(parents=True)
        monkeypatch.chdir(sub)
        assert find_repo_root() == tmp_path


class TestFindRepoRootNoGitDies:
    def test_no_git_dies(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            find_repo_root()


class TestFindRepoRootNoSpecsDies:
    def test_no_specs_dies(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            find_repo_root()


# ===================================================================
# Slug sanitization (tested via cmd_init)
# ===================================================================


class TestSlugSanitizationDoubleHyphens:
    def test_double_hyphens_collapsed(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="auth--flow", json=False)
        cmd_init(args)

        dirs = list((tmp_path / "design" / "specs").iterdir())
        assert len(dirs) == 1
        assert "auth-flow" in dirs[0].name
        assert "--" not in dirs[0].name


class TestSlugSanitizationTrailingHyphen:
    def test_trailing_hyphen_stripped(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="auth-", json=False)
        cmd_init(args)

        dirs = list((tmp_path / "design" / "specs").iterdir())
        assert len(dirs) == 1
        assert dirs[0].name.endswith("auth")


# ===================================================================
# list_features — any digit width
# ===================================================================


class TestListFeaturesAnyDigitWidth:
    def test_any_digit_width(self, tmp_path):
        sd = tmp_path / "design" / "specs"
        sd.mkdir(parents=True)
        (sd / "01-a").mkdir()
        (sd / "001-b").mkdir()
        (sd / "1000-c").mkdir()
        (sd / "not-a-feature").mkdir()

        features = list_features(tmp_path)
        names = [f.name for f in features]
        assert "01-a" in names
        assert "001-b" in names
        assert "1000-c" in names
        assert "not-a-feature" not in names


# ===================================================================
# find_feature_dir_auto
# ===================================================================


class TestFindFeatureDirAuto:
    def test_auto_returns_most_recent(self, tmp_path):
        import time

        sd = tmp_path / "design" / "specs"
        sd.mkdir(parents=True)

        old = sd / "001-old-feature"
        old.mkdir()
        (old / "spec.md").write_text("old")

        time.sleep(0.05)

        new = sd / "002-new-feature"
        new.mkdir()
        (new / "spec.md").write_text("new")

        result = find_feature_dir_auto(tmp_path)
        assert result == new

    def test_auto_no_features_dies(self, tmp_path):
        sd = tmp_path / "design" / "specs"
        sd.mkdir(parents=True)

        with pytest.raises(SystemExit):
            find_feature_dir_auto(tmp_path)


# ===================================================================
# find_feature_dir — resolution modes
# ===================================================================


class TestFindFeatureDirResolution:
    def _setup(self, tmp_path):
        sd = tmp_path / "design" / "specs"
        sd.mkdir(parents=True)
        (sd / "007-spec-helper-v2").mkdir()
        return tmp_path

    def test_resolves_bare_number(self, tmp_path):
        root = self._setup(tmp_path)
        result = find_feature_dir(root, "7")
        assert result.name == "007-spec-helper-v2"

    def test_resolves_padded_number(self, tmp_path):
        root = self._setup(tmp_path)
        result = find_feature_dir(root, "007")
        assert result.name == "007-spec-helper-v2"

    def test_resolves_number_prefix_with_partial_slug(self, tmp_path):
        root = self._setup(tmp_path)
        result = find_feature_dir(root, "007-spec")
        assert result.name == "007-spec-helper-v2"

    def test_resolves_exact_name(self, tmp_path):
        root = self._setup(tmp_path)
        result = find_feature_dir(root, "007-spec-helper-v2")
        assert result.name == "007-spec-helper-v2"


# ===================================================================
# find_wp_file — crash on bad input (challenge finding #3)
# ===================================================================


class TestFindWpFileBadInput:
    def test_non_numeric_input_dies_cleanly(self, tmp_path):
        tasks = tmp_path / "tasks"
        tasks.mkdir()
        (tasks / "WP01.md").write_text("---\nlane: planned\n---\n")

        with pytest.raises(SystemExit):
            find_wp_file(tmp_path, "foo")


# ===================================================================
# Round-trip field preservation
# ===================================================================


class TestRoundtripPreservesUnknownFields:
    def test_roundtrip_with_issue_field(self, tmp_path):
        wp_content = """\
---
work_package_id: WP01
title: Delete permissions subsystem
lane: planned
depends_on: []
issue: '#117'
---

## Activity Log

- 2026-01-01T00:00:00Z — system — lane=planned — WP created
"""
        wp_file = tmp_path / "WP01.md"
        wp_file.write_text(wp_content)

        post = frontmatter.load(str(wp_file))
        post.metadata["lane"] = "for_review"

        out_file = tmp_path / "WP01_out.md"
        with open(out_file, "wb") as f:
            frontmatter.dump(post, f)

        reloaded = frontmatter.load(str(out_file))
        assert reloaded["lane"] == "for_review"
        assert reloaded["issue"] == "#117"
        assert reloaded["title"] == "Delete permissions subsystem"
        assert "Activity Log" in reloaded.content

    def test_roundtrip_real_006_format(self, tmp_path):
        wp_content = """\
---
lane: done
title: Delete permissions subsystem
issue: '#117'
depends:
---

## Content here
"""
        wp_file = tmp_path / "WP01.md"
        wp_file.write_text(wp_content)

        post = frontmatter.load(str(wp_file))
        raw = normalize_wp_metadata(dict(post.metadata), "WP01.md")
        assert raw["depends_on"] == []
        assert raw["issue"] == "#117"

        post.metadata["lane"] = "for_review"

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
            feature="001-test",
            wp_id="WP01",
            lane="doing",
            auto=False,
            json=False,
        )
        cmd_wp_move(args)

        reloaded = frontmatter.load(str(wp_file))
        assert reloaded.metadata["lane"] == "doing"


class TestWpMovePreservesUnknownFields:
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
            feature="001-test",
            wp_id="WP01",
            lane="doing",
            auto=False,
            json=False,
        )
        cmd_wp_move(args)

        reloaded = frontmatter.load(str(wp_file))
        assert reloaded.metadata["lane"] == "doing"
        assert reloaded.metadata["issue"] == "#117"
        assert reloaded.metadata["custom_field"] == "some_value"


class TestWpMoveAtomicWrite:
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

        import tempfile as _tempfile

        captured_dirs = []
        _original_ntf = _tempfile.NamedTemporaryFile

        def _tracking_ntf(*a, **kw):
            captured_dirs.append(kw.get("dir"))
            return _original_ntf(*a, **kw)

        monkeypatch.setattr(_tempfile, "NamedTemporaryFile", _tracking_ntf)

        args = argparse.Namespace(
            feature="001-test",
            wp_id="WP01",
            lane="doing",
            auto=False,
            json=False,
        )
        cmd_wp_move(args)

        assert len(captured_dirs) == 1
        assert captured_dirs[0] == wp_file.parent


class TestActivityLogInsertBeforeNextHeading:
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
            feature="001-test",
            wp_id="WP01",
            lane="doing",
            auto=False,
            json=False,
        )
        cmd_wp_move(args)

        text = wp_file.read_text()
        log_idx = text.index("lane=doing — moved from planned")
        review_idx = text.index("## Review Guidance")
        assert log_idx < review_idx
        assert "- Check things" in text


class TestActivityLogInsertAtEof:
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
            feature="001-test",
            wp_id="WP01",
            lane="doing",
            auto=False,
            json=False,
        )
        cmd_wp_move(args)

        text = wp_file.read_text()
        assert "lane=doing — moved from planned" in text
        lines = text.strip().splitlines()
        assert "lane=doing — moved from planned" in lines[-1]


class TestActivityLogCreatedWhenMissing:
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
            feature="001-test",
            wp_id="WP01",
            lane="doing",
            auto=False,
            json=False,
        )
        cmd_wp_move(args)

        text = wp_file.read_text()
        assert "## Activity Log" in text
        assert "lane=doing — moved from planned" in text
        subtasks_idx = text.index("## Subtasks")
        activity_idx = text.index("## Activity Log")
        assert activity_idx > subtasks_idx


class TestWpMoveNoopWarns:
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
            feature="001-test",
            wp_id="WP01",
            lane="doing",
            auto=False,
            json=False,
        )
        cmd_wp_move(args)

        captured = capsys.readouterr()
        assert "already in lane" in captured.err
        assert "no change" in captured.err

        text = wp_file.read_text()
        assert text.count("lane=doing") == 1


class TestWpMoveInvalidMetadataWarns:
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
            feature="001-test",
            wp_id="WP01",
            lane="doing",
            auto=False,
            json=False,
        )
        cmd_wp_move(args)

        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        assert "work_package_id" in captured.err

        reloaded = frontmatter.load(str(wp_file))
        assert reloaded.metadata["lane"] == "doing"


# ===================================================================
# wp-validate — WP04 tests
# ===================================================================


def _make_feature(tmp_path, wps, *, feature="001-test", design_md=None):
    """Helper: create a feature with WP files and optional design.md."""
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    feature_dir = root / "design" / "specs" / feature
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True)
    for name, content in wps.items():
        (tasks / name).write_text(content)
    if design_md:
        (feature_dir / "design.md").write_text(design_md)
    return root


VALID_WP = """\
---
work_package_id: "{wp_id}"
title: "Test task"
lane: "planned"
plan_section: ""
depends_on: []
---

## Content
"""


class TestWpValidateAllValid:
    def test_wp_validate_all_valid(self, tmp_path, monkeypatch, capsys):
        root = _make_feature(
            tmp_path,
            {
                "WP01.md": VALID_WP.format(wp_id="WP01"),
                "WP02.md": VALID_WP.format(wp_id="WP02"),
            },
        )
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test",
            auto=False,
            json=False,
            fix=False,
        )
        cmd_wp_validate(args)

        captured = capsys.readouterr()
        assert "2 files validated" in captured.out
        assert "0 errors" in captured.out

    def test_wp_validate_all_valid_json(self, tmp_path, monkeypatch, capsys):
        root = _make_feature(
            tmp_path,
            {
                "WP01.md": VALID_WP.format(wp_id="WP01"),
                "WP02.md": VALID_WP.format(wp_id="WP02"),
            },
        )
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test",
            auto=False,
            json=True,
            fix=False,
        )
        cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["valid"] is True
        assert result["files"] == 2
        assert result["errors"] == []


class TestWpValidateMissingField:
    def test_wp_validate_missing_title(self, tmp_path, monkeypatch, capsys):
        root = _make_feature(
            tmp_path,
            {
                "WP01.md": "---\nwork_package_id: WP01\nlane: planned\n---\n",
            },
        )
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test",
            auto=False,
            json=True,
            fix=False,
        )
        with pytest.raises(SystemExit):
            cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["valid"] is False
        assert any("title" in e["message"].lower() for e in result["errors"])


class TestWpValidateBrokenDependency:
    def test_wp_validate_broken_dependency(self, tmp_path, monkeypatch, capsys):
        wp = """\
---
work_package_id: WP01
title: Test
lane: planned
depends_on: ["WP99"]
---
"""
        root = _make_feature(tmp_path, {"WP01.md": wp})
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test",
            auto=False,
            json=True,
            fix=False,
        )
        with pytest.raises(SystemExit):
            cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert any("WP99" in e["message"] for e in result["errors"])


class TestWpValidatePlanSectionMismatch:
    def test_wp_validate_plan_section_mismatch(self, tmp_path, monkeypatch, capsys):
        wp = """\
---
work_package_id: WP01
title: Test
lane: planned
plan_section: "Nonexistent Section"
depends_on: []
---
"""
        design = "# Design\n\n## Architecture\n\nContent\n"
        root = _make_feature(tmp_path, {"WP01.md": wp}, design_md=design)
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test",
            auto=False,
            json=True,
            fix=False,
        )
        cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert any("plan_section" in w["message"] for w in result["warnings"])


class TestWpValidateUnknownFieldWarning:
    def test_wp_validate_unknown_field_warning(self, tmp_path, monkeypatch, capsys):
        wp = """\
---
work_package_id: WP01
title: Test
lane: planned
depends_on: []
issue: '#117'
---
"""
        root = _make_feature(tmp_path, {"WP01.md": wp})
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test",
            auto=False,
            json=True,
            fix=False,
        )
        cmd_wp_validate(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert any("issue" in w["message"] for w in result["warnings"])


class TestWpValidateFixNormalizes:
    def test_wp_validate_fix_normalizes(self, tmp_path, monkeypatch):
        wp = """\
---
lane: done
title: Test
depends: WP02
---
"""
        root = _make_feature(tmp_path, {"WP01.md": wp})
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test",
            auto=False,
            json=False,
            fix=True,
        )
        try:
            cmd_wp_validate(args)
        except SystemExit:
            pass  # may exit 1 due to validation errors

        wp_file = root / "design" / "specs" / "001-test" / "tasks" / "WP01.md"
        reloaded = frontmatter.load(str(wp_file))
        assert "depends_on" in reloaded.metadata
        assert "depends" not in reloaded.metadata


class TestWpValidateFixPreservesUnknown:
    def test_wp_validate_fix_preserves_unknown(self, tmp_path, monkeypatch):
        wp = """\
---
lane: done
title: Test
depends: WP02
issue: '#117'
---
"""
        root = _make_feature(tmp_path, {"WP01.md": wp})
        monkeypatch.chdir(root)

        args = argparse.Namespace(
            feature="001-test",
            auto=False,
            json=False,
            fix=True,
        )
        try:
            cmd_wp_validate(args)
        except SystemExit:
            pass

        wp_file = root / "design" / "specs" / "001-test" / "tasks" / "WP01.md"
        reloaded = frontmatter.load(str(wp_file))
        assert reloaded.metadata["issue"] == "#117"


# ===================================================================
# wp-list — WP04 tests
# ===================================================================


class TestWpListJsonOutput:
    def test_wp_list_json_output(self, tmp_path, monkeypatch, capsys):
        root = _make_feature(
            tmp_path,
            {
                "WP01.md": VALID_WP.format(wp_id="WP01"),
            },
        )
        monkeypatch.chdir(root)

        args = argparse.Namespace(feature="001-test", auto=False, json=False)
        cmd_wp_list(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert len(result) == 1
        assert result[0]["wp_id"] == "WP01"
        assert "path" in result[0]


class TestWpListIncludesAllWps:
    def test_wp_list_includes_all_wps(self, tmp_path, monkeypatch, capsys):
        root = _make_feature(
            tmp_path,
            {
                "WP01.md": VALID_WP.format(wp_id="WP01"),
                "WP02.md": VALID_WP.format(wp_id="WP02"),
                "WP03.md": VALID_WP.format(wp_id="WP03"),
            },
        )
        monkeypatch.chdir(root)

        args = argparse.Namespace(feature="001-test", auto=False, json=False)
        cmd_wp_list(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert len(result) == 3


# ===================================================================
# init — WP05 tests
# ===================================================================


class TestInitCreatesDirectoryOnly:
    def test_init_creates_directory_only(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="test-feature", json=False)
        cmd_init(args)

        dirs = list((tmp_path / "design" / "specs").iterdir())
        assert len(dirs) == 1
        assert not (dirs[0] / "spec.md").exists()
        assert not (dirs[0] / "tasks").exists()


class TestInitJsonOutput:
    def test_init_json_output(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="test-feature", json=True)
        cmd_init(args)

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "feature_number" in result
        assert "slug" in result
        assert "feature_dir" in result


class TestInitHumanOutput:
    def test_init_human_output(self, tmp_path, monkeypatch, capsys):
        (tmp_path / ".git").mkdir()
        (tmp_path / "design" / "specs").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        args = argparse.Namespace(slug="test-feature", json=False)
        cmd_init(args)

        captured = capsys.readouterr()
        assert captured.out.startswith("Created:")


# ===================================================================
# Error output format — WP05 tests
# ===================================================================


class TestErrorJsonFormat:
    def test_error_json_format(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["spec-helper", "--json", "init", "test"])

        with pytest.raises(SystemExit, match="1"):
            die("something went wrong")

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["error"] == "something went wrong"
        assert result["code"] == "error"


class TestErrorHumanFormat:
    def test_error_human_format(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["spec-helper", "init", "test"])

        with pytest.raises(SystemExit, match="1"):
            die("something went wrong")

        captured = capsys.readouterr()
        assert "something went wrong" in captured.err
        assert captured.out == ""


# ===================================================================
# Status invalid lane warning — WP05 tests
# ===================================================================


class TestStatusWarnsOnInvalidLane:
    def test_status_warns_on_invalid_lane(self, tmp_path, monkeypatch, capsys):
        wp = """\
---
work_package_id: WP01
title: Test
lane: invalid_lane
depends_on: []
---
"""
        root = _make_feature(tmp_path, {"WP01.md": wp})
        monkeypatch.chdir(root)

        args = argparse.Namespace(feature="001-test", auto=False, json=True)
        cmd_status(args)

        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        assert "invalid_lane" in captured.err

        result = json.loads(captured.out)
        assert "WP01" in result[0]["lanes"]["planned"]
