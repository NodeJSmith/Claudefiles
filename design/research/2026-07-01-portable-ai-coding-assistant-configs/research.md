---
topic: "Tools and patterns for portable AI coding assistant configs"
date: 2026-07-01
status: Draft
---

# Prior Art: Tools and Patterns for Portable AI Coding Assistant Configs

## The Problem

AI coding assistants now have overlapping but incompatible concepts: repository instructions, rules, skills, slash commands, named agents, subagents, hooks, permissions, MCP tools, and workflow bundles. A complex Claude Code setup cannot be copied directly into Codex, OpenCode, Cursor, Windsurf, Cline, Roo, Continue, or Aider without losing semantics.

The portability challenge is deciding what should be shared as plain instructions, what should be generated into target-native formats, and what should remain harness-specific because it controls enforcement, lifecycle hooks, permissions, or execution semantics.

## How We Do It Today

Claudefiles already has a portability seam for rules: `tool:` frontmatter on `rules/common/*.md` and `bin/codex-rules-sync`, which generates Codex `$CODEX_HOME/AGENTS.md` from rules tagged `codex`. Skills, commands, agents, hooks, and permissions are still Claude-centered; `PORTABILITY.md` now tracks the target capability matrix and local usage counts.

## Patterns Found

### Pattern 1: Canonical AGENTS.md as the Shared Baseline

**Used by**: AGENTS.md community, OpenCode, Cline, Roo Code, Devin/Windsurf Cascade, Aider via config, Codex repo, BMad Method.

**How it works**: Projects keep persistent agent instructions in a root `AGENTS.md`, optionally with nested `AGENTS.md` files for subdirectories. The file stays plain Markdown, so tools do not need to agree on a strict schema; they only need to agree on discovery and precedence.

This treats portability as a documentation-location problem rather than a conversion problem. Tool-specific files either import, symlink, or explicitly read the shared `AGENTS.md`.

**Strengths**: Lowest-friction, version-controlled, human-readable, and already supported by many tools.

**Weaknesses**: Plain Markdown cannot represent richer metadata such as activation modes, modes/personas, permissions, hooks, command definitions, or subagent workflows. Precedence varies by harness.

**Example**: https://agents.md/

### Pattern 2: Tool-Specific Shim Imports the Shared Baseline

**Used by**: Claude Code, Aider, OpenCode, Gemini CLI as documented by AGENTS.md, and other configurable tools.

**How it works**: Instead of translating all instructions into every proprietary format, each tool gets a minimal adapter. For Claude Code, `CLAUDE.md` can contain `@AGENTS.md` plus Claude-specific additions; for Aider, `.aider.conf.yml` can include `read: AGENTS.md`; for OpenCode, `opencode.json` can list shared instruction files and globs.

The shared baseline stays the source of truth, while shims carry only harness-specific details like imports, tool names, activation flags, or model-specific procedures.

**Strengths**: Small, auditable, and compatible with tools that do not natively read every shared file. Reduces drift.

**Weaknesses**: Requires one small adapter per harness. Some tools do not support imports, so the adapter may need config entries instead.

**Example**: https://docs.anthropic.com/en/docs/claude-code/memory

### Pattern 3: Multi-Format Ingestion Instead of Conversion

**Used by**: Cline, Roo Code, OpenCode, Devin/Windsurf Cascade.

**How it works**: The harness reads several known rule formats directly. Cline detects `.clinerules/`, `.cursorrules`, `.windsurfrules`, and `AGENTS.md`. OpenCode prefers `AGENTS.md` but falls back to Claude Code files and skills. Roo and Devin/Windsurf also aggregate legacy and current formats.

This moves portability into the loader. Users can adopt a new assistant without immediately deleting or converting existing config.

**Strengths**: Smooth migration path and lower switching cost.

**Weaknesses**: Loader behavior can be subtle. Precedence, aggregation, fallback, and conditional activation differ by tool, and stale legacy files can keep influencing behavior.

**Example**: https://docs.cline.bot/features/cline-rules

### Pattern 4: Path-Scoped and Conditional Rule Files

**Used by**: Claude Code `.claude/rules/`, Continue `.continue/rules`, Cline `.clinerules`, Devin/Windsurf `.devin/rules`, Roo mode-specific directories.

**How it works**: Rules are split into smaller files with activation metadata. Claude Code supports path-scoped rules; Continue supports `globs`, `regex`, `description`, and `alwaysApply`; Cline supports path frontmatter; Devin/Windsurf supports activation modes such as `glob`, `model_decision`, and `manual`.

The goal is context budgeting: universal rules stay always-on, while domain guidance loads only when relevant.

**Strengths**: Reduces context bloat, supports monorepos, and maps well to domain-specific conventions.

**Weaknesses**: Conditional semantics are not standardized. A converter must either preserve metadata approximately or degrade rules to always-on Markdown.

**Example**: https://docs.continue.dev/customize/deep-dives/rules

### Pattern 5: Installer or Bundler Emits Harness-Specific Artifacts

**Used by**: BMad Method.

**How it works**: A framework owns canonical agents, workflows, skills, and modules, then provides an installer that writes or links artifacts for selected tools. BMad documents `npx bmad-method install`, tool selection such as `--tools claude-code`, structured agents/workflows, and web bundles for Gemini Gems and ChatGPT Custom GPTs.

This is closer to a package manager than a rule-file standard. The reusable unit is a workflow system, not just instructions.

