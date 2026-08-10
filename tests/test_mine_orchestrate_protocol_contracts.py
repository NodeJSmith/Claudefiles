"""Contract guards for canonical mine-orchestrate protocol files."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("relative_path", "required_snippets"),
    [
        (
            "skills/mine-orchestrate/known-issues-protocol.md",
            [
                "<feature_dir>/known-issues.md",
                "Reason not fixed now: <faithful-port | out-of-scope | behavior-change | needs-decision | blocked>",
                "cfl dispatch severity-fixer --agent-type general-purpose --model sonnet",
                "Run: <run_id>",
            ],
        ),
        (
            "skills/mine-orchestrate/resume-protocol.md",
            [
                "cfl run status",
                "Advance to orchestrate",
                "Resume from <next task ID after last_completed>",
                "cfl run resume",
                'git log --since="<started_at>" --oneline -- <feature_dir>/tasks/<task_id>.md',
            ],
        ),
        (
            "skills/mine-orchestrate/spec-fix-loop.md",
            [
                "attempt one automatic fix before escalating to the user",
                "Union** the new changed-files with the original run's changed-files",
                "Fix review findings",
                "Mark as blocked and skip",
                "Stop here",
            ],
        ),
        (
            "skills/mine-orchestrate/wip-commit-protocol.md",
            [
                "Update the task file frontmatter to `status: done` before committing.",
                "--pathspec-from-file=<dir>/<task_id>/committed-files.txt",
                "Do **not** use `git add -A`.",
                "cfl task verdict <task_id> <PASS|WARN> --commit <SHA from Step 17a>",
            ],
        ),
        (
            "skills/mine-orchestrate/agent-routing.md",
            [
                "**First match wins**",
                "| React, Vue, Angular, CSS, frontend components, UI implementation | `engineering-frontend-developer` |",
                "If the WP does not clearly match a row, use `general-purpose`.",
            ],
        ),
    ],
)
def test_protocol_contract_file_contains_required_snippets(
    relative_path: str, required_snippets: list[str]
) -> None:
    text = (REPO_ROOT / relative_path).read_text()

    missing = [snippet for snippet in required_snippets if snippet not in text]

    assert missing == [], f"{relative_path} is missing contract snippet(s): {missing}"
