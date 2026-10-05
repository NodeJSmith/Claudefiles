"""Every skill, command and agent frontmatter block parses as strict YAML.

The harness reads `description:` from frontmatter to route requests, so a
block that doesn't parse can silently drop a skill from routing.
`bin/lint-agent-files` checks required fields with a lightweight reader that
tolerates malformed quoting, so this is the strict check.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

FILES = sorted(
    [
        *(REPO_ROOT / "skills").glob("*/SKILL.md"),
        *(REPO_ROOT / "commands").glob("*.md"),
        *(REPO_ROOT / "agents").glob("*.md"),
    ]
)


def _frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else None


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_frontmatter_is_valid_yaml(path: Path) -> None:
    block = _frontmatter(path.read_text())
    if block is None:
        pytest.skip("no frontmatter")
    assert isinstance(yaml.safe_load(block), dict)