**Strengths**: Scales beyond instructions into agents, skills, commands, workflows, and supporting docs. Good fit for Claudefiles.

**Weaknesses**: Higher complexity. Requires canonical schema, target emitters, tests, and generated-file discipline.

**Example**: https://github.com/bmad-code-org/BMAD-METHOD

### Pattern 6: Direct One-to-One Converters Between Harnesses

**Used by**: [no source found]

**How it works**: A hypothetical converter would read Claude Code commands, agents, skills, hooks, rules, and settings, then emit equivalent Codex/OpenCode/Cursor/Windsurf/Aider/Continue/Roo/Cline artifacts.

The fetched sources did not show a mature, trustworthy general converter. Official docs and reference projects mostly show shared Markdown baselines, native compatibility readers, imports/symlinks, and installer frameworks.

**Strengths**: If built well, it could reduce migration friction for complex setups.

**Weaknesses**: Semantic gaps are hard: hooks and permissions are enforcement in some tools but instructions in others; skills and agents have different activation models; context precedence differs; lossy mappings are likely.

**Example**: [no source found]

## Anti-Patterns

- Duplicating the same instructions into many proprietary files causes drift. Claude Code explicitly recommends importing or symlinking `AGENTS.md` rather than duplicating shared instructions when a repo already uses `AGENTS.md`: https://docs.anthropic.com/en/docs/claude-code/memory
- Making rules too long, vague, or always-on wastes context and reduces adherence. Claude Code, Cline, and Devin/Windsurf all recommend concise, specific rules: https://docs.anthropic.com/en/docs/claude-code/memory, https://docs.cline.bot/features/cline-rules, https://docs.windsurf.com/windsurf/cascade/memories
- Treating instructions as enforcement is unsafe. Claude Code states `CLAUDE.md` is context, not enforced configuration, and recommends hooks or managed settings for behavior that must be blocked or run: https://docs.anthropic.com/en/docs/claude-code/memory
- Ignoring precedence and legacy fallbacks creates surprising behavior. OpenCode, Roo, Cline, and Devin/Windsurf all document different aggregation/fallback orders: https://opencode.ai/docs/rules/, https://docs.roocode.com/features/custom-instructions, https://docs.cline.bot/features/cline-rules, https://docs.windsurf.com/windsurf/cascade/memories

## Emerging Trends

- `AGENTS.md` is becoming the cross-tool lingua franca for repository-level agent instructions: https://agents.md/
- Tools are adding compatibility readers instead of waiting for a universal converter: Cline reads Cursor/Windsurf/AGENTS files; OpenCode reads Claude conventions; Roo reads AGENTS.md and legacy files; Devin/Windsurf processes AGENTS.md through its rules engine.
- Rule systems are moving toward metadata-driven activation: glob/path scoping, model-decision loading, manual mentions, and mode-specific directories.
- Reusable AI workflow packages are expanding beyond rules into agents, skills, workflows, slash commands, and web-agent bundles. BMad Method is the clearest fetched example.

## Relevance to Us

Claudefiles already matches the installer/bundler pattern: `install.py` owns symlinking, bundle selection, package installation, and `codex-rules-sync`. The current `tool:` frontmatter approach also matches prior art: shared source files with target-specific emission.

The likely best path is not to search for a general converter to adopt. The prior art suggests building a Claudefiles-specific portability layer around canonical source files, generated target artifacts, and thin shims. OpenCode should be the first richer target because it already reads Claude conventions and has close Markdown formats for commands and agents. Codex should be next for agents/skills, with TOML generation for agents and careful permission translation.

## Recommendation

Use a hybrid of three patterns:

1. Make `AGENTS.md` or generated `AGENTS.md` the common instruction baseline where possible.
2. Keep `tool:` allowlists and generated target files as the source-of-truth discipline.
3. Evolve `install.py` into a small bundler that can emit OpenCode and Codex commands, agents, skills, and eventually hooks/permissions.

Do not try to build or find a universal one-to-one converter first. The ecosystem does not appear to have a mature general-purpose converter, and the semantic gaps make exact conversion risky. Start with generated shims and target-native artifacts for the parts with clear support: rules, OpenCode commands, OpenCode agents, Codex agents, and simple skills.

## Sources

### Reference implementations

- https://raw.githubusercontent.com/openai/codex/main/AGENTS.md — Codex repository AGENTS.md example.
- https://github.com/bmad-code-org/BMAD-METHOD — Multi-tool AI workflow framework with agents, skills, bundles, and installers.
- https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/main/README.md — BMad install and bundle documentation.

### Blog posts & writeups

- No strong independent experience reports were found in this pass. Coverage here is mostly official docs and reference implementations.

### Documentation & standards

- https://agents.md/ — Cross-tool AGENTS.md convention.
- https://docs.anthropic.com/en/docs/claude-code/memory — Claude Code memory/rules/imports.
- https://opencode.ai/docs/rules/ — OpenCode rule and compatibility behavior.
- https://docs.cursor.com/en/context/rules — Cursor rules docs pointer; fetch was thin.
- https://docs.continue.dev/customize/deep-dives/rules — Continue rule metadata and activation.
- https://aider.chat/docs/usage/conventions.html — Aider conventions file usage.
- https://docs.cline.bot/features/cline-rules — Cline multi-format rules ingestion.
- https://docs.roocode.com/features/custom-instructions — Roo Code custom instruction aggregation.
- https://docs.windsurf.com/windsurf/cascade/memories — Devin/Windsurf memories/rules/AGENTS.md behavior.
