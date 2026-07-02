---
task_id: "T02"
title: "Migrate install.py from ccrecall to cass"
status: "planned"
depends_on: ["T01"]
implements: ["FR#1", "FR#12", "AC#1", "AC#2", "AC#13"]
---

## Summary
Replace all ccrecall installation, plugin management, and uninstall code in install.py with cass binary installation via `bin/cass-update`. Remove settings.json plugin entries. Gate ccrecall/plugin removal on cass install success. Update tests to cover the new ensure_cass() function and uninstall path.

## Target Files
- modify: `install.py`
- modify: `settings.json`
- modify: `tests/test_install.py`
- read: `bin/cass-update` (created in T01 — called by ensure_cass())
- read: `design/specs/1000-ccrecall-to-cass-migration/design.md` (§ Architecture > Removal scope, § Test Strategy)

## Prompt
### install.py changes

**Remove constants** (lines 59-67): `CCRECALL_PACKAGE`, `LEGACY_MEMORY_PACKAGE`, `CCRECALL_MARKETPLACE_REPO`, `CCRECALL_PLUGIN_REF`. The `LEGACY_MEMORY_PACKAGE` cleanup path is no longer needed — all machines have already migrated from claude-memory.

**Remove functions**: `ensure_ccrecall()` (lines 825-859), `ensure_ccrecall_plugin()` (lines 748-796), `ccrecall_plugin_installed()` (lines 728-745), `remove_ccrecall_plugin()` (in `do_uninstall()`).

**Remove from `do_install()`** (lines 1316-1318): the calls to `ensure_ccrecall()` and `ensure_ccrecall_plugin()`.

**Add `ensure_cass()` function** following the `shutil.which()` detection pattern from Convention Examples:
1. Check `shutil.which("cass")` — if present, skip installation.
2. If absent, call `bin/cass-update` via subprocess (use repo_dir / "bin" / "cass-update" as the path). The script is symlinked to `~/.local/bin/` by the existing bin/ symlink infrastructure, but call it by repo path during install since symlinks may not exist yet.
3. After cass-update succeeds, verify `shutil.which("cass")` — if now present, proceed to ccrecall removal.
4. **Safety invariant**: Only remove ccrecall and its plugin AFTER cass is confirmed installed. Call `uninstall_package(CCRECALL_PACKAGE)` (using the literal string "ccrecall") and `run_claude_plugin(claude_bin, ["uninstall", "ccrecall@claude-code-recall"])` only when `shutil.which("cass")` returns a path. If cass install failed, warn but leave ccrecall in place.
5. Return error count.

**Add to `do_install()`**: Call `ensure_cass(repo_dir, console)` where `ensure_ccrecall()` was.

**Update `do_uninstall()`**: Replace `pkgs_to_uninstall.append(CCRECALL_PACKAGE)` and `remove_ccrecall_plugin()` with:
- Delete `~/.local/bin/cass` if it exists
- Delete `~/.local/share/claudefiles-cass/` directory if it exists (timestamp + handoff files)
- Attempt `run_claude_plugin(claude_bin, ["uninstall", "ccrecall@claude-code-recall"])` as a cleanup of any lingering plugin registration (best-effort, don't error on failure)

**Update V1-to-V2 migration** (lines 425-449): The existing code already drops `skills.memory` and `packages.claude-memory` — no changes needed to the migration logic itself, but the comment mentioning ccrecall can be updated.

### settings.json changes

Remove the `extraKnownMarketplaces` block (lines 17-24) and the `enabledPlugins` block (lines 25-27). These are the only entries — after removal, both keys should be absent from the JSON (not empty objects).

### test_install.py changes

**Remove**: `_stub_ccrecall_side_effects` autouse fixture (lines 48-74). Remove `TestCcrecallPlugin` class (8 tests, lines 1106-1243). Remove 6 cases from `TestPackageInstall` — 3 ccrecall-specific (`test_skips_ccrecall_when_present`, `test_installs_ccrecall_when_absent`, `test_install_failure_increments_errors`) and 3 legacy-claude-memory-specific (`test_uninstalls_legacy_claude_memory_when_present`, `test_no_uninstall_when_claude_memory_absent`, `test_keeps_legacy_when_ccrecall_install_fails`). Keep the 3 non-ccrecall tests. Remove `"memory": True/False` from V1-to-V2 migration test fixtures and the paired `"claude-memory": True/False` from the `packages` block (lines 1757-1803).

**Add `TestCassBinary` class**:
- `test_skips_when_cass_on_path`: stub `shutil.which("cass")` to return a path → `ensure_cass()` returns 0, no subprocess called
- `test_installs_when_absent`: stub `shutil.which("cass")` to return None then a path (post-install) → `ensure_cass()` calls `cass-update` subprocess
- `test_handles_download_failure`: stub `shutil.which("cass")` to return None, subprocess returns failure → error count incremented, no ccrecall removal attempted
- `test_removes_ccrecall_after_cass_installed`: stub `shutil.which("cass")` to return a path post-install → verify `uninstall_package("ccrecall")` and plugin uninstall called
- `test_keeps_ccrecall_if_cass_fails`: stub `shutil.which("cass")` to return None throughout → verify ccrecall NOT uninstalled (safety invariant)

**Update `TestDoUninstall`**: verify cass binary and `~/.local/share/claudefiles-cass/` cleanup instead of ccrecall package uninstall. Use `tmp_path` fixture for filesystem assertions.

**Add cass-specific fixture**: stub `shutil.which("cass")` and subprocess calls to `cass-update` in the same pattern as the old `_stub_ccrecall_side_effects`.

## Focus
- The `shutil.which()` pattern is well-established in install.py — follow it exactly.
- `run_uv_tool()` handles subprocess errors consistently — reuse it for `cass-update` invocation or write a similar wrapper.
- The `run_claude_plugin()` function needs the resolved `claude` binary path via `shutil.which("claude")`. This existing pattern is reused for the ccrecall plugin uninstall.
- `settings.json` is the merged source — after removing the plugin entries, `claude-merge-settings` will produce a clean result without them.
- The test file is large (1800+ lines). Be careful with line number references — they may shift after removals. Match on function/class names, not line numbers.

## Verify
- [ ] FR#1: install.py installs cass binary when not on PATH
- [ ] FR#1: install.py removes ccrecall only after cass is confirmed installed
- [ ] FR#1: install.py leaves ccrecall in place if cass install fails
- [ ] FR#12: `install.py --uninstall` removes `~/.local/bin/cass` and `~/.local/share/claudefiles-cass/`
- [ ] AC#1: `cass --version` succeeds from PATH after install.py runs on a clean machine
- [ ] AC#2: ccrecall binary and plugin registration removed after install.py runs
- [ ] AC#13: uninstall removes cass binary and bookkeeping directory
