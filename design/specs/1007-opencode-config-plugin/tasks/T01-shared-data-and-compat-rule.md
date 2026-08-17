---
task_id: "T01"
title: "Create the shared data file and the compatibility rule"
status: "planned"
depends_on: []
implements: ["FR#7", "FR#10", "FR#27"]
---

## Summary

Create the two version-controlled files everything else in this spec reads from: `opencode/config-data.json`, which holds every value both the Python script and the TypeScript plugin need, and `opencode/opencode-compat.md`, which is the compatibility rule promoted out of a Python string constant into a real reviewable file. Neither `bin/opencode-sync` nor the plugin is modified here — this task only puts the data on disk so the tasks that follow have a single source to read. The `opencode/` directory does not exist yet.

## Target Files

- create: `opencode/config-data.json`
- create: `opencode/opencode-compat.md`
- read: `bin/opencode-sync` (constants at `:90` `OPENCODE_EXCLUDED_RULES`, `:101` `INSTRUCTION_DIRS`, `:123` `TIER_MAP`, `:146` `OPENCODE_VARIANTS`, `:159` `SKILL_COMMAND_TEMPLATE`, `:178` `OPENCODE_COMPAT_RULE`)
- read: `design/specs/1007-opencode-config-plugin/design.md`

## Prompt

Create `opencode/config-data.json` carrying five values plus a rationale comment. Source each from the existing constants in `bin/opencode-sync` (do not retype them from memory — read the file):

1. **Tier map** — from `TIER_MAP` (`bin/opencode-sync:123-136`). Three entries: `opus` → `{"model": "openai/gpt-5.6-sol", "variant": "high"}`, `sonnet` → `{"model": "openai/gpt-5.6-terra", "variant": "high"}`, `haiku` → `{"model": "openai/gpt-5.6-luna", "variant": "high"}`.
2. **Allowed variant names** — from `OPENCODE_VARIANTS` (`:146`): `none`, `low`, `medium`, `high`, `xhigh`, `max`. Emit as a JSON array (JSON has no set type).
3. **Rule exclusion list** — **one** entry only: `common/sudo.md`. The current constant (`:90-94`) has three; `common/performance.md` and `common/tmux.md` are deliberately dropped per FR#7. Do not carry them over.
4. **Skill-command template and description — two separate values.** `SKILL_COMMAND_TEMPLATE` (`:159-168`) is a whole markdown *file*: YAML frontmatter carrying `description:`, then a `{marker}` line, then the body. Split it:
   - **template**: the body only — `Load the \`{name}\` skill using the native skill tool and follow it with these arguments:`, a blank line, then `$ARGUMENTS`. Keep the `{name}` placeholder.
   - **description**: the text from the frontmatter's `description:` line — `Load and run the {name} skill.` — as its own key, also keeping `{name}`.

   Drop the frontmatter delimiters, the `description:` key line, and the `{marker}` line entirely. The marker existed to stamp generated `.md` wrapper files for later pruning; no wrapper files are written anymore.

   **This split is required, not cosmetic.** The old pipeline wrote that string to `<config_dir>/commands/<name>.md`, and OpenCode's disk loader parsed it — `ConfigCommand.load()` (`packages/opencode/src/config/command.ts`) runs `ConfigMarkdown.parse()` and builds `{name, ...md.data, template: md.content.trim()}`, so the frontmatter became the `description` field and only the body became `template`. A plugin-supplied `cfg.command` entry never goes through that loader: `packages/opencode/src/command/index.ts:90-102` reads `command.template` and `command.description` as independent fields with no parsing between them. Storing the whole file string as `template` would put literal `---` delimiters and a duplicate description line into every command's prompt text. The frontmatter-stripping the disk path did for free is now this data file's responsibility.
5. **Instruction directory list** — `rules/common` and `rules/personal`, replacing `INSTRUCTION_DIRS` (`:101`), which currently names only `rules/common`. The plugin emits `cfg.instructions` from this list and `--check-source`'s coverage check validates against it (see design doc FR#27 and the Dependencies and Assumptions entry on the check being repo-scoped).

Carry `TIER_MAP`'s explanatory comment (`bin/opencode-sync:111-122`) into the JSON as a `$comment` string key. JSON has no comment syntax and both `json.loads` and `JSON.parse` pass unknown keys through untouched, so a `$comment` key is the mechanism. This is not decoration: the comment records why the key is `variant` and not `effort` — OpenCode's `AgentConfig` schema has no `effort` key and does not set `additionalProperties: false`, so an `effort` entry is accepted and silently discarded, dropping every subagent to the provider default. That is bug #514 and losing its rationale to a format choice would be a bad trade. Condense the comment if you like, but the `variant`-not-`effort` reason and the #514 date reference (`2026-08-14`) must survive.

