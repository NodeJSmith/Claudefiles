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

**Skills** — reusable prompts Claude invokes by name (`/mine-challenge`, `/mine-plan`). The main interface. You type the slash command; Claude runs the structured workflow behind it.

**Commands** — lightweight slash commands for daily tasks (`/mine-status`, `/mine-end-of-day`). Quicker than skills, no multi-step flow.

**Agents** — specialized subagents dispatched by skills (code-reviewer, researcher, planner). You don't invoke these directly; skills launch them when needed.

**Rules** — coding guidelines that load automatically. They shape how Claude writes code, handles git, runs tests, and approaches security. Always active, no invocation needed.

**Hooks** — event-driven scripts that run before or after tool calls (pytest safety guard, sudo handling, tmux session naming). Background infrastructure you don't think about.

**Plugins** — third-party Claude Code plugins bundled via `settings.json`. These register automatically when settings are merged, so you get them without manual setup. None currently bundled.

**Bundles** — use-case packages. The base bundle gives you the pipeline. Optional bundles add capabilities: frontend design, CLI tooling, conversation memory, engineering specialists, and extra planning agents.

## Choose Your Path

### Path A: Pick and Choose

Start with whatever problem you have right now.

**"I want better code review"**
The base is enough. Before every commit, code-reviewer, integration-reviewer, and wtf-reviewer run automatically. For an on-demand review of your current branch: `/mine-review`. For a style and debt check: `/mine-clean-code`. For prose quality (PR descriptions, docs, commit messages): `/mine-humanize`. Included in base — no extra bundles needed.

**"I want structured planning for complex features"**
The base is enough. The full pipeline is `/mine-define` (produces a `design.md`) → `/mine-plan` (generates task files) → `/mine-orchestrate` (executes them with reviewer loops) → `/mine-ship` (commits, pushes, opens the PR). Start with `/mine-grill` to sharpen a raw idea first. Included in base.

**"I want to brainstorm and challenge ideas"**
The base is enough. `/mine-brainstorm` runs four parallel thinkers and ranks ideas. `/mine-grill` interrogates a rough idea across product, engineering, and adversarial lenses. `/mine-challenge` assumes your approach is wrong and argues for better. Included in base.

**"I want frontend design help"**
Add the **Frontend** bundle. You get the Impeccable UI design skills for audit (`/i-audit`), layout (`/i-layout`), typography (`/i-typeset`), color systems (`/i-colorize`), and more. Start with `/i-teach-impeccable` to set up design context, then pick the skill that matches your current problem.

**"I want help building CLI tools"**
Add the **CLI** bundle. Six skills cover hardening, output formatting, discoverability, error messages, complexity reduction, and comprehensive auditing. Start with `/cli-audit` for an existing tool, or `/cli-affordances` when designing a new one.

**"I want conversation memory across sessions"**
Add the **Memory** bundle. Claude remembers corrections, architectural decisions, and preferences across sessions. `/cm-recall-conversations` searches past sessions.

**"I want domain-specific engineering agents"**
Add the **Engineering** bundle. You get agents for FastAPI backends, PySpark pipelines, React/Vue/Angular frontends, SRE work (SLOs, observability), technical writing, and an adversarial pre-ship testing gate.

**"I want architecture and QA agents"**
Add the **Extra agents** bundle. Architect produces Mermaid diagrams and high-level overviews. Planner breaks complex features into task files. QA Specialist finds defects adversarially. Visual Diff catches unintended UI changes via Playwright.

---

### Path B: The Full Pipeline

This is the workflow that makes Claude Code feel like a senior engineer on your team, not a code autocomplete. It takes 10–30 minutes to run end to end for a small feature.

**Example:** adding rate limiting to a public API endpoint — a token-bucket limiter, per-key configuration, and `429` responses with retry headers.

**Step 1: Sharpen the idea**

```
/mine-grill
```

You describe the feature. `/mine-grill` interrogates it across five lenses — product fit, design clarity, engineering complexity, scope, and adversarial ("what could go wrong?"). It produces a `brief.md` that surfaces the decisions you haven't made yet.

*What you get:* a one-page brief identifying the key decisions and risks before you write any code.

**Step 2: Define the design**

```
/mine-define
```

Feed it your brief (or start fresh). The skill reads the codebase, asks the right clarifying questions, and produces a `design.md` with problem statement, functional requirements, acceptance criteria, and architecture notes. One sign-off gate before it finalizes.

*What you get:* a `design/specs/<spec-name>/design.md` that captures what you're building and why.

**Step 3: Generate a task plan**

```
/mine-plan
```

