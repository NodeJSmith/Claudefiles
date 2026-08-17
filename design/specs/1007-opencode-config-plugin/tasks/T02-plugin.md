---
task_id: "T02"
title: "Write the OpenCode plugin that populates agent, command, instructions"
status: "planned"
depends_on: ["T01"]
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "FR#5", "FR#6", "FR#9"]
---

## Summary

Write `opencode/claudefiles.ts`, the dependency-free TypeScript plugin that supplies OpenCode's `agent`, `command`, and `instructions` config keys at process start by reading the live Claude install under `~/.claude/`. This replaces every file the old sync copied to disk. The plugin is the whole delivery mechanism: after this task and its symlink (T05), nothing is written to `~/.config/opencode/` except a three-key `config.json`.

The plugin is verified by running it under Node rather than by unit tests — the design's Test Strategy deliberately substitutes observation for unit coverage here, and Node 24 can execute the file directly.

## Target Files

- create: `opencode/claudefiles.ts`
- read: `opencode/config-data.json`
- read: `bin/opencode-sync` (`_split_frontmatter` at `:499-516`, `OPENCODE_COMMAND_RE` at `:170-172`)
- read: `design/specs/1007-opencode-config-plugin/design.md` (Architecture, Implementation Preferences, Key Constraints, Edge Cases)
- read: `~/.claude/agents/*.md`, `~/.claude/skills/*/SKILL.md`, `~/.claude/rules/common/*.md`, `~/.claude/rules/personal/*.md` (inputs at runtime)

## Prompt

Write `opencode/claudefiles.ts` exporting an OpenCode plugin with a single `config(cfg)` hook. `@opencode-ai/plugin` is already installed at `~/.config/opencode/node_modules` (OpenCode auto-installs it — `packages/opencode/src/config/config.ts:438-446`), so import its types if useful, but add no other dependency.

Resolve the install root as `~/.claude` — read `$CLAUDE_CONFIG_DIR` first and fall back to `path.join(os.homedir(), ".claude")`. **Never read `~/Claudefiles` or `~/Dotfiles`.** `~/.claude` is the union of both repos as installed; either repo alone is strictly less complete (Dotfiles owns eleven skills and all five personal rules). This is a Key Constraint in the design doc, not a preference.

Load `opencode/config-data.json` for every shared value — the tier map, the exclusion list, the skill-command template, and the instruction-directory list. Resolve its path relative to the plugin file's own location (`import.meta.url`), not relative to the config dir or the cwd: the plugin reaches `~/.config/opencode/claudefiles.ts` as a symlink into this repo, so a sibling-relative lookup is what finds the repo copy. **Define none of these values as literals in the plugin** — AC#22 greps for exactly that.

Populate three keys and no others:

