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
                    "stored feature directory propagation",
                    r"set `feature_dir` to the status response's stored `feature_dir`.*carry that value into Phase 0",
                ),
                (
                    "skip fresh task discovery",
                    r"Do not perform most-recent-task discovery",
                ),
                (
                    "missing lint baseline warning",
                    r"Lint baseline from prior session is gone.*nonzero lint exit will block fixer re-review",
                ),
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
                (
                    "unspecified target fallback",
                    r"target_files: unspecified[\s\S]*targets: unspecified",
                ),
                (
                    "portable test and lint pipeline status",
                    r"set -o pipefail[\s\S]*preserves a failing lint status",
                ),
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
                (
                    "visual dispatch failure cleanup",
                    r"cleanup is mandatory on every exit path",
                ),
                (
                    "visual primary failure preservation",
                    r"cleanup failure must never replace\s+the original launch/wait error",
                ),
                (
                    "executor result visual field",
                    r"extract the `\*\*Visual verification:\*\*`\s+field/block from its `## Task result`",
                ),
                (
                    "visual prompt output source",
                    r"<the \*\*Visual verification:\*\* field/block from the executor's ## Task result>",
                ),
                (
                    "visual mode short circuit",
                    r"visual_mode.*not.*enabled.*Visual.*SKIPPED",
                ),
                (
                    "missing screenshot fallback",
                    r"(?s)no `\.png` files.*Executor reported all scenarios as SKIPPED",
                ),
                (
                    "infrastructure warning fallback",
                    r"(?s)WARN \[INFRA\].*visual verification.*inconclusive",
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
                (
                    "scoped cached diff",
                    r"git -C <repo_root> diff --cached --quiet --pathspec-from-file=<dir>/<task_id>/committed-files\.txt",
                ),
                (
                    "no changes scope",
                    r"Do not use repo-wide `git status` to make this decision",
                ),
                ("no broad staging", r"Do \*\*not\*\* use `git add -A`\."),
                (
                    "task verdict command",
                    r"cfl task verdict <task_id> <PASS\|WARN> --commit <SHA from Step 17a\|no-changes>",
                ),
                (
                    "verdict data schema",
                    r"--data.*spec.*code.*integration.*test.*lint.*visual",
                ),
                ("commit SHA capture", r"git rev-parse --short HEAD"),
                (
                    "commit failure blocks task",
                    r"cfl task block <task_id> --reason \"WIP commit failed: <error>\"",
                ),
                (
                    "full staged path allowlist",
                    r"full staged path\s+set.*exactly match `committed-files\.txt`",
                ),
                (
                    "unexpected staged paths block",
                    r"unexpected staged paths.*block the task",
                ),
            ],
        ),
        (
            "skills/mine-orchestrate/findings-fix-loop.md",
            [
                (
                    "fingerprint section",
                    r"^### Content fingerprint \(no-op detection\)$",
                ),
                (
                    "checked untracked enumeration",
                    r"git ls-files --others --exclude-standard -z >\"\$untracked\" \|\| exit 1",
                ),
                (
                    "fingerprint capture fail closed",
                    r"If either capture exits non-zero",
                ),
                (
                    "no-op route",
                    r"(?i)no-op short-circuit.*classify-mode terminal pass",
                ),
                (
                    "classify-only behavior",
                    r"\*\*This is a classify-only pass\. Apply no code changes\.\*\*",
                ),
            ],
        ),
        (
            "skills/mine-orchestrate/post-execution-pipeline.md",
            [
                (
                    "phase 3 foreground dispatch contract",
                    r"(?s)Phase 3 subagents always run in the foreground.*cfl_dispatch_id",
                ),
                (
                    "phase 3 failure cleanup",
                    r"always attempt its matching `cfl dispatch end` on success or failure",
                ),
                (
                    "implementation fixer reviewer lifecycle",
                    r"(?s)cfl dispatch impl-fix-code-reviewer.*cfl dispatch impl-fix-integration-reviewer.*cfl_dispatch_id: <impl_fix_code_reviewer_dispatch_id>.*cfl_dispatch_id: <impl_fix_integration_reviewer_dispatch_id>.*cfl dispatch end <impl_fix_code_reviewer_dispatch_id>.*cfl dispatch end <impl_fix_integration_reviewer_dispatch_id>",
                ),
                (
                    "implementation review rerun lifecycle",
                    r"(?s)cfl_dispatch_id: <impl_review_rerun_dispatch_id>.*cfl dispatch impl-review-rerun.*cfl dispatch end <impl_review_rerun_dispatch_id>",
                ),
                (
                    "cross-file rerun dispatch lifecycle",
                    r"(?s)cfl dispatch cross-file-reviewer-rerun.*cfl_dispatch_id: <cross_file_reviewer_rerun_dispatch_id>.*cfl dispatch end <cross_file_reviewer_rerun_dispatch_id>",
                ),
                (
                    "implementation blocking gate",
                    r"If impl-review returns FAIL.*prompt the user",
                ),
                (
                    "blocking fixer reviewer gate",
                    r"Do not\s+re-review until tests pass or are skipped and lint passes,\s+skips, has no regressions, or has a\s+missing baseline with a zero exit",
                ),
                (
                    "missing lint baseline fails closed",
                    r"With a missing baseline, a zero lint exit passes\s+but any nonzero exit blocks re-review",
                ),
                (
                    "shared versus gate handoff",
                    r"shared protocol owns only fixer lifecycle and verification:[\s\S]*Each gate\s+still owns its own re-review",
                ),
                (
                    "real suggestion definition",
                    r"A real suggestion identifies a concrete defect, risk, or actionable\s+improvement",
                ),
            ],
        ),
        (
            "skills/mine-orchestrate/verdict-line-format.md",
            [
                (
                    "last verdict extraction",
                    r"Consumers take the \*\*last line matching\*\*",
                ),
                (
                    "concise return activation",
                    r"Activated when \*\*both\*\* conditions hold",
                ),
                (
                    "concise output behavior",
                    r"Return \*\*only the canonical verdict line\*\*",
                ),
            ],
        ),
        (
            "skills/mine-orchestrate/implementer-prompt.md",
            [
                ("executor result heading", r"^## Task result$"),
                ("executor verify heading", r"^\*\*Verify section:\*\*$"),
                ("executor visual heading", r"^\*\*Visual verification:\*\*$"),
                (
                    "executor verdict schema",
                    r"\*\*Verdict:\*\* PASS \| FAIL \| BLOCKED",
                ),
                (
                    "canonical skip sentinels",
                    r"`no test suite` and `no lint tools` are valid orchestrator decisions",
                ),
                (
                    "verbatim visual skip reason",
                    r"exact reason from the orchestrator's Visual verification status, verbatim",
                ),
            ],
        ),
        (
            "skills/mine-orchestrate/tdd.md",
            [
                (
                    "tdd skip sentinels",
                    r"`no test suite` and\s+`no lint tools` are canonical skip sentinels",
                ),
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
        (
            "skills/mine-orchestrate/visual-reviewer-prompt.md",
            [
                (
                    "canonical task sections",
                    r"task's `Prompt` section and `Summary` if present",
                )
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
