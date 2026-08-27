"""Contract guards for canonical mine-orchestrate protocol files."""

import os
import re
import subprocess
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
                    r"cfl dispatch severity-fixer --agent-type standard-worker",
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
                    "resume status report",
                    r"Picking up from <next task ID after last_completed>",
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
                    r"feature_dir.*stored `feature_dir`",
                ),
                (
                    "stored run status precedes discovery",
                    r"^\s*cfl run status\s*$",
                ),
                (
                    "missing lint baseline warning",
                    r"Lint baseline from prior session is gone.*not classified as a regression without a valid baseline",
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
                    r"set -o pipefail",
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
                    r"except launch_or_wait_error:[\s\S]*cfl dispatch end <visual_reviewer_dispatch_id>",
                ),
                (
                    "visual primary failure preservation",
                    r"except launch_or_wait_error:[\s\S]*except cleanup_error:[\s\S]*launch_or_wait_error",
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
                ("retry gate retry choice", r'label: "Try again"'),
                (
                    "retry gate block choice",
                    r'label: "Mark as blocked and skip"',
                ),
                (
                    "retry gate stop choice",
                    r'label: "Stop here"',
                ),
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
                    r'git -C <repo_root> diff --cached --quiet -- "\$\{committed_files\[@\]\}"',
                ),
                (
                    "Bash execution contract",
                    r"Run the following block through the Bash tool",
                ),
                (
                    "rename-aware staged path capture",
                    r"git-changed-paths -C <repo_root> --cached",
                ),
                (
                    "rename-aware changed path capture",
                    r"git-changed-paths -C <repo_root> >",
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
                    "failed commit restores status",
                    r"pre-Step-17 status",
                ),
                (
                    "full staged path allowlist",
                    r"full staged\s+path allowlist[\s\S]*old and new paths[\s\S]*`committed-files\.txt`",
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
                    "full branch scope includes working tree",
                    r"(?s)git diff --name-only <base_commit> HEAD.*git diff --name-only HEAD.*git ls-files --others --exclude-standard",
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
                    r"Do not\s+re-review until tests pass or are skipped and lint passes, skips, has no regressions, or has a\s+no valid baseline for regression comparison",
                ),
                (
                    "missing lint baseline is unclassified",
                    r"With a missing baseline or persisted\s+`lint-baseline-unavailable` marker, record `NO BASELINE`",
                ),
                (
                    "shared versus gate handoff",
                    r"^### Shared blocking-review fixer protocol$[\s\S]*Return to the gate-specific re-review instructions above",
                ),
                ("implementation rerun report", r"<dir>/impl-fix/code-review\.md"),
                ("cross-file rerun report", r"<dir>/cross-file/review\.md"),
                (
                    "phase 3 artifact setup",
                    r"mkdir -p <dir>/impl-fix <dir>/cross-file <dir>/final",
                ),
                (
                    "clean-code receives concrete scope",
                    r"The orchestration run's recorded base commit is: <base_commit>",
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
            "skills/mine-orchestrate/retry-prompt.md",
            [
                ("retry heading", r"^# Retry Instructions$"),
                ("feedback heading", r"^## Previous review feedback$"),
                ("retry finding disposition", r"^## Finding Disposition$"),
            ],
        ),
        (
            "skills/mine-orchestrate/contested-criteria.md",
            [
                ("protocol heading", r"^# CONTESTED Criteria Protocol"),
                ("accept option", r'label: "Accept — criterion is met as implemented"'),
                ("reject option", r'label: "Reject — criterion must be satisfied"'),
                ("single retry", r"dispatch one Step 5 retry"),
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
                ("fallback route", r"standard-worker"),
            ],
        ),
        (
            "skills/mine-orchestrate/visual-reviewer-prompt.md",
            [
                (
                    "canonical task sections",
                    r"task's `Prompt` section and `Summary` if present",
                ),
                (
                    "per-scenario infrastructure warning",
                    r"report the scenario as \*\*WARN \[INFRA\]\*\*",
                ),
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


def test_git_changed_paths_handles_staged_rename_and_untracked(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    script = REPO_ROOT / "bin" / "git-changed-paths"

    def run_git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, env=env)

    def run_script(*args: str) -> list[str]:
        result = subprocess.run(
            [str(script), *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        return result.stdout.splitlines()

    run_git("init", "-q")
    (repo / "old.txt").write_text("content\n")
    run_git("add", "old.txt")
    run_git("commit", "-qm", "initial")
    run_git("mv", "old.txt", "new.txt")
    (repo / "extra.txt").write_text("untracked\n")

    # Default mode: worktree diff (the rename, already staged by `git mv`)
    # unioned with the untracked file, deduplicated and sorted.
    assert run_script() == ["extra.txt", "new.txt", "old.txt"]

    # --cached mode: only the staged rename, no untracked files.
    assert run_script("--cached") == ["new.txt", "old.txt"]
