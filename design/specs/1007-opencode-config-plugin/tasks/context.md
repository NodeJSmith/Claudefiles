# Context: OpenCode Config Plugin — Runtime Generation from the Live Install

## Problem & Motivation

`bin/opencode-sync` delivers Claudefiles to OpenCode by copying files to disk — staging a clean tree, invoking OpenPackage, rewriting agent frontmatter in place, generating skill-command wrappers, writing `config.json`, and maintaining sync-state so it can tell whether any of that went stale. Most of the script exists to make those disk writes safe rather than to decide anything.

Three problems observed on the live install: (1) the synced skills are worse than not syncing — OpenCode natively scans `~/.claude/skills/**/SKILL.md`, and the second copy under `~/.config/opencode/skills/` shadows the live symlink, producing 41 duplicate-name warnings per startup where the potentially-stale copy wins; (2) generated artifacts outlive their source — `~/.config/opencode/agents/` holds 33 agents against 26 real ones, the extra seven being output from machinery spec 1008 already deleted; (3) personal rules from Dotfiles never arrive at all.

Spec 1008 removed the largest reason the copy-to-disk design existed: with every dispatch naming a real agent file, there is no dispatch syntax left to translate. What remains is transport, and transport can be replaced by a plugin that reads the live install at session start.

## Visual Artifacts

None.

## Key Decisions

1. **A TypeScript plugin at `opencode/claudefiles.ts`, symlinked into `~/.config/opencode/`, owns exactly three config keys** — `cfg.agent` (from `~/.claude/agents/*.md`), `cfg.command` (from skills declaring `opencode-command: true`), and `cfg.instructions` (from `~/.claude/rules/{common,personal}/*.md`). Nothing else. Path-like plugin specs resolve relative to the declaring config file, and `@opencode-ai/plugin` is already installed at `~/.config/opencode/node_modules`, so there is no build step and no publish.

2. **The plugin reads `~/.claude/`, never `~/Claudefiles` or `~/Dotfiles`.** `~/.claude` is the union of both repos as installed by `install.py` and Dotfiles' own installer. Dotfiles owns eleven of the skills OpenCode currently gets and all five personal rules; reading either repo directly is strictly less complete. Tradeoff accepted: OpenCode now depends on `install.py` having run, which deliberately breaks the roadmap's Claude-fallback invariants.

3. **Skills get no config entry at all.** OpenCode's native `~/.claude/skills` scan already delivers all 78. Once the second copy stops being installed, that scan is the only source and the duplicate warnings disappear. `cfg.skills.paths` is probe-verified racy (absent in all but one of ~16 runs) and is deliberately never set.

4. **The tier→model transform survives even though the transport does not.** `ConfigAgentV1.Info` types `model` as an unvalidated optional string and `Provider.parseModel()` splits on `/`, so an agent reaching OpenCode with `model: sonnet` resolves to `providerID: "sonnet"`, `modelID: ""` — no error, just a nonexistent model. The remap moves from a disk rewrite into `config()`.

