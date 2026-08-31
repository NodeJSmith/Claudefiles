// OpenCode plugin that populates cfg.agent, cfg.command, and cfg.instructions
// from the live Claude install at ~/.claude/. This is the entire transport
// mechanism -- see design/specs/1007-opencode-config-plugin/design.md.
//
// Symlinked into ~/.config/opencode/claudefiles.ts by `bin/opencode-sync
// --bootstrap` (T05). Editing this file takes effect on the next OpenCode
// *process* -- config() runs once per process and its result is cached
// (effect/instance-state.ts), so a running `opencode serve` needs a restart.
//
// Dependency-free by design (Implementation Preferences): frontmatter is
// parsed by line scan, mirroring bin/opencode-sync's _split_frontmatter(),
// rather than pulling in a YAML parser.
//
// A throw here is invisible: OpenCode discards both plugin-load exceptions
// (plugin/index.ts:222-238) and config()-hook exceptions (:243-251,
// Effect.ignore). Every per-file failure below is therefore a skip plus a
// console.error, never a throw -- `bin/opencode-sync --verify` is the actual
// detection mechanism (FR#20).

import type { Config, Plugin } from "@opencode-ai/plugin";
import { readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

type TierEntry = {
  model: string;
  variant: string;
};

type ConfigData = {
  tier_map: Record<string, TierEntry>;
  variants: string[];
  excluded_rules: string[];
  skill_command_template: string;
  skill_command_description: string;
  instruction_dirs: string[];
};

type AgentEntry = {
  model: string;
  variant: string;
  description: string;
  prompt: string;
  mode: "subagent";
};

type CommandEntry = {
  template: string;
  description: string;
};

// Resolved relative to this file's own location, not cwd and not
// CLAUDE_CONFIG_DIR: the plugin reaches ~/.config/opencode/claudefiles.ts as
// a symlink into this repo, so a sibling-relative lookup is what finds this
// repo's copy of the shared data file.
const PLUGIN_DIR = dirname(fileURLToPath(import.meta.url));
const CONFIG_DATA_PATH = join(PLUGIN_DIR, "config-data.json");

// The OpenCode config dir, resolved the same way bin/opencode-sync's
// OPENCODE_CONFIG constant does (XDG_CONFIG_HOME/opencode when that
// variable is set, falling back to ~/.config/opencode otherwise) --
// OpenCode itself honors XDG_CONFIG_HOME for its own config path. T05's
// --bootstrap must symlink opencode/opencode-compat.md to exactly this
// path for FR#9 to hold.
const OPENCODE_CONFIG_DIR = join(
  process.env.XDG_CONFIG_HOME?.trim() || join(homedir(), ".config"),
  "opencode",
);
const COMPAT_RULE_PATH = join(OPENCODE_CONFIG_DIR, "opencode-compat.md");

// Single declaration site for the default root, shared by resolveClaudeRoot()
// (falls back to it) and buildSkillCommands() (compares against it to detect a
// CLAUDE_CONFIG_DIR override) -- two independent join(homedir(), ".claude")
// calls would encode the same fact twice with nothing to catch them drifting
// apart if the default ever changed.
const DEFAULT_CLAUDE_ROOT = join(homedir(), ".claude");

function resolveClaudeRoot(): string {
  const override = process.env.CLAUDE_CONFIG_DIR?.trim();
  if (override) return override;
  return DEFAULT_CLAUDE_ROOT;
}

function loadConfigData(): ConfigData | undefined {
  try {
    const raw = readFileSync(CONFIG_DATA_PATH, "utf8");
    return JSON.parse(raw) as ConfigData;
  } catch (err) {
    console.error(`claudefiles plugin: failed to read ${CONFIG_DATA_PATH}: ${String(err)}`);
    return undefined;
  }
}

// Mirrors bin/opencode-sync's _split_frontmatter() (bin/opencode-sync:181-198):
// a line scan for the frontmatter block between the first two `---` lines,
// deliberately not a YAML parser. Returns [frontmatter-incl-delimiters, body];
// [ "", content ] when there is no frontmatter block.
function splitFrontmatter(content: string): [string, string] {
  const lines = content.split(/(?<=\n)/);
  if (lines.length === 0 || lines[0].trim() !== "---") return ["", content];

  let endIdx = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === "---") {
      endIdx = i;
      break;
    }
  }
  if (endIdx === -1) return ["", content];

  return [lines.slice(0, endIdx + 1).join(""), lines.slice(endIdx + 1).join("")];
}

