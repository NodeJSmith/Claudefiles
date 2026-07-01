"""Tests for bin/lint-verdict-line."""

import runpy
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "bin" / "lint-verdict-line"
SUBPROCESS_TIMEOUT_SECONDS = 10


def _load_script() -> dict:
    return runpy.run_path(str(SCRIPT))


def test_lint_verdict_line_passes_current_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    assert result.returncode == 0
    assert "active contracts use normalized vocabulary" in result.stdout


def test_visual_reviewer_uses_standard_verdicts() -> None:
    module = _load_script()

    visual_path = (
        REPO_ROOT / "skills" / "mine-orchestrate" / "visual-reviewer-prompt.md"
    )
    allowed = module["REVIEWER_ALLOWED_VERDICTS"][visual_path]

    assert allowed == {"PASS", "WARN", "FAIL"}


def test_forbidden_vocab_scanner_rejects_old_terms(tmp_path: Path) -> None:
    module = _load_script()
    module["check_forbidden_vocab"].__globals__["ROOT"] = tmp_path
    sample = tmp_path / "sample.md"
    sample.write_text("**Verdict:** VERIFIED | WARN | FAIL\ncode=APPROVE\n")

    errors = module["check_forbidden_vocab"](sample)

    assert errors
    assert any("VERIFIED" in error and "use PASS" in error for error in errors)
    assert any("APPROVE" in error and "use PASS" in error for error in errors)
