# Onboarding

## What This Is

Claudefiles is a set of skills, rules, and agents that make Claude Code better at planning, reviewing, and shipping code. The core value is a complete workflow — from raw idea to merged PR — with structured tools for each step. You get better code review, consistent coding standards that apply automatically, and a pipeline that keeps Claude focused on the right work at each stage.

It's for anyone using Claude Code who wants more structure than raw prompting. You don't need to adopt everything at once. The base bundle gives you the full pipeline; optional bundles add capabilities as you need them.

## Install

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/NodeJSmith/Claudefiles.git ~/Claudefiles
cd ~/Claudefiles
uv run install.py
```

The base (pipeline workflow) always installs. On a first install the wizard asks which optional bundles you want, then which rule categories to install. Re-running later applies your saved selections silently and only prompts for bundles or rule categories added since last time. Use `--reconfigure` to change selections, or `--uninstall` to remove everything.

## Key Concepts

**Skills** — reusable prompts Claude invokes by name (`/mine-challenge`, `/mine-sketch`). The main interface. You type the slash command; Claude runs the structured workflow behind it.

**Commands** — lightweight slash commands for daily tasks (`/mine-status`, `/mine-end-of-day`). Quicker than skills, no multi-step flow.

**Agents** — specialized subagents dispatched by skills (code-reviewer, researcher, planner). A dispatch always names an agent directly — there's no separate model parameter at the call site. Each agent's own frontmatter (in `agents/`) declares its model, effort, tools, description, and bundle in one place, so retuning an agent's model touches only that file. You don't invoke agents directly; skills launch them when needed.

**Rules** — coding guidelines that load automatically. They shape how Claude writes code, handles git, runs tests, and approaches security. Always active, no invocation needed.

**Hooks** — event-driven scripts that run before or after tool calls (pytest safety guard, sudo handling, tmux session naming). Background infrastructure you don't think about.

**Plugins** — third-party Claude Code plugins bundled via `settings.json`. These register automatically when settings are merged, so you get them without manual setup. Currently: `ccrecall` (conversation memory — recall, resume).

**Bundles** — use-case packages. The base bundle gives you the pipeline. Optional bundles add capabilities: engineering specialists and extra planning agents. (Conversation memory used to be a bundle — it's now the `ccrecall` plugin.)

## Choose Your Path

### Path A: Pick and Choose

Start with whatever problem you have right now.

**"I want better code review"**
The base is enough. Before every commit, code-reviewer, integration-reviewer, and wtf-reviewer run automatically. For an on-demand review of your current branch: `/mine-review`. For a style and debt check: `/mine-clean-code`. For prose quality (PR descriptions, docs, commit messages): `/mine-humanize`. To comb a brief, design, plan, or implementation for consistency, accuracy, and drift: `/mine-comb`. Included in base — no extra bundles needed.

**"I want structured planning for complex features"**
The base is enough. `/mine-sketch` writes a decision ledger you ratify one decision at a time, then a fresh session builds the whole change from it with `/mine-sketch <dir>`. Work too big for one session splits into separate ledgers. Start with `/mine-grill` to sharpen a raw idea, or `/mine-research` when you don't yet know enough to decide. Included in base.

**"I want to brainstorm and challenge ideas"**
The base is enough. `/mine-brainstorm` runs four parallel thinkers and ranks ideas. `/mine-grill` interrogates a rough idea across product, engineering, and adversarial lenses. `/mine-challenge` assumes your approach is wrong and argues for better. Included in base.

**"I want to keep terminology and decisions straight during design conversations"**
The base is enough. `/mine-domain-model` maintains a `CONTEXT.md` glossary and ADRs as you talk through a design, challenging fuzzy language and cross-referencing the code as it goes. Included in base.

**"I need to write up technical research for my boss"**
The base is enough. `/mine-writeup` turns investigation notes or dense working documents into a structured, scannable document for a specific audience. It interviews you on audience and outcome, locks scope before writing, and follows an answer-first template (bottom line, situation, findings, decisions, risks). Built-in editorial discipline keeps the agent from expanding scope or resisting cuts. Included in base.

**"I want conversation memory across sessions"**
Enable the **`ccrecall`** plugin (wired in `settings.json`; its hook binaries come from the `ccrecall` PyPI package that `install.py` installs). Claude remembers corrections, architectural decisions, and preferences across sessions. `/ccrecall:ccr-recall` searches past sessions; `/ccrecall:ccr-resume` picks up a fresh session after `/clear`.

**"I want domain-specific engineering agents"**
Add the **Engineering** bundle. You get agents for FastAPI backends, PySpark pipelines, React/Vue/Angular frontends, SRE work (SLOs, observability), technical writing, and an adversarial pre-ship testing gate.

**"I want architecture and QA agents"**
Add the **Extra agents** bundle. Architect produces Mermaid diagrams and high-level overviews. Planner breaks a feature into a step-by-step plan. QA Specialist finds defects adversarially.

---

### Path B: Idea to PR

This is the workflow that makes Claude Code feel like a senior engineer on your team, not a code autocomplete. It takes 10–30 minutes to run end to end for a small feature.

**Example:** adding rate limiting to a public API endpoint — a token-bucket limiter, per-key configuration, and `429` responses with retry headers.

**Step 1: Sharpen the idea**

```
/mine-grill
```

You describe the feature. `/mine-grill` interrogates it across five lenses — product fit, design clarity, engineering complexity, scope, and adversarial ("what could go wrong?"). It produces a `brief.md` that surfaces the decisions you haven't made yet.

*What you get:* a one-page brief identifying the key decisions and risks before you write any code.

**Step 2: Sketch the decisions**

```
/mine-sketch design/specs/<spec-name>
```

Point it at the brief's directory. Sketch reads the brief and the codebase, then writes a decision ledger (`design.md`): every place the change has more than one reasonable answer, each with its options scored and a recommendation. You ratify the decisions one at a time, then a mandatory challenge and a consistency comb check the ledger before you ratify the whole thing.

*What you get:* a `design/specs/<spec-name>/design.md` where every judgment call the change needs is already made.

**Step 3: Build**

Start a fresh session and run the same command:

```
/mine-sketch design/specs/<spec-name>
```

On a ratified ledger, sketch builds the whole change in one session, with tests, through the normal pre-commit reviewers. Calls the ledger didn't settle get recorded in it. A real issue the build decides not to fix (faithful-port behavior that must stay unchanged, say) is recorded in `known-issues.md` beside the ledger and walked with you before ship. A ship-time challenge checks what landed against the ledger.

*What you get:* the feature implemented, reviewed, and challenged — ready to ship.

**Step 4: Ship**

```
/mine-ship
```

Commits, pushes, and opens a PR in one step. Picks up the right commit message format, links the related issue, and handles the PR description.

*What you get:* an open PR.

---

That's the full loop. For a feature like rate limiting — limiter logic, config, request-handler integration, and tests across a few files — the build takes 20–30 minutes of wall-clock time, most of it waiting for Claude to execute. You stay in the reviewer seat, not the implementer seat.

---

### Path C: Everything

When you have all bundles installed, the system covers the full development lifecycle plus the surrounding workflow.

**Daily workflow pattern:**

```
/mine-good-morning          → read yesterday's handoff, orient, pick up where you left off
<work happens>
/mine-end-of-day            → capture session state as a handoff file
```

After a `/clear` (e.g. to drop a huge uncached context the morning after a long build), `/ccrecall:ccr-resume` (from the `ccrecall` plugin) reads the *prior* session's transcript tail to recover your last instruction and any decision you left unanswered — no hand-written handoff needed. With the plugin enabled, the SessionStart hook also auto-warns when the previous session ended on an unanswered question.

**Worktree-based development:**

```bash
claude --worktree <branch>  → start a fresh Claude session in an isolated branch
```

Each worktree gets its own context, isolated from the main working tree.

**Research before committing to a direction:**

```
/mine-research              → architecture mapping and feasibility analysis
/mine-prior-art             → survey how others solve the same problem
/mine-challenge             → adversarial review of your proposed approach
```

**How the pieces interact:** Rules load automatically and shape every response — Claude writes code, handles git, and approaches security according to the rule files in `rules/common/`. Hooks run in the background — the sudo poller handles privilege prompts, the tmux-drift check keeps your session name aligned with your work. Skills and agents sit on top: you invoke a skill, it dispatches the right agents, they report back.

The result is a consistent development environment that works the same way every session, regardless of which codebase you're in.

## Run State: cfl

`cfl` is the run-state CLI, part of the base bundle, backed by a durable SQLite database at `~/.local/share/claudefiles/cfl.db` (overridable via `$CFL_DB`). `/mine-sketch` records each sketch's spec, run, gate results, subagent dispatches, and events there.

Key commands:

```bash
cfl run status          # current run state
cfl spec status         # spec-level state including active run
cfl gate                # record a gate evaluation result
cfl event               # append a free-form event to the audit trail
```

`mine-sketch` calls `cfl` automatically — you rarely need to invoke it directly.

## Customizing

**Choosing rule categories** — every rule in `rules/common/` loads into Claude's context each session, so the installer lets you install only the categories you need. A small **Core** set (capabilities routing, interaction style, invariants, agent dispatch, model selection, worktree safety) always installs. Everything else — language conventions, testing discipline, planning rules, and so on — is grouped into opt-out categories: selected by default, but you can drop the ones that don't fit your stack (a Python-only user might skip nothing, a backend-only user might drop frontend rules). Run `uv run install.py --reconfigure` to change the selection. If a rule you keep references one you dropped, the installer warns but installs anyway — the references are pointers, not hard dependencies. See the Rules table in [REFERENCE.md](REFERENCE.md) for the categories and their files.

**Add your own rules** — drop a `.md` file straight into `$CLAUDE_CONFIG_DIR/rules/common/` (defaults to `~/.claude/rules/common/`) and it loads automatically next session, no installer step. If you add it to the repo's `rules/common/` instead (so it's version-controlled), re-run `uv run install.py` to symlink it.

**Add your own skills** — `/mine-write-skill` walks you through requirements, drafts the `SKILL.md`, validates a quality checklist, and wires the routing entry. The result lands in `skills/` ready to install.

**Settings** — edit `settings.json` in the repo root, then run `claude-merge-settings` to write `$CLAUDE_CONFIG_DIR/settings.json`. It merges the repo's shared settings with a per-machine `$CLAUDE_CONFIG_DIR/settings.machine.json`, so each box can keep its own permissions, env vars, and hook tweaks without touching the version-controlled config. When you re-run the merge, it detects permissions you granted at runtime and offers to promote them into the machine file so they survive. Only the layers that actually exist are applied.

**Removing things** — run `uv run install.py --reconfigure` and deselect the bundle or rule category. For an individual rule file within a category you otherwise want, delete the symlink from `$CLAUDE_CONFIG_DIR/rules/common/` or remove the source file.

## OpenCode Support

OpenCode support is a plugin (`opencode/claudefiles.ts`) that reads the live Claude install directly — `install.py` is a **prerequisite** for OpenCode now, not only for Claude Code: run it first, since the plugin has nothing to read from `~/.claude/` otherwise. The plugin populates `cfg.agent`, `cfg.command`, and `cfg.instructions` in memory at OpenCode session start, resolving each agent's Claude tier name on `model:` to a provider-qualified model ID and reasoning `variant`. Since a dispatch already names a real agent file on both harnesses (see Key Concepts, above), there's nothing to rewrite in skill, command, or agent body content — every agent, worker and specialist alike, is a real file that resolves the same way on both harnesses.

OpenCode loads skills through its native skill tool; unlike Claude Code, it does not automatically expose every skill as a slash command. The plugin builds thin `/` command entries for skills declaring `opencode-command: true`, a curated set of frequently invoked workflows. Standalone files under `commands/`, such as `/mine-issues`, are read directly and merged into the same `cfg.command` map — their body is already a complete prompt, not a skill wrapper, so it needs no bridge and works the same way on both harnesses.

Model routing lives entirely in each agent's own frontmatter, read live and transformed by the plugin — there is no config-level agent pinning. A generated `config.json` carries only the plugin declaration and `subagent_depth`; it has no `agent` key. `opencode.jsonc` stays entirely user-managed and is never written by the plugin or `bin/opencode-sync` (see [REFERENCE.md's OpenCode Sync section](REFERENCE.md#opencode-sync) for the full merge order).

```bash
opencode-sync --prune       # once, if upgrading from the old copy-based sync: remove the stale generated tree
opencode-sync --bootstrap   # symlink the plugin and compatibility rule, write config.json, then verify
opencode-sync --verify      # re-check that every agent resolves through the live install
```

Existing users upgrading from the prior copy-based sync need that `--prune` step once, to clear out the stale generated files and orphaned agents it left behind — `--bootstrap` does not do this for you, it only sets up the new plugin-based path. `--bootstrap` runs the full `--verify` sweep automatically as its final step. Editing an agent, skill, or rule takes effect in the next OpenCode **process** — `config()` runs once per process and its result is cached, so a running `opencode serve` needs a restart, not just a new session. OpenCode discovering the live Claude artifacts is the delivery mechanism, not a confound: there's no separate generated copy anymore for a passing check to have missed.

The native-support roadmap's Spec 2 (native agents and model enforcement) is complete; `design/specs/1008-opencode-named-roles` closed most of Spec 3 (skill compatibility adapter) by removing the need for dispatch rewriting in the first place, and `design/specs/1007-opencode-config-plugin` replaced the copy-to-disk transport with this plugin. Interactive question syntax conversion and skill classification remain open. See [design/opencode-integration-roadmap.md](design/opencode-integration-roadmap.md) for the full spec sequence and the constraints future OpenCode work must preserve.

## Reference

See [REFERENCE.md](REFERENCE.md) for the full list of skills, agents, commands, hooks, bin scripts, and packages.
