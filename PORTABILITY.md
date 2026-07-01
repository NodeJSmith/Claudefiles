# Tool Portability Matrix

This document tracks what Claudefiles capabilities can be mapped across AI coding
harnesses. It is intentionally evidence-oriented: entries should say whether they
are known from this repo, known from target documentation, or still need probing.

## Evidence Levels

| Level | Meaning |
| --- | --- |
| Known | Verified from this repo, target docs, or a working local install. |
| Likely | The target appears to support the concept, but exact format/limits need confirmation. |
| Unknown | Needs documentation lookup or an empirical probe. |
| No native support | The target does not expose an equivalent capability; use generated prose or a wrapper. |

## Capability Matrix

| Capability | Claude Code / Claudefiles | Codex CLI | OpenCode | Mapping Notes |
| --- | --- | --- | --- | --- |
| Always-on project or global instructions | Known: `rules/common/*.md` symlink into `$CLAUDE_CONFIG_DIR`; rules use `tool:` frontmatter for portability. | Known: native `$CODEX_HOME/AGENTS.md`, `$CODEX_HOME/AGENTS.override.md`, and project `AGENTS.md` chain. This repo already generates global Codex rules with `bin/codex-rules-sync`. | Known: project `AGENTS.md`, global `~/.config/opencode/AGENTS.md`, `instructions` config entries, and Claude fallback files. | Rules are the easiest mapping. Keep fail-closed `tool:` allowlists and generate target-native instruction files. |
| Nested/project-local instruction precedence | Known for Claude via installed config and project `CLAUDE.md` conventions. | Known: global, then project root-to-leaf `AGENTS.md`; closer files appear later and can override. | Known: walks local files upward; `AGENTS.md` wins over `CLAUDE.md`; global OpenCode instructions after local files; global Claude fallback if no OpenCode global file. | Generated global files must avoid overriding project-specific guidance. |
| Slash commands | Known: `commands/*.md` installed into Claude config. | Likely no native user-defined slash-command files; built-in slash commands exist. | Known: custom commands in `~/.config/opencode/commands/*.md`, `.opencode/commands/*.md`, or JSON config. Supports `$ARGUMENTS`, positional args, `agent`, `model`, and `subtask`. | Codex commands should probably convert to skills. OpenCode commands are a close direct mapping. |
| Skills as invocable workflows | Known: 71 `SKILL.md` files with `name`, `description`, `user-invocable`; many use `$ARGUMENTS`, temp dirs, and subagents. | Known: native skills in `$HOME/.agents/skills`, `.agents/skills`, and `/etc/codex/skills`; can be invoked or selected. | Known: native skills in global/project skill dirs; also discovers Claude Code skills under `~/.claude/skills`. | Simple skills likely map well. Workflow skills still need syntax/tool-name cleanup and empirical testing. |
| Skill auto-routing by description | Known: `SKILL.md` frontmatter descriptions drive loading/routing in Claude. | Known: skills have metadata and can be selected via `/skills` or `$skill-name`; implicit routing support exists via descriptions. | Known: skills have `name` and `description`; can be loaded by agents subject to skill permissions. | Descriptions are portable, but frontmatter schemas may need normalization. |
| Agent definitions | Known: 21 `agents/*.md` files with `name`, `model`, `description`, and `tools`. | Known: custom named agents in `~/.codex/agents/*.toml` or `.codex/agents/*.toml`; required fields include `name`, `description`, and `developer_instructions`. | Known: global/project markdown agents in `agents/*.md`; filename is the agent name; supports `mode: primary`, `mode: subagent`, or `mode: all`. | Codex needs Markdown-to-TOML conversion. OpenCode is structurally closer but needs frontmatter cleanup. |
| Parallel subagent dispatch | Known: many skills require launching multiple agents in one message. Local audit found `subagent_type` in 27 files. | Known: supports subagents, parallel workflows, max agent threads, and fan-out/fan-in patterns. | Known for subagents/child sessions; likely supports parallel fan-out through Task/subagents, but exact concurrency semantics should be probed. | Workflow-preserving conversion is feasible, not hypothetical, but needs target-specific prompt rewrites. |
| Subagent model selection | Known: agent frontmatter uses Claude aliases: 19 `sonnet`, 1 `haiku`, 1 `opus`; skills mention model aliases too. | Known: custom agent TOML supports `model` and reasoning effort. | Known: agent and command frontmatter can set `model`; subagents inherit caller model unless overridden. | Need target-specific model alias maps. Do not preserve `sonnet`/`haiku` literally unless configured. |
| Tool allowlists per agent | Known: 21 agent `tools:` lists use Claude tool names like `Read`, `Grep`, `Glob`, `Bash`, `Task`, MCP names. | Partial: no exact Claude-style per-agent `tools:` field; use sandbox, approval policy, MCP allowlists, app-tool settings, permissions, and external command rules. | Known: `permission` supports `read`, `edit`, `glob`, `grep`, `bash`, `task`, `skill`, `webfetch`, `websearch`, etc.; agent permissions override global. | OpenCode can map many tool restrictions directly. Codex needs semantic permission translation, not a field rename. |
| File read/search/edit tools | Known: Claude harness exposes file/search/bash tools; repo instructions depend on them. | Known: Codex has read/edit/shell/MCP tool surfaces governed by sandbox and permissions. | Known: OpenCode exposes read/edit/glob/grep/bash permissions and tools. | Prose instructions survive, but tool names and permission policy need target-specific mapping. |
| Bash/shell execution | Known: many skills assume Bash and repo helper CLIs. | Known: shell execution exists and can be governed by sandbox, approval, and `.rules`. | Known: `bash` permission supports allow/ask/deny rules. | Portable only if helper scripts are installed on PATH and command policies permit them. |
| Hook lifecycle events | Known: `settings.json` defines `PreToolUse`, `PostToolUse`, `PreCompact`, `SessionStart`, `SessionEnd`, and `Stop`. | Known: native hooks support `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`, `PostCompact`, `SubagentStart`, `SubagentStop`, and `Stop`. | Partial: no Claude-style shell hook config, but plugins expose events such as `tool.execute.before/after`, `session.*`, `permission.*`, and experimental compaction. | Codex hook conversion is plausible with JSON schema adaptation. OpenCode requires plugin rewrites. |
| Permission rules / allowlists | Known: `settings.json` uses Claude permission DSL; local audit found 9 `permissions.allow` entries. | Known: approval policy, permission profiles, MCP/app tool settings, `.rules`, and hooks. | Known: granular `permission` rules with last-match-wins behavior; most permissions default to allow. | Permissions are portable only semantically. Build explicit translators and warnings. |
| External helper binaries | Known: `bin/` tools such as `get-skill-tmpdir`, `cfl`, `codex-rules-sync`, `agnix-check`. | Known if installed into PATH; independent of harness. | Known if installed into PATH; independent of harness. | This is a useful portability anchor. Workflow conversion can lean on external CLIs when native harness features differ. |
| Persistent workflow state | Known: `cfl` provides SQLite-backed orchestration state. | Known if `cfl` is installed and callable. | Known if `cfl` is installed and callable. | Prefer external state over harness-specific session variables for portable workflows. |
| Temporary skill workspace | Known: `get-skill-tmpdir <skill>` is the repo convention. | Known if installed and callable. | Known if installed and callable. | Portable as an external helper; generated docs should avoid `$CLAUDE_SESSION_ID`. |
| Generated target config | Known for Codex rules only: `codex-rules-sync`. | Known for rules today; feasible for skills and agents using Codex config locations. | Feasible using `~/.config/opencode/` or project `.opencode/` component dirs. | Follow the generated-file pattern: header, source markers, deterministic order, no manual edits. |

