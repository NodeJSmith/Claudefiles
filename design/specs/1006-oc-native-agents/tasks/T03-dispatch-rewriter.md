---
task_id: "T03"
title: "Implement dispatch rewriter and model remap"
status: "done"
depends_on: ["T02"]
implements: ["FR#4", "FR#5", "FR#9", "FR#14", "FR#15", "AC#5", "AC#6", "AC#9", "AC#11", "AC#16", "AC#17"]
---

## Summary

Implement the dispatch rewriter that transforms Claude Code dispatch patterns in synced skill, command, and agent body files into OpenCode-native equivalents. This covers seven documented cases plus a bare-dispatch default: replacing `subagent_type: general-purpose` + `model: sonnet/haiku` with named workers, stripping `model:` from named agent dispatches, mapping Claude Code built-in types to lowercase OpenCode equivalents, and handling bare `general-purpose` dispatches with no model clause. Also implements the anchored model remap for agent frontmatter as a separate pass.

## Target Files

- modify: `bin/opencode-sync` — add dispatch rewriter functions, model remap function, wire into main()
- read: `skills/mine-brainstorm/SKILL.md` — example of `subagent_type: general-purpose`, `model: sonnet` pattern
- read: `skills/mine-decompose/SKILL.md` — example of `subagent_type: general-purpose`, `model: haiku` pattern
- read: `skills/mine-how/SKILL.md` — example of inline Agent() call pattern
- read: `skills/mine-orchestrate/known-issues-protocol.md` — example of `cfl dispatch --agent-type general-purpose --model sonnet` pattern
- read: `skills/mine-review/SKILL.md` — example of named agent type (`code-reviewer`) dispatch

## Prompt

Add the dispatch rewriter to `bin/opencode-sync`, filling in the T03 stub points from T01. The rewriter is implemented as **two token-extraction passes** feeding **one shared `resolve()` function** backed by TIER_MAP (defined in T02). The seven documented cases are real input shapes, not seven separate code paths.

### Core resolve function

`resolve(agent_type: str, model_tier: str | None) -> tuple[str, str | None]`

Takes the extracted `subagent_type` value and optional `model` tier name. Returns `(new_agent_type, new_model_or_none)` where `new_model_or_none` is None (meaning strip the model clause) or a replacement value.

