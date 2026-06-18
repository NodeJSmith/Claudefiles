# Rulesync Investigation: Multi-Tool Config Sync for Claudefiles

**Date:** 2026-06-06
**Goal:** Evaluate whether rulesync (npm package) can sync Claudefiles rules/skills/agents to Codex CLI, Antigravity CLI, and Cursor from a single source of truth.

## Tools Evaluated

| Tool | Binary | Version Tested | Install Method |
|---|---|---|---|
| Rulesync | `rulesync` (npx) | 8.24.1 | `npm install -g rulesync` |
| Codex CLI | `codex` | 0.137.0 | `mise install codex` |
| Antigravity CLI | `agy` | 1.0.6 | `curl -fsSL https://antigravity.google/cli/install.sh \| bash` |
| Cursor CLI | `agent` | not tested | already installed on work machines |
| Gemini CLI | `gemini` | 0.45.2 | `mise install gemini` (deprecated June 18, 2026) |

## Key Findings

### 1. Symlink Support

Tested by creating a rule file, symlinking it as AGENTS.md, and checking if the tool loaded it.

| Tool | Follows symlinks? | Tested how |
|---|---|---|
| Claude Code | Yes | Known behavior |
| Codex CLI | **Yes** | `codex exec` + `codex debug prompt-input` with symlinked AGENTS.md |
| Antigravity CLI | **Yes** | `agy --print` with symlinked AGENTS.md |
| Cursor | **No** | Forum bug reports confirm skills not discovered through symlinks |

**Conclusion:** Symlinks work for Codex and Antigravity. The existing `install.py` symlink approach extends directly to these tools. Cursor is the exception.

### 2. Rulesync's Import/Generate Pipeline

Rulesync has two workflows:
- **`convert`** — direct tool-to-tool, no intermediate format
- **`import` → `generate`** — import to `.rulesync/` format, then generate for any target

The import from `~/.claude/` (global mode) fails because:
- **Symlinks not followed** — install.py creates symlinks; rulesync's find doesn't traverse them
- **Nested rules directories** — rulesync expects `~/.claude/rules/*.md` (flat), our structure is `~/.claude/rules/common/*.md`
- **`learned/` directory without SKILL.md** — causes hard failure, aborting all skill import

**Workaround tested:** Build a flat staging copy from source repos (not the installed symlink tree). This works — all 43 rules, 70 skills, 18 agents, 14 commands, hooks, and permissions imported successfully.

### 3. Rulesync Feature Support by Target

Tested with `generate --dry-run` from a complete `.rulesync/` import.

| Target | Rules | Skills | Agents | Commands | Hooks | Permissions | MCP | Total files |
|---|---|---|---|---|---|---|---|---|
| `codexcli` | 43 | 70 | 18 | — | 2 | 2 | 1 | 136 |
| `geminicli` | 43 | 70 | 18 | 14 | 1 | 1 | — | 148 |
| `antigravity-cli` | 43 | 70 | — | — | 1 | — | — | 114 |
| `cursor` | 43 (.mdc) | 70 | 18 | 14 | 1 | — | 1 | ~150 |