// Matches a Claude tier name anchored at the start of a frontmatter `model:`
// line, ignoring any trailing content -- most agent files carry a trailing
// inline comment on that line (e.g. "model: sonnet  # ... do not
// downgrade"), and a naive split-on-colon would capture the comment as part
// of the tier name and fail every tier-map lookup. This used to mirror
// bin/opencode-sync's FRONTMATTER_MODEL_RE, but that constant was retired
// when the Python-side validation it backed was removed; the equivalent
// model-tier parsing now lives only in this file.
function parseModelTier(frontmatter: string): string | undefined {
  const match = frontmatter.match(/^model:\s*(sonnet|haiku|opus)\b/m);
  return match ? match[1] : undefined;
}

function parseFrontmatterField(frontmatter: string, field: string): string | undefined {
  const match = frontmatter.match(new RegExp(`^${field}:\\s*(.*)$`, "m"));
  return match ? match[1].trim() : undefined;
}

// Mirrors validation bin/opencode-sync used to perform via OPENCODE_COMMAND_RE
// before that constant was retired: collect every `opencode-command:` line
// found *within the frontmatter block only* (never the body --
// skills/mine-write-skill/SKILL.md discusses the field in prose at line 51,
// and its REFERENCE.md documents it as "true|false", both of which must not
// produce a command). Select only when there is exactly one such line and its
// value is the literal string "true" -- "true|false" is not "true".
function isSkillCommand(frontmatter: string): boolean {
  const re = /^opencode-command:\s*(\S.*?)\s*$/gm;
  const values: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = re.exec(frontmatter)) !== null) {
    values.push(match[1]);
  }
  return values.length === 1 && values[0] === "true";
}

// Shared by every cfg.* builder below: each reads a live ~/.claude
// subdirectory that may not exist (an unselected bundle, a stale
// CLAUDE_CONFIG_DIR) and must degrade to "nothing found" rather than throw --
// a throw here is invisible to the caller (see module docstring), so the
// failure has to be logged here instead. Returns undefined on failure so
// each caller decides its own empty-result shape (an empty object to merge,
// or `continue` to the next instruction directory).
function readDirLogged(dir: string, label: string): string[] | undefined {
  try {
    return readdirSync(dir);
  } catch (err) {
    console.error(`claudefiles plugin: cannot read ${label} ${dir}: ${String(err)}`);
    return undefined;
  }
}

// cfg.agent: one entry per *.md file directly under <claudeRoot>/agents/,
// keyed by file stem. Skips any file that can't be read and any whose
// model: tier doesn't resolve through the shared tier map -- an entry with
// an empty prompt, or a bare tier name passed through as `model`, is worse
// than an absent entry (design doc, Edge Cases; Provider.parseModel() splits
// an unqualified "sonnet" into providerID: "sonnet", modelID: "" with no
// error).
function buildAgents(claudeRoot: string, tierMap: Record<string, TierEntry>): Record<string, AgentEntry> {
  const agentsDir = join(claudeRoot, "agents");
  const agents: Record<string, AgentEntry> = {};

  const names = readDirLogged(agentsDir, "agents dir");
  if (names === undefined) return agents;

  for (const name of names) {
    if (!name.endsWith(".md")) continue;
    const stem = name.slice(0, -".md".length);
    const filePath = join(agentsDir, name);

    let content: string;
    try {
      // readdirSync + readFileSync follow symlinks; everything under
      // ~/.claude/ is a symlink, so a withFileTypes().isFile() check here
      // would report isSymbolicLink() instead and silently skip every file.
      content = readFileSync(filePath, "utf8");
    } catch (err) {
      console.error(`claudefiles plugin: skipping unreadable agent file ${filePath}: ${String(err)}`);
      continue;
    }

    const [frontmatter, body] = splitFrontmatter(content);
    const tier = parseModelTier(frontmatter);
    if (!tier || !(tier in tierMap)) {
      console.error(`claudefiles plugin: skipping agent ${name} -- no resolvable model tier`);
      continue;
    }

    const tierEntry = tierMap[tier];
    const description = parseFrontmatterField(frontmatter, "description") ?? "";

    agents[stem] = {
      model: tierEntry.model,
      variant: tierEntry.variant,
      description,
      prompt: body,
      mode: "subagent",
    };
  }

  return agents;
}

