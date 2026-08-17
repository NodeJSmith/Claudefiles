# Context: Named Agents as the Single Dispatch Concept

## Problem & Motivation

Shared skills, agents, and commands hardcode Claude Code's subagent dispatch ABI: a dispatch is written as `subagent_type` naming a generic agent plus a separate `model:` tier clause, across six different prose shapes. This couples shared content to one harness's tool signature, forces `bin/opencode-sync` to carry a whole dispatch-rewriting translation layer (five regexes, three of them using Python-only conditional groups), and contradicts the project's own target architecture, in which Claude Code is supposed to be one adapter among two rather than the native format. Compounding it, agent metadata is declared in three places at once — each agent's frontmatter, `rules/common/performance.md`'s list, and `install.py`'s per-bundle tuples — with `bin/lint-agent-models` existing solely to keep them in sync. This work makes the agent the single dispatch concept: every dispatch names a real agent file, model tier lives in that file's frontmatter, and the other two declaration sites become generated artifacts.

## Visual Artifacts

None.

## Key Decisions

1. **A dispatch names an agent — nothing else.** No roles, no mapping tables, no tier vocabulary at call sites, no per-call model parameter. Both harnesses resolve an agent name to a file in `agents/` identically, confirmed by source read of OpenCode v1.18.18 (`packages/opencode/src/config/agent.ts:11-32`, `config.ts:460-461`, `agent/agent.ts:267-294`).

2. **Two workers, named for what they are, not nine intent agents.** An earlier draft proposed `triager`, `analyzer`, `critic`, `synthesizer`, `ideator`, `judge`, `reviewer`, `writer`, `implementer`. Reading every site's actual model clause showed that roster was a model-tier partition wearing verbs: the haiku sites were exactly `triager` ∪ `analyzer`, the sonnet sites exactly everything else, with no exceptions. So the roster is `light-worker` (haiku) and `standard-worker` (sonnet). Tradeoff accepted: tier-shaped names "weld role to model," which only bites when there is a role to retune — and at these sites there is not, since every one assembles its full prompt at dispatch time.

3. **The bar for a new agent is the body, and only the body.** Does an invariant methodology exist that every caller of this name would rely on and none would contradict? Caller count is evidence, not a gate: `analyzer` had four callers and failed (their methodologies contradicted each other); `spec-reviewer` has one caller and passes (126 self-contained lines the caller re-derives none of).

4. **Frontmatter is authoritative; generation runs outward.** Agent files are hand-written in full — neither frontmatter nor body is generated. `rules/common/performance.md`'s agent list and `install.py`'s bundle tuples are generated from frontmatter. The reverse direction was rejected as lossy: a whole-block frontmatter generator erases the trailing `model:` rationale comments thirteen of twenty-three agent files carry (three of them explicit safety-gate warnings) and drops the `color:`/`emoji:`/`vibe:` keys six files carry outside the five-field schema.

5. **Escalation is removed, not ported.** `mine-orchestrate`'s "Try again with stronger model" exists only because OpenCode has no per-call model override, which forced generated `-opus` variants. Tradeoff accepted explicitly by the user: no recovery path remains for a task failing review repeatedly.

6. **Tool lists are widened fleet-wide.** This overrides two roadmap invariants and costs `secrets-auditor` its read-only guarantee specifically. Accepted because the restriction was largely fiction already — `code-reviewer` declares no `Write` yet is instructed to write a report, which it can only do through `Bash`.

7. **Promotion may change a site's model tier, and that is accepted.** Where an existing specialist covers a site's intent, the site dispatches that specialist even if its pinned model differs from what the site runs at today. Every such change is recorded individually in the design's Dependencies and Assumptions rather than riding silently.

## Constraints & Anti-Patterns

