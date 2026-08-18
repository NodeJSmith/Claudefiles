---
task_id: "T07"
title: "Bootstrap the live install and run the smoke test"
status: "done"
depends_on: ["T06"]
implements: ["AC#1", "AC#2", "AC#3", "AC#4", "AC#6", "AC#14", "AC#15", "AC#16", "AC#23"]
---

## Summary

Cut the live install over and observe that it works. Every prior task was verified against scratch directories, fakes, or a Node harness; this is where the plugin meets a real OpenCode process. Run `--bootstrap`, then `--prune`, then work through the design's six-step Smoke Test, capturing the output of each observation.

This task deliberately observes the running system rather than adding tests. The design's Test Strategy says so explicitly: there is no TypeScript test infrastructure in this repo, and OpenCode's own introspection surfaces are stronger evidence than a unit test of a config-shaping function, because they prove the consuming service actually resolved the value.

## Target Files

- read: `bin/opencode-sync`
- read: `opencode/claudefiles.ts`
- read: `opencode/config-data.json`
- read: `design/specs/1007-opencode-config-plugin/design.md` (Smoke Test; Acceptance Criteria)
- modify: `~/.config/opencode/config.json` (via `--bootstrap`)
- create: `~/.config/opencode/claudefiles.ts` (symlink, via `--bootstrap`)
- create: `~/.config/opencode/opencode-compat.md` (symlink, via `--bootstrap`; exact path per the plugin)
- delete: `~/.config/opencode/agents/`, `~/.config/opencode/skills/`, `~/.config/opencode/commands/`, `~/.config/opencode/rules/` (via `--prune`)

## Prompt

Run in this order — bootstrap before prune, so a failed bootstrap leaves the old install intact as a fallback:

1. `bin/opencode-sync --bootstrap`. Its verification tail must pass. If it fails, stop and fix — do not prune.
2. `bin/opencode-sync --prune`.
3. `bin/opencode-sync --verify` once more, now that the old files are gone. A pass here and a fail before pruning would mean the old files were doing the work.

Then the design's Smoke Test, capturing output for each:

- **`opencode debug agent code-reviewer`** — expect a `providerID`/`modelID` pair and a `variant`, not the bare tier `sonnet` (AC#1).
- **The same command with `--pure`** — expect failure, proving the entry came from the plugin and not from a file on disk (AC#2). This is the control that makes AC#1 mean anything; without it, a leftover file would produce the same output.
- **Per-tier resolution** (AC#23) — assert all three tiers resolve to distinct, specific triples matching `opencode/config-data.json`: `opus` → `openai/gpt-5.6-sol`, `sonnet` → `openai/gpt-5.6-terra`, `haiku` → `openai/gpt-5.6-luna`, each at `variant: high`. Pick one agent of each tier from `~/.claude/agents/` (check frontmatter to choose). "Some `providerID`/`modelID` pair resolved" is not sufficient — a tier map that mapped everything to one model would pass that and fail this.
- **`GET /command` on a running `opencode serve`** — expect one entry per skill whose **frontmatter** declares `opencode-command: true`, which is 12, not the 14 a bare grep for the string returns (`mine-write-skill/SKILL.md`'s body and `mine-write-skill/REFERENCE.md` are decoys — see T02) (AC#3). Poll for readiness before querying: a request issued before the server finishes starting returns zero commands, which reads as a failure and is not one.
- **`opencode debug config`** — expect every non-excluded file under `~/.claude/rules/common/` and `~/.claude/rules/personal/` listed in `instructions`, and `sudo.md` absent (AC#4). Confirm all five personal rules are present by name; this is the roadmap `:194` closure and the one instruction-layer behavior the design's probes never verified at service level.
- **The compatibility rule** — its path appears in `instructions`, and the file at that path contains the `mcp__<server>__<tool>` → `<server>_<tool>` mapping (AC#6). Follow the symlink and read it; a path in the array pointing at nothing produces no error and no rule.
- **Session startup log** — no `duplicate skill name` warnings (AC#14). The baseline was 41 per startup, with the stale synced copy winning each time. Zero is the target, and the number is the whole point of dropping the skills sync.
- **`bin/opencode-variant-audit --json`** — `fell_back: 0` across a dogfooded session's dispatches (AC#15). This requires actually running a dispatch-bearing workflow in OpenCode first; the audit reads `opencode.db` and has nothing to report otherwise (it exits 3 on no dispatched sessions in the window). Use `--since` or `--all` as appropriate.

Finally run the full local gates: `mise run test:root` (AC#16) and `prek run --all-files`.

Record every observation with its actual command output. If any AC fails, that is a finding about the implementation, not a reason to soften the criterion.

## Focus

**This task mutates the developer's live OpenCode install.** `--prune` deletes four directories under `~/.config/opencode/` irreversibly. Confirm `--bootstrap` succeeded and `--verify` passed before running it. Everything else in that directory — `AGENTS.md`, `opencode.jsonc`, `node_modules/`, `package.json`, `package-lock.json`, `tui.json`, `config.json.bak` — must survive.

**Propagation is per-process, not per-session.** `config()` runs once during plugin-layer init and its result is cached for the instance (`effect/instance-state.ts:26-40`, `ScopedCache` with `capacity: POSITIVE_INFINITY`). Kill any long-running `opencode serve` between changes. A stale server showing old behavior is the single most likely way to misread a result here — it produced a false negative during the design's own probing.

**Smoke Test step 4 (edit a rule, restart, confirm it took effect) is the goal-#1 proof** and has no AC of its own. Run it anyway: edit a rule under `~/Claudefiles/rules/common/`, start a **new** `opencode` process, confirm the change is live with no sync command in between, then revert the edit.

**The seven orphans are the check that `--prune` did its job.** Before pruning, `~/.config/opencode/agents/` holds 33 files against 26 real agents; the extra seven are `worker-lightweight`, `worker-standard`, `worker-opus`, and four `engineering-*-opus`. After pruning and bootstrapping, `opencode debug agent worker-standard` should fail — that name has no source file and must no longer resolve.

**`opencode debug agent --pure` failing is a pass, not an error.** Do not treat a non-zero exit there as a problem to fix.

**Do not weaken an AC to make it pass.** In particular AC#14's target is zero duplicate-skill warnings, not "fewer than before" — if warnings remain, something is still installing a second copy of a skill, and finding it is the work.

**AC#15 needs a real workflow run.** Dispatching a single trivial subagent may not exercise enough for a meaningful result; run something that dispatches several. If `opencode-variant-audit` exits 3 (no dispatched sessions in window), that is not a pass.

## Verify

- [ ] AC#1: `opencode debug agent <name>` resolves for every file in `~/.claude/agents/`, and its output shows a `providerID`/`modelID` pair and a `variant` rather than a bare Claude tier name.
- [ ] AC#2: `opencode debug agent <name> --pure` fails for the same agent.
- [ ] AC#3: `GET /command` on a running `opencode serve` returns exactly 12 entries, one per skill whose frontmatter declares `opencode-command: true`, with no `mine-write-skill` entry.
- [ ] AC#4: `opencode debug config` lists every non-excluded file under `~/.claude/rules/common/` and `~/.claude/rules/personal/` in `instructions`, including all five personal rules, and does not list `sudo.md`.
- [ ] AC#6: the compatibility rule's path appears in `instructions`, and reading the file at that path shows the `mcp__<server>__<tool>` → `<server>_<tool>` mapping.
- [ ] AC#14: starting an OpenCode session emits zero `duplicate skill name` warnings.
- [ ] AC#15: `bin/opencode-variant-audit --json` reports `fell_back: 0` across a dogfooded session's dispatches, with a non-zero dispatch count.
- [ ] AC#16: `mise run test:root` passes with zero failures.
- [ ] AC#23: `opus`, `sonnet`, and `haiku` agents each resolve to their distinct expected triple — `openai/gpt-5.6-sol`, `openai/gpt-5.6-terra`, `openai/gpt-5.6-luna` respectively, all at `variant: high`.