// cfg.command, skill-bridge half: one entry per <claudeRoot>/skills/*/SKILL.md
// whose frontmatter declares opencode-command: true. Three filters are all
// load-bearing (see isSkillCommand and the SKILL.md-only glob below) --
// dropping any one of them inflates the count past the true 12. Paired with
// buildNativeCommands() below, which builds the other half of cfg.command
// from this repo's own commands/*.md files.
//
// Skipped entirely when claudeRoot is not the default ~/.claude: OpenCode's
// own native skill scan (skill/index.ts:187-193) is hardcoded to
// ~/.claude/skills and does not honor CLAUDE_CONFIG_DIR, so a command built
// from a custom root would tell the skill tool to load a skill OpenCode can
// never find there -- a silent, broken command rather than an absent one.
// Pointing cfg.skills.paths at the custom root instead was already
// probe-verified as racy (design.md, Dependencies and Assumptions), so
// degrading to no commands is the only reliable option here.
function buildSkillCommands(
  claudeRoot: string,
  template: string,
  description: string,
): Record<string, CommandEntry> {
  if (claudeRoot !== DEFAULT_CLAUDE_ROOT) {
    console.error(
      `claudefiles plugin: skipping cfg.command generation -- CLAUDE_CONFIG_DIR overrides the ` +
        `default root (${DEFAULT_CLAUDE_ROOT}), but OpenCode's native skill scan only ever reads ` +
        `that default path, so generated commands would reference skills it can never resolve`,
    );
    return {};
  }

  const skillsDir = join(claudeRoot, "skills");
  const commands: Record<string, CommandEntry> = {};

  const names = readDirLogged(skillsDir, "skills dir");
  if (names === undefined) return commands;

  for (const name of names) {
    // Match only SKILL.md, never **/*.md under skills/ -- REFERENCE.md files
    // document the opencode-command field in prose and must not be scanned.
    const skillFile = join(skillsDir, name, "SKILL.md");

    let content: string;
    try {
      content = readFileSync(skillFile, "utf8");
    } catch {
      // Not a skill directory (a stray file under skills/), or unreadable.
      // Neither is an error worth surfacing -- the entry is simply absent.
      continue;
    }

    const [frontmatter] = splitFrontmatter(content);
    if (!isSkillCommand(frontmatter)) continue;

    commands[name] = {
      template: template.replaceAll("{name}", name),
      description: description.replaceAll("{name}", name),
    };
  }

  return commands;
}

// cfg.command, native half: one entry per *.md file directly under
// <claudeRoot>/commands/ -- Claude Code's own native slash-command
// directory (mine-issues, mine-status, etc.). Unlike buildSkillCommands()'s
// skill-bridge wrappers, a command file's body IS the full prompt already
// (already written to forward $ARGUMENTS where it takes any), so this reads
// it verbatim rather than wrapping it in skill_command_template. That also
// means it carries none of buildSkillCommands()'s CLAUDE_CONFIG_DIR restriction:
// the restriction there exists because a generated wrapper tells OpenCode's
// skill tool to load a skill from OpenCode's own hardcoded ~/.claude/skills
// scan, which a custom root can't redirect. A native command has no such
// second hop -- the body is inlined directly from whatever root is
// resolved, so it works under any CLAUDE_CONFIG_DIR override.
function buildNativeCommands(claudeRoot: string): Record<string, CommandEntry> {
  const commandsDir = join(claudeRoot, "commands");
  const commands: Record<string, CommandEntry> = {};

  const names = readDirLogged(commandsDir, "commands dir");
  if (names === undefined) return commands;

  for (const name of names) {
    if (!name.endsWith(".md")) continue;
    const stem = name.slice(0, -".md".length);
    const filePath = join(commandsDir, name);

    let content: string;
    try {
      content = readFileSync(filePath, "utf8");
    } catch (err) {
      console.error(`claudefiles plugin: skipping unreadable command file ${filePath}: ${String(err)}`);
      continue;
    }

    const [frontmatter, body] = splitFrontmatter(content);
    const description = parseFrontmatterField(frontmatter, "description") ?? "";

    commands[stem] = { template: body, description };
  }

  return commands;
}

