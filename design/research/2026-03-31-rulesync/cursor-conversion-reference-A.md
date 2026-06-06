# Cursor CLI Conversion Reference

**Date:** 2026-03-31
**Purpose:** Practical reference for converting a Claude Code configuration (Claudefiles + Dotfiles) to work with Cursor CLI. Per-section confidence ratings reflect how well-tested each path is.

---

## 1. Zero-Conversion Files

**Confidence: HIGH**

The majority of the configuration transfers without file modification. Cursor reads SKILL.md and agent markdown natively. CLI scripts are on PATH and agent-agnostic. Symlink into `~/.cursor/` the same way they go into `~/.claude/`.

### Skills (57 Claudefiles + 14 Dotfiles = 71 total)

Cursor reads SKILL.md from `~/.cursor/skills/` and legacy `~/.claude/skills/`. Symlink directly.

- **30 mine.* skills:** address-pr-issues, audit, brainstorm, build, challenge, clean-code, commit-push, create-issue, create-pr, debug, decompose, define, eval-repo, gap-close, grill, implementation-review, issues-triage, mockup, mutation-test, orchestrate, plan, prior-art, research, review, ship, tool-gaps, visual-qa, worktree-rebase, wp, write-skill
- **19 i-* skills:** adapt, animate, audit, bolder, clarify, colorize, critique, delight, distill, frontend-design, harden, layout, optimize, overdrive, polish, quieter, shape, teach-impeccable, typeset
- **6 cli-* skills:** affordances, audit, clarify, distill, harden, output
- **2 cm-* skills:** get-token-insights, recall-conversations
- **14 Dotfiles skills:** 3d-print, banfield-api, container-metrics, domuscura-api, gog, ha-api, karakeep-api, karakeep-enrich, kimai, listonic-api, monarch-api, otf-api, paperless-api, plus learned/

