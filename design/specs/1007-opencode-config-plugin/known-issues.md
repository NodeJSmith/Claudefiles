# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: `check_source_dispatch_patterns()` exceeds the file's own function-size and nesting guidelines

Status: open
Run: 91
Source: clean-code
Reason not fixed now: out-of-scope
Observed in: T03-commit-time-gates.md, T04-shrink-the-script.md (commit b1ff3dc)
Affected files:
- bin/opencode-sync (`check_source_dispatch_patterns()`, currently spanning roughly lines 377-518)

Issue:
The function is ~144 lines including its docstring (~100 lines of executable code) and reaches
roughly 5 levels of nesting in its dispatch-scanning loop (`for subdir_name` -> `for md_file` ->
`for i, line` -> `for match in ...RE.finditer(line)` -> `if name not in known_agents`), exceeding
this repo's own guidance (`rules/common/coding-style.md`: functions under 50 lines, nesting under
4 levels). It grew from ~118 lines at this branch's base commit (e8fab97) to its current size as
T03/T04 folded in the rules-exclusion check, the instruction-directory coverage check, and the
tier_map/variant validation check that FR#8, FR#23, and FR#27 require, on top of the pre-existing
dispatch-name and residual-`model:`-clause checks.

Why deferred:
The function's docstring explains the consolidation is deliberate: check_source_dispatch_patterns()
is now the single caller of find_unmatched_rule_exclusions() and
check_instruction_directory_coverage(), replacing a "shared reporter" function that both this check
and the now-retired installed-file lint used to feed -- the design's own Impact/Changed Files gap
check log records that splitting reporting logic apart previously produced the `_atomic_write_json`
mismatch this design already had to fix once. Restructuring this function (e.g., splitting the
scanning loop into per-concern helpers that still funnel into one `(errors, warnings)` return) is
a legitimate way to bring it under the size/nesting guideline without reopening that shared-reporter
problem, but it touches a security-relevant commit-time gate with 7+ direct tests
(`test_check_source_gate_*` in tests/test_opencode_sync.py) exercising exact line-number and
ordering behavior. That refactor is not named in any of spec 1007's FRs or ACs, so doing it now
would expand this orchestration run beyond its approved scope and risks a subtle behavior change
in a pre-commit gate with no corresponding acceptance criterion to catch a regression.

Recommended follow-up:
A future pass (either a dedicated cleanup task or the next spec that touches this function) should
split check_source_dispatch_patterns() into smaller per-concern helpers (e.g., one for the
per-line dispatch/model-clause scan, one for the rules-tree checks, one for the tier_map/variant
check), each independently testable, with check_source_dispatch_patterns() itself reduced to
calling them and merging the returned (errors, warnings) pairs -- preserving the single shared
return path the current docstring says matters.

Acceptance criteria:
- check_source_dispatch_patterns() (or its replacement entry point) is under 50 lines of
  executable code, excluding docstring.
- No loop in the reworked code exceeds 4 levels of nesting.
- All existing `test_check_source_gate_*` tests in tests/test_opencode_sync.py continue to pass
  unmodified (or are updated only for the new internal function names, not for behavior).