5. **Shared values live in `opencode/config-data.json`, read by both sides.** JSON specifically — `tomllib` is Python-stdlib only from 3.11 (this script's floor is 3.10) and TypeScript has no built-in TOML parser, so TOML would force a plugin dependency the design otherwise avoids. JSON is the one format both read with zero dependencies. `TIER_MAP`'s load-bearing `variant`-not-`effort` comment (the #514 lesson) rides along as a `$comment` key.

6. **Propagation granularity is the process, not the session — probe-verified.** `config()` runs once during plugin-layer init and its result is cached per instance. A new session against an already-running `opencode serve` does not pick up edits; a fresh process does. TUI invocations are separate processes, so this is the ordinary case.

7. **A silently-unloaded plugin cannot be detected from inside the plugin.** OpenCode swallows both plugin-load failures (`plugin/index.ts:222-238`, `Effect.catch(() => Effect.void)`) and `config()` hook failures (`:243-251`, `Effect.ignore`). Detection is therefore external and explicit: `--verify` shells out to `opencode debug agent`, runs automatically at the end of every `--bootstrap`, and is wired as a file-scoped pre-commit hook.

8. **The exclusion list shrinks to one entry, `common/sudo.md`.** `performance.md`'s rationale is stale post-1008 and `tmux.md`'s `claude-tmux` works under either harness. `sudo.md` is different in kind — its instruction is "write `sudo` directly, the hook manages authentication," and with no hook firing the command hits a passwordless prompt with no TTY and hangs. That is an active failure, not an inapplicable paragraph.

## Constraints & Anti-Patterns

- **Do not read `~/Claudefiles` or `~/Dotfiles` directly** from the plugin. Read `~/.claude/`.
- **Do not reintroduce a copy of shared content under `~/.config/opencode/`.** A second copy is what produces the duplicate-name shadowing this change removes.
- **Do not set `cfg.skills.paths` from the plugin.** Probe-verified racy. Skills need no config.
- **Do not manage `opencode.jsonc`.** It is the machine-local overlay for `permission` and `mcp`, owned by the user, and `loadGlobal()` merges it last so it wins.
- **Do not rewrite skill or rule content.** Translation is the compatibility rule's job, performed by the model at read time.
- **Do not add a YAML or TOML dependency to the plugin.** Frontmatter is parsed by line scan, mirroring `_split_frontmatter()` (`bin/opencode-sync:499`).
- **Do not hand-copy any value `opencode/config-data.json` owns** into either `bin/opencode-sync` or `opencode/claudefiles.ts`.
- **Python side follows repo rules**: no `from __future__ import annotations`, `X | None` over `Optional[X]`, no lazy imports, `whenever` if any date handling arises.
- **Non-goals — do not implement**: Track 1 runtime hook parity (porting `scripts/hooks/*.sh` to plugins), `chat.params` for reasoning effort, any `experimental.*` hook, `oh-my-opencode-slim` adoption, `tool.execute.after` skill-content rewriting, or the filed resolutions of issues #500/#501/#517.

## Design Doc References

Design doc: `design/specs/1007-opencode-config-plugin/design.md`

- **## Problem** — the three observed failures on the live install, with counts.
- **## Goals** — the five outcomes, including the process-not-session propagation caveat.
- **## Non-Goals** — what is explicitly out of scope, with the reasons each was ruled out.
- **## Functional Requirements** — FR#1–FR#28.
- **## Edge Cases** — silent plugin-load failure, the seven orphaned agents, uninstalled bundles, `--prune`'s wholesale deletion assumption, dangling symlinks, renamed exclusions.
- **## Acceptance Criteria** — AC#1–AC#24.
- **## Key Constraints** — the five "do not" rules, reproduced above.
- **## Dependencies and Assumptions** — the probe results table, the declared-dependency-theory refutation, propagation granularity, and the deliberately-broken roadmap invariants.
- **## Architecture** — the three-key table, what `bin/opencode-sync` becomes, and the existing-code-leverage table.
- **## Implementation Preferences** — plugin location, the JSON-not-TOML decision, frontmatter line scan.
- **## Replacement Targets** — the per-function disposition table with line numbers. `_atomic_write()` survives; `_atomic_write_json()`, `_atomic_write_text()`, and `_split_eol()` do not.
- **## Test Strategy** — unit tests via `runpy` for Python; observation rather than unit tests for the plugin, with the stated reason.
- **## Smoke Test** — the six-step verification sequence.
- **## Documentation Updates** — the eight files to touch.
- **## Impact** — Changed Files, Behavioral Invariants, Blast Radius.

## Convention Examples

### `bin/` scripts are `uv run --script` with inline PEP 723 metadata

**Source:** `bin/opencode-sync:1-5`

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
```

### Docstrings cite upstream source and defend the non-obvious choice

**Source:** `bin/opencode-sync:833-855`

```python
def build_instructions(config_dir: Path) -> list[str]:
    """Build the `instructions` list of config.json: the synced shared rules.

    [...]

    One glob per directory, never `**`: for an absolute path OpenCode globs
    only `basename(pattern)` within `dirname(pattern)`, so a recursive
    pattern silently matches nothing. Add a line here when a rules
    subdirectory is added, and see check_instruction_globs() -- which fails
    the sync if a synced rules directory has no glob covering it -- rather
    than relying on remembering to.
    """
```

(Excerpted — the full docstring also explains why the rules would be inert without this list, and why paths derive from `config_dir` rather than the module constant.)

Non-obvious behavior gets its upstream mechanism named and the wrong-looking-but-correct choice defended, so it survives future cleanup.

### Frontmatter is split by line scan, not a YAML parser

**Source:** `bin/opencode-sync:499-516`

```python
def _split_frontmatter(content: str) -> tuple[str, str]:
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return "", content

    return "".join(lines[: end_idx + 1]), "".join(lines[end_idx + 1 :])
```

### Testing a `bin/` script

**Source:** `tests/test_opencode_variant_audit.py`

```python
import runpy
import pytest

def _load_script() -> dict:
    ...

@pytest.mark.parametrize("variant,expected_resolved", [...])
def test_classify_verdicts(variant: str | None, expected_resolved: bool) -> None:
    ...
```

`bin/` scripts have no importable module, so tests load them via `runpy`, with `parametrize` for cases and `tmp_path` for filesystem fixtures.

### Wiring a check as a pre-commit hook

**Source:** `prek.toml:114-121`

```toml
[[repos.hooks]]
id = "lint-opencode-sync"
name = "OpenCode dispatch pattern coverage"
entry = "bin/opencode-sync --check-source"
language = "system"
pass_filenames = false
always_run = true
stages = ["pre-commit"]
```

## Environment Facts (from Phase 2 exploration)

- **Test command**: root suite runs via `mise run test:root` → `env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_PREFIX uv run --with pytest --with questionary --with rich pytest tests/`. CI runs `mise run 'test:*'` (`.github/workflows/test.yml`) and `prek run --all-files --stage pre-commit`. AC#16's `pytest tests/` is the same suite; prefer the mise task so the git-env stripping applies.
- **Installed OpenCode binary**: `~/.local/share/mise/installs/aqua-opencode/latest/opencode`, version `1.18.18` — matches the reference clone at `~/source/opencode` (commit `3fd77ae`).
- **No `bun` on PATH.** Node is `v24.19.0`, which runs `.ts` files directly via type stripping (erasable syntax only — no `enum`, `namespace`, or parameter properties). This makes the plugin locally testable without OpenCode.
- **`~/.claude/agents/`** currently holds 26 files. **`~/.config/opencode/agents/`** holds 33 — the seven orphans.
- **`~/.claude/rules/personal/`** holds exactly five symlinks into `~/Dotfiles/config/claude/rules/personal/`: `capabilities-base.md`, `capabilities.md`, `machines.md`, `mcp-tools.md`, `python-packaging.md`.
- **The Claudefiles repo's own `rules/` tree has only `common/`** (34 `.md` files). There is no `rules/personal/` in this repo — it exists only in the installed union.
- **Thirteen `SKILL.md` files declare `opencode-command: true`**: `mine-address-pr-issues`, `mine-challenge`, `mine-clean-code`, `mine-comb`, `mine-define`, `mine-eval-repo`, `mine-orchestrate`, `mine-plan`, `mine-prior-art`, `mine-review`, `mine-ship`, `mine-sketch`, `mine-write-skill`. (`skills/mine-write-skill/REFERENCE.md` also contains the string but is documentation, not a `SKILL.md`, and must not produce a command.)
- **`opencode/` does not exist yet** — T01 creates it.
- **`~/.config/opencode/` currently contains**: `AGENTS.md`, `agents/`, `commands/`, `config.json`, `config.json.bak`, `node_modules/`, `opencode.jsonc`, `package-lock.json`, `package.json`, `rules/`, `skills/`, `tui.json`.
- **`find_orphaned_definitions()` counts raw substring occurrences**, including comments and docstrings (`bin/opencode-sync:1400-1407`, deliberate). A docstring that still names a deleted helper will keep it out of the orphan report — do not rely on `--check-orphans` alone to prove a name is gone; grep as well.