Choose key names yourself, but keep them stable and obvious — both `bin/opencode-sync` and `opencode/claudefiles.ts` will index into this structure by literal key in later tasks, and renaming later means touching both.

Then create `opencode/opencode-compat.md` from the `OPENCODE_COMPAT_RULE` string constant (`bin/opencode-sync:178-196`), preserving its `tool: opencode` frontmatter and its body, with two changes:

- **Add the MCP tool-name mapping line** (FR#10): Claude names MCP tools `mcp__<server>__<tool>`; OpenCode builds `sanitize(client) + "_" + sanitize(name)` (`packages/opencode/src/mcp/catalog.ts:119`), so the same tool is `<server>_<tool>` — e.g. `mcp__context7__query-docs` becomes `context7_query-docs`. State the transformation, not just one example, since it has to cover every rule and skill naming a Claude MCP tool.
- **Delete the line `- "${CLAUDE_CONFIG_DIR:-~/.claude}" paths → ~/.config/opencode`** (currently `bin/opencode-sync:191`). It is now actively wrong in an interesting direction: under this design the plugin reads `~/.claude` deliberately, so a rule or skill referencing `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/...` names a path OpenCode genuinely reads. Telling the model to rewrite it to `~/.config/opencode` would send it to a directory this spec empties. Delete rather than invert — an instruction saying "these paths are already correct" is noise.

Leave the rest of the rule's body as-is. In particular keep the line about slash-command bridges existing only for selected skills (still true) and the closing instruction to skip clearly inapplicable instructions silently (load-bearing — it is what covers `capabilities.md` routing to `/ccr-recall`, which does not exist under OpenCode).

Do not modify `bin/opencode-sync` in this task. Its constants stay in place until T03 and T04 migrate their consumers.

## Focus

`opencode/` does not exist — create it. It sits at the repo root alongside `bin/`, `rules/`, `skills/`.

The `$comment` key must not collide with a real key name, and must not be nested somewhere a consumer iterates blindly. If the tier map is a top-level object whose keys are tier names, do **not** put `$comment` inside it — a consumer looping over tier names would see `$comment` as a fourth tier. Put it at the top level of the document, or give the tier map a wrapper object with separate `$comment` and data keys. Whichever you choose, the plugin and the Python side both have to iterate the tier map, so make the shape unambiguous.

Watch the skill-command template's trailing newline and its `$ARGUMENTS` line — the template becomes `cfg.command[].template` verbatim, so whitespace is content. Encode it as a JSON string with `\n` escapes; do not reflow it. Note that the disk loader called `.trim()` on the body (`config/command.ts`), so a stored template with leading or trailing blank lines is not equivalent to what shipped before — store it already trimmed.

`bin/opencode-sync`'s `--check-orphans` hook runs at every commit and flags a module-level `def` or `ALL_CAPS` binding whose name appears exactly once in the file. This task adds no Python, so it cannot trip that — but note for later tasks that the check counts raw substring occurrences including comments and docstrings (`bin/opencode-sync:1400-1407`, deliberate), so it is not a reliable proof that a name is truly gone.

Gap-check item this task addresses: the compat rule's `${CLAUDE_CONFIG_DIR:-~/.claude}` line (gap 5) is removed here rather than in the documentation task, because the file is being authored here and correcting it later would mean editing the same three lines twice.

## Verify

- [ ] FR#7: `opencode/config-data.json`'s exclusion list contains exactly one entry, the string `common/sudo.md` — confirmed by loading the file with `python3 -c` and printing the list's length and contents.
- [ ] FR#10: `opencode/opencode-compat.md` contains both the literal `mcp__` and the described `<server>_<tool>` target form, and states the transformation between them — confirmed by reading the file and by `rg -c 'mcp__' opencode/opencode-compat.md` returning non-zero.
- [ ] FR#27: `opencode/config-data.json` parses under both `python3 -c 'import json; json.load(open("opencode/config-data.json"))'` and `node -e 'JSON.parse(require("fs").readFileSync("opencode/config-data.json","utf8"))'`, and contains the tier map with three tiers, the variant-name array, the one-entry exclusion list, the skill-command template **and** its separate description string, and the two-entry instruction-directory list, plus a `$comment` whose text names `variant`, `effort`, and `2026-08-14`. The stored template contains no `---` delimiter and no `description:` line.
