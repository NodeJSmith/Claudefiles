---
task_id: "T01"
title: "Create bin/cass-update bootstrap and update script"
status: "planned"
depends_on: []
implements: ["FR#2", "AC#3"]
---

## Summary
Create `bin/cass-update`, a bash script that handles both initial bootstrap (downloading cass from GitHub releases) and updates (delegating to `cass upgrade --yes`). This is the foundation — install.py and the SessionStart hook both call this script. Supports an `--if-stale` flag for the hook's 24-hour update cadence.

## Target Files
- create: `bin/cass-update`
- read: `bin/orchestrate-cost` (reference for bin/ script conventions — shebang, permissions)
- read: `design/specs/1000-ccrecall-to-cass-migration/design.md` (§ Architecture > Binary lifecycle)

## Prompt
Create `bin/cass-update` as an executable bash script. The script has two modes:

**Bootstrap (cass not on PATH):**
1. Query the GitHub releases API: `https://api.github.com/repos/Dicklesworthstone/coding_agent_session_search/releases/latest` to get the tag name.
2. Download `cass-linux-amd64.tar.gz` and `cass-linux-amd64.tar.gz.sha256` from the release assets to a temp directory.
3. Verify the SHA-256 checksum. If mismatch, abort with a warning — no binary placed.
4. Extract the tarball and atomically move the `cass` binary to `~/.local/bin/cass`. Ensure `~/.local/bin/` exists.
5. Make the binary executable.

**Update (cass already on PATH):**
1. Run `cass upgrade --yes` which natively handles version checking, checksum verification, and in-place replacement.

**`--if-stale` flag:**
- Check timestamp file at `~/.local/share/claudefiles-cass/last-update-check`.
- If the file exists and was modified less than 24 hours ago, exit 0 immediately (skip check).
- Create the directory `~/.local/share/claudefiles-cass/` if it doesn't exist.
- After any completed check (bootstrap, update, or "already current"), write the current timestamp to the file.

**Error handling:**
- If `curl` fails (GitHub unavailable), warn to stderr and exit 0 — never leave the caller blocked.
- If the checksum fails during bootstrap, clean up temp files and exit 1.
- If `cass upgrade` fails during update, warn to stderr and exit 0 — the existing binary is still functional.

The script should NOT use `set -euo pipefail` since failures in background-spawned hooks should not propagate. Use explicit error checking instead.

Refer to the Convention Examples in context.md for bin/ script conventions. The script must be executable (`chmod +x`).

## Focus
- The GitHub releases API returns JSON. Use `curl -fsSL` and parse with basic tools (`grep`/`sed`) or `jq` if available, with a fallback if `jq` is not installed.
- The `cass-linux-amd64.tar.gz` asset contains a single `cass` binary. Use `tar xzf` to extract.
- Atomic move: extract to a temp location, then `mv` to the final path. This prevents a partially-written binary from being found on PATH.
- `~/.local/bin/` should already be on PATH (standard convention across all 5 machines), but create it if missing.
- The `--if-stale` check uses file modification time, not file contents. `touch` updates the mtime.
- When called from the SessionStart hook, this runs in a detached background process — stdout/stderr go nowhere useful. Warnings to stderr are for direct invocation.

## Verify
- [ ] FR#2: `cass-update` downloads and installs cass when not on PATH (bootstrap path)
- [ ] FR#2: `cass-update` delegates to `cass upgrade --yes` when cass is already on PATH (update path)
- [ ] FR#2: `cass-update --if-stale` exits immediately when timestamp is <24h old
- [ ] FR#2: `cass-update` writes timestamp file after any completed check
- [ ] AC#3: Running `cass-update` when a newer release exists installs the new binary; running when current skips
