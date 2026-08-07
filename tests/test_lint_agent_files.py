"""Tests for bin/lint-agent-files."""

import runpy
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "bin" / "lint-agent-files"
SUBPROCESS_TIMEOUT_SECONDS = 30


def _load_script() -> dict:
    return runpy.run_path(str(SCRIPT))


def _write_skill(root: Path, dirname: str, name: str, description: str) -> Path:
    skill_dir = root / "skills" / dirname
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    path.write_text(f"---\nname: {name}\ndescription: {description}\n---\nbody\n")
    return path


def _write_agent(root: Path, filename: str, name: str, description: str) -> Path:
    agents_dir = root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / filename
    path.write_text(f"---\nname: {name}\ndescription: {description}\n---\nbody\n")
    return path


def test_lint_agent_files_passes_current_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "."],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0
    assert "OK" in result.stdout


def test_valid_skill_and_agent_pass(tmp_path: Path) -> None:
    _write_skill(
        tmp_path, "good-skill", "good-skill", '"Use when testing. Does a thing."'
    )
    _write_agent(tmp_path, "good-agent.md", "good-agent", "An agent for testing.")

    module = _load_script()
    errors = module["check_skill"](
        tmp_path / "skills" / "good-skill" / "SKILL.md", tmp_path
    )
    errors += module["check_agent"](tmp_path / "agents" / "good-agent.md", tmp_path)

    assert errors == []


def test_skill_missing_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "no-frontmatter"
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    path.write_text("no frontmatter block here\n")

    module = _load_script()
    errors = module["check_skill"](path, tmp_path)

    assert len(errors) == 1
    assert "must have YAML frontmatter" in errors[0]


def test_skill_missing_name_field(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "no-name"
    skill_dir.mkdir(parents=True)
    path = skill_dir / "SKILL.md"
    path.write_text('---\ndescription: "Use when testing."\n---\nbody\n')

    module = _load_script()
    errors = module["check_skill"](path, tmp_path)

    assert any("missing required 'name' field" in e for e in errors)


def test_skill_missing_description_field(tmp_path: Path) -> None:
    path = _write_skill(tmp_path, "no-desc", "no-desc", "")
    path.write_text("---\nname: no-desc\n---\nbody\n")

    module = _load_script()
    errors = module["check_skill"](path, tmp_path)

    assert any("missing required 'description' field" in e for e in errors)


def test_skill_name_not_kebab_case(tmp_path: Path) -> None:
    path = _write_skill(
        tmp_path, "bad-name", "BadName_Not_Kebab", '"Use when testing."'
    )

    module = _load_script()
    errors = module["check_skill"](path, tmp_path)

    assert any("lowercase" in e for e in errors)


def test_skill_name_must_match_parent_directory(tmp_path: Path) -> None:
    path = _write_skill(tmp_path, "actual-dir", "different-name", '"Use when testing."')

    module = _load_script()
    errors = module["check_skill"](path, tmp_path)

    assert any("must match parent directory 'actual-dir'" in e for e in errors)


def test_skill_description_without_trigger_phrase(tmp_path: Path) -> None:
    path = _write_skill(
        tmp_path, "no-trigger", "no-trigger", '"Does something useful."'
    )

    module = _load_script()
    errors = module["check_skill"](path, tmp_path)

    assert any("Use when..." in e for e in errors)


def test_agent_missing_name_field(tmp_path: Path) -> None:
    path = _write_agent(tmp_path, "no-name.md", "", "")
    path.write_text('---\ndescription: "an agent"\n---\nbody\n')

    module = _load_script()
    errors = module["check_agent"](path, tmp_path)

    assert any("missing required 'name' field" in e for e in errors)


def test_agent_missing_description_field(tmp_path: Path) -> None:
    path = _write_agent(tmp_path, "no-desc.md", "", "")
    path.write_text("---\nname: no-desc\n---\nbody\n")

    module = _load_script()
    errors = module["check_agent"](path, tmp_path)

    assert any("missing required 'description' field" in e for e in errors)


def test_hardcoded_username_path_flagged(tmp_path: Path) -> None:
    path = tmp_path / "CLAUDE.md"
    path.write_text("absolute path /home/jessica/foo/bar for testing\n")

    module = _load_script()
    errors = module["check_hardcoded_paths"](path, tmp_path)

    assert len(errors) == 1
    assert "/home/jessica/" in errors[0]


def test_tilde_and_generic_paths_not_flagged(tmp_path: Path) -> None:
    path = tmp_path / "CLAUDE.md"
    path.write_text("tilde path ~/.claude/ is fine\ngeneric /home/user/ is fine\n")

    module = _load_script()
    errors = module["check_hardcoded_paths"](path, tmp_path)

    assert errors == []


def test_cli_reports_multiple_errors_and_exits_nonzero(tmp_path: Path) -> None:
    _write_skill(tmp_path, "broken", "broken", '"no trigger phrase here"')

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 1
    assert "Use when..." in result.stderr


def test_malformed_opening_delimiter_not_treated_as_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "CLAUDE.md"
    path.write_text(
        '---invalid\nname: x\ndescription: "Use when testing."\n---\nbody\n'
    )

    module = _load_script()
    fm = module["parse_frontmatter"](path.read_text())

    assert fm is None


def test_embedded_triple_dash_does_not_satisfy_closing_delimiter(
    tmp_path: Path,
) -> None:
    # A "---" appearing mid-body must not substitute for a missing closing
    # delimiter on its own line.
    text = "---\nname: x\ndescription: has --- embedded, no real closer\nbody\n"

    module = _load_script()
    fm = module["parse_frontmatter"](text)

    assert fm is None


def test_agents_dir_passed_directly_is_scanned(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "broken.md").write_text("---\nname: broken\n---\nbody\n")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(agents_dir)],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 1
    assert "missing required 'description' field" in result.stderr
