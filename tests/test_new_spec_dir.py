"""Tests for bin/new-spec-dir."""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "bin" / "new-spec-dir"
GIT_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=GIT_ENV)
    return repo


def run_script(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, env=GIT_ENV
    )


def test_first_spec_is_001(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    result = run_script(repo, "webhooks")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "design/specs/001-webhooks"
    assert (repo / "design/specs/001-webhooks").is_dir()


def test_numbers_past_highest_prefix_from_a_subdirectory(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    specs = repo / "design/specs"
    for name in ("009-old", "1015-newer", "no-number", "042-mid"):
        (specs / name).mkdir(parents=True)
    (repo / "src").mkdir()

    result = run_script(repo / "src", "next-thing")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "design/specs/1016-next-thing"
    assert (specs / "1016-next-thing").is_dir()


def test_rejects_non_kebab_slug(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)

    result = run_script(repo, "Bad_Slug")

    assert result.returncode == 2
    assert not (repo / "design").exists()
