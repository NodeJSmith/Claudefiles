# Claude Code to Cursor CLI: Conversion Reference

**Date:** 2026-03-31
**Purpose:** Self-contained guide for converting an existing Claude Code configuration
(Claudefiles + Dotfiles) to work with Cursor CLI. Designed to be fed directly to another
AI agent performing the conversion.

**Scope:** This covers the full surface area: rules, permissions, hooks, MCP config,
CLAUDE.md, worktrees, and preflight wrappers. It does NOT cover the IDE (VS Code) mode
of Cursor -- only the terminal CLI (`agent` binary).

---

## 1. Zero-Conversion Files

These files use shared standards and work in both tools without modification. Symlink or
copy them into the Cursor equivalents.

| Category | Count | Claude Code location | Cursor location | Notes |
|----------|-------|---------------------|-----------------|-------|
| Skills | 57+ | `~/.claude/skills/*/SKILL.md` | `~/.cursor/skills/*/SKILL.md` | SKILL.md is a shared standard. Cursor also reads from `~/.claude/skills/` as a legacy path. |
| Agents | 18 | `~/.claude/agents/*.md` | `~/.cursor/agents/*.md` | YAML frontmatter fields are compatible. Cursor adds `readonly` and `is_background` fields (ignored by Claude Code). |
| Commands | 6 | `~/.claude/commands/*.md` | `~/.cursor/commands/*.md` | Cursor commands are simpler (inline prompts, not workflows). Minor format differences. |
| CLI scripts | 20 | `~/.local/bin/` (via `~/Claudefiles/bin/`) | Same PATH | Agent-agnostic executables. Both tools invoke them via shell. |

**Personal Dotfiles additions (also zero-conversion):**

| Category | Count | Location |
|----------|-------|----------|
| Personal skills | 13 | `~/Dotfiles/config/claude/skills/*/SKILL.md` |
| Personal commands | 8 | `~/Dotfiles/config/claude/commands/*.md` |

**Total zero-conversion: ~122 files** (57 skills + 13 personal skills + 18 agents + 6 commands + 8 personal commands + 20 CLI scripts).

### Agent frontmatter mapping

```yaml
# Claude Code agent definition
---
name: code-reviewer
description: Reviews code for correctness, style, and bugs
model: sonnet
tools:
  - Read
  - Grep
  - Glob
  - Bash
---

# Cursor equivalent (same file works in both)
# Cursor ignores `tools` and uses `readonly` instead.
# Add Cursor-specific fields if needed:
---
name: code-reviewer
description: Reviews code for correctness, style, and bugs
model: sonnet
readonly: true
---
```

Both tools read the same markdown body below the frontmatter. Agent files are the most
portable component of the entire setup.

---

## 2. Rules Conversion

Claude Code rules are plain `.md` files loaded from `~/.claude/rules/common/`. Cursor
rules are `.mdc` files in `~/.cursor/rules/` with YAML frontmatter controlling when they
apply.

### The .mdc format

Every Cursor rule needs a YAML frontmatter block:

```markdown
---
description: Coding style conventions for all projects
alwaysApply: true
---

# Coding Style

(rule content here)
```

**Frontmatter fields:**

| Field | Values | Use when |
|-------|--------|----------|
| `alwaysApply` | `true` | Rule should load for every conversation (equivalent to Claude Code global rules) |
| `globs` | `"*.py"`, `"src/**"` | Rule should load only when matching files are in context |
| `description` | string | Always required. Cursor uses this for auto-attach decisions. |

### Per-file classification

**39 total rules** (common + personal). Here is the portability breakdown:

#### Fully portable (31 common + 3 personal = 34 rules)

These rules contain no Claude Code-specific tool references. Wrap each in `.mdc`
frontmatter and they work as-is.

**Use `globs` for language-specific rules:**