## Conversion Difficulty

| Component | Difficulty | Why |
| --- | --- | --- |
| Rules | Low | Already have `tool:` frontmatter and a working Codex generator pattern. |
| OpenCode commands | Low to medium | OpenCode custom command Markdown supports `$ARGUMENTS`, agents, models, and subtask dispatch. Claude-specific prose/tool names still need cleanup. |
| OpenCode agents | Medium | Markdown shape is close, but Claude `name`, `model` aliases, and `tools` need conversion to OpenCode fields/permissions. |
| Codex agents | Medium | Agent bodies are portable, but need TOML generation and semantic permission/model mapping. |
| Simple skills | Medium | Both targets have native skills, but frontmatter compatibility and argument/routing conventions need probes. |
| Workflow skills | Medium to high | Codex and OpenCode both support subagents, so conversion is feasible; the hard part is rewriting Claude-specific dispatch syntax and validating concurrency/fan-in behavior. |
| Codex hooks | Medium to high | Lifecycle concepts overlap, but scripts must adapt to Codex hook JSON schemas. |
| OpenCode hooks/plugins | High | Requires plugin rewrites rather than config translation. |

## Local Usage Audit

| Feature | Local Usage | Converter Implication |
| --- | --- | --- |
| Skills | 71 `SKILL.md` files: 46 `mine-*`, 19 `i-*`, 6 `cli-*`; 59 user-invocable. | Skill conversion is high-value and should be automated, but not all skills are equally portable. |
| Commands | 6 Markdown commands, all with `description` frontmatter only. | OpenCode command conversion can infer names from filenames. Codex should likely convert these to skills. |
| Agents | 21 Markdown agents, all with `name`, `model`, `description`, `tools`. | Agent conversion needs model and tool/permission translation. |
| Rules | 31 common rules: 22 tagged `tool: claude, codex, antigravity`; 9 tagged `tool: claude`. | Existing fail-closed target tagging works and should extend to skills/agents once mappings are clear. |
| `$ARGUMENTS` | 41 files, 96 occurrences. | Target command/skill argument interpolation must be explicit. |
| `CLAUDE_CONFIG_DIR` | 53 files, 125 occurrences. | Replace with target config dir variables or generated absolute paths. |
| `get-skill-tmpdir` | 37 files, 44 occurrences. | Keep as a harness-neutral helper dependency. |
| Subagents | `subagent_type` in 27 files, 62 occurrences; Task/subagent prose in roughly 36 files. | Need dispatch syntax translation and target-specific built-in agent aliases. |
| Models | Agent frontmatter: 19 `sonnet`, 1 `haiku`, 1 `opus`. | Need configurable alias maps per target. |
| Hooks | 6 Claude lifecycle event keys and 5 hook scripts. | Treat as a later phase; hook schemas differ. |
| Permissions | 9 Claude permission allow entries. | Translate semantically; never copy raw DSL into target config. |

