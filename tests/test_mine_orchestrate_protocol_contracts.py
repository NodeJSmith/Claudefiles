"""Contract guards for canonical mine-orchestrate protocol files."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("relative_path", "required_anchors"),
    [
        (
            "skills/mine-orchestrate/known-issues-protocol.md",
            [
                ("protocol heading", r"^# Known Issues Protocol$"),
                ("canonical artifact path", r"<feature_dir>/known-issues\.md"),
                (
                    "reason field schema",
                    r"^Reason not fixed now: <faithful-port \| out-of-scope \| behavior-change \| needs-decision \| blocked>$",
                ),
                ("severity gate", r"^## Severity Gate$"),
                (
                    "severity fixer dispatch",
                    r"cfl dispatch severity-fixer --agent-type general-purpose --model sonnet",
                ),
                ("run ID field", r"^Run: <run_id>$"),
                ("entry schema", r"^## Entry Format$"),
                ("gate rule", r"^## Gate Rule$"),
            ],
        ),
        (
            "skills/mine-orchestrate/resume-protocol.md",
            [
                ("protocol heading", r"^# Resume Protocol \(Phase 0\)$"),
                ("run status command", r"^\s*cfl run status\s*$"),
                ("phase advance branch", r"Advance to orchestrate"),
                (
                    "resume choice shape",
                    r"Resume from <next task ID after last_completed>",
                ),
                ("resume command", r"^\s*cfl run resume\s*$"),
                (
                    "resume state fields",
                    r"feature_dir.*tmpdir.*visual_mode.*base_commit.*last_completed.*current_task",
                ),
                ("task path retention", r"actual file path.*task_id"),
                (
                    "stale verdict log check",
                    r'git log --since="<started_at>" --oneline -- <resolved_task_file_path>',
                ),
                ("sketch prior phase", r'phase is `"sketch"`'),
                ("sketch advance", r"advance_from_prior_phase = true"),
                (
                    "sketch stop choice",
                    r"spec remains in sketch phase",
                ),
            ],
        ),
        (
            "skills/mine-orchestrate/SKILL.md",
            [
                ("sketch phase advance", r"define`, `plan`, or `sketch` phase"),
                ("prior phase flag", r"advance_from_prior_phase"),
            ],
        ),
        (
            "skills/mine-orchestrate/visual-reviewer-launch.md",
            [
                ("visual dispatch", r"cfl dispatch visual-reviewer <task_id>"),
                (
                    "visual dispatch telemetry",
                    r"cfl_dispatch_id: <visual_reviewer_dispatch_id>",
                ),
                (
                    "visual dispatch end",
                    r"cfl dispatch end <visual_reviewer_dispatch_id>",
                ),
            ],
        ),
        (
            "skills/mine-orchestrate/spec-fix-loop.md",
            [
                ("protocol heading", r"^# Spec Fix Loop \(Step 10\)$"),
                ("automatic retry budget", r"\*\*If still FAIL after 1 retry\*\*"),
                (
                    "changed-file union",
                    r"changed-files.*deduplicated.*reviewers must see all touched files",
                ),
                ("fixing transition", r"fixing.*reviewing"),
                ("retry gate fix choice", r'label: "Fix review findings"'),
                ("retry gate block choice", r'label: "Mark as blocked and skip"'),
                ("retry gate stop choice", r'label: "Stop here"'),
                ("block command", r"cfl task block <task_id> --reason"),
            ],
        ),
        (
            "skills/mine-orchestrate/wip-commit-protocol.md",
            [
                ("protocol heading", r"^# WIP Commit Protocol \(Step 17\)$"),
                ("done status transition", r"status: done"),
                (
                    "scoped staging",
                    r"--pathspec-from-file=<dir>/<task_id>/committed-files\.txt",
                ),
                ("no broad staging", r"Do \*\*not\*\* use `git add -A`\."),
                (
                    "task verdict command",
                    r"cfl task verdict <task_id> <PASS\|WARN> --commit <SHA from Step 17a>",
                ),
                (
                    "verdict data schema",
                    r"--data.*spec.*code.*integration.*test.*lint.*visual",
                ),
                ("commit SHA capture", r"git rev-parse --short HEAD"),
            ],
        ),
        (
            "skills/mine-orchestrate/agent-routing.md",
            [
                ("routing heading", r"^# Agent Routing Table$"),
                ("routing precedence", r"First match wins"),
                (
                    "routing table columns",
                    r"\| WP content signals \| Use `subagent_type` \|",
                ),
                (
                    "frontend route",
                    r"React, Vue, Angular, CSS.*engineering-frontend-developer",
                ),
                ("backend route", r"FastAPI.*engineering-backend-developer"),
                ("fallback route", r"general-purpose"),
            ],
        ),
    ],
)
def test_protocol_contract_file_contains_required_anchors(
    relative_path: str, required_anchors: list[tuple[str, str]]
) -> None:
    text = (REPO_ROOT / relative_path).read_text()

    missing = [
        label
        for label, pattern in required_anchors
        if re.search(pattern, text, re.MULTILINE) is None
    ]

    assert missing == [], f"{relative_path} is missing contract anchor(s): {missing}"
