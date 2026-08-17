---
task_id: "T05"
title: "Add --bootstrap, --prune, and --verify plus the prek hook"
status: "planned"
depends_on: ["T04"]
implements: ["FR#19", "FR#20", "FR#22", "FR#25", "FR#26", "FR#28", "AC#10", "AC#11", "AC#13", "AC#20", "AC#21", "AC#24"]
---

## Summary

The construction half. Add the three commands that replace the sync: `--bootstrap` (symlink the plugin and the compatibility rule into the OpenCode config dir, write `config.json`, then verify), `--prune` (delete the four previously-installed trees, including the seven orphaned agents), and `--verify` (shell out to `opencode debug agent` and fail if any agent does not resolve). Wire `--verify` into `prek.toml` as a file-scoped hook.

`--verify` is the only detection mechanism this architecture has. OpenCode swallows both plugin-load and `config()` exceptions, so a broken plugin yields a session with no Claudefiles agents and no message. Everything about this task's value depends on `--verify` actually failing when it should.

## Target Files

- modify: `bin/opencode-sync` (`parse_args`, `main`, `generate_config`, `OPENCODE_CONFIG:43`, `CONFIG_JSON_FILENAME:54`)
- modify: `prek.toml`
- modify: `tests/test_opencode_sync.py`
- read: `opencode/claudefiles.ts`
- read: `opencode/opencode-compat.md`
- read: `opencode/config-data.json`
- read: `design/specs/1007-opencode-config-plugin/design.md` (Architecture → "What `bin/opencode-sync` becomes"; Edge Cases)

## Prompt