**Caveat:** Many skills contain AskUserQuestion YAML blocks Cursor cannot execute natively. See [Section 7](#7-askuserquestion-gap).

### Agents (18)

Cursor reads from `~/.cursor/agents/` and `~/.claude/agents/`. Frontmatter maps cleanly:

| Claude Code | Cursor | Notes |
|---|---|---|
| `name`, `description` | Same | Identical |
| `tools` | `readonly` | Cursor uses boolean instead of tool list |
| `model` | `model` | Cursor accepts `inherit`, `fast`, or specific ID |
| N/A | `is_background` | Cursor-only |

All 18 agents transfer: architect, code-reviewer, engineering-{backend,data,frontend,sre,technical-writer}, integration-reviewer, issue-refiner, lazy-checker, llm-checker, nitpicker, planner, qa-specialist, researcher, testing-reality-checker, visual-diff, wtf-reviewer.

### Commands (14 total: 6 Claudefiles + 8 Dotfiles)

Cursor commands in `.cursor/commands/*.md` are simpler prompt templates. Minor adaptation for complex commands, but markdown files transfer directly.

### CLI Scripts (20 bin/ scripts)

Standalone PATH executables. No conversion. Both tools invoke them via shell.

### Symlink strategy

Extend `install.py` to symlink into `~/.cursor/` alongside `~/.claude/`:

```
~/.cursor/skills/   -> same targets as ~/.claude/skills/
~/.cursor/agents/   -> same targets as ~/.claude/agents/
~/.cursor/commands/ -> same targets as ~/.claude/commands/
```

---

## 2. Rules Conversion

**Confidence: MEDIUM-HIGH** -- .mdc format is documented. Conditional block strategy for mixed-content rules is untested.

### .mdc format

Cursor rules use `.mdc` extension with YAML frontmatter:

```yaml
---
description: Brief description of what this rule covers
alwaysApply: true
---
# Rule content (standard markdown)
```

Fields: `description` (required), `alwaysApply: true` (global), `globs: "*.py"` (file-scoped).

### 18 rules analyzed in depth

**Category A: Fully portable (10 rules) -- add frontmatter only**

| Rule | Frontmatter |
|---|---|
| `coding-style.md` | `alwaysApply: true` |
| `python.md` | `globs: "*.py"` |
| `typescript.md` | `globs: "*.ts,*.tsx"` |
| `frontend.md` | `globs: "*.tsx,*.jsx,*.css"` |
| `testing.md` | `alwaysApply: true` |
| `security.md` | `alwaysApply: true` |
| `reliability.md` | `alwaysApply: true` |
| `dependency-injection.md` | `alwaysApply: true` |
| `writing-quality.md` | `alwaysApply: true` |
| `verification.md` | `alwaysApply: true` |

**Category B: Mixed content (6 rules) -- conditional comment blocks**

| Rule | Portable % | Claude-specific content |
|---|---|---|
| `agents.md` | ~5% | Agent tool, subagent_type dispatch |
| `capabilities-core.md` | ~10% | Intent routing, Skill() tool |
| `interaction.md` | ~30% | AskUserQuestion, EnterPlanMode |
| `bash-tools.md` | ~50% | Tool mapping (Read, Grep, Glob, Edit, Write) |
| `performance.md` | ~30% | Context window hooks |
| `command-output.md` | ~70% | get-tmp-filename specifics |

Conditional block strategy maintains a single source file:

```markdown
<!-- claude-only -->
Content visible to Claude Code, stripped for Cursor.
<!-- /claude-only -->

<!-- cursor-only
Content invisible to Claude Code (single HTML comment),
unwrapped by build script for Cursor.
-->
```

Build step: strip `<!-- claude-only -->` blocks, unwrap `<!-- cursor-only -->` blocks, add .mdc frontmatter, write to `~/.cursor/rules/`.

**Category C: Wholesale replacement (2 rules)**

| Rule | Why |
|---|---|
| `agents.md` | ~95% Claude Code Agent tool specifics |
| `worktrees.md` | `claude --worktree`, Claude Code safety rules |

Write separate Cursor-native versions in `rules/cursor/`.

### Remaining 21 common rules

All fully portable -- apply Category A (add frontmatter, `alwaysApply: true`): autonomous-run-discipline, build-the-lever, debugging-discipline, decomposition-discipline, encode-lessons-in-structure, eval-discipline, exhaust-the-design-space, experience-first, frontend-workflow (`globs`), git-workflow, instruction-quality, invariants, laziness-protocol, outcome-oriented-execution, performance-discipline, reader-load, receiving-code-review, redesign-from-first-principles, refactoring-discipline, subtract-first, sudo, tmux.

**Note:** `git-workflow.md` and `invariants.md` reference Claude Code concepts (code-reviewer dispatch, Agent tool isolation) but the references are small -- Cursor ignores instructions about tools it doesn't have.

### Personal rules (5 Dotfiles)

| Rule | Category |
|---|---|
| `capabilities.md` | C (replace) -- entirely Claude Code intent routing |
| `coding-style.md` | A (portable) |
| `machines.md` | A (portable) |
| `mcp-tools.md` | B (mixed) -- Context7 portable, Serena Claude-specific |
| `python-packaging.md` | A (portable) |

### Conversion script

```bash
#!/usr/bin/env bash
# convert-rules.sh -- build .mdc files from source .md rules
set -euo pipefail

SRC_DIR="${1:-rules/common}"
OUT_DIR="${2:-$HOME/.cursor/rules}"
mkdir -p "$OUT_DIR"

for src in "$SRC_DIR"/*.md; do
    base=$(basename "$src" .md)
    dest="$OUT_DIR/${base}.mdc"

    # Read frontmatter from sidecar .meta.yaml if present
    if [[ -f "${src%.md}.meta.yaml" ]]; then
        frontmatter=$(cat "${src%.md}.meta.yaml")
    else
        desc=$(head -1 "$src" | sed 's/^# //')
        frontmatter="description: \"${desc}\"\nalwaysApply: true"
    fi

    # Process conditional blocks
    content=$(cat "$src" \
        | sed '/<!-- claude-only -->/,/<!-- \/claude-only -->/d' \
        | sed 's/<!-- cursor-only//' \
        | sed 's/-->//')

    printf -- "---\n%b\n---\n\n%s\n" "$frontmatter" "$content" > "$dest"
done
```

---

## 3. CLAUDE.md Conversion

**Confidence: HIGH**

Wrap in .mdc frontmatter. Strip Claude Code-specific sections.

```yaml
---
description: Project context and instructions
alwaysApply: true
---
<!-- original CLAUDE.md content -->
```

**Strip:** Bash tool eval wrapping notes, `${CLAUDE_HOME}` references (change to `~/.cursor`), `get-skill-tmpdir`/`get-tmp-filename`, `claude-merge-settings`, three-layer settings merge section, `Skill()` permission type.

**Keep:** naming conventions, making-changes checklist, project-specific guidance.

---

## 4. Permissions

**Confidence: HIGH** -- mechanical mapping.

### Format: `Bash(cmd:*)` becomes `Shell(cmd)`

Claude Code uses typed permissions (`Bash()`, `Read()`, `Write()`, `Edit()`, `Grep()`, `Skill()`). Cursor uses `Shell(pattern)` for commands only. File permissions and `Skill()` have no equivalent -- drop them.

### All 52 entries mapped

**42 Bash entries convert to Shell** (drop the `:*` suffix -- Cursor uses prefix matching):

`gh`, `gh-issue`, `gh-pr-create`, `gh-pr-reply`, `gh-pr-resolve-thread`, `gh-pr-threads`, `ado-api`, `get-tmp-filename`, `get-skill-tmpdir`, `git-default-branch`, `git-branch-base`, `git-branch-log`, `git-branch-diff-stat`, `git-branch-diff-files`, `git-platform`, `cm-backfill-summaries`, `cm-clear-handoff`, `cm-import-conversations`, `cm-ingest-token-data`, `cm-memory-context`, `cm-memory-setup`, `cm-memory-sync`, `cm-onboarding`, `cm-recent-chats`, `cm-search-conversations`, `cm-sync-current`, `cm-write-config`, `git`, `ruff`, `pyright`, `bandit`, `pip-audit`, `safety`, `pytest`, `timeout`, `agnix`, `ls`, `uv`, `claude-tmux`, `edit-manifest`, `which`, `pytest-loop-reset`

**9 entries dropped** (no Cursor equivalent):
- `Read(/tmp/*)`, `Read(/tmp/**)` -- no per-path file read permissions
- `Write(/tmp/*)`, `Write(/tmp/**)` -- same
- `Edit(/tmp/*)`, `Edit(/tmp/**)` -- same
- `Grep(/tmp/*)`, `Grep(/tmp/**)` -- same
- `Skill(mine.commit-push)` -- no Skill() type

### Conversion script

```python
import re

def convert_permission(entry: str) -> str | None:
    for prefix in ("Read(", "Write(", "Edit(", "Grep(", "Skill("):
        if entry.startswith(prefix):
            return None
    m = re.match(r"Bash\(([^:)]+)(?::?\*?)?\)", entry)
    return f"Shell({m.group(1)})" if m else None
```

### Ready-to-use cli-config.json

```json
{
  "permissions": {
    "allow": [
      "Shell(gh)",
      "Shell(gh-issue)",
      "Shell(gh-pr-create)",
      "Shell(gh-pr-reply)",
      "Shell(gh-pr-resolve-thread)",
      "Shell(gh-pr-threads)",
      "Shell(ado-api)",
      "Shell(get-tmp-filename)",
      "Shell(get-skill-tmpdir)",
      "Shell(git-default-branch)",
      "Shell(git-branch-base)",
      "Shell(git-branch-log)",
      "Shell(git-branch-diff-stat)",
      "Shell(git-branch-diff-files)",
      "Shell(git-platform)",
      "Shell(git)",
      "Shell(ruff)",
      "Shell(pyright)",
      "Shell(bandit)",
      "Shell(pip-audit)",
      "Shell(safety)",
      "Shell(pytest)",
      "Shell(timeout)",
      "Shell(agnix)",
      "Shell(ls)",
      "Shell(uv)",
      "Shell(claude-tmux)",
      "Shell(edit-manifest)",
      "Shell(which)",
      "Shell(pytest-loop-reset)",
      "Shell(cm-backfill-summaries)",
      "Shell(cm-clear-handoff)",
      "Shell(cm-import-conversations)",
      "Shell(cm-ingest-token-data)",
      "Shell(cm-memory-context)",
      "Shell(cm-memory-setup)",
      "Shell(cm-memory-sync)",
      "Shell(cm-onboarding)",
      "Shell(cm-recent-chats)",
      "Shell(cm-search-conversations)",
      "Shell(cm-sync-current)",
      "Shell(cm-write-config)"
    ]
  }
}
```

---

## 5. Hooks

**Confidence: MEDIUM** -- preToolUse/postToolUse documented. CLI support for session events unconfirmed.

### Schema differences

| Aspect | Claude Code | Cursor |
|---|---|---|
| Location | `settings.json` `hooks` key | `.cursor/hooks.json` |
| Event names | PascalCase (`PreToolUse`) | camelCase (`preToolUse`) |
| Structure | Nested: events -> matchers -> hook arrays | Flat: array of hook objects |
| Timeout unit | Milliseconds | Seconds |
| Matcher | `"matcher": "Bash"` | `"match": { "tool": "shell" }` |

### Event name mapping

| Claude Code | Cursor | CLI support |
|---|---|---|
| `PreToolUse` | `preToolUse` | Working |
| `PostToolUse` | `postToolUse` | Working |
| `SessionStart` | `sessionStart` | Unknown in CLI |
| `SessionEnd` | N/A | No equivalent |
| `PreCompact` | N/A | No equivalent |
| `Stop` | N/A | No equivalent |
| `Notification` | N/A | No equivalent |
| `StatusLine` | N/A | No equivalent |

### Matcher mapping

| Claude Code | Cursor |
|---|---|
| `"Bash"` | `{ "tool": "shell" }` |
| `"Edit\|Write\|MultiEdit\|NotebookEdit"` | `{ "tool": "file_edit" }` |
| `"Agent"` | `{ "tool": "agent" }` |
| `"*"` | Omit `match` field |

### Timeout: divide by 1000

35000ms -> 35s, 5000ms -> 5s, 2000ms -> 2s, 10000ms -> 10s, 30000ms -> 30s.

### 15 hooks inventory

**Convert (7):**
- `sudo-poll.sh` (PreToolUse/Bash) -> preToolUse/shell
- `pytest-guard.sh` (PreToolUse/Bash) -> preToolUse/shell
- `pytest-loop-detector.sh` (PreToolUse/Bash) -> preToolUse/shell
- `tmux-drift-check.sh` (PreToolUse/*) -> preToolUse (no match)
- `phrase-monitor.sh` (PreToolUse/*) -> preToolUse (no match)
- `pytest-loop-reset.sh` (PostToolUse/Edit|Write) -> postToolUse/file_edit
- `pytest-loop-status.sh` (PostToolUse/Bash) -> postToolUse/shell

**Unknown (3)** -- depend on Cursor CLI sessionStart support:
- UUID session ID generator (SessionStart)
- `tmux-remind.sh` (SessionStart)
- `cm-memory-setup`, `cm-onboarding`, `cm-memory-context` (SessionStart)

**Drop (5):**
- `context-tier.sh` (PreToolUse/*) -- Claude Code-specific context tier system
- `subagent-compaction-check.sh` (PostToolUse/Agent) -- Claude Code JSONL parsing
- `cm-clear-handoff` (SessionEnd) -- no equivalent event
- `cm-memory-sync` (Stop) -- no equivalent event

### Converted hooks.json

Ready-to-use output for the 7 convertible hooks:

```json
{
  "hooks": [
    {
      "event": "preToolUse",
      "match": { "tool": "shell" },
      "command": "bash -c 'f=\"${CURSOR_HOME:-$HOME/.cursor}/scripts/hooks/sudo-poll.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 35
    },
    {
      "event": "preToolUse",
      "match": { "tool": "shell" },
      "command": "bash -c 'f=\"${CURSOR_HOME:-$HOME/.cursor}/scripts/hooks/pytest-guard.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 5
    },
    {
      "event": "preToolUse",
      "match": { "tool": "shell" },
      "command": "bash -c 'f=\"${CURSOR_HOME:-$HOME/.cursor}/scripts/hooks/pytest-loop-detector.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 5
    },
    {
      "event": "preToolUse",
      "command": "bash -c 'f=\"${CURSOR_HOME:-$HOME/.cursor}/scripts/hooks/tmux-drift-check.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 2
    },
    {
      "event": "preToolUse",
      "command": "bash -c 'f=\"${CURSOR_HOME:-$HOME/.cursor}/scripts/hooks/phrase-monitor.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 3
    },
    {
      "event": "postToolUse",
      "match": { "tool": "file_edit" },
      "command": "bash -c 'f=\"${CURSOR_HOME:-$HOME/.cursor}/scripts/hooks/pytest-loop-reset.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 2
    },
    {
      "event": "postToolUse",
      "match": { "tool": "shell" },
      "command": "bash -c 'f=\"${CURSOR_HOME:-$HOME/.cursor}/scripts/hooks/pytest-loop-status.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 2
    }
  ]
}
```

### Hook script changes

The hook scripts are bash executables and mostly agent-agnostic. Replace `${CLAUDE_HOME:-$HOME/.claude}` with `${CURSOR_HOME:-$HOME/.cursor}` in path references within the scripts themselves.

---

## 6. MCP Config

**Confidence: HIGH** -- nearly identical format.

Both use `mcpServers` object in JSON. Same `command`/`args`/`type` schema. Same `stdio`/`sse` transports.

```bash
cp ~/.claude/mcp.json ~/.cursor/mcp.json
```

One difference: Cursor has a ~40 tool limit across all MCP servers combined. Context7 (2 tools) + Home Assistant (many tools) could hit this ceiling.

---

## 7. AskUserQuestion Gap

**Confidence: MEDIUM** -- MCP workaround exists but timeout risk is untested.

### The problem

Claude Code has a native `AskUserQuestion` tool with labeled options, descriptions, multi-select, and preview. Cursor has no equivalent.

### Scale of impact

**2 rules** reference AUQ: `interaction.md`, `sudo.md`

**50 skills/commands** use AskUserQuestion YAML blocks:

| Category | Skills |
|---|---|
| mine.* (25) | address-pr-issues, audit, brainstorm, build, challenge, clean-code, create-issue, decompose, define, eval-repo, gap-close, grill, implementation-review, issues-triage, mutation-test, orchestrate, plan, prior-art, research, review, ship, tool-gaps, visual-qa, worktree-rebase, write-skill |
| i-* (17) | adapt, animate, bolder, clarify, colorize, delight, distill, frontend-design, harden, layout, optimize, overdrive, polish, quieter, shape, teach-impeccable, typeset |
| cli-* (6) | affordances, audit, clarify, distill, harden, output |
| Dotfiles (1) | 3d-print |
| Commands (9) | good-morning, issues, permissions-audit, bills, inbox, karakeep, monarch-money, paperless, tmux |

### MCP workaround: auq-mcp-server

**Package:** `paulp-o/ask-user-questions-mcp`
**Architecture:** Terminal-native stdio MCP server + `auq` client in a tmux pane. Architecturally compatible with WSL2+tmux.

**Supports:** single/multi-select options, free-text input, timeout auto-selection.

**Limitations:**
- Flat option arrays only -- loses label/description/preview richness
- Cursor MCP timeout reportedly as low as 60s
- Requires Bun or Node.js runtime
- Requires dedicated tmux pane for `auq` client

### Setup

```bash
# Install
bun add -g auq-mcp-server   # or: npm install -g auq-mcp-server

# Add to ~/.cursor/mcp.json
{
  "mcpServers": {
    "ask-user": {
      "command": "auq-mcp-server",
      "args": [],
      "type": "stdio"
    }
  }
}

# Run client in second tmux pane
auq
```

### Test procedure

1. Install and configure as above
2. Start Cursor CLI: `agent`
3. Trigger a skill that uses AUQ (e.g., `/mine.define`)
4. Verify the question appears in the `auq` pane
5. Answer within 60s (test normal flow)
6. Wait >60s on next question (test timeout behavior)

### Adaptation

Rich AUQ options lose fidelity. This:
```yaml
options:
  - label: "Option A"
    description: "Conservative approach with minimal changes"
```
becomes flat: `["Option A: Conservative approach"]`

---

## 8. Worktree Differences

**Confidence: MEDIUM-LOW** -- sparsely documented. Manual workaround inferred, not tested.

### Claude Code

```bash
claude --worktree my-branch  # creates worktree, enters it, runs claude
```

### Cursor CLI

Binary is `agent` (in `~/.local/bin/`). No `--worktree` flag. Auto-worktree is IDE-only (parallel background agents).

### Manual workaround

```bash
git worktree add ../.worktrees/my-branch -b my-branch
agent --workspace ../.worktrees/my-branch
```

### Open questions

- Does `agent --workspace` resolve project `.cursor/rules/` from worktree path?
- Does Cursor pick up the worktree's `.cursor/mcp.json` or the main repo's?
- Do hooks fire correctly when working directory is a worktree?

All undocumented. Test empirically.

---

## 9. Preflight Wrappers

**Confidence: HIGH** -- fully agent-agnostic.

Shell wrappers (`claude_funcs`) do VPN check, SSO validation, `env -u` credential stripping, tmux naming. The checks are agent-agnostic; only the final binary name needs changing.

### Recommended refactor

Parameterize the binary so both tools share preflight logic:

```bash
_agent_preflight() {
    local binary="$1"; shift
    # VPN, SSO, credential checks...
    env -u AWS_SECRET_ACCESS_KEY -u GITHUB_TOKEN "$binary" "$@"
}

claude() { _agent_preflight claude "$@"; }
cursor() { _agent_preflight agent "$@"; }
```

### Flag mapping

| Claude Code | Cursor | Notes |
|---|---|---|
| `--worktree <branch>` | None | See Section 8 |
| `--model <id>` | `--model <id>` | Same |
| `--resume` | `--session <id>` | Different name |
| `--print` | `--print` | Same |

---

## 10. Accepted Gaps

**Confidence: HIGH** -- confirmed incompatibilities with no known workaround.

### Notification system
Claude Code's `Notification` hook fires `claude-notify.sh` -> `wsl-notify-send.exe`. No Cursor CLI equivalent. **Impact:** Low-medium.

### StatusLine
Starship prompt integration. No Cursor CLI equivalent. **Impact:** Low.

### Settings merge (three-layer)
Claude Code merges Claudefiles + Dotfiles + machine overrides. Cursor has single `cli-config.json`. **Impact:** Medium. Options: template script, env vars, or flat config.

### Typed subagent dispatch
Claude Code's `Agent(subagent_type: "code-reviewer")` has no direct equivalent. Cursor delegates based on agent descriptions or explicit `/agent-name`. **Impact:** High for orchestration skills (mine.orchestrate, mine.review, mine.challenge, mine.clean-code). Workaround: rewrite dispatch instructions from "launch Agent with subagent_type" to "delegate to the code-reviewer agent."

### Skill() permission type
No equivalent. Skills invoke without gating. **Impact:** None in practice.

### TaskCreate
No Cursor equivalent. Skills using it lose progress display. **Impact:** Low-medium.

### Memory / learned rules
No native equivalent. Community workarounds: Memory Bank rules, MCP servers. Learned rules in Dotfiles can convert to regular Cursor rules, but auto-learning is lost. **Impact:** Medium.

### Plugin system
Claude Code plugins (pyright-lsp, typescript-lsp, playwright) have no CLI equivalent. Cursor extensions are IDE-only. **Impact:** Medium for LSP, low for Playwright (available as MCP).

### get-tmp-filename / get-skill-tmpdir
Scripts work in Cursor (they're on PATH). No equivalent convention, but no actual breakage. **Impact:** None.

### includeGitInstructions
Claude Code's `"includeGitInstructions": false` has no confirmed Cursor toggle. May get redundant git guidance. **Impact:** Low.

---

## 11. Confidence Levels

| Area | Confidence | Rationale |
|---|---|---|
| Zero-conversion files | **HIGH** | Shared SKILL.md/agent standards documented |
| Rules (Category A) | **HIGH** | .mdc format is simple frontmatter |
| Rules (Category B) | **MEDIUM** | Conditional comment block strategy untested |
| Rules (Category C) | **MEDIUM** | Replacement files need writing from scratch |
| CLAUDE.md | **HIGH** | Mechanical wrapping |
| Permissions | **HIGH** | Documented 1:1 `Bash()` -> `Shell()` mapping |
| Hooks (pre/postToolUse) | **MEDIUM-HIGH** | Documented events, matcher mapping needs testing |
| Hooks (sessionStart) | **LOW** | CLI-mode support undocumented |
| Hooks (sessionEnd/stop) | **LOW** | No Cursor equivalents found |
| MCP config | **HIGH** | Nearly identical, copy the file |
| AskUserQuestion | **MEDIUM** | auq-mcp-server exists, 60s timeout risk unknown |
| Worktrees | **MEDIUM-LOW** | Manual workaround inferred, not tested |
| Preflight wrappers | **HIGH** | Agent-agnostic, binary name swap only |
| Accepted gaps | **HIGH** | Confirmed absences |

### Overall

~75% of the configuration transfers with zero or minimal changes (skills, agents, CLI scripts, MCP, preflights). The remaining 25% splits between mechanical conversion (rules, permissions, hooks) and genuine gaps (AskUserQuestion, typed subagents, session hooks).

Practical blockers for full migration:
1. **AskUserQuestion** -- 50 skills/commands depend on it
2. **Typed subagent dispatch** -- orchestration skills assume Claude Code's Agent tool
3. **SessionStart/Stop hooks** -- memory system hooks have no conversion path

None prevent basic coding work. They block the workflow orchestration built on top of Claude Code.

### Quick-start checklist

```
[ ] Install Cursor CLI: curl https://cursor.com/install -fsS | bash
[ ] Verify: agent --version
[ ] Symlink skills/agents: ln -s ~/.claude/{skills,agents}/* ~/.cursor/{skills,agents}/
[ ] Convert 5 core rules to .mdc (coding-style, python, testing, git-workflow, security)
[ ] Create ~/.cursor/cli-config.json with Shell() permissions
[ ] Copy MCP: cp ~/.claude/mcp.json ~/.cursor/mcp.json
[ ] Create ~/.cursor/hooks.json with portable hooks
[ ] Install auq-mcp-server if AUQ skills needed
[ ] Add cursor() wrapper to shell functions
[ ] Test with a real task; note gaps; decide on dual-stack vs. migrate
```

### File count summary

| Category | Count | Conversion |
|---|---|---|
| Skills | 71 total | Symlink only |
| Agents | 18 | Symlink only |
| Commands | 14 | Symlink (minor adaptation) |
| CLI scripts | 20 | No change |
| Rules | 44 (39 common + 5 personal) | .mdc conversion |
| Hooks | 15 configured | 7 convert, 3 unknown, 5 drop |
| Permissions | 52 entries | 42 convert, 9 drop, 1 Skill() drop |
| MCP | 1 file | Copy |
| Settings | 1 file | Rewrite |
