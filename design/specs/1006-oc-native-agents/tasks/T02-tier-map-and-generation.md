---
task_id: "T02"
title: "Add TIER_MAP, worker agent generation, and config.json generation"
status: "done"
depends_on: ["T01"]
implements: ["FR#1", "FR#2", "FR#7", "AC#1", "AC#2", "AC#3"]
---

## Summary

Define the `TIER_MAP` data structure that drives all model routing, implement worker agent markdown generation (`worker-standard.md`, `worker-lightweight.md`), and implement `config.json` generation with model pins for both built-in subagents and generated workers plus `subagent_depth`. Worker agents are written directly by the sync script after opkg runs. Config is written atomically with validation and backup.

## Target Files

- modify: `bin/opencode-sync` — add TIER_MAP, worker generation, config generation functions
- read: `design/specs/1006-oc-native-agents/design.md` — Architecture sections for TIER_MAP, worker agent, and config.json specs

## Prompt

Add three components to `bin/opencode-sync`, filling in the T02 stub points left by T01:

### 1. TIER_MAP constant

Define at the top of the script, after existing constants:

```python
TIER_MAP = {
    "opus":   {"model": "openai/gpt-5.6-sol",   "worker": None,                 "builtins": []},
    "sonnet": {"model": "openai/gpt-5.6-terra",  "worker": "worker-standard",    "builtins": ["general", "plan"]},
    "haiku":  {"model": "openai/gpt-5.6-luna",   "worker": "worker-lightweight",  "builtins": ["explore", "scout"]},
}
```

`opus` has no worker because no `general-purpose` dispatches currently use opus. `plan` is in the sonnet row deliberately — planning is not lightweight-tier work.

### 2. `generate_worker_agents(agents_dir: Path, dry_run: bool) -> list[str]`

Generate two markdown files under `~/.config/opencode/agents/`:

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

Derive the `name`, `model`, and filenames from TIER_MAP entries where `worker` is not None. Before writing, glob `agents_dir / "worker-*.md"` and delete any file whose basename doesn't correspond to a current TIER_MAP `worker` value — prevents orphaned worker agents when tiers are renamed.

In dry-run mode, print what would be generated but don't write files. Return the list of worker names generated.

### 3. `generate_config(config_dir: Path, dry_run: bool)`

Generate `config.json` at `config_dir / "config.json"` containing:

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

Build the `agent` dict programmatically from TIER_MAP: for each tier, add entries for each `builtins` name and for the `worker` name (if not None), all mapping to that tier's `model`.

**Atomic write** (FR#2): write to a temp file in the same directory, validate via `json.load()` on the temp file, then `os.replace()` into place. Preserve a backup at `config.json.bak` before overwriting (copy the existing file, if any, to `.bak` before the `os.replace()`). A malformed `config.json` would silently wipe all three global config files due to OpenCode's single-fallback error handler in `loadGlobal()`.

`subagent_depth` is set to 3 (FR#7).

In dry-run mode, print the JSON that would be generated but don't write.

### Wire into main()

Call `generate_worker_agents()` and `generate_config()` at the T02 stub points in `main()`, after color field stripping and before the lint stub.

## Focus

- The TIER_MAP is the single source of truth for model routing. T03 (dispatch rewriter) and T04 (lint) will also read from it. Place it as a module-level constant so all functions can access it.
- Worker agents are NOT opkg-managed — they're written directly by the sync script after opkg runs. They supplement the named agents opkg installs.
- The orphaned worker cleanup (glob + delete) must run before writing new workers, so a renamed tier doesn't leave stale files.
- The atomic write pattern: `tempfile.NamedTemporaryFile` in the same directory → `json.load()` validation → `shutil.copy2` existing to `.bak` → `os.replace()` temp to final. Using the same directory ensures `os.replace()` is atomic (same filesystem).
- The `$schema` key in config.json is informational — OpenCode doesn't validate against it, but it enables IDE autocompletion.

## Verify

- [ ] FR#1: After sync, `~/.config/opencode/agents/worker-standard.md` exists with `model: openai/gpt-5.6-terra` in frontmatter
- [ ] FR#2: After sync, `~/.config/opencode/config.json` exists, is valid JSON, and contains the expected `agent` entries and `subagent_depth: 3`
- [ ] FR#7: `config.json` contains `"subagent_depth": 3`
- [ ] AC#1: `worker-standard.md` exists with correct model in frontmatter
- [ ] AC#2: `worker-lightweight.md` exists with correct model in frontmatter
- [ ] AC#3: `config.json` contains `agent.general.model`, `agent.explore.model`, `agent.scout.model`, `agent.plan.model`, `agent.worker-standard.model`, `agent.worker-lightweight.model`, and `subagent_depth: 3`
- [ ] FR#1: `opencode-sync --dry-run` output shows the worker agent files that would be generated
- [ ] FR#2: `opencode-sync --dry-run` output shows the config.json content that would be generated