**`--bootstrap` (FR#25, FR#22, FR#26).** Symlink `opencode/claudefiles.ts` to `<config_dir>/claudefiles.ts` and `opencode/opencode-compat.md` to a path under `<config_dir>/` that matches whatever the plugin appends to `cfg.instructions` — read `opencode/claudefiles.ts` to get that path rather than picking one and hoping. Write `config.json` via the reduced `generate_config()`. Then run the full `--verify` sweep as the final step and propagate its exit code.

Symlinks, not copies: FR#22's point is that editing the plugin needs no reinstall. Must be idempotent — re-running after a plugin edit is a no-op, not a duplicate or an error. An existing symlink already pointing at the right target is success; an existing *file* at that path is a conflict worth failing loudly on rather than clobbering.

The verification tail (FR#26) exists because bootstrap is the one moment the plugin is guaranteed to have just changed, and therefore the moment breakage is most likely introduced. A bootstrap that exits 0 while every agent silently fails to resolve is the exact failure this whole design accepts as its cost; the tail is what pays it back.

**`--prune` (FR#19).** Remove `<config_dir>/agents/`, `<config_dir>/skills/`, `<config_dir>/commands/`, and `<config_dir>/rules/` wholesale. This is what deletes the seven orphaned agents — `worker-lightweight`, `worker-standard`, `worker-opus`, and four `engineering-*-opus` — which are still installed and still dispatchable with no source file behind them.

Wholesale deletion is deliberate and differs from the old `generate_skill_commands()`, which deleted only marker-tagged files and explicitly preserved source commands. It is safe **on the assumption that those four directories are 100% generated output today**, which the design confirms by accounting (33 agents installed against 26 real). Record that assumption in the function's docstring, because nothing enforces it: OpenCode natively scans those same directories for user-authored content, so a hand-dropped native agent added after this ships would be indistinguishable from generated output and silently deleted by a later `--prune`. Note in the docstring what the fix would be if that becomes a real workflow (marker-based selectivity, or a dry-run default). Do not build either now.

**`--verify` (FR#20).** With no argument, check every `*.md` file under `~/.claude/agents/` by shelling out to `opencode debug agent <stem>`; exit non-zero if any fails to resolve, naming **every** one that failed rather than stopping at the first. With an agent name argument, check only that one.

Resolve the `opencode` binary from `PATH`. If it is not found, that is a distinct failure from "an agent did not resolve" — say so, and exit non-zero rather than reporting a false pass. Give each subprocess a timeout; a hung `opencode` must not hang a pre-commit hook.

**`prek.toml` hook (FR#28).** Add a hook whose `entry` invokes `--verify` and whose `files` pattern matches `opencode/claudefiles.ts` and `opencode/config-data.json`. It must **not** set `always_run = true` — it starts an OpenCode process and is too slow for every commit. This is the one hook in the file that is file-scoped; the two existing `lint-opencode-sync*` blocks (`prek.toml:114-121` and `:123-130`) are `always_run` and stay that way. Follow their shape otherwise (`language = "system"`, `stages = ["pre-commit"]`). Note that `pass_filenames` should be false — `--verify`'s optional positional argument is an agent name, not a file path, so letting prek append filenames would be actively wrong.

**Tests.** Add:
- `--bootstrap` run twice against a scratch config dir leaves `config.json`, the plugin symlink, and the compat-rule symlink identical after the second run (AC#20).
- `--bootstrap` against a config dir whose plugin symlink points at a deliberately broken file exits non-zero and names the failing agent (AC#21).
- `--prune` against a scratch config dir seeded with all four trees leaves none of them (AC#10).
- `--verify` exit codes: zero when every agent resolves, non-zero naming the agent when one does not; the single-name form checks only that one (AC#11).
- the `--verify` hook's `files` pattern matches `opencode/claudefiles.ts` and `opencode/config-data.json` and does not match unrelated paths, and the hook does not set `always_run` (AC#24).

For the `--verify` tests, fake the `opencode` subprocess rather than invoking the real binary — `tests/test_opencode_sync.py` already monkeypatches `subprocess.run` for the old opkg tests (see the `fake_run` helpers around `:81` and `:119` before T04 deletes them; the pattern is worth preserving even though those particular tests are gone). A test that shells out to the real `opencode` would be slow, machine-dependent, and would fail in CI where no OpenCode install exists.

## Focus

**`--verify` is tested against a fake but must work against the real thing.** After the unit tests pass, run `bin/opencode-sync --verify` for real once. The binary is at `~/.local/share/mise/installs/aqua-opencode/latest/opencode` (version 1.18.18) and is on `PATH` via mise. If it reports failures, that is a genuine finding about T02's plugin — do not weaken `--verify` to make it pass.

**Bootstrap ordering matters.** `config.json` must declare the plugin before `--verify` runs, or the verification tail tests a config that does not load the plugin yet and reports a false failure. Write config, then symlink, then verify — or symlink, write, verify. Not verify-then-write.

**The compat rule's installed path is a contract between this task and T02.** The plugin appends a path to `cfg.instructions`; bootstrap must create a symlink at exactly that path. Read `opencode/claudefiles.ts` for the literal rather than inferring it. If the two disagree, `opencode debug config` shows an `instructions` entry pointing at nothing, and nothing fails — the rule is simply never loaded, which is the failure mode `build_instructions()`'s docstring was written to prevent in the first place.

**`--prune` is destructive and points at the user's live config dir by default.** `~/.config/opencode/` currently holds `AGENTS.md`, `config.json`, `config.json.bak`, `node_modules/`, `opencode.jsonc`, `package.json`, `package-lock.json`, and `tui.json` alongside the four trees being removed. Delete only the four named directories. `node_modules/` in particular must survive — OpenCode auto-installs `@opencode-ai/plugin` there and the plugin needs it. Make the config dir an injectable parameter so tests never touch the real one.

**`opencode.jsonc` must remain untouched by every command in this task** (FR#18, verified in T04). It is the machine-local overlay for `permission` and `mcp` and `loadGlobal()` merges it last so it wins on conflict.

**Do not run `--prune` against the live config dir as part of this task's verification.** That is T07's job, after the bootstrap is proven. Pruning before the plugin is confirmed working would leave the machine with neither the old files nor working config.

## Verify

- [ ] FR#19: a test seeds a scratch config dir with `agents/`, `skills/`, `commands/`, `rules/` plus an `opencode.jsonc` and a `node_modules/`, runs `--prune`, and asserts the four trees are gone and the other two remain.
- [ ] FR#20: a test with a faked `opencode` subprocess asserts `--verify` exits 0 when all agents resolve, exits non-zero listing every failing agent when two fail, and checks only the named agent when given one.
- [ ] FR#22: `readlink <scratch_config>/claudefiles.ts` after `--bootstrap` resolves to the repo's `opencode/claudefiles.ts`.
- [ ] FR#25: `--bootstrap` run twice against a scratch config dir produces byte-identical `config.json` and identical symlink targets after each run, with exit 0 both times.
- [ ] FR#26: `--bootstrap` propagates a non-zero exit when its verification tail fails — asserted with a faked failing `opencode`.
- [ ] FR#28: `prek.toml` contains a hook whose `entry` includes `--verify`, whose `files` pattern matches both `opencode/claudefiles.ts` and `opencode/config-data.json`, and which does not set `always_run = true`.
- [ ] AC#10: covered by the FR#19 test; no `agents/`, `skills/`, `commands/`, or `rules/` directory remains under the scratch config dir.
- [ ] AC#11: covered by the FR#20 test.
- [ ] AC#13: after running `--bootstrap` against the real config dir, `test <config>/claudefiles.ts -ef opencode/claudefiles.ts` succeeds (same inode).
- [ ] AC#20: covered by the FR#25 test.
- [ ] AC#21: covered by the FR#26 test.
- [ ] AC#24: covered by the FR#28 test, asserted by parsing `prek.toml` rather than by eye.
