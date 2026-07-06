"""Help epilogues for cfl CLI commands.

Each constant is a help_epilogue string showing usage examples and valid values.
Separated from cli.py to keep the command definitions readable.
"""

from cfl.direct import ENTITY_COLUMNS
from cfl.event import KNOWN_EVENT_NAMES
from cfl.gate import KNOWN_GATE_TYPES

SPEC_INIT = """\
Examples:
  cfl spec init my-feature
  cfl spec init my-feature --number 35"""

SPEC_SET_STATUS = """\
Examples:
  cfl spec set-status approved
  cfl spec set-status abandoned --spec 035"""

RUN_START = """\
Examples:
  cfl run start
  cfl run start --phase define
  cfl run start --phase plan --base-commit abc1234
  cfl run start --visual-mode enabled --dev-server-url http://localhost:3000
  cfl run start --base-commit abc1234 --tmpdir /tmp/cfl-run-42"""

RUN_ADVANCE_PHASE = """\
Examples:
  cfl run advance-phase plan
  cfl run advance-phase orchestrate --base-commit abc1234 --tmpdir /tmp/cfl-run-42
  cfl run advance-phase orchestrate --visual-mode enabled --dev-server-url http://localhost:3000"""

RUN_STOP = """\
Examples:
  cfl run stop --reason "blocked on API design"
  cfl run stop --at-task T03 --reason "need user input"
"""

RUN_RESUME = """\
Examples:
  cfl run resume
  cfl run resume --run-id 7"""

RUN_COMPLETE = """\
Examples:
  cfl run complete
  cfl run complete --pr-url https://github.com/org/repo/pull/42"""

TASK_START = """\
Examples:
  cfl task start T01"""

TASK_UPDATE = """\
Examples:
  cfl task update T01 --status reviewing
  cfl task update T02 --status fixing"""

TASK_VERDICT = """\
Examples:
  cfl task verdict T01 PASS --commit abc1234
  cfl task verdict T02 FAIL --detail "test-gate failed: 3 errors"
  cfl task verdict T01 PASS --data '{"code-review": "PASS", "test-gate": "PASS"}'"""

TASK_BLOCK = """\
Examples:
  cfl task block T03 --reason "depends on external API not yet available"
"""

_GATE_TYPES_LIST = ", ".join(sorted(KNOWN_GATE_TYPES))
GATE = f"""\
Valid gate types: {_GATE_TYPES_LIST}

Examples:
  cfl gate code-review T01 --verdict PASS --detail "no issues"
  cfl gate test-gate T01 --verdict FAIL --detail "2 failures" --data '{{"failures": 2}}'
  cfl gate impl-review --verdict PASS --detail "all specs covered"
"""

_EVENT_NAMES_LIST = ", ".join(sorted(KNOWN_EVENT_NAMES))
EVENT = f"""\
Valid event names: {_EVENT_NAMES_LIST}

Examples:
  cfl event task.contested T01 --detail "reviewer disagrees with approach"
  cfl event task.retried T02 --data '{{"attempt": 2, "reason": "test flake"}}'
  cfl event run.stopped --detail "user requested stop"
"""

EVENT_LIST = """\
Examples:
  cfl event list
  cfl event list --event task.verdict --limit 10
  cfl event list --run 5 --task-id T01"""

DISPATCH = """\
Examples:
  cfl dispatch executor T01 --agent-type engineering-backend-developer --model sonnet
  cfl dispatch reviewer T01 --agent-type code-reviewer --gate-id 5
  cfl dispatch reviewer --agent-type integration-reviewer --routing-reason "Phase 3"
"""

DISPATCH_END = """\
Examples:
  cfl dispatch end 42"""

ARCHIVE = """\
Examples:
  cfl archive
  cfl archive --dry-run
  cfl archive --spec 035"""

_SET_FIELDS_HELP = "\n".join(
    f"  {entity}: {', '.join(sorted(cols))}"
    for entity, cols in sorted(ENTITY_COLUMNS.items())
)
SET = f"""\
Writable fields per entity:
{_SET_FIELDS_HELP}

Examples:
  cfl set run 7 status=stopped
  cfl set task T01 status=executing started_at=null
  cfl set spec 3 status=draft
  cfl set session 1 ended_at=null"""

STOP_ORPHANS = """\
Examples:
  cfl stop-orphans"""

SESSION_END = """\
Examples:
  cfl session end
  cfl session end --reason clear"""

SESSION_COMPACTED = """\
Examples:
  cfl session compacted
  cfl session compacted --context-pct 85"""
