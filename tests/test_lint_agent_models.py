"""Tests for bin/lint-agent-models.

The script is the pre-commit gate for required agent frontmatter. These tests
build a minimal fixture repo under tmp_path rather than touching the real repo,
and drive the script through `--root`.
"""

import runpy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "lint-agent-models"


def _load_script() -> dict:
    return runpy.run_path(str(SCRIPT), run_name="_test_lint_agent_models")


def _write_agent(
    agents_dir: Path,
    stem: str,
    *,
    model: str = "sonnet",
    effort: str = "high",
    include_fields: tuple[str, ...] = (
        "model",
        "effort",
        "tools",
        "description",
    ),
) -> None:
    """Write agents/<stem>.md with the given frontmatter fields.

    `include_fields` lets a test omit one required field to exercise the
    completeness check; the omitted field's line is simply not written.
    """
    fields = {
        "model": f"model: {model}",
        "effort": f"effort: {effort}",
        "tools": 'tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "Skill", "Agent"]',
        "description": f"description: {stem} test agent.",
    }
    lines = ["---", f"name: {stem}"]
    lines += [fields[f] for f in include_fields]
    lines += ["---", "", f"# {stem}", "", "Body."]
    (agents_dir / f"{stem}.md").write_text("\n".join(lines) + "\n")


def _build_fixture_repo(root: Path) -> None:
    (root / "agents").mkdir(parents=True)
    _write_agent(root / "agents", "foo")
    _write_agent(root / "agents", "bar")


def test_complete_frontmatter_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    _build_fixture_repo(tmp_path)
    module = _load_script()

    assert module["main"](["--root", str(tmp_path)]) == 0
    assert "2 agents" in capsys.readouterr().out


@pytest.mark.parametrize("missing_field", ["model", "effort", "tools", "description"])
def test_completeness_check_names_missing_field(
    tmp_path: Path, capsys: pytest.CaptureFixture, missing_field: str
) -> None:
    _build_fixture_repo(tmp_path)
    all_fields = ("model", "effort", "tools", "description")
    _write_agent(
        tmp_path / "agents",
        "foo",
        include_fields=tuple(f for f in all_fields if f != missing_field),
    )
    module = _load_script()

    result = module["main"](["--root", str(tmp_path)])
    output = capsys.readouterr()

    assert result == 1
    assert "agents/foo.md" in output.err
    assert missing_field in output.err


def test_baseline_check_names_missing_tool(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """AC#19: every agent's `tools:` list must be a superset of the fleet
    baseline. A file that narrows below it fails the gate, naming the file
    and the specific missing tool(s) -- rather than passing silently just
    because `tools:` is present.
    """
    _build_fixture_repo(tmp_path)
    (tmp_path / "agents" / "foo.md").write_text(
        (tmp_path / "agents" / "foo.md")
        .read_text()
        .replace(
            'tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "Skill", "Agent"]',
            'tools: ["Read", "Grep", "Glob"]',
        )
    )
    module = _load_script()

    result = module["main"](["--root", str(tmp_path)])
    output = capsys.readouterr()

    assert result == 1
    assert "agents/foo.md" in output.err
    assert "Write" in output.err
    assert "Edit" in output.err
    assert "Bash" in output.err


def test_block_style_tools_rejected_with_distinct_message(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A `tools:` list reformatted to block-style YAML is present, not
    missing -- FIELD_PATTERNS["tools"] only matches flow-style, so without a
    dedicated check this would misreport a valid field as absent. The error
    message must say so distinctly rather than reusing the generic
    "missing required frontmatter field(s)" wording.
    """
    _build_fixture_repo(tmp_path)
    (tmp_path / "agents" / "foo.md").write_text(
        (tmp_path / "agents" / "foo.md")
        .read_text()
        .replace(
            'tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "Skill", "Agent"]',
            "tools:\n  - Read\n  - Write\n  - Edit\n  - Bash\n  - Grep\n  - Glob\n  - Skill\n  - Agent",
        )
    )
    module = _load_script()

    result = module["main"](["--root", str(tmp_path)])
    output = capsys.readouterr()

    assert result == 1
    assert "agents/foo.md" in output.err
    assert "block-style" in output.err
    assert "missing required frontmatter field(s): tools" not in output.err
