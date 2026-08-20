# Context: Mandatory Challenge in Orchestration Workflows

## Problem & Motivation
Challenge is optional at every point it appears in an orchestration workflow, so it gets skipped. The gate that exists to catch design-level problems — wrong approaches, structural fragility, missing edge cases — is the one gate that never runs. When it does run, its findings are written to a `mktemp -d` directory and lost as soon as that directory is cleaned. There is no record of what challenge found, making it impossible to evaluate whether the gate earns its cost or what it catches that other gates miss.

## Visual Artifacts
None.

## Key Decisions
1. Challenge runs at exactly three call sites — design-time in mine-define, design-time in mine-sketch, and ship-time in mine-orchestrate — each mandatory with no option to decline. The three sites use distinct gate types (`define-challenge`, `sketch-challenge`, `ship-challenge`) so telemetry can distinguish them.
2. A shared recipe file (`challenge-gate.md`) owns the invariant and mechanical sequence, following the `comb-gate.md` pattern. Callers supply parameters (gate type, target, critic count) and own site-specific post-resolution handling.
3. Callers record findings to cfl, not challenge itself. Challenge stays free of cfl, keeping it working unchanged for its nineteen non-orchestration callers.
4. The `findings` table is a new cfl schema migration (v7 → v8). `run_id` and `gate_id` are nullable to support future ad-hoc recording. The `source` column is unconstrained TEXT for forward-compatibility with other producers.
5. Ship-time challenge runs at Step 3.5 (after cross-file review, before clean-code), so its edits are absorbed by existing downstream re-review steps without new machinery.
6. `cfl finding record-batch` writes all findings for a gate in a single transaction, replacing the per-finding loop to eliminate partial-write windows.
7. The `--critics=N` flag pins the critic count and takes precedence over both triage defaults and the re-challenge cap. `--re-challenge` replaces dead file-based detection code.

## Constraints & Anti-Patterns
- Do NOT add `challenge` to `KNOWN_GATE_TYPES`. The gate types are `define-challenge`, `sketch-challenge`, and `ship-challenge`.
- Do NOT put a `CHECK` constraint on `findings.source` — the forward-compatibility promise requires it to be unconstrained.
- Do NOT make `mine-challenge` call `cfl`. Recording lives in the callers.
- Do NOT add an `iteration` column to `findings`. `gate_id` discriminates rounds.
- `design_level` is `TEXT` with a `CHECK`, not `INTEGER` — cfl has no boolean columns.
- No compatibility shims for replaced branches — delete "Challenge first" options and file-based detection in the same change that adds their replacements.
- `cli.py` contains no SQL — every command body delegates to the module function.
- `finding` subcommands use named commands (not `.default`) to avoid reopening the `_parse_argv_for_telemetry` special case.

## Design Doc References
- `## Architecture → Where challenge runs` — the three call sites table with position, target, critics, and gate type
- `## Architecture → The shared recipe` — the six-step procedure extracted to `challenge-gate.md`
- `## Architecture → The findings table` — DDL, column rationale, validation tiers
- `## Architecture → The module and command` — module structure modelled on `question.py`
- `## Architecture → Challenge's two flags` — `--critics=N` and `--re-challenge` semantics
- `## Architecture → Validation tiers` — open/closed/free column treatment
- `## Convention Examples` — `record_question` structure, open-vocabulary validation, membership assertions, contract guards, shared gate file parameters

## Convention Examples
### Record function structure — warn tier, error tier, insert, emit

**Source:** `packages/cfl/src/cfl/question.py:61-132`

Body order: docstring stating the warn-versus-exit contract, then warn-tier checks, then error-tier checks, then a single `conn.execute` INSERT, then `cursor.lastrowid`, then `output_module.emit`. A single-row write needs no explicit transaction.

### Open-vocabulary validation — warn but still write

**Source:** `packages/cfl/src/cfl/gate.py:14-37, 63-67`

Module-level `KNOWN_*` frozenset, `emit_warning`, row still written. No DDL `CHECK`.

### Vocabulary membership assertions

**Source:** `packages/cfl/tests/test_gate.py:284-290`

Assert specific canonical values are present in the frozenset.

### Skill-file contract guards

**Source:** `tests/test_mine_orchestrate_protocol_contracts.py:12-38`

Parametrized test with `(relative_path, required_anchors)` where each anchor is `(label, regex)`. The test reads the file and asserts all anchors match.

### Shared gate file — declaring caller-supplied parameters

**Source:** `skills/mine-comb/comb-gate.md:9-17`

Parameters section documents what callers supply, with names, types, and descriptions.