`geminicli` has the richest support but is deprecated June 18, 2026. `antigravity-cli` support is expanding rapidly (issues #1679, #1749, #1760).

### 4. Codex CLI Rules Are Broken in Rulesync (Issue #1765)

**Bug:** Rulesync writes non-root rules to `.codex/memories/*.md`. Codex CLI does not read from this directory.

**What `.codex/memories/` actually is:** Codex's own auto-memory system (SQLite-backed at `~/.codex/memories_1.sqlite`). Not a location for user-provided rules.

**How Codex actually loads instructions:**
1. `AGENTS.md` files (project root + hierarchical walking from git root to cwd)
2. `config.toml` `instructions` / `developer_instructions` fields (single string)
3. Skills — discovered from a hierarchy: `$CWD/.agents/skills` → parent → `$REPO_ROOT/.agents/skills` → `$HOME/.agents/skills` → `/etc/codex/skills` → built-in
4. That's it — no global rules directory

**Note:** `~/.codex/skills/` is deprecated upstream; the canonical path is `$HOME/.agents/skills/` (see [official docs](https://developers.openai.com/codex/skills)). Rulesync still writes to `.codex/skills/` — tracked in issue #1685.

**TOON workaround:** Rulesync prepends a TOON-formatted reference section to AGENTS.md asking the LLM to read the non-root files. This is prompt engineering, not native loading. Verified unreliable via `codex debug prompt-input`.

**Root rule works correctly:** A rule with `root: true` generates `AGENTS.md` which Codex reads. The bug is only for multi-rule setups where non-root rules are silently dropped.

**Filed:** https://github.com/dyoshikawa/rulesync/issues/1765

### 5. Skill Portability

56 of 71 skills reference Claude Code-specific internals:
- 15 use `subagent_type` (Agent tool dispatch)
- 48 use `AskUserQuestion`
- 25 use `get-skill-tmpdir`

Only 15 skills are fully portable (mostly personal API wrappers: Monarch, Karakeep, HA, etc.).

Rulesync does **zero content transformation** on skill bodies — it only adjusts YAML frontmatter (strips `targets`, flattens `description`). Claude-specific tool references pass through verbatim.

### 6. Cursor Dropped from Scope

Cursor adds significant complexity:
- Doesn't follow symlinks (requires file copies, not symlinks)
- Needs `.mdc` format conversion for rules
- Skills with Claude-specific content break (56 of 71)
- "Seriously mediocre product" — not worth the engineering investment

### 7. Gemini CLI → Antigravity CLI Migration

- Gemini CLI stops serving requests June 18, 2026
- Antigravity CLI (`agy`) is the replacement
- Not in mise; installed via Google's install script
- Rulesync split target: `antigravity-ide` (desktop) vs `antigravity-cli` (the `agy` binary)
- `geminicli` target will be deprecated in rulesync

## Re-verification 2026-06-18 (rulesync 8.30.1)

Re-ran the import → generate pipeline on **8.30.1** (findings above were on 8.24.1) to confirm the tables still hold before building. Method: flat staging copy of this worktree (28 rules flattened from `rules/common/`, 59 skills, 20 agents, 6 commands, settings) → `rulesync import -t claudecode -f '*'` → `rulesync generate -t {codexcli,antigravity-cli} -f '*'`.

Counts differ from the original tables only because of repo changes since 2026-06-06 (the `mine.*`→`mine-*` rename, #357 removals, single-repo vs the original multi-repo staging). The **structural findings all hold**:

| Original finding | Status on 8.30.1 |
|---|---|
| #1765 — codex non-root rules → `.codex/memories/` (Codex never reads) | **Still broken.** All 28 non-root rules written there |
| Codex skills path (our PR #1766, fixes #1685) | **Live.** Skills now write to `.agents/skills/` |
| `learned/` dir aborts skill import | **Gone** (removed by #357). Import ran clean, 117 files, no hard failure |
| Codex agents → `.toml` | Confirmed (`.codex/agents/*.toml`) |
| Codex hooks + permissions | Confirmed (`.codex/config.toml`, `.codex/rules/rulesync.rules`); the 3 hook events our PR wired map correctly |
| Codex commands unsupported | Confirmed ("does not support... Skipping") |
| Antigravity rules → `.agents/rules/` (symlinkable) | Confirmed |
| Antigravity agents / commands / permissions unsupported | Confirmed skipped |

**Material update — `.agents/skills/` is a shared canonical path.** Both `codexcli` and `antigravity-cli` write skills to `.agents/skills/`. Our PR #1766 aligning the codex path means **one symlink target (`~/.agents/skills/`) serves both tools** — Next Step #1 is simpler than originally assumed (one symlink, not per-tool copies).

**Still open:** #1765. Codex rules remain the one hard piece; the concat-into-`AGENTS.md` approach (below) is still required, no upstream fix to wait on.

## Architecture Decision

### What works without rulesync (symlinks via install.py)

| File type | Codex | Antigravity |
|---|---|---|
| Skills (SKILL.md) | Symlink to `~/.agents/skills/` (canonical) | Symlink to `.agents/skills/` |
| Rules (.md) | **Cannot symlink** — no rules directory in Codex | Symlink to `.agents/rules/` |
| Agents (.md) | **Needs conversion** — Codex uses `.toml` format | Not supported yet |
| Commands (.md) | Not supported | Not supported yet |

### What rulesync is needed for

1. **Codex agents** — `.md` → `.toml` format conversion
2. **Codex hooks** — Claude Code nested schema → Codex flat schema
3. **Codex permissions** — `settings.json` → `config.toml` format

### What needs a different approach

**Codex rules** — no directory-based discovery. The correct approach is concatenating non-root rules into AGENTS.md under section headers. This matches Claude Code's always-on semantics (rules load every conversation). Skills are wrong for rules because skills are opt-in — they load on demand when Codex decides they're relevant, which means rules like "use conventional commits" might not activate when needed.

Rulesync issue #1765 proposes a `ruleDiscoveryMode: "inline"` option for this.

## Next Steps (Not Started)

1. Extend `install.py` to symlink skills into `~/.agents/skills/` for Codex/Antigravity (one shared target serves both — see Re-verification above)
2. Watch rulesync issue #1765 (rules → AGENTS.md inline) for upstream fix. #1685 (skills path `.codex/` → `.agents/`) — **done**, our PR #1766, shipped in 8.28.0
3. Revisit `antigravity-cli` target coverage as rulesync adds features
4. Build the pre-push hook for rulesync generation if/when format conversions are needed