## Sources To Cite In Converter Design

| Target | Source |
| --- | --- |
| Codex config | `https://developers.openai.com/codex/config-basic` |
| Codex advanced config | `https://developers.openai.com/codex/config-advanced` |
| Codex config reference | `https://developers.openai.com/codex/config-reference` |
| Codex `AGENTS.md` | `https://developers.openai.com/codex/guides/agents-md` |
| Codex slash commands | `https://developers.openai.com/codex/cli/slash-commands` |
| Codex skills | `https://developers.openai.com/codex/skills` |
| Codex subagents | `https://developers.openai.com/codex/subagents` |
| Codex hooks | `https://developers.openai.com/codex/hooks` |
| Codex permissions | `https://developers.openai.com/codex/permissions` |
| OpenCode config | `https://opencode.ai/docs/config/` |
| OpenCode rules | `https://opencode.ai/docs/rules/` |
| OpenCode skills | `https://opencode.ai/docs/skills/` |
| OpenCode agents | `https://opencode.ai/docs/agents/` |
| OpenCode commands | `https://opencode.ai/docs/commands/` |
| OpenCode permissions | `https://opencode.ai/docs/permissions/` |
| OpenCode plugins | `https://opencode.ai/docs/plugins/` |
| OpenCode MCP | `https://opencode.ai/docs/mcp-servers/` |
| OpenCode schema | `https://opencode.ai/config.json` |

## Information We Still Need Next

| Question | How to Get It | Effort |
| --- | --- | --- |
| Do Claude-style skill frontmatter files load unchanged in Codex? | Symlink one simple existing skill into `$HOME/.agents/skills` under a temp profile/config and inspect discovery. | Low |
| Do Claude-style skill frontmatter files load unchanged in OpenCode? | Use a temp `OPENCODE_CONFIG_DIR` and `opencode debug config` or equivalent with one copied skill. | Low |
| How should `general-purpose` and `Explore` map to Codex/OpenCode built-ins? | Create minimal target configs and ask each harness to dispatch built-in agents. | Medium |
| Does OpenCode actually run multiple Task subagents concurrently? | Probe with two sleep/log subagents and compare timestamps. | Medium |
| How do Codex hooks and existing Claude shell hooks differ at stdin/stdout level? | Add a temporary logging hook and compare emitted JSON to existing hook expectations. | Medium |
| Can Codex or OpenCode safely consume generated config from symlinks? | Generate temp component dirs using symlinks and inspect target config loading. | Low |
| What model aliases should this repo expose? | Query installed target models and write an explicit alias table. | Medium |

## Recommended Starting Point

1. Build a read-only `bin/portability-audit` that classifies every skill/agent by the local usage patterns above.
2. Add target allowlist frontmatter to agents and skills only after audit output shows what would be included.
3. Convert OpenCode commands and agents first because their native formats are closest to the repo's current Markdown artifacts.
4. Convert Codex agents next through generated TOML.
5. Convert simple skills for both targets, then workflow skills with empirical subagent probes.
6. Leave hooks/plugins for a later phase after rules, commands, agents, and skills are working.

The feasibility picture is better than the initial unknown-heavy matrix suggested:
both Codex and OpenCode have native support for instructions, skills, named agents,
subagents, permissions, and hooks/plugin events. The work is mostly schema translation,
model/tool alias mapping, and empirical validation of workflow semantics.
