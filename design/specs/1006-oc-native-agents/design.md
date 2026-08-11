# Design: OpenCode Native Agents and Skill Dispatch Adapter

**Date:** 2026-08-10
**Status:** archived
**Scope-mode:** hold
**Research:** Research briefs at scratchpad: `opencode-subagent-research.md`, `opencode-task-source.md`, `opencode-config-layering.md`

## Problem

Claudefiles represents a year of investment in skills, agents, hooks, and orchestration workflows built for Claude Code. OpenCode provides native subscription-based access to non-Anthropic models (GPT-5.6 Sol, Luna, etc.) that Claude Code cannot reach without per-token API billing. The goal is to run the full Claudefiles workflow in OpenCode — not to replace Claude Code, but to have access to the same tooling when working with non-Anthropic models.

The current `opencode-sync` script copies artifacts and remaps model names, but the adaptation is shallow. OpenCode's Task tool has no per-call `model` parameter, so when a skill says `Agent(subagent_type: "general-purpose", model: "sonnet")`, the `model:` part is instruction text that OpenCode cannot act on. The Task tool dispatches `general` and inherits the primary session's model. Skills reference `general-purpose` (a Claude Code agent name) rather than an OpenCode-native worker role, and no config enforces which models subagents actually use.

A July 30 quick fix manually pinned the three built-in subagents (`general`, `explore`, `scout`) in `opencode.jsonc`, but this is a local edit that a re-sync could overwrite, and it doesn't address the dispatch pattern mismatch.

## Goals