| Rule | Frontmatter |
|------|-------------|
| `python.md` | `globs: "*.py"` |
| `typescript.md` | `globs: "*.ts,*.tsx"` |
| `frontend.md`, `frontend-workflow.md` | `globs: "*.tsx,*.jsx,*.css"` |
| `python-packaging.md` (personal) | `globs: "pyproject.toml"` |

**Use `alwaysApply: true` for everything else** (27 common + 2 personal):
`coding-style`, `testing`, `git-workflow`, `security`, `reliability`,
`dependency-injection`, `debugging-discipline`, `verification`, `laziness-protocol`,
`reader-load`, `refactoring-discipline`, `writing-quality`, `decomposition-discipline`,
`autonomous-run-discipline`, `performance-discipline`, `subtract-first`,
`redesign-from-first-principles`, `outcome-oriented-execution`,
`encode-lessons-in-structure`, `build-the-lever`, `exhaust-the-design-space`,
`experience-first`, `instruction-quality`, `receiving-code-review`, `eval-discipline`,
`invariants`, `command-output`, plus personal `coding-style` and `machines`.

**Conversion script** -- for each fully portable rule:

```bash
# Example: convert coding-style.md to coding-style.mdc
SOURCE="~/.claude/rules/common/coding-style.md"
TARGET="~/.cursor/rules/coding-style.mdc"

# Prepend frontmatter
cat > "$TARGET" << 'FRONTMATTER'
---
description: Coding style conventions -- immutability, file organization, naming
alwaysApply: true
---

FRONTMATTER
cat "$SOURCE" >> "$TARGET"
```

#### Mixed content (6 rules) -- need conditional comment blocks

These rules contain some Claude Code-specific content (tool names, API references)
mixed with portable guidance. Use conditional comment blocks to mark tool-specific
sections:

```markdown
<!-- claude-only -->
Use the `Agent` tool with `subagent_type: "code-reviewer"` to dispatch...
<!-- /claude-only -->

<!-- cursor-only
Use `/code-reviewer` or describe the review task to trigger auto-delegation...
-->
```

**How this works:**
- Claude Code sees the `claude-only` content as regular markdown (HTML comments are
  stripped by the renderer) and ignores the `cursor-only` block (it is an HTML comment).
- A conversion script strips `<!-- claude-only -->...<!-- /claude-only -->` blocks and
  unwraps `<!-- cursor-only ... -->` blocks for the Cursor version.

