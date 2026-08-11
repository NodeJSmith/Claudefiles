---
task_id: "T01"
title: "Rewrite opencode-sync skeleton from bash to Python"
status: "done"
depends_on: []
implements: ["FR#3", "FR#10", "AC#4", "AC#10", "AC#12"]
---

## Summary

Rewrite `bin/opencode-sync` from bash to Python, preserving the existing CLI interface (`--dry-run`, `--verbose`, `--allow-worktree`, `--check`) and adding `--lint-only`. This task establishes the script skeleton: argument parsing, staging with rsync/shutil, opkg invocation via subprocess, worktree detection, color field stripping from agent frontmatter, sync status checking, and the main control flow that later tasks plug into. The script must be runnable via `uv run bin/opencode-sync` using inline script metadata. No third-party dependencies beyond what `uv` provides.

## Target Files

- modify: `bin/opencode-sync` — full rewrite from bash to Python
- read: `bin/opencode-sync` — existing bash script (source of behavior to port)
- read: `design/specs/1006-oc-native-agents/design.md` — FR#3, FR#10, Architecture sections

## Prompt

Rewrite `bin/opencode-sync` from a bash script to a Python script. The script must be runnable via `uv run bin/opencode-sync` — add inline script metadata (`# /// script` / `# ///`) at the top with `requires-python = ">=3.10"` and no dependencies. Follow the `install.py` shebang pattern: `#!/usr/bin/env -S uv run --script`.

Preserve the existing CLI interface and behavior:
- `--dry-run` / `-n` — show what would be installed without modifying files
- `--verbose` / `-v` — show opkg output
- `--allow-worktree` — permit running from a worktree checkout
- `--check` — report sync status (exit 0=current, 1=stale)
- `--help` / `-h` — usage text
- Add `--lint-only` — run the compatibility lint without syncing (implemented as a no-op stub that exits 0; T04 fills it in)

Use `argparse` for argument parsing.

Implement these components, each as a function:

1. **`check_deps()`** — verify `npx` is available. Drop the `rsync` dependency — use `shutil.copytree` with an ignore pattern instead.

2. **`in_worktree(claudefiles: Path) -> bool`** — detect if running from a worktree. Port the existing bash logic: compare `git rev-parse --absolute-git-dir` against `git rev-parse --path-format=absolute --git-common-dir`. Use `subprocess.run` with `capture_output=True`.

3. **`stage_config(claudefiles: Path, tmpdir: Path)`** — create a clean staging copy. Use `shutil.copytree` with an `ignore` callback that excludes: `.claude`, `__pycache__`, `node_modules`, `.git`, `packages`, `tests`, `design`, `.venv`. Remove harness-only rules (`sudo.md`, `tmux.md`) from the staged copy. Write the `opencode-compat.md` compatibility rule into the staged copy (same content as the current bash script's heredoc).

4. **`run_opkg(staged_dir: Path, dry_run: bool, verbose: bool)`** — invoke `npx --yes "opkg@0.11.3" install <staged_dir>/claudefiles --platforms opencode --cwd $HOME -g --force` via `subprocess.run` with `timeout=120`, `capture_output=True`, `text=True`. On failure, print stderr and exit non-zero. In non-verbose mode, filter output to show only lines matching `^✓|Installed files:|No files`. Add `--dry-run` flag when in dry-run mode.

5. **`strip_color_fields(agents_dir: Path)`** — remove `color:` lines from agent frontmatter. Read each `.md` file, remove lines matching `^color: ` that appear between the opening `---` markers, write back. This is FR#10. Only touch frontmatter lines (between the first two `---` markers).

6. **`check_sync_status(claudefiles: Path, sync_sha_file: Path) -> bool`** — compare current `HEAD` against stored SHA. Print status message. Return True if current.

7. **`main()`** — orchestrate: parse args → check-only path → check deps → worktree guard → stage → uninstall previous → opkg install → strip colors → (placeholder for dispatch rewrite, T03) → (placeholder for model remap, T03) → (placeholder for worker generation, T02) → (placeholder for config generation, T02) → (placeholder for lint, T04) → record sync SHA → done message.

Leave clearly marked stub points for T02 (worker/config generation), T03 (dispatch rewrite + model remap), and T04 (lint + collision detection + foreign config backup). Use comments like `# T02: worker agent generation` and `# T03: dispatch rewrite` to mark where later tasks plug in.

Constants to define at the top:
- `OPKG_VERSION = "0.11.3"`
- `OPENCODE_CONFIG = Path.home() / ".config" / "opencode"`
- `SYNC_SHA_FILE = OPENCODE_CONFIG / ".claudefiles-sync-sha"`
- `EXCLUDE_DIRS` set
- `HARNESS_ONLY_RULES` list
- `OPKG_SUCCESS_PATTERN` regex

The `opencode.jsonc` must not be modified (FR#3) — verify via AC#4 that its mtime is unchanged.

## Focus

- The current bash script is 298 lines at `bin/opencode-sync`. Read it fully before rewriting.
- `install.py` uses `#!/usr/bin/env -S uv run --script` with inline script metadata — follow this pattern exactly.
- The worktree detection logic (lines 61–71 of the bash script) uses `--path-format=absolute --git-common-dir` to avoid a subtle detection bug where `--git-common-dir` returns a relative path from the repo root. Port this correctly.
- The staging function writes an `opencode-compat.md` rule file into the staged copy (lines 163–182). Copy this content exactly.
- The opkg uninstall step (lines 245–249) checks if `claudefiles` is in the opkg list before uninstalling. Port this check.
- The `CLAUDEFILES` path comes from `$CLAUDEFILES_DIR` env var or defaults to `$HOME/Claudefiles`. The Python script should read `os.environ.get("CLAUDEFILES_DIR", str(Path.home() / "Claudefiles"))`.
- The sync SHA is the full git commit hash, but display uses first 12 chars.
- The script replaces a bash script, so the pre-commit hook `shellcheck` will no longer apply to it, but `ruff` will. Ensure the Python passes ruff.

## Verify

- [ ] FR#3: `opencode.jsonc` has the same mtime before and after running `opencode-sync`
- [ ] FR#10: After sync, `grep -r '^color:' ~/.config/opencode/agents/` returns zero matches
- [ ] AC#4: `opencode.jsonc` mtime unchanged after sync
- [ ] AC#10: `opencode-sync --check` reports sync status (current/stale/never-synced)
- [ ] AC#12: After sync, `grep -r '^color:' ~/.config/opencode/agents/` returns zero matches