Takes the `design.md` and breaks it into concrete task files (`T01.md`, `T02.md`, ...) with FR/AC traceability. A 10-point review validates the plan before you approve it.

*What you get:* `design/specs/<spec-name>/tasks/` with one file per work package.

**Step 4: Execute**

```
/mine-orchestrate
```

Executes task files one by one. For each task, it runs code-reviewer, integration-reviewer, and wtf-reviewer in parallel on the diff. Findings are fixed before moving to the next task. A post-execution implementation review checks the full diff at the end.

*What you get:* the feature implemented, reviewed, and verified — ready to ship.

**Step 5: Ship**

```
/mine-ship
```

Commits, pushes, and opens a PR in one step. Picks up the right commit message format, links the related issue, and handles the PR description.

*What you get:* an open PR.

---

That's the full loop. For a feature like rate limiting — limiter logic, config, request-handler integration, and tests across a few files — the pipeline takes 20–30 minutes of wall-clock time, most of it waiting for Claude to execute. You stay in the reviewer seat, not the implementer seat.

---

### Path C: Everything

When you have all bundles installed, the system covers the full development lifecycle plus the surrounding workflow.

**Daily workflow pattern:**

```
/mine-good-morning          → read yesterday's handoff, orient, pick up where you left off
<work happens>
/mine-end-of-day            → capture session state as a handoff file
```

After a `/clear` (e.g. to drop a huge uncached context the morning after an orchestration), `/mine-resume` reads the *prior* session's transcript tail to recover your last instruction and any decision you left unanswered — no hand-written handoff needed. With the Memory bundle, the SessionStart hook also auto-warns when the previous session ended on an unanswered question.

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

**How the pieces interact:** Rules load automatically and shape every response — Claude writes code, handles git, and approaches security according to the rule files in `rules/common/`. Hooks run in the background — the pytest guard prevents hanging test runs, the context-tier hook prevents hallucinated context pressure. Skills and agents sit on top: you invoke a skill, it dispatches the right agents, they report back.

The result is a consistent development environment that works the same way every session, regardless of which codebase you're in.

## Customizing

**Choosing rule categories** — every rule in `rules/common/` loads into Claude's context each session, so the installer lets you install only the categories you need. A small **Core** set (capabilities routing, interaction style, invariants, agent dispatch, model selection, worktree safety) always installs. Everything else — language conventions, testing discipline, planning rules, and so on — is grouped into opt-out categories: selected by default, but you can drop the ones that don't fit your stack (a Python-only user might skip nothing, a backend-only user might drop frontend rules). Run `uv run install.py --reconfigure` to change the selection. If a rule you keep references one you dropped, the installer warns but installs anyway — the references are pointers, not hard dependencies. See the Rules table in [REFERENCE.md](REFERENCE.md) for the categories and their files.

**Add your own rules** — drop a `.md` file straight into `~/.claude/rules/common/` and it loads automatically next session, no installer step. If you add it to the repo's `rules/common/` instead (so it's version-controlled), re-run `uv run install.py` to symlink it.

**Codex CLI also gets the rules** — if you run OpenAI Codex CLI on the same machine, `install.py` generates a global `~/.codex/AGENTS.md` from the portable rules (via `codex-rules-sync`), so Codex is governed by the same always-on behavioral rules as Claude Code. Each rule's `tool:` frontmatter decides where it goes: portable rules carry `tool: claude, codex, antigravity`, while Claude-Code-harness-specific ones (skill routing, the code-review gate, tmux/sudo helpers) carry `tool: claude` and are excluded — they'd only mislead a tool that can't act on them. The default is fail-closed (a rule with no `tool:` key stays Claude-only), and the step skips silently if Codex isn't installed. Run `codex-rules-sync --list` to see the breakdown.

**Add your own skills** — `/mine-write-skill` walks you through requirements, drafts the `SKILL.md`, validates a quality checklist, and wires the routing entry. The result lands in `skills/` ready to install.

**Settings** — edit `settings.json` in the repo root, then run `claude-merge-settings` to write `~/.claude/settings.json`. It merges the repo's shared settings with a per-machine `~/.claude/settings.machine.json`, so each box can keep its own permissions, env vars, and hook tweaks without touching the version-controlled config. When you re-run the merge, it detects permissions you granted at runtime and offers to promote them into the machine file so they survive. Only the layers that actually exist are applied.

**Removing things** — run `uv run install.py --reconfigure` and deselect the bundle or rule category. For an individual rule file within a category you otherwise want, delete the symlink from `~/.claude/rules/common/` or remove the source file.

## Reference

See [REFERENCE.md](REFERENCE.md) for the full list of skills, agents, commands, hooks, bin scripts, and packages.