- **Do not introduce a per-harness mapping table.** It would reintroduce the two-source drift this work exists to remove.
- **Do not migrate prose shapes for their own sake.** The six structural dispatch shapes (YAML block, function-call, inline prose, list item, heading, table cell) stay as shapes. Only their *content* changes: an agent name, no model clause. Restructuring prose beyond that risks Claude Code regressions for no gain.
- **Do not generate any part of an agent file.** Both frontmatter and body are hand-written.
- **Do not preserve `-opus` variants in any form.**
- **Do not create an agent for a dispatch intent.** A verb describing what a dispatch does is not a role. If there is no invariant body every caller would rely on, it names a worker and keeps its prompt at the call site.
- **Do not strip `model:` from an agent's own frontmatter.** That line is the declaration site FR#7 requires. Only *dispatch-site* model clauses are removed. Twenty-two of the twenty-three files in `agents/` match a naive `model:` grep on their frontmatter alone and contain no dispatch at all — `agents/researcher.md` is the only agent file with real dispatches in its body.
- **Non-goals:** the OpenCode `config()` plugin (spec 1007), Track 1 hook injection, `oh-my-opencode-slim` adoption, the `experimental.*` hook surface, executing KI-002 (#500) or KI-003 (#501), and the `customAppendPrompt` pattern.
- Per repo rules: no `from __future__ import annotations`, `X | None` over `Optional[X]`, no lazy imports, `whenever` over stdlib `datetime` if any date handling arises.

## Design Doc References

Design doc: `design/specs/1008-opencode-named-roles/design.md`

- **## Problem** — the three concrete costs of the current coupling, and the authoritative scoping grep (AC#2's pattern, not the two characterizing greps).
- **## Functional Requirements** — FR#1–18, FR#20–29. Note FR#19 was cut; the numbering gap is deliberate.
- **## Edge Cases** — what each check catches, and the one case deliberately left uncaught (cross-bundle dispatch).
- **## Acceptance Criteria** — AC#1–11, AC#13–28. AC#12 was cut with FR#19.
- **## Key Constraints** — the five hard rules, including the body-only bar for creating an agent.
- **## Dependencies and Assumptions** — every accepted risk and tier change, with its mitigation. Read before accepting any new tier change.
- **## Architecture** — "One concept: the agent", "The new agents" (including why the nine-agent roster was rejected), "The declaration site", and "What leaves `bin/opencode-sync`" — the last is the authoritative deletion analysis, including the symbols that look dead but survive.
- **## Implementation Preferences** — generator shape, prek wiring, generated-region markers, and the preference for extending `bin/lint-agent-models` over a new script.
- **## Replacement Targets** — per-symbol disposition table: remove outright vs rewrite vs migrate.
- **## Convention Examples** — copied verbatim below.
- **## Test Strategy** — required test types, existing tests to adapt, new coverage, tests to remove.
- **## Smoke Test** — two scenarios for the generator and the dispatch hook.
- **## Documentation Updates** — the doc set that must follow the change.
- **## Impact** — changed files, behavioral invariants, blast radius.

## Convention Examples

### Testing a `bin/` script

**Source:** `tests/test_opencode_variant_audit.py`

```python
import runpy
import pytest

def _load_script() -> dict:
    ...

@pytest.mark.parametrize(
    "variant,expected_resolved",
    [...],
)
def test_classify_verdicts(variant: str | None, expected_resolved: bool) -> None:
    ...

def test_fetch_honors_cutoff(tmp_path: Path) -> None:
    ...
```

`bin/` scripts are `uv run --script` files with no importable module, so tests load them via `runpy`. Parametrized cases plus `tmp_path` for filesystem fixtures.

### Docstrings explain why, cite sources, and warn against reverting

**Source:** `bin/opencode-sync:1080-1102`

```python
def build_instructions(config_dir: Path) -> list[str]:
    """Build the `instructions` list of config.json: the synced shared rules.

    Without this, the rules opkg installs under `<config>/rules/` are inert.
    OpenCode discovers global instructions from exactly two places
    (session/instruction.ts): its `instructions` config array, and the first
    existing entry of `[<config>/AGENTS.md, ~/.claude/CLAUDE.md]` -- note the
    `break`, so a present AGENTS.md means the Claude file is never read
    either. Nothing globs `<config>/rules/`.

    One glob per directory, never `**`: for an absolute path OpenCode globs
    only `basename(pattern)` within `dirname(pattern)`, so a recursive
    pattern silently matches nothing. [...]
    """
```

(Excerpted — the full docstring also cross-references `check_instruction_globs()` and explains why paths derive from `config_dir` rather than the module constant.)

Non-obvious behavior gets its upstream source cited by file and symbol, the failure mode named, and the wrong-looking-but-correct choice defended so it survives future cleanup.

### Wiring a check as a pre-commit hook

**Source:** `prek.toml:114-121`

```toml
[[repos.hooks]]
id = "lint-opencode-sync"
name = "OpenCode dispatch pattern coverage"
entry = "bin/opencode-sync --check-source"
language = "system"
pass_filenames = false
always_run = true
stages = ["pre-commit"]
```

### Marking generated content

**Source:** `bin/opencode-sync:189`

```python
GENERATED_FILE_MARKER = "<!-- GENERATED BY opencode-sync -- DO NOT EDIT MANUALLY. -->"
```

## Repo Facts (verified during planning)

- **Test command:** `mise run test:root` runs `pytest tests/` for repo-level tests. CI (`.github/workflows/test.yml`) runs `prek run --all-files --stage pre-commit` and `mise run 'test:*'`.
- **Test files under `tests/`:** `test_context_tier.py`, `test_hooks.py`, `test_install.py`, `test_lint_agent_files.py`, `test_lint_verdict_line.py`, `test_mine_orchestrate_protocol_contracts.py`, `test_opencode_sync.py`, `test_opencode_variant_audit.py`. There is no `test_lint_agent_models.py` — that script is currently untested.
- **Agent count:** 23 files in `agents/`.
- **Dispatch-migration surface:** 31 files — 28 under `skills/`, 2 under `commands/`, plus `agents/researcher.md`. A naive union grep returns 53 because 22 agent files match on their own frontmatter `model:` line; those are declaration sites, not dispatches.
- **Verified counts:** `grep -rl 'general-purpose' skills skills-cli skills-impeccable commands agents` → 25 files. Nine `Explore` dispatch sites across `agents/researcher.md` (4), `skills/mine-eval-repo/SKILL.md` (3), `skills/mine-prior-art/SKILL.md` (1), `commands/mine-issues.md` (1). `cfl dispatch --model` appears in 9 files, 32 occurrences.
- **Every `bin/opencode-sync` line anchor in Replacement Targets was spot-checked and resolves to the named symbol.**