Logic:
1. **Claude Code built-in mapping** — if `agent_type` is one of `general-purpose`, `Explore`, `Plan`, `claude`:
   - `general-purpose`: look up `model_tier` in TIER_MAP (default to `"sonnet"` if None per FR#15). If `TIER_MAP[tier]["worker"]` is `None` (e.g. `opus`), return a sentinel meaning "leave this line unmodified" — the caller must skip the rewrite for that match, leaving the original line intact so the lint catches it as a residual pattern (per the "Unmapped tier" edge case in the design doc).  Otherwise return `(TIER_MAP[tier]["worker"], None)`.
   - `Explore` → `("explore", None)`, `Plan` → `("plan", None)`, `claude` → `("general", None)`.
2. **Named agent** (anything else, e.g. `code-reviewer`): return `(agent_type, None)` — keep the type, strip the model.

### Pass 1: Prose and YAML dispatch patterns

`rewrite_dispatches_prose(content: str) -> str`

Handles Patterns 1–4 and Cases 6–7 from the design doc. Uses regex to find lines containing `subagent_type` (or backtick-quoted type references) paired with `model:` on the same or adjacent line. Extract the agent type and model tier, call `resolve()`, and rebuild the line with the new type and no model clause.

Pattern shapes to match (all from real skill files):
- `Agent(subagent_type: "general-purpose", model: "sonnet")` → `Agent(subagent_type: "worker-standard")`
- `` Launch a `general-purpose` subagent with `model: sonnet` `` → `` Launch a `worker-standard` subagent ``
- `` (`subagent_type: "general-purpose"`, `model: sonnet`) `` → `` (`subagent_type: "worker-standard"`) ``
- `subagent_type: general-purpose, model: sonnet` → `subagent_type: worker-standard`
- `subagent_type: "code-reviewer", model: sonnet` → `subagent_type: "code-reviewer"` (strip model only)
- `subagent_type: Explore, model: haiku` → `subagent_type: explore` (built-in mapping)

**Word-boundary anchoring** (FR#14): built-in name matches must be word-boundary anchored. `claude` must never match `claude-code-guide`. `Plan` must never match `Planner` or prose uses of "planning". Use `\b` word boundaries in regex patterns for built-in names.

Also handle standalone built-in references without a `model:` clause: `subagent_type: Explore` → `subagent_type: explore`, `subagent_type: "claude"` → `subagent_type: "general"`, etc. These don't need `resolve()` — they're direct case-mapping.

### Pass 2: cfl dispatch CLI patterns

`rewrite_dispatches_cli(content: str) -> str`

Handles Pattern 5 from the design doc. Find `--agent-type general-purpose --model sonnet` (or haiku) and rewrite to `--agent-type worker-standard` (or worker-lightweight), removing the `--model` flag. Also handle `--agent-type general-purpose` with no `--model` (bare dispatch → `--agent-type worker-standard` per FR#15).

### Bare dispatch handling (FR#15)

`subagent_type: general-purpose` with no `model:` clause on the same or adjacent line rewrites to `subagent_type: worker-standard`. This mirrors the Claude Code default where the model-default hook injects sonnet for model-less `general-purpose` dispatches.

### Model remap (agent frontmatter only)

`remap_agent_models(agents_dir: Path, dry_run: bool) -> int`

Separate pass that runs after dispatch rewrite. Reads each `.md` file in `agents_dir`, finds the frontmatter block (between the first two `---` markers), and replaces Claude tier names in `model:` lines with provider-qualified model IDs from TIER_MAP. **Must handle trailing inline comments** — most agent files have lines like `model: sonnet  # claude-sonnet-5 as of 2026-07-07 — do not downgrade; pre-commit safety gate`. Match `model: <tier>` at line start with optional trailing content (whitespace + `#` comment), replace only the tier name while preserving the comment. Does not touch body content — the dispatch rewriter already handled body content. Returns count of files modified.

### Orchestration function

`rewrite_all_dispatches(config_dir: Path, dry_run: bool) -> int`

Applies `rewrite_dispatches_prose` and `rewrite_dispatches_cli` to every `.md` file under `config_dir/skills/`, `config_dir/commands/`, and `config_dir/agents/` (body content only — frontmatter excluded for agent files). For agent files, split at the second `---` marker: leave frontmatter untouched, apply rewriters to body only. Returns count of files modified.

### Wire into main()

1. Call `rewrite_all_dispatches()` at the T03 dispatch-rewrite stub point (after color strip, before model remap).
2. Call `remap_agent_models()` at the T03 model-remap stub point (after dispatch rewrite, before worker generation).
3. In dry-run mode, show what would be rewritten.

The pipeline order per the design: opkg install → color strip → dispatch rewrite (skills + commands + agent bodies) → model remap (agent frontmatter only, anchored) → worker agent generation → config.json generation → lint.

## Focus

- The rewriter must handle multi-line dispatch blocks. Some skills put `subagent_type:` and `model:` on adjacent lines, not the same line. Check for `model:` on the line immediately following a `subagent_type:` match.
- Real examples from the codebase:
  - `skills/mine-brainstorm/SKILL.md` line 66: `subagent_type: general-purpose`, `model: sonnet` on the same line
  - `skills/mine-decompose/SKILL.md` line 42: `subagent_type: general-purpose`, `model: haiku` inline
  - `skills/mine-how/SKILL.md` line 69: `Agent(subagent_type: "general-purpose", model: "sonnet")`
  - `skills/mine-orchestrate/known-issues-protocol.md` line 88: `cfl dispatch ... --agent-type general-purpose --model sonnet`
  - `skills/mine-review/SKILL.md` line 41: `subagent_type: "code-reviewer"` (named agent, no model to strip on this particular line — but other named dispatches may have inline `model:`)
- The model remap only needs to handle the three Claude tier names (`sonnet`, `haiku`, `opus`) in anchored frontmatter `model:` lines. After opkg installs the agents, their frontmatter still has Claude tier names — this pass converts them to provider-qualified IDs. **Critical:** 12 of 13 agent files have trailing inline comments on their `model:` line (e.g., `model: sonnet  # claude-sonnet-5 as of 2026-07-07 — do not downgrade; pre-commit safety gate`). A regex matching `^model: sonnet$` (end-of-line anchor) will silently skip these. Use a pattern like `^model:\s*<tier>\b(.*)$` to capture and preserve the trailing content.
- Agent body content may contain `model:` in prose/examples (e.g., explaining what model to use). The dispatch rewriter handles these via pattern matching; the model remap must NOT touch body content or it would corrupt prose.
- The `resolve()` function is the single routing decision point — both passes call it. This is the architectural invariant from Key Constraints.

## Verify

- [ ] FR#4: After sync, `grep -r 'subagent_type.*general-purpose' ~/.config/opencode/skills/ ~/.config/opencode/commands/ ~/.config/opencode/agents/` returns zero matches
- [ ] FR#5: After sync, `grep -r '\-\-agent-type general-purpose' ~/.config/opencode/skills/ ~/.config/opencode/commands/ ~/.config/opencode/agents/` returns zero matches
- [ ] FR#9: Named agent dispatches (e.g. `code-reviewer`) with inline `model:` have the model stripped, `subagent_type` unchanged
- [ ] FR#14: Built-in type mappings are word-boundary anchored — `claude` does not match `claude-code-guide`, `Plan` does not match `Planner`
- [ ] FR#15: Bare `general-purpose` dispatch (no `model:` clause) rewritten to `worker-standard`
- [ ] AC#5: `grep -r 'subagent_type.*general-purpose' ~/.config/opencode/skills/ ~/.config/opencode/commands/ ~/.config/opencode/agents/` returns zero matches
- [ ] AC#9: `opencode-sync --dry-run` shows the dispatch rewrites that would be applied without modifying installed files
- [ ] AC#6: `grep -r '\-\-agent-type general-purpose' ~/.config/opencode/skills/ ~/.config/opencode/commands/ ~/.config/opencode/agents/` returns zero matches
- [ ] AC#11: `grep -r 'model:.*sonnet\|model:.*haiku\|model:.*opus' ~/.config/opencode/skills/` returns zero matches for lines that also reference a named agent type
- [ ] AC#16: `grep -r 'subagent_type.*Explore\|subagent_type.*Plan\|subagent_type: "claude"' ~/.config/opencode/skills/ ~/.config/opencode/commands/ ~/.config/opencode/agents/` returns zero matches
- [ ] AC#17: A skill line that read `subagent_type: general-purpose` with no `model:` clause reads `subagent_type: worker-standard`