- The full Claudefiles workflow (skills, agents, orchestration) runs correctly in OpenCode with intentional model routing
- Subagents dispatch at the intended model tier, verified from the OpenCode session database
- The sync script generates the full agent and config stack — no manual local edits needed for model enforcement on a fresh install. Existing installs with stale manual pins (July 30 quick fix) require a one-time manual removal, surfaced by a sync warning (FR#13)
- Claude Code source files are never modified; all adaptation happens during sync
- Residual Claude-only dispatch patterns in synced output are caught by a lint

## Non-Goals

- Converting Claude-specific interactive question syntax (`AskUserQuestion` to OpenCode prompting)
- Runtime enforcement via OpenCode plugins
- Worktree isolation for parallel writers
- Full instruction loading (roadmap Spec 4)
- Establishing an isolated test fixture for OpenCode (roadmap Spec 1 — we verify against the live install)

## User Scenarios

### Developer: OpenCode user with Claudefiles

- **Goal:** Run orchestration workflows where subagents use appropriate model tiers
- **Context:** After running `opencode-sync` and restarting OpenCode

#### Sync and verify

1. **Run `opencode-sync`**
   - Sees: generated agent count, remapped model count, lint results
   - Then: worker agents, config, and rewritten skills are installed to `~/.config/opencode/`

2. **Restart OpenCode and invoke a skill**
   - Sees: skill dispatches subagents by named worker role
   - Then: Task tool resolves the worker agent's configured model, not the primary session's model

3. **Verify model routing**
   - Sees: `opencode-sync --check` confirms sync is current; verification query shows child sessions used expected models
   - Then: confidence that cost policy is enforced

## Functional Requirements

- **FR#1** `opencode-sync` generates worker agent markdown files (`worker-standard.md`, `worker-lightweight.md`) in `~/.config/opencode/agents/` with explicit `model` fields using the provider-qualified model ID from the tier mapping
- **FR#2** `opencode-sync` generates a `config.json` in `~/.config/opencode/` containing model overrides for the built-in subagents (`general`, `explore`, `scout`, `plan`) and the generated worker agents (`worker-standard`, `worker-lightweight`), plus `subagent_depth`. Pinning the workers at config level as well as in their frontmatter guards against the frontmatter-ignored failure mode (issues #17870/#35126) — all model enforcement flows through one mechanism. The file is written atomically (write to temp path, validate via `json.load()`, `os.replace()` into place) with `config.json.bak` preserved as a one-command rollback — a malformed `config.json` would silently wipe all three global config files due to OpenCode's single-fallback error handler in `loadGlobal()`
- **FR#3** `opencode-sync` never writes to `opencode.jsonc` — user-managed config is preserved across syncs
- **FR#4** `opencode-sync` rewrites dispatch lines in synced skill, command, and agent body files, replacing `subagent_type: general-purpose` + `model: sonnet` with `subagent_type: worker-standard`, and `model: haiku` with `subagent_type: worker-lightweight`
- **FR#5** `opencode-sync` rewrites `cfl dispatch` commands in synced skill, command, and agent body files, replacing `--agent-type general-purpose --model sonnet` with `--agent-type worker-standard` (and haiku with worker-lightweight), removing the `--model` flag
- **FR#6** A compatibility lint, implemented as `opencode-sync --lint-only` (same process and same pattern table as the rewriter — there is no standalone lint binary), scans synced output under `~/.config/opencode/skills/`, `~/.config/opencode/commands/`, and `~/.config/opencode/agents/` (for agent files, body content only — frontmatter is excluded because it contains remapped model IDs that would false-positive; skill and command files are scanned whole since their frontmatter has no model fields) and reports any residual dispatch patterns the rewriter missed. One shared pattern table prevents drift between the rewriter and its safety net. The lint also runs automatically at the end of every sync; a lint failure makes the sync exit non-zero but leaves installed files in place — the remedy is extending the pattern table (or fixing the source file) and re-syncing, not uninstalling
- **FR#7** The generated `config.json` sets `subagent_depth: 3` — the deepest current workflow is depth 2 (mine-orchestrate dispatches executors which dispatch reviewers), plus one level of margin. OpenCode's depth-counting semantics are documented in the research brief (`subagent_depth: 1` = subagents can't nest, `2` = one nesting level), so depth 2 covers the current workflow, but depth 3 provides headroom for future three-level workflows without requiring a config regeneration
- ~~**FR#8**~~ **Removed** — `permission.task` allowlists dropped. The user's `opencode.jsonc` already grants blanket `"permission": "allow"` which loads last and wins. Per-agent-name gating has no threat model for a personal/solo tool and risks either being inert or introducing regressive "ask" friction
- **FR#9** When a synced skill dispatch line references a named agent (e.g. `code-reviewer`) with an inline `model:` override, the rewriter strips the `model:` clause without changing `subagent_type` — named agents already have models in their frontmatter
- **FR#10** `opencode-sync` strips Claude-specific `color:` frontmatter fields from synced agent files (preserving existing behavior from the bash script)
- **FR#11** The compatibility lint flags unsupported platform semantics in synced output: `isolation: "worktree"` directives and `run_in_background` parameters that OpenCode cannot honor — these are surfaced as warnings, not silently dropped
- ~~**FR#12**~~ **Removed** — canary test dropped. The atomic write + validation (FR#2) is sufficient protection against malformed config. A runtime canary that writes to `config.json` on every `--check` would reintroduce the corruption risk it's meant to detect
- **FR#13** `opencode-sync` warns when `opencode.jsonc` contains `agent` keys that collide with generated `config.json` keys (stale July 30 quick-fix pins). Warns on every sync while the collision exists — no persisted suppression state. (Revised post-launch: the original design tracked warning state per-key-set in the sync state file to avoid repeat nagging; that state added a 44-line hand-rolled JSONC parser's worth of permanent machinery, an admitted block-comment gap, and was the trigger condition for a since-filed bug, all to silence a warning about a scenario the design itself frames as one-time cleanup. Removed in favor of the simpler always-warn behavior.)
- **FR#14** `opencode-sync` maps Claude Code built-in agent types (`Explore` → `explore`, `Plan` → `plan`, `claude` → `general`) to their lowercase OpenCode equivalents and strips any inline `model:` override — these built-ins are pinned in `config.json`, not via frontmatter. All built-in name matches are word-boundary anchored: `claude` must never match `claude-code-guide`, and `Plan` must never match `Planner` or prose uses of "planning"
- **FR#15** The rewriter maps `subagent_type: general-purpose` dispatches that have **no** `model:` clause to `subagent_type: worker-standard` — mirroring the Claude Code default, where the model-default hook injects sonnet for model-less `general-purpose` dispatches
- **FR#16** `opencode-sync` records the hash of the `config.json` it generates in a unified JSON sync state file (`.claudefiles-sync-state.json`). This state file also holds the commit SHA and the sync script's own hash. On a later sync, if `~/.config/opencode/config.json` exists but its hash doesn't match the recorded one (a foreign or hand-edited file), the sync backs it up to `config.json.foreign.bak` and prints a warning before overwriting. No in-file ownership marker is used — an unknown top-level key could fail OpenCode's config schema validation. (Revised post-launch: the original design also migrated a legacy plain-text `.claudefiles-sync-sha` file from the old bash script into this JSON state file on first read. That migration was one-time machinery for a single historical transition — it forced a `dry_run` parameter onto the state-loading function purely to suppress the migration's write/unlink during `--dry-run` — and was removed. The file is now simply ignored by the script rather than migrated — anyone whose install still has it (confirmed absent on the maintainer's own machine) can delete `~/.config/opencode/.claudefiles-sync-sha` manually as harmless cleanup, but leaving it in place has no effect.)

## Edge Cases

- **Model name drift:** The TIER_MAP maps Claude tiers to provider-qualified model IDs. When models change, one dict update propagates to all generated agents and config.
- **Unmapped tier:** A skill uses `model: opus` with `general-purpose`. Currently no `general-purpose` dispatches use opus — if one is added, the compatibility lint catches it as a residual pattern (the rewriter only handles tiers with a `worker` entry in TIER_MAP), and a `worker-deep` role should be defined.
- **Pattern miss:** A new skill uses a dispatch format the rewriter doesn't recognize. The compatibility lint catches this as a residual pattern. The lint runs automatically at the end of sync.
- **Built-in name change:** OpenCode renames `general`/`explore`/`scout`. The generated `config.json` contains stale keys — harmless (OpenCode ignores unknown names) but model enforcement for the renamed built-in silently stops working. Manual TIER_MAP update needed.
- **Failed reinstall:** opkg uninstalls previous artifacts before reinstalling. If reinstall fails, OpenCode has zero Claudefiles content until the user reruns `opencode-sync`. Accepted risk — recovery is a rerun. Same behavior as the existing bash script.
- **Dual-target dispatch:** A dispatch line references both a named agent type (e.g. `code-reviewer`) AND a `model:` override. Named agents already have models in frontmatter — the rewriter should strip the `model:` without changing `subagent_type`.
- **Bare dispatch:** A skill line references `general-purpose` with no `model:` clause. Rewritten to `worker-standard` (FR#15). The lint's literal-string rule still errors on any surviving `general-purpose` occurrence — including ordinary English uses of the phrase. That over-sensitivity is deliberate (false positives beat false negatives); the fix for a genuine prose false positive is rewording the source text.
- **Lint failure after install:** The end-of-sync lint fails. Sync exits non-zero but installed files stay in place — installed-but-flagged beats uninstalling. Remedy: extend the pattern table (or fix the source file) and re-sync.
- **Pre-existing foreign `config.json`:** A hand-written or third-party `config.json` exists before the first sync. Detected via the missing/mismatched hash in the sync state file (FR#16), backed up to `config.json.foreign.bak`, warned about, then overwritten.

## Acceptance Criteria

- **AC#1** After running `opencode-sync`, `~/.config/opencode/agents/worker-standard.md` exists with `model: openai/gpt-5.6-terra` in frontmatter (FR#1)
- **AC#2** After running `opencode-sync`, `~/.config/opencode/agents/worker-lightweight.md` exists with `model: openai/gpt-5.6-luna` in frontmatter (FR#1)
- **AC#3** After running `opencode-sync`, `~/.config/opencode/config.json` exists and contains `agent.general.model`, `agent.explore.model`, `agent.scout.model`, `agent.plan.model`, `agent.worker-standard.model`, `agent.worker-lightweight.model`, and `subagent_depth: 3` (FR#2, FR#7)
- **AC#4** `opencode.jsonc` has the same mtime before and after running `opencode-sync` (FR#3)
- **AC#5** `grep -r 'subagent_type.*general-purpose' ~/.config/opencode/skills/ ~/.config/opencode/commands/ ~/.config/opencode/agents/` returns zero matches after sync (FR#4)
- **AC#6** `grep -r '\-\-agent-type general-purpose' ~/.config/opencode/skills/ ~/.config/opencode/commands/ ~/.config/opencode/agents/` returns zero matches after sync (FR#5)
- **AC#7** `opencode-sync --lint-only` exits 0 after a clean sync (FR#6)
- **AC#8** `opencode-sync --lint-only` exits non-zero when a synced skill file is manually edited to re-introduce `model: sonnet` with `subagent_type: general-purpose` (FR#6)
- **AC#9** `opencode-sync --dry-run` shows the dispatch rewrites without modifying installed files
- **AC#10** `opencode-sync --check` reports sync status (current/stale/never-synced)
- **AC#11** After sync, `grep -r 'model:.*sonnet\|model:.*haiku\|model:.*opus' ~/.config/opencode/skills/` returns zero matches for lines that also reference a named agent type like `code-reviewer` (FR#9)
- **AC#12** After sync, `grep -r '^color:' ~/.config/opencode/agents/` returns zero matches (FR#10)
- **AC#13** `opencode-sync --lint-only` reports warnings for any `isolation: "worktree"` or `run_in_background` directives found in synced skills (FR#11)
- ~~**AC#14**~~ **Removed** — canary test dropped (FR#12 removed)
- **AC#15** `opencode-sync` prints a warning when `opencode.jsonc` contains `agent` keys that shadow generated `config.json` entries (FR#13)
- **AC#16** After sync, `grep -r 'subagent_type.*Explore\|subagent_type.*Plan\|subagent_type: "claude"' ~/.config/opencode/skills/ ~/.config/opencode/commands/ ~/.config/opencode/agents/` returns zero matches for uppercase Claude Code built-in names (FR#14)
- **AC#17** After sync, a skill line that read `subagent_type: general-purpose` with no `model:` clause reads `subagent_type: worker-standard` (FR#15)
- **AC#18** When `~/.config/opencode/config.json` exists with content not matching the hash recorded in the sync state file, `opencode-sync` backs it up to `config.json.foreign.bak` and prints a warning before overwriting (FR#16)

## Key Constraints

- The dispatch rewriter handles seven documented cases (cataloged in Architecture) but implements them as **two token-extraction passes** (prose/YAML shapes + `cfl dispatch` CLI flags) feeding **one shared `resolve()` function** backed by a single routing table. The seven cases exist as documentation of real input shapes, not as seven separate code paths. A regex that catches one shape but misses others is a correctness bug, not a style issue.
- The generated `config.json` must not contain keys that conflict with `opencode.jsonc` in a way that breaks deep merge. Since `permission.task` was dropped (FR#8 removed), no `permission` key is generated, avoiding this concern entirely. (See Dependencies for the permission normalization detail.)
- `opkg install --platforms opencode` writes only into subdirectories (`agents/`, `commands/`, `rules/`, `skills/`), never top-level files. The generated `config.json` does not collide with opkg output — verified empirically.

## Dependencies and Assumptions

- **OpenCode's three-file global merge:** `loadGlobal()` in `config.ts` (near line 258 at time of research — verify before implementation) loads `config.json` < `opencode.json` < `opencode.jsonc` and deep-merges them via `remeda.mergeDeep`. This is visible in source and consistent across issues (#3407, #18953) but not explicitly documented on the official config docs page. Risk: a future OpenCode version could change to first-found-wins. Mitigation: the SQLite child-session verification (Test Strategy) is the empirical check — if merge behavior changes, the generated pins stop taking effect and the verification query shows child sessions on the wrong models. (An in-config canary was considered and rejected — see FR#12 removal.)
- **Permission normalization before merge:** `ConfigPermissionV1.Info` normalizes the string shorthand per-file before merging (`permission.ts`, near line 40 at time of research). Not directly relevant now that `permission.task` was dropped (FR#8 removed), but retained as reference in case permission generation is reconsidered later.
- **Node.js available:** Required for `npx opkg`. Already a dependency of the current sync script.
- **Python/uv available:** Required for the rewritten sync script. Already a dependency of `install.py`.
- **Agent `model:` frontmatter is honored by the Task tool:** The design depends on OpenCode using the agent's configured `model` field when spawning a child session. Issues #17870 and #35126 report cases where subagents ignore their `model:` frontmatter and fall back to the global default; both were closed "not planned." Mitigation: the generated `config.json` pins the built-in subagents (`general`, `explore`, `scout`, `plan`) **and** the generated workers (`worker-standard`, `worker-lightweight`) at the global config level, so even if frontmatter is ignored the fallback is a controlled tier rather than the SOTA primary model. Implementation-time check: confirm config-level `agent` entries merge onto markdown-defined agents (expected — same mechanism as the built-in pins — but verify in source or empirically before relying on it). The SQLite child-session verification (Test Strategy) is the empirical check that catches any regression.
- **`permission.task` (reference only — not generated):** Uses glob-pattern matching on `subagent_type` strings. Documented here for reference since the mechanism was investigated and could be added later, but FR#8 was removed — no `permission` key is generated.

## Architecture

### Config layering

OpenCode natively loads and deep-merges three global config files in order:

```
config.json (lowest)  →  opencode.json (middle)  →  opencode.jsonc (highest)
```

The sync script owns `config.json` (generated, overwritten each sync). The user owns `opencode.jsonc` (manual, never touched). User settings win on any conflict.

Generated `config.json` content:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "general": {"model": "openai/gpt-5.6-terra"},
    "plan": {"model": "openai/gpt-5.6-terra"},
    "explore": {"model": "openai/gpt-5.6-luna"},
    "scout": {"model": "openai/gpt-5.6-luna"},
    "worker-standard": {"model": "openai/gpt-5.6-terra"},
    "worker-lightweight": {"model": "openai/gpt-5.6-luna"}
  },
  "subagent_depth": 3
}
```

`config.json` carries no in-file ownership marker — an unknown top-level key risks failing OpenCode's config schema validation. Sync-ownership is tracked instead by recording the generated file's hash in the sync state file (FR#16).

### Worker agent generation

Two markdown files generated under `~/.config/opencode/agents/`:

```markdown
---
name: worker-standard
mode: subagent
model: openai/gpt-5.6-terra
description: Standard worker for implementation, review, and synthesis tasks
---
```

```markdown
---
name: worker-lightweight
mode: subagent
model: openai/gpt-5.6-luna
description: Lightweight worker for triage, mechanical analysis, and low-cost tasks
---
```

These are generated alongside the named agents that opkg installs (the count depends on which bundles are selected — 13 base agents are always installed; Engineering and Extra bundles add more). Before writing, the sync globs `~/.config/opencode/agents/worker-*.md` and deletes any file whose basename doesn't correspond to a current TIER_MAP `worker` value — preventing orphaned worker agents when tiers are renamed or removed. The worker agents are not opkg-managed — they're written directly by the sync script after opkg runs. Both workers are additionally pinned in the generated `config.json` (FR#2), so model enforcement doesn't depend solely on frontmatter being honored (see Dependencies).

### Tier mapping

A single Python dict drives agent generation, config generation, and dispatch rewriting:

```python
TIER_MAP = {
    "opus":   {"model": "openai/gpt-5.6-sol",   "worker": None,                 "builtins": []},
    "sonnet": {"model": "openai/gpt-5.6-terra",  "worker": "worker-standard",    "builtins": ["general", "plan"]},
    "haiku":  {"model": "openai/gpt-5.6-luna",   "worker": "worker-lightweight",  "builtins": ["explore", "scout"]},
}
```

`opus` has no worker agent because no `general-purpose` dispatches currently use opus. If one appears, the lint will flag it and a `worker-deep` can be added.

`plan` sits in the sonnet row deliberately: Claude Code's model-default hook runs the `Plan` built-in at sonnet, and planning is not lightweight-tier work — pinning it at luna would be a silent tier downgrade. `explore` and `scout` are search agents and stay at the lightweight tier.

### Dispatch rewriter

The rewriter handles seven cases found across skill files, plus a bare-dispatch default. Patterns 1–5 pair `subagent_type: general-purpose` with a `model: <tier>` and rewrite to the named worker:

**Pattern 1 — Inline call-site:**
```
Agent(subagent_type: "general-purpose", model: "sonnet")
→ Agent(subagent_type: "worker-standard")
```

**Pattern 2 — Prose with backtick-quoted type:**
```
Launch a `general-purpose` subagent with `model: sonnet`
→ Launch a `worker-standard` subagent
```

**Pattern 3 — Prose with parenthetical:**
```
(`subagent_type: "general-purpose"`, `model: sonnet`)
→ (`subagent_type: "worker-standard"`)
```

**Pattern 4 — Prose comma-separated:**
```
subagent_type: general-purpose, model: sonnet
→ subagent_type: worker-standard
```

**Pattern 5 — cfl dispatch command:**
```
cfl dispatch <role> --agent-type general-purpose --model sonnet
→ cfl dispatch <role> --agent-type worker-standard
```

**Case 6 — Named agent with model override:**
```
subagent_type: "code-reviewer", model: sonnet
→ subagent_type: "code-reviewer"
```

For lines referencing named agents (not `general-purpose` or Claude Code built-ins) with an inline `model:`, the rewriter strips the `model:` clause without changing `subagent_type` — named agents already have models in their frontmatter.

**Case 7 — Claude Code built-in type with model override:**
```
subagent_type: Explore, model: haiku
→ subagent_type: explore
```

Claude Code built-in types (`Explore`, `Plan`, `general-purpose`, `claude`) have no model frontmatter and inherit the parent model. In OpenCode, the equivalent built-ins (`explore`, `plan`, `general`) are lowercase and pinned in `config.json`. The rewriter maps these to their lowercase OpenCode equivalents and strips the `model:` clause. The special case `general-purpose` is already handled by Patterns 1-5 (mapped to `worker-standard`/`worker-lightweight`). This case covers `Explore` → `explore`, `Plan` → `plan`. `claude` (the catch-all built-in) maps to `general`. Matches are word-boundary anchored (FR#14): `claude` never matches `claude-code-guide`, `Plan` never matches `Planner` or prose "planning".

**Bare dispatch (no model):** `subagent_type: general-purpose` with no `model:` clause → `subagent_type: worker-standard` (FR#15), mirroring the Claude-side default where the model hook injects sonnet.

The rewriter processes synced skill, command, and agent body files (frontmatter excluded) after opkg install. It matches on Claude tier names (`sonnet`, `haiku`, `opus`) in body content and removes the `model:` clause entirely. The model remap is a separate pass that runs after dispatch rewrite and operates only on agent frontmatter (anchored `model:` lines, which may have trailing inline comments like `# claude-sonnet-5 as of 2026-07-07`) — it replaces Claude tier names with provider-qualified model IDs while preserving any trailing comment, without touching body content. The dispatch rewriter replaces the old script's inline body remap; the frontmatter remap replaces its anchored remap.

Order: opkg install → color strip → dispatch rewrite (skills + commands + agent bodies) → model remap (agent frontmatter only, anchored) → worker agent generation → config.json generation → lint.

### Script rewrite

`bin/opencode-sync` is rewritten from bash to Python. It preserves the existing CLI interface (`--dry-run`, `--verbose`, `--allow-worktree`, `--check`), adds `--lint-only`, and keeps the opkg-based distribution pipeline. The Python script replaces:

- `stage_config()` → Python with `shutil`/`pathlib`
- `remap_models()` → Python regex with the unified `TIER_MAP`
- `postprocess_config()` → color field stripping + dispatch rewriting (skills + commands) + model remapping (agent frontmatter only, anchored) + worker agent generation + config.json generation + lint invocation
- `check_sync_status()` → SHA comparison logic reading from a unified JSON state file (`.claudefiles-sync-state.json`), with the hash input extended to include `bin/opencode-sync` itself — so a TIER_MAP edit marks the install stale. (The old plain-text `.claudefiles-sync-sha` file's one-time migration into this format was later removed — see FR#16.)
- `opkg()` wrapper → `subprocess.run(["npx", ...], timeout=120)` (explicit timeout per the "Timeouts on External Calls" invariant)

### Compatibility lint

The lint is a mode of the sync script (`opencode-sync --lint-only`), not a standalone tool — it shares the rewriter's pattern table in-process, which is what keeps the two from drifting. It scans `~/.config/opencode/skills/`, `~/.config/opencode/commands/`, and `~/.config/opencode/agents/` (for agent files, body content only — frontmatter excluded to avoid false-positives on remapped model IDs; skill and command files are scanned whole) for residual Claude-only dispatch constructs:

- `subagent_type.*general-purpose` paired with `model:` on the same or adjacent line
- Backtick-quoted `` `general-purpose` `` paired with `model:` on the same or adjacent line (catches Pattern 2 prose format which lacks the `subagent_type:` token)
- `--agent-type general-purpose` paired with `--model`
- Any remaining `model: sonnet` / `model: haiku` / `model: opus` (unrewritten Claude tier names) in non-frontmatter context
- The literal string `general-purpose` in any context (after correct sync, no Claude Code agent name should remain — catches templated/prose dispatch guidance the regex-based rewriter can't match). Ordinary English uses of the phrase are accepted false positives — deliberate over-sensitivity; reword the source text if one appears

Additionally flags unsupported platform semantics (as warnings, not errors):
- `isolation: "worktree"` directives (OpenCode has no equivalent)
- `run_in_background` parameters (OpenCode's background subagents are behind an experimental flag)

Exits 0 if no errors (warnings alone don't fail). Exits non-zero if residual dispatch patterns found. When invoked automatically at the end of a sync, a lint failure makes the sync exit non-zero but leaves installed files in place (see Edge Cases).

## Implementation Preferences

- Python script using `pathlib`, `re`, `json`, `subprocess`, `shutil` — no third-party dependencies beyond what `uv` provides
- The script should be runnable via `uv run bin/opencode-sync` (add inline script metadata) or directly if Python is on PATH
- Follow the existing `install.py` patterns for CLI argument parsing and output formatting
- The lint is a flag on the sync script (`--lint-only`), not a separate CLI — follow whatever argument-parsing approach the sync script itself uses

## Replacement Targets

- `bin/opencode-sync` (bash) → `bin/opencode-sync` (Python) — full rewrite, same filename
- The manual `agent` overrides in `opencode.jsonc` (the July 30 quick fix for `general`, `explore`, `scout`) → generated `config.json`. After the first sync, the user should remove the `agent` block from `opencode.jsonc` since `config.json` now handles it.
- The existing `remap_models()` inline sed approach → Python dispatch rewriter that changes `subagent_type` not just `model` names

## Convention Examples

No convention examples — the sync script is a full rewrite, so existing bash conventions are not a reference. The lint is a mode of the sync script, not a standalone tool.

## Alternatives Considered

**1. Keep bash, add Python helpers.** The sync script stays bash and calls Python for complex transforms (dispatch rewriting, config generation). Rejected: creates a two-language maintenance burden for one tool. The entire script's job is structured text transforms — Python is the natural fit.

**2. Duplicate agents per model tier without a dispatch rewriter.** Create `worker-standard`, `worker-lightweight` but leave skill files unchanged. The model text would be rewritten but `subagent_type` would still say `general-purpose`, which dispatches to the built-in `general` agent. Rejected: this was the original roadmap Spec 2 scope; it delivers agent definitions nobody calls.

**3. Use `OPENCODE_CONFIG` env var for generated config.** Write generated config to a separate file, load via env var. Rejected: requires shell profile changes, less discoverable, single-file limitation conflicts with other uses.

**4. Section markers in one file.** Write between `# BEGIN GENERATED` / `# END GENERATED` markers in `opencode.jsonc`. Rejected: fragile, JSON/JSONC doesn't support comments natively in a way that survives parse-rewrite cycles, and marker-based editing is error-prone.

## Test Strategy

### Required Test Types

Verification against the live OpenCode install. No formal test framework for the sync script exists — testing is shell-level validation.

- Dry-run output validation (sync produces expected files/rewrites)
- Filesystem assertions (generated files exist with correct content after sync)
- Grep-based assertions (no residual patterns in synced output)
- SQLite query against `~/.local/share/opencode/opencode.db` for child session model verification (post-sync, after running a workflow). Open with `PRAGMA busy_timeout = 5000` to avoid lock contention errors if OpenCode is still running. The query is a documented snippet in REFERENCE.md, run manually after exercising a workflow — not a sync subcommand

Gap: no isolated test fixture for OpenCode. Tests run against the live `~/.config/opencode/` directory. Roadmap Spec 1 was supposed to establish this — accepted gap for now.

### Existing Tests to Adapt

No existing tests for the sync script.

### New Test Coverage

- `opencode-sync --dry-run` output includes worker agent generation (FR#1)
- `opencode-sync --dry-run` output includes config.json generation (FR#2)
- `opencode-sync --dry-run` shows dispatch rewrites (FR#4, FR#5)
- `opencode-sync --lint-only` exits 0 on clean output (FR#6)
- `opencode-sync --lint-only` exits non-zero on planted residuals (FR#6)
- Post-sync grep for residual `general-purpose` in skills returns zero matches (FR#4, FR#5)
- Post-sync grep for `color:` in agent frontmatter returns zero matches (FR#10)
- Named agent dispatches with inline `model:` have the model stripped after sync (FR#9)
- `opencode-sync --lint-only` reports warnings for `isolation: "worktree"` and `run_in_background` in synced skills (FR#11)
- Bare `general-purpose` dispatch (no `model:` clause) rewritten to `worker-standard` (FR#15)
- Pre-existing foreign `config.json` is backed up to `config.json.foreign.bak` with a warning (FR#16)

### Tests to Remove

No tests to remove.

## Documentation Updates

- **REFERENCE.md** — update the `opencode-sync` entry to reflect the Python rewrite and the `--check`/`--lint-only` behavior, and document the SQLite child-session verification query
- **ONBOARDING.md** — update OpenCode support section to reflect config.json/opencode.jsonc split and the worker agent mechanism
- **CHANGELOG.md** — at PR creation time
- **`design/opencode-integration-roadmap.md`** — mark Spec 2 complete; mark Spec 3 partially complete (this spec covers dispatch rewriting and the compatibility lint; interactive question syntax conversion, vertical-slice-first validation, and skill classification as portable/adapter-required/harness-specific are deferred to a follow-up)

## Impact

### Changed Files

- **modify** `bin/opencode-sync` — full rewrite from bash to Python (includes the `--lint-only` compatibility lint)
- **modify** `REFERENCE.md` — update the `opencode-sync` entry; add the verification query
- **modify** `ONBOARDING.md` — update OpenCode support section
- **modify** `design/opencode-integration-roadmap.md` — mark Spec 2 complete; mark Spec 3 partially complete (dispatch rewriting and lint done; interactive question syntax conversion, vertical-slice validation, and skill classification deferred to a follow-up spec)

Generated (not committed, produced at runtime by sync):
- **create** `~/.config/opencode/config.json` — generated config
- **create** `~/.config/opencode/agents/worker-standard.md` — generated worker agent
- **create** `~/.config/opencode/agents/worker-lightweight.md` — generated worker agent
- **modify** `~/.config/opencode/skills/**/*.md` — dispatch rewrites in synced skill files
- **modify** `~/.config/opencode/commands/**/*.md` — dispatch rewrites in synced command files
- **modify** `~/.config/opencode/agents/**/*.md` — color-strip (frontmatter), dispatch rewrite (body), and model remap (frontmatter) on all synced agent files

### Behavioral Invariants

- `opencode-sync --dry-run` must still show what would be installed without modifying files
- `opencode-sync --check` must still report sync status
- `opencode-sync --allow-worktree` must still permit running from a worktree
- Named agents (code-reviewer, integration-reviewer, etc.) must still have correct model mappings in their frontmatter after sync
- The sync must still uninstall previous opkg output before reinstalling
- Claude-specific `color:` fields must still be stripped from agent frontmatter

### Blast Radius

- **OpenCode runtime:** After sync + restart, all subagent dispatches route through named workers instead of inheriting the primary model. This is the intended behavioral change.
- **OpenCode config:** `config.json` is a new file that didn't exist before. Users who manually inspect their OpenCode config need to know about the two-file split.
- **Existing opencode.jsonc:** The manual `agent` overrides from the July 30 quick fix become redundant. The user should remove them after the first sync — `opencode.jsonc` wins over `config.json` in the merge order, so stale pins in `opencode.jsonc` would silently override the TIER_MAP-driven values in `config.json`. The sync emits a warning on every run while it detects `agent` keys in `opencode.jsonc` that collide with generated `config.json` keys (FR#13).

## Open Questions

None — all items resolved during blind spot assessment and comb review.
