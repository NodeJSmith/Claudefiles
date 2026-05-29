---
task_id: "T03"
title: "Add ado-api standalone detection and packages lifecycle"
status: "planned"
depends_on: ["T01", "T02"]
implements: ["FR#13"]
---

## Summary

Wire the `packages` config section (established as a data slot in T02) into real behavior: when `git-platform` detects Azure DevOps in the current repo, the installer offers `ado-api` as a standalone package (not a bundle), records the choice in `config["packages"]["ado-api"]`, installs/uninstalls it from that flag, pre-checks it on `--reconfigure`, and shows it in `--dry-run`. This is the only standalone package; the `packages` section is built to generalize but `ado-api` is its sole current member.

## Prompt

Work in `install.py` and `tests/test_install.py`. Implement design `## Functional Requirements` FR#13 and `## Architecture` → "Config format" (the `packages` section behavior) and the `do_uninstall` packages-section contribution.

**1. ADO detection.** Add a helper that invokes the `git-platform` CLI (in `bin/git-platform`) via `subprocess.run` against the current repo and returns whether the platform is Azure DevOps. Follow the existing subprocess idioms in `install.py` (`capture_output=True, text=True`, explicit `timeout=`, catch `FileNotFoundError`/`TimeoutExpired` and treat as "not detected"). There is no existing in-module pattern for calling a repo `bin/` tool — model the call on `_get_installed_packages` (install.py:449) and `_is_git_worktree` (install.py:252) for structure.

**2. Wizard prompt.** In the interactive flow, after the optional-bundle checkbox, if ADO is detected, ask a single contextual confirm: "This repo uses Azure DevOps. Install ado-api?" (default per the design — a detected suggestion, not forced). Record the answer in `config["packages"]["ado-api"]`. On `--reconfigure`, pre-check based on the saved `config["packages"]["ado-api"]`. Do not prompt when ADO is not detected; preserve any existing saved `packages.ado-api` value untouched in that case.

**3. Install/uninstall wiring.**
- `do_install`: after bundle packages, install `ado-api` iff `config["packages"]["ado-api"]` is true (skip if already installed, same as bundle packages). If it was true in `prev_config` and is now false, uninstall it (mirror the deselected-package path).
- `do_uninstall`: add packages flagged true in `cfg["packages"]` to the uninstall list, alongside the bundle-derived packages and base packages (design `## Architecture` → Config contract → `do_uninstall`).

**4. Dry-run.** `_print_dry_run` shows `ado-api` standalone-package status (install/remove/skip) when relevant, separate from the bundle list.

Add co-located tests: ADO-detected → prompt offered and choice recorded in `packages`; ADO-not-detected → no prompt, existing `packages.ado-api` preserved; `do_install` installs/uninstalls ado-api from the flag; `do_uninstall` removes a flagged ado-api; `--reconfigure` pre-checks a previously-installed ado-api. Mock the `git-platform` subprocess at the boundary (do not shell out in tests).

## Focus

- `bin/git-platform` exists in the repo. The design's capabilities files describe it as the platform-detection tool ("detect git platform, github or ado"). Confirm its output contract by reading `bin/git-platform` before wiring — match on its actual stdout/exit-code convention, not an assumption.
- This task touches `do_install`, `do_uninstall`, `run_wizard`, `_print_dry_run`, and `main` again — all rewritten in T01. Keep the standalone-package handling as a small, clearly-separated addition; do not entangle it with bundle iteration. The `packages` section is config-only and never lists bundle packages (those derive from `bundles` + `BUNDLES`).
- Mock subprocess at the boundary per the repo's testing rules (mock external boundaries only). The detection helper should accept the repo dir so tests can drive it without a real ADO repo, and the subprocess call should be patchable.
- There is no AC in the design doc for FR#13 (it was added after the AC list was written). Verification is anchored to FR#13 behavior directly.
- Test command: `timeout 300 uv run --with pytest --with python-frontmatter --with rich --with questionary --find-links packages/spec-helper pytest tests/ -v`.

## Verify
- [ ] FR#13: when `git-platform` reports Azure DevOps for the current repo, the installer offers `ado-api` via a contextual confirm; the choice is recorded in `config["packages"]["ado-api"]`; `do_install` installs it when true and uninstalls when toggled false; `do_uninstall` removes it; `--reconfigure` pre-checks a previously-installed ado-api; no prompt appears when ADO is not detected.