| Rule file | Claude-specific content | Portable % |
|-----------|------------------------|------------|
| `capabilities-core.md` | Intent routing table referencing `Skill()` permission type, `/mine.*` skills | ~30% portable (CLI tool table is portable; skill routing is Claude-specific) |
| `interaction.md` | References `AskUserQuestion`, `EnterPlanMode`, `Agent` tool with `subagent_type`, `TaskCreate` | ~50% portable (clarify-don't-plan principle is universal; tool names differ) |
| `bash-tools.md` | References Claude Code-specific tools (`Read`, `Grep`, `Glob`, `Edit`, `Write`) | ~70% portable (the principle of using built-in tools over shell commands applies; tool names differ) |
| `sudo.md` | References PreToolUse hooks, hook script paths | ~60% portable (the sudo workflow pattern is universal; hook mechanism differs) |
| `tmux.md` | References `claude-tmux` script (portable), but mentions PreToolUse hook for drift detection | ~80% portable |
| `performance.md` | References specific agent files, model declarations, subagent types, PreToolUse/PostToolUse hooks | ~5% portable (almost entirely Claude Code model/agent routing) |

**Personal rules (mixed):**

| Rule file | Claude-specific content | Portable % |
|-----------|------------------------|------------|
| `capabilities.md` (personal) | Entire file is CLI tool routing + skill dispatch | ~70% portable (CLI tool table is agent-agnostic; skill dispatch differs) |
| `mcp-tools.md` | References Context7 and Serena MCP tools | ~90% portable (MCP is shared; just update paths) |

#### Wholesale replacement needed (2 rules)

These rules are so deeply tied to Claude Code internals that a separate Cursor-native
version is more practical than conditional blocks.

| Rule file | Why | Replacement approach |
|-----------|-----|---------------------|
| `agents.md` | Entire file is a routing table for Claude Code's `Agent` tool with `subagent_type` dispatch. References `isolation: "worktree"`, `Explore` subagent type, `run_in_background`. | Write `rules/cursor/agents.mdc` describing Cursor's agent delegation model, `/agent-name` invocation, and parallel agent worktree isolation. |
| `worktrees.md` | References Claude Code's `--worktree` flag, git worktree safety rules specific to Claude Code's implementation, and the `isolation: "worktree"` parameter on the Agent tool. | Write `rules/cursor/worktrees.mdc` covering `agent --workspace <path>` and Cursor's native parallel agent worktree system. |

---

## 3. CLAUDE.md Conversion

`CLAUDE.md` (project-level instructions) becomes an always-apply `.mdc` rule in Cursor.

**Before** -- `<project>/CLAUDE.md` (plain markdown, loaded automatically).

**After** -- `<project>/.cursor/rules/project-context.mdc`:

```markdown
---
description: Project-level instructions and conventions
alwaysApply: true
---

(CLAUDE.md content here, with Claude-specific sections stripped)
```

**What to strip from CLAUDE.md during conversion:**
- References to `Bash tool wraps commands in eval` (Claude Code-specific sandbox detail)
- `$(...)` command substitution workarounds (Claude Code-specific)
- `get-skill-tmpdir` / `get-tmp-filename` references (replace with standard `mktemp`)
- `claude-merge-settings` references (no Cursor equivalent)
- `${CLAUDE_HOME:-~/.claude}` path references (replace with `~/.cursor`)

---

## 4. Permissions Mapping

Claude Code permissions live in `settings.json` under `permissions.allow`. Cursor
permissions live in `~/.cursor/cli-config.json` under `permissions.allow`.

### Format differences

| Claude Code format | Cursor format | Notes |
|-------------------|---------------|-------|
| `Bash(git:*)` | `Shell(git)` | Cursor uses `Shell()` not `Bash()`. No glob -- just the command name. |
| `Bash(gh)` | `Shell(gh)` | Same pattern. |
| `Bash(timeout:*)` | `Shell(timeout)` | Same pattern. |
| `Read(/tmp/*)` | (not needed) | Cursor has no `Read()` permission type. File reads are allowed by default. |
| `Write(/tmp/*)` | (not needed) | Cursor has no `Write()` permission type. |
| `Edit(/tmp/*)` | (not needed) | Cursor has no `Edit()` permission type. |
| `Grep(/tmp/*)` | (not needed) | Cursor has no `Grep()` permission type. |
| `Skill(mine.commit-push)` | (not needed) | Cursor has no `Skill()` permission type. Skills auto-invoke. |

### Conversion rules

Apply these transforms to every entry in `settings.json` `permissions.allow`:

1. **`Bash(cmd:*)` or `Bash(cmd)`** becomes **`Shell(cmd)`**. Drop the glob suffix.
2. **`Read()`, `Write()`, `Edit()`, `Grep()`** entries -- drop entirely. Cursor does not gate these operations.
3. **`Skill()`** entries -- drop entirely. Cursor has no Skill permission type.
4. **Deduplicate.** `Bash(gh)` and `Bash(gh:*)` both become `Shell(gh)`. Keep one.

### Example (representative subset)

```
Claude Code                    Cursor
─────────────────────────────  ──────────────────
Bash(gh)                  -->  Shell(gh)
Bash(gh:*)                -->  (merged into above)
Bash(gh-issue:*)          -->  Shell(gh-issue)
Bash(git:*)               -->  Shell(git)
Bash(ruff:*)              -->  Shell(ruff)
Bash(pytest:*)            -->  Shell(pytest)
Bash(timeout:*)           -->  Shell(timeout)
Bash(uv:*)                -->  Shell(uv)
Bash(cm-memory-sync:*)    -->  Shell(cm-memory-sync)
Read(/tmp/**)             -->  (drop)
Write(/tmp/**)            -->  (drop)
Edit(/tmp/**)             -->  (drop)
Grep(/tmp/**)             -->  (drop)
Skill(mine.commit-push)   -->  (drop)
```

The full settings.json has 51 allow entries. After deduplication and dropping
unsupported types, the Cursor config has ~42 `Shell()` entries.

---

## 5. Hooks Conversion

Claude Code hooks are defined in `settings.json` under the `hooks` key. Cursor hooks
live in a separate `hooks.json` file (project: `.cursor/hooks.json`, global:
`~/.cursor/hooks.json`).

### Schema differences

| Aspect | Claude Code | Cursor |
|--------|------------|--------|
| **Event names** | PascalCase: `PreToolUse`, `PostToolUse`, `SessionStart` | camelCase: `preToolUse`, `postToolUse`, `sessionStart` |
| **Timeouts** | Milliseconds: `"timeout": 5000` | Seconds: `"timeout": 5` |
| **Matcher location** | Sibling to `hooks` array: `{ "matcher": "Bash", "hooks": [...] }` | Inside each hook: `{ "event": "preToolUse", "matcher": "Bash", ... }` |
| **Config location** | Embedded in `settings.json` | Separate `hooks.json` file |
| **Hook type** | `"type": "command"` always | `"type": "command"` always |
| **Supported events** | `PreToolUse`, `PostToolUse`, `SessionStart`, `SessionEnd`, `PreCompact`, `Stop`, `Notification` | `preToolUse`, `postToolUse`, `sessionStart`, `beforeShellExecution`, `afterShellExecution`, `afterFileEdit` |

### Event mapping

| Claude Code event | Cursor event | Compatibility |
|------------------|--------------|---------------|
| `PreToolUse` | `preToolUse` | Direct mapping. Matcher syntax may differ slightly. |
| `PostToolUse` | `postToolUse` | Direct mapping. |
| `SessionStart` | `sessionStart` | Direct mapping. |
| `SessionEnd` | (unknown) | No documented equivalent. |
| `PreCompact` | (none) | No equivalent. Cursor handles compaction internally. |
| `Stop` | (none) | No equivalent. |
| `Notification` | (none) | **No equivalent in CLI mode.** The WSL notification pipeline cannot be ported. |

### Before/After: single hook entry

**Claude Code** (nested in `settings.json` under `hooks.PreToolUse`):

```json
{
  "matcher": "Bash",
  "hooks": [{
    "type": "command",
    "command": "bash -c 'f=\"${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/pytest-guard.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
    "timeout": 5000
  }]
}
```

**Cursor** (flat entry in `~/.cursor/hooks.json` `hooks` array):

```json
{
  "event": "preToolUse",
  "matcher": "Bash",
  "type": "command",
  "command": "bash -c 'f=\"$HOME/.cursor/scripts/hooks/pytest-guard.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
  "timeout": 5
}
```

### Key differences in the conversion

1. **Flatten the nested structure.** Claude Code groups hooks by event, then by matcher,
   then lists hooks. Cursor uses a flat array where each hook declares its own event and
   matcher.

2. **Convert timeouts.** Divide milliseconds by 1000. Round up fractional values.
   `5000` becomes `5`. `2000` becomes `2`. `35000` becomes `35`.

3. **Replace `${CLAUDE_HOME:-$HOME/.claude}`** with `$HOME/.cursor` in all command
   strings (or keep a shared scripts directory that both tools can reference).

4. **Drop unsupported hooks.** `Notification`, `PreCompact`, `Stop`, and `SessionEnd`
   hooks have no Cursor equivalent. The functionality they provide (WSL notifications,
   memory sync on stop, handoff clearing) is lost.

### Full hook inventory and portability

| Hook script | Claude Code event | Portable? | Notes |
|-------------|------------------|-----------|-------|
| `pytest-guard.sh` | PreToolUse (Bash) | Yes | Guards pytest invocations. Works in both. |
| `pytest-loop-detector.sh` | PreToolUse (Bash) | Yes | Detects test failure loops. Works in both. |
| `sudo-poll.sh` | PreToolUse (Bash) | Yes | Handles sudo auth. Works in both. |
| `context-tier.sh` | PreToolUse (*) | Partial | Context tier guidance. Cursor may not expose the same env vars. |
| `tmux-drift-check.sh` | PreToolUse (*) | Yes | Tmux session rename prompts. Agent-agnostic. |
| `phrase-monitor.sh` | PreToolUse (*) | Yes | Monitors for specific phrases. Agent-agnostic. |
| `pytest-loop-reset.sh` | PostToolUse (Edit\|Write\|...) | Yes | Resets loop counter on code edit. Works in both. |
| `pytest-loop-status.sh` | PostToolUse (Bash) | Yes | Reports loop status after shell commands. Works in both. |
| `subagent-compaction-check.sh` | PostToolUse (Agent) | No | Reads Claude Code-specific JSONL format. Not portable. |
| `tmux-remind.sh` | SessionStart | Yes | One-time tmux session rename. Agent-agnostic. |
| `cm-memory-setup` | SessionStart | Partial | claude-memory tool. Needs its own Cursor adaptation. |
| `cm-onboarding` | SessionStart | Partial | claude-memory tool. Same. |
| `cm-memory-context` | SessionStart | Partial | claude-memory tool. Same. |
| `cm-clear-handoff` | SessionEnd | No | No Cursor SessionEnd event. |
| `cm-memory-sync` | Stop | No | No Cursor Stop event. |

---

## 6. MCP Configuration

Both tools support MCP (Model Context Protocol) servers with nearly identical JSON
format. The only difference is file location.

| Aspect | Claude Code | Cursor |
|--------|------------|--------|
| **Global config** | `~/.claude/mcp.json` | `~/.cursor/mcp.json` |
| **Project config** | `<project>/.claude/mcp.json` | `<project>/.cursor/mcp.json` |
| **Format** | JSON with `mcpServers` key | JSON with `mcpServers` key |
| **Transports** | `stdio`, `sse`, `streamable-http` | `stdio`, `sse`, `streamable-http` |

### Conversion

```bash
cp ~/.claude/mcp.json ~/.cursor/mcp.json
# Then: search-replace any ~/.claude/ paths inside env/args to ~/.cursor/
```

The JSON structure is identical -- same `mcpServers` key, same `command`/`args`/`env`
fields, same stdio/SSE/streamable-http transports. The only difference is the file
location.

**Cursor limitation:** ~40 active MCP tools across all servers. If you have many MCP
servers, Cursor may hit this ceiling and silently disable some tools.

---

## 7. AskUserQuestion Gap

This is the single biggest portability issue. `AskUserQuestion` is a Claude Code
built-in tool that presents interactive prompts with single-select or multi-select
options. It is used extensively throughout the skill library.

### Impact assessment

- **2 rules** reference AskUserQuestion: `interaction.md`, `invariants.md` (indirectly)
- **48 skills** use AskUserQuestion (every skill that presents choices to the user)
- **0 agents** use it directly (agents delegate to skills that use it)

Skills that use AskUserQuestion range from light usage (1 call for a confirmation) to
heavy usage (mine.define with 17 references, mine.plan with 8, mine.brainstorm with 7).

### Cursor has no built-in equivalent

Cursor CLI has no interactive elicitation tool. When a skill says "call
AskUserQuestion with these options," Cursor will either:
- Ignore the instruction and pick an option itself
- Print the options as markdown text (not interactive)
- Error out

### Workaround: AskUserQuestion MCP Server

The `paulp-o/ask-user-questions-mcp` project provides an MCP server that emulates
AskUserQuestion via a terminal UI.

**Setup:**

```bash
# Install (requires Bun or Node 18+)
bunx ask-user-questions-mcp
# Or: npx ask-user-questions-mcp

# Add to ~/.cursor/mcp.json
{
  "mcpServers": {
    "ask-user": {
      "command": "bunx",
      "args": ["ask-user-questions-mcp"],
      "env": {}
    }
  }
}
```

**Capabilities:**
- Single-select and multi-select question types
- Renders in a separate tmux pane (the "client" pane)
- stdio transport -- compatible with WSL2 + tmux

**Limitations:**
- Flat options only. Claude Code's AskUserQuestion supports `label`, `description`,
  and `preview` fields on each option. The MCP server only supports flat string
  options, losing the richness of labeled/described choices.
- ~60-second timeout. Cursor's MCP call timeout is approximately 60 seconds. If the
  user does not respond within that window, the call fails. Claude Code has no such
  timeout on AskUserQuestion.
- Requires a separate tmux pane running the client process.
- The MCP server exposes a different tool name (`ask_user_question` vs
  `AskUserQuestion`), so skills would need their tool references updated.

### Adaptation strategy for skills

For skills with light AskUserQuestion usage (1-2 calls), the MCP workaround is
sufficient. For skills with heavy usage (mine.define, mine.plan, mine.brainstorm),
consider:

1. **Replace AskUserQuestion YAML blocks** with natural-language prompts that ask
   Cursor to present numbered options to the user as markdown.
2. **Accept the timeout risk.** Document that the user should answer within 60 seconds.
3. **Use the MCP server for critical choice points** and fall back to markdown-rendered
   options for low-stakes confirmations.

---

## 8. Worktree Differences

Claude Code has first-class worktree support via `claude --worktree <branch>`. Cursor
CLI has no equivalent flag.

### Claude Code workflow

```bash
# Creates a git worktree and enters it in one step
claude --worktree feature-branch
```

The `worktrees.md` rule file then governs behavior inside the worktree (edit only
worktree files, never run the installer, use `git -C`).

### Cursor CLI equivalent

```bash
# Step 1: Create the worktree manually
git worktree add .cursor/worktrees/feature-branch origin/main -b feature-branch

# Step 2: Launch Cursor CLI in the worktree directory
cd .cursor/worktrees/feature-branch
agent  # or: agent --workspace .
```

### Cursor's parallel agents

Cursor has native parallel agent support with automatic worktree isolation. When
Cursor launches multiple agents in parallel, each gets its own worktree
automatically. This is more mature than Claude Code's manual `isolation: "worktree"`
parameter.

### What to change in rules

The `worktrees.md` rule references Claude Code-specific concepts:
- `claude --worktree` flag
- `isolation: "worktree"` on the Agent tool
- `/mine.worktree-rebase` skill

For Cursor, write a replacement rule covering:
- Manual `git worktree add` + `agent --workspace <path>`
- Cursor's built-in parallel agent worktree isolation
- The same safety principles (edit only worktree files, never install from worktree)

---

## 9. Preflight Wrappers

Preflight wrappers (VPN checks, SSO auth, environment stripping) are agent-agnostic
shell functions. They just launch a binary after running checks.

### Conversion

Extract the binary name into a parameter so both tools share the same preflight logic:

```bash
_ai_preflight() {
  local binary="$1"; shift
  # VPN check, SSO refresh, env stripping -- all agent-agnostic
  if ! ip route | grep -q "tun0\|wg0"; then echo "VPN not connected"; return 1; fi
  aws sso login --profile work 2>/dev/null
  env -u CONDA_PREFIX -u VIRTUAL_ENV "$binary" "$@"
}

claude_funcs() { _ai_preflight claude "$@"; }
cursor_funcs() { _ai_preflight agent "$@"; }
```

---

## 10. Accepted Gaps

These Claude Code features have no Cursor equivalent and are accepted losses in a
conversion. They do not block basic usage but reduce workflow sophistication.

| Feature | What it does | Impact of losing it |
|---------|-------------|-------------------|
| **Notification hooks** | WSL desktop notifications on completion, errors, mentions | Lose passive monitoring. Must watch the terminal. |
| **StatusLine** | Starship integration showing agent state in the prompt | Cosmetic loss only. No functional impact. |
| **Settings merge** | Three-layer merge (Claudefiles + Dotfiles + machine overrides) | Must maintain a single flat config. Machine-specific overrides need manual management. |
| **Typed subagents** | `Agent` tool with `subagent_type` dispatching to 18 named agents | Lose precise agent routing. Cursor uses description-based auto-delegation. |
| **TaskCreate** | Built-in task tracking with progress display | Lose in-session task tracking. Use external tools (GitHub issues, todo files). |
| **Skill() permission** | Explicit permission grants for skill invocation | Skills auto-invoke in Cursor. No permission needed (but also no control). |
| **SessionEnd / Stop hooks** | Memory sync and cleanup on session end | Lose automatic memory operations. Must run manually. |
| **PreCompact hooks** | Custom behavior before context compaction | No Cursor equivalent. Context management is internal. |
| **Plugin system** | Claude Code plugins (pyright-lsp, playwright, last30days) | Cursor uses VS Code extensions (IDE mode) or MCP servers (CLI mode). Different ecosystem entirely. |
| **includeGitInstructions** | Toggle for built-in git instructions | No equivalent setting. Cursor always includes its own git guidance. |

---

## 11. Confidence Levels

Per-area assessment of conversion reliability.

| Area | Confidence | Rationale |
|------|-----------|-----------|
| **Skills (SKILL.md)** | **High (95%)** | Shared standard. Cursor reads them natively. Only risk: skills that reference Claude Code-specific tools (AskUserQuestion, Agent, TaskCreate) in their body text. |
| **Agents** | **High (90%)** | Compatible format. Minor frontmatter differences (`tools` vs `readonly`). |
| **CLI scripts** | **High (95%)** | Agent-agnostic PATH executables. Nothing to convert. |
| **Rules (portable)** | **High (90%)** | Mechanical conversion: add YAML frontmatter. Content is tool-agnostic. |
| **Rules (mixed)** | **Medium (60%)** | Conditional comment blocks work but need manual review. The Claude-specific sections must be identified correctly. |
| **Rules (replacement)** | **Medium (50%)** | agents.md and worktrees.md need full rewrites. Quality depends on understanding Cursor's agent delegation model. |
| **CLAUDE.md** | **High (85%)** | Mechanical wrap in .mdc. Strip Claude-specific sections. |
| **Permissions** | **High (85%)** | Format change is mechanical: `Bash(x:*)` to `Shell(x)`. Drop unsupported types. |
| **Hooks (portable)** | **Medium (70%)** | Schema conversion is straightforward. Uncertainty: does Cursor CLI respect all documented event types in practice? CLI mode is 5 months old. |
| **Hooks (dropped)** | **Low (20%)** | Notification, SessionEnd, Stop, PreCompact have no equivalents. Functionality is lost. |
| **MCP config** | **High (95%)** | Nearly identical format. Just change file location. |
| **AskUserQuestion** | **Low (30%)** | MCP workaround exists but has timeout limits, flat options, and requires separate process. Heavy-usage skills need redesign. |
| **Worktrees** | **Medium (65%)** | Manual `git worktree add` works but loses the one-command convenience. Cursor's parallel agent worktrees are actually better for multi-agent scenarios. |
| **Preflight wrappers** | **High (95%)** | Swap binary name. Trivially parameterizable. |
| **Settings merge** | **Low (15%)** | No Cursor equivalent. The three-layer architecture must be replaced with something else entirely. |

### Overall conversion feasibility

~70% of the configuration transfers with mechanical or no conversion. The remaining
~30% is split between partial workarounds (AskUserQuestion, mixed-content rules) and
accepted losses (notifications, settings merge, typed subagents).

The practical recommendation: start with the zero-conversion files (skills, agents,
scripts), add the fully-portable rules as `.mdc`, set up permissions and MCP config,
and evaluate whether the gaps matter for your actual work before investing in the
harder conversions.

---

## Appendix A: Conversion Checklist

```
[ ] Copy/symlink skills to ~/.cursor/skills/
[ ] Copy/symlink agents to ~/.cursor/agents/
[ ] Copy/symlink commands to ~/.cursor/commands/
[ ] Verify CLI scripts are on PATH
[ ] Convert 31 portable rules to .mdc (add frontmatter)
[ ] Handle 6 mixed-content rules (add conditional blocks, strip for Cursor)
[ ] Write 2 replacement rules (agents.mdc, worktrees.mdc)
[ ] Convert CLAUDE.md to project-context.mdc
[ ] Create ~/.cursor/cli-config.json with permissions
[ ] Create ~/.cursor/hooks.json with portable hooks
[ ] Copy ~/.claude/mcp.json to ~/.cursor/mcp.json
[ ] Install AskUserQuestion MCP server (if needed)
[ ] Create preflight wrapper for Cursor binary
[ ] Test with a real project
```

## Appendix B: Quick Reference -- Format Conversion Patterns

### Rule file .md to .mdc

```bash
# Input:  rules/common/python.md
# Output: ~/.cursor/rules/python.mdc

# 1. Create frontmatter
echo '---'
echo 'description: Python coding conventions'
echo 'globs: "*.py"'
echo '---'
echo ''
# 2. Append original content
cat rules/common/python.md
```

### Permission entry

```
Claude Code:  Bash(gh-issue:*)      -->  Cursor:  Shell(gh-issue)
Claude Code:  Bash(git:*)           -->  Cursor:  Shell(git)
Claude Code:  Read(/tmp/*)          -->  Cursor:  (drop)
Claude Code:  Skill(mine.ship)      -->  Cursor:  (drop)
```

### Hook entry

```
Claude Code:                              Cursor:
{                                         {
  "PreToolUse": [{                          "event": "preToolUse",
    "matcher": "Bash",                      "matcher": "Bash",
    "hooks": [{                             "type": "command",
      "type": "command",                    "command": "...",
      "command": "...",                     "timeout": 5
      "timeout": 5000                     }
    }]
  }]
}
```

### MCP server entry

```
~/.claude/mcp.json  -->  ~/.cursor/mcp.json  (copy, update internal paths)
```

## Appendix C: Files That Reference Claude Code Internals

Skills that reference Claude Code-specific tools and would need body-text updates for
full Cursor compatibility:

| Tool referenced | Skills using it | Conversion approach |
|----------------|----------------|-------------------|
| `AskUserQuestion` | 48 skills (see Section 7) | Use MCP workaround or rewrite as markdown prompts |
| `Agent` (with `subagent_type`) | mine.orchestrate, mine.challenge, mine.review, mine.clean-code, mine.plan, mine.build, mine.decompose, mine.issues-triage | Rewrite to use Cursor's `/agent-name` invocation or description-based delegation |
| `TaskCreate` | mine.orchestrate, mine.plan, mine.build, mine.define | Remove task tracking or use external todo mechanism |
| `EnterPlanMode` | interaction.md (tells agent NOT to use it) | Remove the prohibition (Cursor has no equivalent) |
| `Skill()` permission | settings.json, capabilities-core.md | Drop entirely (Cursor auto-invokes skills) |
| `Explore` subagent type | agents.md | Replace with Cursor's `readonly: true` agent concept |
| `isolation: "worktree"` | agents.md, worktrees.md | Replace with Cursor's native parallel worktree isolation |
| `get-skill-tmpdir` / `get-tmp-filename` | Many skills | Replace with `mktemp -d` / `mktemp` |

---

*This document was reconstructed from session artifacts dated 2026-03-31. Source
material: `research-cursor-cli-migration.md`, the Claudefiles rules directory, and
`settings.json` permission entries.*
