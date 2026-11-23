# REVIEW.md — packages/ado-api/src/ado_api/

The CLI contract every command follows is in the package README
(Conventions section). These questions check a change against it.

## Exit Codes
When an ADO call fails, including for one item of a batch, does the command exit
`EXIT_API_ERROR` (5)? Does a "no" outcome (refused, failed build, timeout, declined
prompt) exit `EXIT_FAILURE` (1)? Trace each `sys.exit` and every early `return`. A
command that made several checks should combine them with `combined_exit_code`, and
watch/wait should use `watch_exit_code`/`wait_exit_code`, not a new rule.

## stdout Under --json
With `--json`, is the only thing on stdout one `json_output` call, printed after any
prompt? Check per-item lines (`print_result(..., as_json=)`), tables, hints and
warnings. A bare `print()` without `file=sys.stderr` is the usual leak.

## Sibling Parity for Commands That Change Things
Does a new or changed command that acts on several builds, threads or work items show
its plan, call `confirm_or_exit(..., yes=)`, and support `--dry-run`, like `builds
cancel` and `retry-stage`? If it skips the prompt, is the reason documented next to
`pr resolve` in the reference? Does a per-item failure print `Failed <thing> <id>: <error>`
to stderr and let the batch continue?

## JSON Shape
Does a record the CLI builds subclass `formatting.Record`, so its keys come out
camelCase, while raw ADO objects pass through untouched? Is its per-item result called
`status`, with lowercase values, like `CancelRecord`, `ThreadResolution` and
`WorkItemLink`? Does the reference's "Release JSON" list still match it?

## Flags
Does a flag that several commands share come from `cli/params.py` (`YesParam`,
`DryRunParam`, `PipelineParam`, `DefaultBranchParam`…) rather than a local
`Parameter(...)` under the same name? Is a list argument capped with
`validate_item_limit`?