// cfg.instructions: explicit absolute paths, never globs -- OpenCode globs
// only basename(pattern) within dirname(pattern) for an absolute path and
// never recurses, so a `rules/**/*.md`-style pattern would silently match
// nothing. Enumerating files here sidesteps that class of bug, at the cost
// of needing a fresh process to see a file added after startup (accepted
// propagation granularity -- see the module docstring).
function buildInstructions(
  claudeRoot: string,
  instructionDirs: string[],
  excludedRules: string[],
): string[] {
  const excluded = new Set(excludedRules);
  const paths: string[] = [];

  for (const dir of instructionDirs) {
    const absDir = join(claudeRoot, dir);
    // instruction_dirs entries look like "rules/common"; excluded_rules
    // entries are "<that-same-basename>/<filename>" (see
    // opencode/config-data.json) -- strip the "rules/" prefix so the two
    // vocabularies match on the same key.
    const dirKey = dir.startsWith("rules/") ? dir.slice("rules/".length) : dir;

    const names = readDirLogged(absDir, "instructions dir");
    if (names === undefined) continue;

    for (const name of names) {
      if (!name.endsWith(".md")) continue;
      if (excluded.has(`${dirKey}/${name}`)) continue;
      paths.push(join(absDir, name));
    }
  }

  paths.push(COMPAT_RULE_PATH);
  return paths;
}

export const ClaudefilesPlugin: Plugin = async () => {
  return {
    // Lets shell-tool subprocesses (e.g. bin/opencode-resume, run as the
    // native /mine-resume command) tell which OpenCode session invoked
    // them. Without this, a script that queries "most recently active
    // session" via time_updated would see its own invoking session --
    // touched by the very message that triggered the command -- as the
    // most recent, and resolve to itself instead of the prior session.
    "shell.env": async (input, output) => {
      if (input.sessionID) {
        output.env.OPENCODE_SESSION_ID = input.sessionID;
      }
    },
    config: async (cfg: Config) => {
      const data = loadConfigData();
      if (!data) return;

      const claudeRoot = resolveClaudeRoot();

      cfg.agent = {
        ...(cfg.agent ?? {}),
        ...buildAgents(claudeRoot, data.tier_map),
      };

      const skillCommands = buildSkillCommands(
        claudeRoot,
        data.skill_command_template,
        data.skill_command_description,
      );
      const nativeCommands = buildNativeCommands(claudeRoot);
      // Logs the same collision the spread below resolves silently -- kept
      // as one unit so a reader sees why an overlapping name is safe rather
      // than tripping over a silent overwrite. Native must be spread last:
      // that's what makes "the native command file wins" (the message
      // below) true. If this order ever changes, that message goes stale
      // with it.
      for (const name of Object.keys(nativeCommands)) {
        if (name in skillCommands) {
          console.error(
            `claudefiles plugin: commands/${name}.md collides with a skill declaring ` +
              `opencode-command: true under the same name -- the native command file wins`,
          );
        }
      }

      cfg.command = {
        ...(cfg.command ?? {}),
        ...skillCommands,
        ...nativeCommands,
      };

      cfg.instructions = [
        ...(cfg.instructions ?? []),
        ...buildInstructions(claudeRoot, data.instruction_dirs, data.excluded_rules),
      ];
    },
  };
};

export default ClaudefilesPlugin;