**`cfg.agent`** (FR#1, FR#2, FR#3) — one entry per `*.md` file directly under `<root>/agents/`. Key the entry by the file's stem. For each file, split frontmatter by line scan and build:
- `model`: the tier map's `model` for the frontmatter's `model:` tier name (`sonnet`/`haiku`/`opus`). The remap is load-bearing, not legacy plumbing: `ConfigAgentV1.Info` types `model` as `Schema.optional(Schema.String)` with no format validation and `Provider.parseModel()` splits on `/` (`provider/provider.ts:1997-2003`), so passing `sonnet` through unchanged yields `providerID: "sonnet"`, `modelID: ""` — a nonexistent model, silently.
- `variant`: the tier map's `variant` for the same tier.
- `description`: the frontmatter's `description` field.
- `prompt`: the file body — everything after the closing frontmatter delimiter.
- `mode`: `"subagent"`.

Skip any agent file you cannot read, and any whose `model:` tier is not in the tier map, rather than emitting a malformed entry. An entry with an empty prompt is worse than an absent one (design doc, Edge Cases — "A symlink dangles"). Emitting a bare tier name as `model` is worse still.

**`cfg.command`** (FR#4) — one entry per `<root>/skills/*/SKILL.md` whose frontmatter declares `opencode-command: true`. Key by the skill directory name. Set `template` to the shared skill-command template with `{name}` substituted, and `description` to something naming the skill. Match only `SKILL.md`; do not glob `**/*.md` under `skills/`. `skills/mine-write-skill/REFERENCE.md` contains the string `opencode-command: true|false` as documentation and must not produce a command. Match `opencode-command` in frontmatter only, and match the value strictly — `true|false` is not `true`. Thirteen skills currently qualify.

**`cfg.instructions`** (FR#5, FR#6, FR#9) — an array of explicit absolute file paths (not glob patterns), one per `.md` file in each directory named by the shared instruction-directory list, minus any whose `<dir>/<name>.md` matches an exclusion-list entry. Append the path to the compatibility rule as installed by T05's bootstrap. Preserve whatever `cfg.instructions` already holds rather than replacing it.

Explicit paths, not globs: the old `build_instructions()` emitted one glob per directory because OpenCode globs only `basename(pattern)` within `dirname(pattern)` for an absolute path and never recurses, so `rules/**/*.md` silently matches nothing. Enumerating files in the plugin sidesteps that class of bug entirely — but it means a file added between process starts is invisible until the next start, which is the accepted propagation granularity.

**Do not set `cfg.skills.paths`.** Probe-verified racy — absent in all but one of roughly sixteen runs, with the hook confirmed firing each time. OpenCode's native scan of `~/.claude/skills/**/SKILL.md` (`skill/index.ts:187-193`) already delivers all 78 skills. Setting it occasionally is more dangerous than never setting it. This is a Key Constraint.

Parse frontmatter by line scan, mirroring `_split_frontmatter()` (`bin/opencode-sync:499-516`): if the first line is not `---`, there is no frontmatter; otherwise scan forward for the next `---` and split there. Do not pull in a YAML dependency for the four fields this needs (`model`, `description`, `opencode-command`, and the body boundary).

Write the file in **erasable-only TypeScript syntax** — no `enum`, no `namespace`, no parameter properties, no `declare`-merging. Node 24 runs `.ts` directly by stripping types, and that is how this task is verified; non-erasable syntax breaks it. Types-as-annotations, `interface`, and `as` casts are all fine.

Verify by writing a throwaway harness (scratchpad, not committed) that imports the plugin, calls `config()` on a plain object, and prints the resulting shape. Run it with `node --experimental-strip-types opencode/claudefiles.ts`-style invocation or a small `.ts` driver. Assert against the real `~/.claude` contents.

## Focus

**Node 24 is on PATH (`v24.19.0`) and `bun` is not.** Node ≥22.18 strips types by default; on 24 a bare `node harness.ts` works. This is the only way to observe the plugin's output without a full OpenCode bootstrap, and it makes every FR in this task locally checkable. Do not skip it and defer everything to T07.

**Ground-truth counts to assert against** (from Phase 2 exploration, re-derive rather than trusting these if they drift):
- `~/.claude/agents/` — 26 files.
- Skills declaring `opencode-command: true` — 13: `mine-address-pr-issues`, `mine-challenge`, `mine-clean-code`, `mine-comb`, `mine-define`, `mine-eval-repo`, `mine-orchestrate`, `mine-plan`, `mine-prior-art`, `mine-review`, `mine-ship`, `mine-sketch`, `mine-write-skill`.
- `~/.claude/rules/common/` — 34 files; one (`sudo.md`) is excluded, so 33 reach `instructions`.
- `~/.claude/rules/personal/` — exactly 5, all symlinks into `~/Dotfiles/config/claude/rules/personal/`: `capabilities-base.md`, `capabilities.md`, `machines.md`, `mcp-tools.md`, `python-packaging.md`. These are the roadmap `:194` closure — if they are missing from your output, the main point of the task is unmet.

**Everything under `~/.claude/` is symlinks.** Use APIs that follow them (`fs.readdirSync` + `fs.readFileSync` do; a `withFileTypes` check for `isFile()` does **not** — a symlink reports `isSymbolicLink()`, not `isFile()`). Getting this wrong yields zero agents and zero rules with no error.

**The plugin cannot report its own failure.** OpenCode catches and discards both plugin-load exceptions (`plugin/index.ts:222-238`, `Effect.catch(() => Effect.void)` with the session-event publish commented out under a TODO) and `config()` hook exceptions (`:243-251`, `Effect.ignore`). A throw here produces a session with no Claudefiles agents at all and no message. So: do not use exceptions as a signalling mechanism, degrade gracefully per-file, and rely on T05's `--verify` for detection. Writing to `console.error` is fine and shows up in OpenCode's log, but nothing acts on it.

**`config()` runs once per process and its result is cached** (`effect/instance-state.ts:26-40`, `ScopedCache` with `capacity: POSITIVE_INFINITY`). Do not attempt lazy re-reads, watchers, or invalidation — out of scope, and the caching defeats them.

**The declared-dependency-graph theory does not predict which config surfaces work.** `Agent.node` lists `Plugin.node` in its deps and works; `Command.node` does not and works anyway; `Skill.node` does not and does not work. If you find yourself reasoning from the layer graph about whether a fourth key would work, stop — the design's probe is the authority, and no fourth key is in scope.

## Verify

- [ ] FR#1: a Node harness invoking the plugin's `config()` on an empty object produces a `cfg.agent` entry for every `*.md` file directly under `~/.claude/agents/` — entry count equals the file count (26 at time of writing), keyed by file stem.
- [ ] FR#2: every `cfg.agent` entry's `model` matches `openai/gpt-5.6-{sol,terra,luna}` and its `variant` is `high`, with the specific triple matching the tier named in that agent's own frontmatter; no entry's `model` is a bare `sonnet`/`haiku`/`opus`.
- [ ] FR#3: for at least two agents of differing tiers, the entry's `prompt` equals that file's content after the closing frontmatter delimiter and its `description` equals the frontmatter `description` value — compared byte-for-byte in the harness.
- [ ] FR#4: `cfg.command` has exactly one entry per `SKILL.md` declaring `opencode-command: true` (13), each `template` being the shared template with `{name}` substituted; no entry exists for `mine-write-skill/REFERENCE.md`.
- [ ] FR#5: `cfg.instructions` contains an explicit absolute path for every `.md` file in `~/.claude/rules/common/` and `~/.claude/rules/personal/`, including all five personal rules; no entry contains a `*` or `**` glob character.
- [ ] FR#6: no `cfg.instructions` entry ends in `sudo.md`.
- [ ] FR#9: `cfg.instructions` contains the compatibility rule's installed path.
