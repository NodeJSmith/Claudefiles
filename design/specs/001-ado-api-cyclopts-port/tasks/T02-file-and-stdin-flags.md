---
task_id: "T02"
title: "Re-apply --body-file / --description-file (with stdin) on the cyclopts CLI layer"
status: "done"
depends_on: ["T01"]
implements: ["FR#4", "FR#5"]
---

## Target Files

- modify: `packages/ado-api/src/ado_api/cli/commands/pr.py`
- modify: `packages/ado-api/src/ado_api/cli/commands/work_item.py`
- create: `packages/ado-api/tests/test_file_args.py`

## Prompt

The version of `ado-api` this repo just replaced had a feature the replacement lacks entirely: every
command taking a body or description could read it from a file instead, with `-` meaning stdin. That
matters because the main caller is an AI agent writing multi-line markdown PR bodies, which are
awkward and error-prone as shell arguments. Re-apply it on the new cyclopts surface.

Read `tasks/context.md` and `design.md` in this spec directory first — the design's "Grafting the
file flags onto cyclopts" section tables all six sites and is authoritative.

Task T01 already restored the helper this task consumes: `resolve_file_text()` in
`packages/ado-api/src/ado_api/cli/context.py`. Read it before starting. Its signature already covers
every case here (`required=`, `inline_name=`) — use it as-is rather than reimplementing or extending
it. It prints to stderr and raises `SystemExit` itself, so callers need no try/except.

### The six sites

In `cli/commands/pr.py`:

| Function | Inline param | Add | Required? |
|---|---|---|---|
| `cli_pr_create` | `description` (keyword) | `--description-file` | no |
| `cli_pr_update` | `description` (keyword) | `--description-file` | no |
| `cli_pr_work_item_create` | `description` (keyword) | `--description-file` | no |
| `cli_pr_thread_add` | `body` (required keyword) | `--body-file` | yes |
| `cli_pr_reply` | `body` (required **positional**) | `--body-file` | yes |

In `cli/commands/work_item.py`:

| Function | Inline param | Add | Required? |
|---|---|---|---|
| `cli_work_item_create` | `description` (keyword) | `--description-file` | no |

These modules are a thin parse-and-dispatch layer over `ado_api/commands/*.py`. Keep them that way:
add the parameter, call `resolve_file_text`, pass the resolved value down. **Do not** change anything
under `ado_api/commands/` — the business-logic functions already take a plain string and need no
knowledge that it came from a file.

### The two required sites need parser changes

`cli_pr_thread_add`'s `body` and `cli_pr_reply`'s positional `body` are currently required at the
parser level. If they stay required, `--body-file` can never be used alone. Each must become optional
in the signature, with `resolve_file_text(..., required=True)` enforcing "exactly one of the two"
afterward.

`cli_pr_reply` is the awkward one: `body` is a positional following two other required positionals
(`pr_id`, `thread_id`). Pass `inline_name="<body>"` so the conflict and missing-value errors read
`<body> and --body-file` rather than naming a `--body` flag that does not exist. Verify the resulting
positional arrangement actually parses under cyclopts — an optional positional after required ones is
the kind of thing worth confirming by running it, not by reading the signature.

### Do not regress the leading-hyphen fix

Several of these params carry `Parameter(allow_leading_hyphen=True)` in the code T01 brought over.
That is a deliberate upstream fix letting a body or description begin with `-`. Keep it on every
param that has it.

### Tests

Write `packages/ado-api/tests/test_file_args.py` covering the CLI surface (invoke through the app
entry point the existing `tests/test_integration.py` uses, so the tests exercise real argument
parsing rather than calling the handler functions directly). Follow the conventions in the existing
test files — mock at the `ado_api.commands.*` boundary and assert on what the CLI layer passed down.

Cover, for all six commands:
- the file's contents reach the underlying `cmd_*` function
- passing both the inline value and the file flag exits non-zero, with an error naming both
- omitting both, on the two required sites, exits non-zero

And once per flag family (`--body-file`, `--description-file`):
- `-` reads stdin

## Verify

- [ ] FR#4 / AC#5: `ado-api pr create --help`, `pr update --help`, `pr thread-add --help`, `pr reply --help`, `pr work-item-create --help`, and `work-item create --help` each show their file flag.
- [ ] FR#4 / AC#5: `tests/test_file_args.py` proves file contents reach the `cmd_*` function for all six commands, and proves `-` reads stdin for at least one `--body-file` and one `--description-file` command.
- [ ] FR#5 / AC#6: for each of the six commands, a test proves that passing both the inline value and the file flag exits non-zero with an error naming both.
- [ ] FR#5 / AC#6: for `pr thread-add` and `pr reply`, a test proves that omitting both exits non-zero.
- [ ] `pr reply`'s conflict error names `<body>`, not `--body`.
- [ ] `uv run --project packages/ado-api pytest` passes with zero failures.
- [ ] `git diff --stat packages/ado-api/src/ado_api/commands/` is empty — the business-logic layer was not touched.
- [ ] Every `allow_leading_hyphen=True` present before this task is still present: compare against `git show HEAD:packages/ado-api/src/ado_api/cli/commands/pr.py`.
