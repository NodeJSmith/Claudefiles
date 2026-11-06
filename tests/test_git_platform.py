"""Tests for bin/git-platform."""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "bin" / "git-platform"


def make_repo(path: Path, origin: str | None) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    if origin is not None:
        subprocess.run(["git", "remote", "add", "origin", origin], cwd=path, check=True)
    return path


def run_script(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args], cwd=cwd, check=True, capture_output=True, text=True
    )


@pytest.mark.parametrize(
    ("origin", "expected"),
    [
        ("git@github.com:owner/repo.git", "github"),
        ("https://dev.azure.com/org/proj/_git/repo", "ado"),
        ("git@ssh.dev.azure.com:v3/org/proj/repo", "ado"),
    ],
)
def test_detects_platform_from_cwd(tmp_path: Path, origin: str, expected: str) -> None:
    repo = make_repo(tmp_path / "repo", origin)
    assert run_script(cwd=repo).stdout.strip() == expected


def test_dash_c_detects_platform_from_outside_the_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", "git@ssh.dev.azure.com:v3/org/proj/repo")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert run_script("-C", str(repo), cwd=outside).stdout.strip() == "ado"


def test_unknown_explains_missing_origin_on_stderr(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    result = run_script(cwd=not_a_repo)
    assert result.stdout.strip() == "unknown"
    assert "no origin remote" in result.stderr
    assert str(not_a_repo) in result.stderr


def test_unknown_explains_unrecognized_url_on_stderr(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", "https://gitlab.com/owner/repo.git")
    result = run_script(cwd=repo)
    assert result.stdout.strip() == "unknown"
    assert "gitlab.com" in result.stderr
