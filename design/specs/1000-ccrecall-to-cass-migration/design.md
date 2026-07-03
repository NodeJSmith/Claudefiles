# Design: Migrate from ccrecall to cass

**Date:** 2026-07-02
**Status:** archived
**Scope-mode:** hold

## Problem

The conversation search backend (ccrecall) is a 10-day-old Python tool with brute-force KNN vector search, no secret redaction, and limited production hardening. Search quality degrades as conversation history grows — sqlite-vec does linear-scan KNN, which scales linearly with vector count. The tool works but returns worse results than a purpose-built search engine would, and the gap widens over time.

cass (coding_agent_session_search) is a mature Rust search engine with HNSW approximate nearest neighbor search, two-tier progressive retrieval (fast in-process embeddings ~1ms, quality refinement ~130ms), sub-60ms BM25 lexical search via Tantivy, secret redaction at ingestion, and `cass doctor` recovery tooling. It indexes 22+ agent providers from their native session file locations — including Claude Code JSONL files — without any sync hooks.

## Goals

- **Search parity or better:** cass search returns useful results for past sessions, at least as good as ccrecall.
- **Full lifecycle:** Install, index, search, and auto-update all work end-to-end across all 5 machines.
- **Transparent swap:** Everything that worked via ccrecall works via cass — search, context injection, session resume, clear handoff. Two accepted trade-offs: (1) automatic unanswered-question warnings on SessionStart are replaced by the manually-invoked `/cass-resume` skill; (2) intra-session index freshness is reduced — ccrecall synced after every turn via its Stop hook, while cass indexes only at SessionStart. Within a long session, new turns aren't searchable until the next session. The `cass search --refresh` flag (catches up the index before searching) can mitigate this if it proves to be a pain point.

## Non-Goals

- No cass_memory_system MCP server — CLI with `--robot` mode is sufficient for structured output.
- No systemd watch daemon — hooks trigger indexing.
- No token analytics — the `/ccr-tokens` dashboard is not used and is dropped.
- No procedural memory / learning layer — playbook rules, confidence decay, and trauma patterns are out of scope. Skill design allows plugging cm in later without rewriting.
- No brew — binary installed from GitHub releases.
- No lens taxonomy in the search skill — simplified search interface.

## User Scenarios

### Jessica: Solo developer across 5 machines

- **Goal:** Search past conversations and resume prior work seamlessly
- **Context:** Starts Claude Code sessions on any of 5 Linux machines (WSL2 or VPS), expects conversation history to be searchable and context to be injected automatically

#### Fresh install

1. **Runs `uv run install.py`**
   - Sees: install.py downloads cass binary from GitHub releases to `~/.local/bin/cass`
   - Then: cass binary is on PATH, ready to use
2. **Runs `cass index` manually**
   - Sees: cass discovers Claude Code JSONL files and indexes them (lexical + semantic)
   - Then: search is available for all indexed sessions

#### Ongoing session

1. **Starts a Claude Code session**
   - Sees: SessionStart hook runs `cass index` in background (incremental catch-up)
   - Sees: SessionStart hook injects recent project context via `cass search --robot`
   - Then: Claude has prior-session context without manual invocation
2. **Invokes `/cass-recall` with a query**
   - Sees: ranked search results from cass
   - Then: can drill into specific sessions
3. **Invokes `/cass-context` with a task description**
   - Sees: synthesized context brief relevant to the task
   - Then: can proceed with full historical context
4. **Invokes `/cass-resume` after `/clear` or session stop**
   - Sees: prior session's tail, last instruction, any unanswered question
   - Decides: how to proceed based on where the prior session left off
   - Then: work continues without lost context

#### Binary updates

1. **Starts a session (update check fires, >24h since last check)**
   - Sees: SessionStart hook checks GitHub releases API, finds newer version
   - Then: downloads and replaces binary silently in background

## Functional Requirements

- **FR#1** `install.py` installs the cass binary from the latest GitHub release to `~/.local/bin/cass` when cass is not on PATH. It removes ccrecall (PyPI package) and its plugin registration only after cass is confirmed installed — never leaving a machine with neither search tool
- **FR#2** A `bin/cass-update` script handles both bootstrap (not installed: downloads from GitHub releases with SHA-256 verification) and update (installed: delegates to `cass upgrade --yes`). Supports an `--if-stale` flag that checks a timestamp file (`~/.local/share/claudefiles-cass/last-update-check`) and exits early if the last check was less than 24 hours ago
- **FR#3** A SessionStart hook runs `cass index` in a detached background process for incremental indexing of new session files
- **FR#4** A SessionStart hook injects prior-session context by running `cass search --robot` scoped to the current project directory and emitting a summary
- **FR#5** A SessionEnd hook writes a handoff file linking `/clear` to the next session (same mechanism as ccrecall's `ccrecall-clear-handoff`)
- **FR#6** The `/cass-recall` skill accepts a query string, calls `cass search --robot`, and returns ranked session results with metadata
- **FR#7** The `/cass-context` skill accepts a task description, extracts content-bearing keywords, calls `cass search --robot` scoped to the current workspace, and synthesizes a context brief from the results
- **FR#8** The `/cass-resume` skill reads the clear-handoff file (if present from FR#5) to identify the prior session, retrieves its transcript tail via cass, reconciles against disk state (`git status`, `git log`, task files), and surfaces any unanswered question without auto-resolving it
- **FR#9** The `orchestrate-cost` script uses a standalone pricing module extracted from ccrecall — `_LEGACY_OPUS_RATES`, `MODEL_PRICING`, `DEFAULT_PRICING`, `get_pricing()`, and `turn_cost()` — with no runtime dependency on ccrecall
- **FR#10** The `mine-tool-gaps` skill calls `cass search --robot` instead of `ccrecall --json search` for session discovery
- **FR#11** The SessionStart hook triggers `cass-update --if-stale` in a background process, checking for binary updates when the last check was more than 24 hours ago
- **FR#12** `install.py --uninstall` removes the cass binary (`~/.local/bin/cass`) and the Claudefiles bookkeeping directory (`~/.local/share/claudefiles-cass/`, containing the update-check timestamp and clear-handoff files). cass's own index data (`~/.local/share/coding-agent-search/`) is intentionally left behind — it is owned by cass, not Claudefiles

## Edge Cases

- **GitHub API unavailable during install/update:** `install.py` and `cass-update` degrade gracefully — warn and continue without cass if installing fresh, skip update if already installed. Never leave a machine with a partially-downloaded binary.
- **cass binary not available for platform:** All 5 machines are Linux x86_64 (WSL2 or native). The `cass-linux-amd64.tar.gz` asset covers all of them. If the asset is missing from a release, warn and skip.
- **cass index fails or hangs:** The SessionStart hook runs indexing in a detached background process with no timeout dependency on the session — a hung index does not block session start. Search degrades to whatever was previously indexed.
- **cass not installed when hook fires:** Hooks guard on `command -v cass` before invoking. If missing, exit silently — a missing binary is a warning, not a session-blocking error.
- **First session before initial `cass index`:** Context injection and search return empty results. The SessionStart hook's background `cass index` begins populating the index for subsequent sessions.
- **SHA-256 checksum mismatch during bootstrap:** `cass-update` aborts the install and warns — no binary is placed. On the update path, checksum verification is handled internally by `cass upgrade`.
- **Concurrent `cass index` runs:** cass uses SQLite with WAL mode and atomic index publishing. Multiple concurrent index runs are safe — the second one will be a no-op or merge cleanly.
- **Context injection times out or fails:** The synchronous `cass search --robot` call in the SessionStart hook has a 3-second timeout. On timeout, error, or empty results, the hook emits nothing and exits 0 — context injection is best-effort, never session-blocking.

## Acceptance Criteria

- **AC#1** Running `uv run install.py` on a machine without cass results in `cass --version` succeeding from PATH (FR#1)
- **AC#2** Running `uv run install.py` on a machine with ccrecall removes the ccrecall binary and plugin registration (FR#1)
- **AC#3** Running `cass-update` when a newer release exists downloads and installs the new binary; running it when current skips the download (FR#2)
- **AC#4** Starting a Claude Code session triggers a background `cass index` — verified by checking for the spawned process (FR#3)
- **AC#5** Starting a Claude Code session in a project with indexed history produces context output from the hook (FR#4)
- **AC#6** Running `/clear` writes a handoff file that the next session's `/cass-resume` can read (FR#5, FR#8)
- **AC#7** `/cass-recall "pytest fixtures"` returns ranked results from past sessions mentioning pytest fixtures (FR#6)
- **AC#8** `/cass-context "implementing rate limiting"` returns a synthesized context brief with relevant history (FR#7)
- **AC#9** `/cass-resume` after `/clear` surfaces the prior session's last instruction and any unanswered question (FR#8)
- **AC#10** `orchestrate-cost` runs without ccrecall installed — the pricing module is standalone (FR#9)
- **AC#11** `/mine-tool-gaps` session discovery uses cass, not ccrecall (FR#10)
- **AC#12** Starting a Claude Code session when the last update check was >24h ago triggers a background `cass-update` — verified by checking the timestamp file is refreshed (FR#11)
- **AC#13** Running `uv run install.py --uninstall` removes `~/.local/bin/cass` and `~/.local/share/claudefiles-cass/` (FR#12)

## Key Constraints

- The cass binary must be installed from GitHub releases, not brew or cargo. All 5 machines are Linux x86_64; the `cass-linux-amd64.tar.gz` asset is the single target.
- SessionStart hook indexing and update checks must not block session startup — they run in detached background processes. Context injection is a deliberate synchronous exception with a 3-second timeout; on timeout or error, it emits nothing and exits 0.
- The clear-handoff mechanism must work without ccrecall's database — it writes a file to a known location, not a database record.
- Skills call `cass search --robot` via Bash and parse JSON output. No MCP server dependency.

## Dependencies and Assumptions

- cass continues publishing `cass-linux-amd64.tar.gz` and `cass-linux-amd64.tar.gz.sha256` assets on GitHub releases with a `latest` tag.
- `cass index` auto-discovers Claude Code session files from `~/.claude/projects/*/` without explicit path arguments.
- `cass search --robot` returns structured JSON with session metadata and snippets.
- `cass sessions --current --json` returns session metadata for the current/recent sessions, supporting transcript-tail retrieval for the resume skill.
- The GitHub releases API (`api.github.com/repos/Dicklesworthstone/coding_agent_session_search/releases/latest`) is accessible from all 5 machines.

## Architecture

### Binary lifecycle

`bin/cass-update` is a bash script with two modes:

**Bootstrap (cass not on PATH):** Downloads `cass-linux-amd64.tar.gz` + `.sha256` from the GitHub releases `latest` endpoint, verifies checksum, extracts, and atomically moves to `~/.local/bin/cass`. This is the only path that requires custom download logic.

**Update (cass already on PATH):** Delegates to `cass upgrade --yes`, which natively handles GitHub release version checks, checksum-verified downloads, and in-place binary replacement. The `--if-stale` flag checks a timestamp file (`~/.local/share/claudefiles-cass/last-update-check`) and exits early if <24h old — this staleness gate wraps around both modes. After any completed check (bootstrap or update, success or "already current"), the script writes the current timestamp to the file.

`install.py` calls `cass-update` during installation (replacing the ccrecall install path). The SessionStart hook calls it with `--if-stale`.

### Hook architecture

Two hooks, both in `scripts/hooks/`:

**`cass-session-start.sh`** (SessionStart):
- Guards on `command -v cass`
- Runs `cass-update --if-stale` in background (checks timestamp, skips if <24h)
- Runs `cass index` in a detached background process (incremental catch-up)
- Runs `cass search --robot --workspace "$(pwd)" --days 7 --limit 3 --fields minimal` with a 3-second timeout and emits a context summary to stdout (synchronous — the context injection). On timeout or empty results, exits 0 silently

**`cass-clear-handoff.sh`** (SessionEnd):
- Writes a handoff marker file to a known location (e.g., `~/.local/share/claudefiles-cass/clear-handoff/<project-key>.json`) containing the session ID, timestamp, and project path
- `/cass-resume` reads this file to locate the prior session

### Skill architecture

Three skills in `skills/`:

**`cass-recall`** — Direct search. Takes a query, calls `cass search --robot`, returns ranked results. The skill file defines query construction guidance (content-bearing keywords, workspace scoping, time filtering) and synthesis format. Equivalent to ccrecall's `/ccr-recall` without the lens taxonomy.

**`cass-context`** — Task-oriented context assembly. Takes a task description, instructs Claude to extract keywords, calls `cass search --robot --workspace <cwd>`, and synthesizes a structured context brief. Designed so cm's `cm context` CLI could be swapped in later without rewriting the skill's output contract.

**`cass-resume`** — Session resume. Reads the clear-handoff file (if present), uses `cass sessions --current --json` or `cass search` to locate the prior session, reads its transcript tail, reconciles against `git status`, `git log`, and task files, and surfaces any unanswered question. Preserves ccrecall's `/ccr-resume` core invariant: surface open decisions, never auto-resolve them.

### Pricing extraction

The pricing code moves from ccrecall's `token_parser.py`: `_LEGACY_OPUS_RATES`, `MODEL_PRICING`, `DEFAULT_PRICING`, `get_pricing()`, and `turn_cost()` (~100 lines, contiguous block at lines 63-162). Two options:

- **Inline in `orchestrate-cost`**: Add the pricing code directly to the PEP 723 script. Removes the external dependency entirely. The script is already self-contained by design.
- **Shared module in `packages/`**: Create a tiny `claude-pricing` package if other scripts also need pricing data.

`orchestrate-cost` is the only consumer. Inline is simpler.

### Removal scope

- `install.py`: Remove `CCRECALL_PACKAGE`, `CCRECALL_MARKETPLACE_REPO`, `CCRECALL_PLUGIN_REF` constants. Remove `LEGACY_MEMORY_PACKAGE` — all machines have already been migrated from claude-memory to ccrecall; the legacy cleanup path is no longer needed. Remove `ensure_ccrecall()`, `ensure_ccrecall_plugin()`, `ccrecall_plugin_installed()`, `remove_ccrecall_plugin()`. Remove ccrecall calls from `do_install()` and `do_uninstall()`. Add `ensure_cass()` that calls `bin/cass-update` and gates ccrecall/plugin removal on cass install success (preserving the "never leave a machine with neither" safety invariant from `ensure_ccrecall()`).
- `install.py` (`do_uninstall()`): Replace ccrecall package uninstall with cass binary cleanup — delete `~/.local/bin/cass` and `~/.local/share/claudefiles-cass/` (timestamp file, any other state).
- `settings.json`: Remove `extraKnownMarketplaces` and `enabledPlugins` blocks. Add SessionStart and SessionEnd hook entries.
- `tests/test_install.py`: Remove `TestCcrecallPlugin` (8 tests), ccrecall-specific cases from `TestPackageInstall` (6 of 9 tests — 3 non-ccrecall tests remain), ccrecall from `TestDoUninstall`, and the `_stub_ccrecall_side_effects` fixture. Add equivalent tests for cass binary installation.

## Implementation Preferences

No specific implementation preferences — follow codebase conventions. In particular:
- Hooks use the existing `bash -c` guard pattern with `$CLAUDE_CONFIG_DIR` resolution
- `install.py` uses the existing `shutil.which()` detection and error-counting pattern
- bin/ scripts follow the existing structure (executable, symlinked to `~/.local/bin/`)
- Skills follow SKILL.md conventions in the repo

## Replacement Targets

| Target | Replaced by | Action |
|---|---|---|
| `ccrecall` PyPI package (uv tool install) | cass binary from GitHub releases | Remove `ensure_ccrecall()` from install.py |
| ccrecall Claude Code plugin (`ccrecall@claude-code-recall`) | Skills + hooks directly in Claudefiles | Remove `ensure_ccrecall_plugin()`, remove settings.json plugin entries |
| `ccrecall.token_parser.get_pricing` / `turn_cost` | Inlined in `orchestrate-cost` | Copy ~100 lines, remove `ccrecall` from PEP 723 dependencies |
| `ccrecall --json search` in mine-tool-gaps | `cass search --robot` | Update SKILL.md CLI call |
| `/ccrecall:ccr-recall` skill (plugin) | `/cass-recall` skill (Claudefiles) | New skill file |
| `/ccrecall:ccr-resume` skill (plugin) | `/cass-resume` skill (Claudefiles) | New skill file |
| `/ccrecall:ccr-tokens` skill (plugin) | Dropped | No replacement |
| `/cm-recall-conversations` references in capabilities.md | `/cass-recall` | Update trigger phrases and proactive recall section |
| `ccrecall-context` hook (plugin) | `cass-session-start.sh` hook | New hook file |
| `ccrecall-sync` hook (plugin) | Dropped — cass indexes from JSONL directly | No replacement |
| `ccrecall-setup` hook (plugin) | `cass-session-start.sh` hook (background `cass index`) | New hook file |
| `ccrecall-onboarding` hook (plugin) | Dropped | One-time first-run guidance handled by `install.py` output instead |
| `ccrecall-clear-handoff` hook (plugin) | `cass-clear-handoff.sh` hook | New hook file |

## Convention Examples

### SessionStart hook pattern

**Source:** `scripts/hooks/tmux-remind.sh`

```bash
#!/usr/bin/env bash
# SessionStart hook: remind Claude to rename the tmux session.
# No set -euo pipefail — this is a cosmetic hook; failure should not block session start.

if [ -n "${TMUX:-}" ]; then
  echo "You are inside a tmux session. Rename it now with: claude-tmux rename \"<project>-<context>\"" || true
fi
```

### settings.json hook wiring

**Source:** `settings.json`

```json
"SessionStart": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/tmux-remind.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
        "timeout": 5000
      }
    ]
  }
]
```

### install.py binary detection pattern

**Source:** `install.py:ensure_ccrecall()`

```python
ccrecall_present = shutil.which("ccrecall") is not None
if not ccrecall_present:
    console.print(f"  Installing package: {CCRECALL_PACKAGE} (PyPI)...")
    ok, detail = install_pypi_tool(CCRECALL_PACKAGE)
    if ok:
        ccrecall_present = True
    else:
        console.print(f"  [red]Failed to install {CCRECALL_PACKAGE}[/red]")
        if detail:
            console.print(f"  [dim]{detail}[/dim]")
        errors += 1
```

### install.py test pattern

**Source:** `tests/test_install.py:TestCcrecallPlugin`

```python
def test_resolves_claude_via_which_not_bare_name(self) -> None:
    resolved = MISE_CLAUDE_BIN
    def fake_run(claude_bin, args):
        if args[0] == "list":
            return (True, "[]")
        return (True, "")
    mock_run = MagicMock(side_effect=fake_run)
    with (
        patch("install.shutil.which", return_value=resolved),
        patch("install.run_claude_plugin", mock_run),
    ):
        errors = install.ensure_ccrecall_plugin(install.Console())
    assert errors == 0
```

### PEP 723 bin/ script structure

**Source:** `bin/orchestrate-cost`

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["ccrecall>=0.12.0", "whenever>=0.10"]
# ///
```

DO: Use `#!/usr/bin/env -S uv run --script` with PEP 723 inline metadata for scripts with external dependencies.
DON'T: Add dependencies to the script that could be inlined — `orchestrate-cost` will inline the pricing module and drop its `ccrecall` dependency.

## Alternatives Considered

### Keep ccrecall and improve its search layer

Swap sqlite-vec for a proper ANN index (e.g., `hnswlib` Python bindings), add secret redaction at ingest. This closes the biggest search quality gaps without taking on cass's single-author Rust ecosystem.

**Rejected because:** The search quality gap is the symptom, not the disease. cass has years of hardening — atomic index publishing, quarantine-and-inspect for corrupt artifacts, doctor/recovery tooling, two-tier progressive search, a background daemon for model residency. Reimplementing these in ccrecall would be a months-long effort to reach parity with an existing tool.

### Use cass_memory_system MCP server

Install cass + cm, run `cm serve` as a Claude Code MCP server. Gets the full procedural memory layer (rules with confidence decay, feedback, reflection) alongside raw search.

**Rejected because:** Requires Bun runtime as an additional dependency, adds a second single-author project to manage, and the learning layer is not valued for the current use case. The CLI-only path delivers the search quality improvement with one binary and no additional runtime. The skill design allows swapping in cm later without rewriting.

### Adopt cass and rebuild integration in Dotfiles

Split the installation across Dotfiles (binary, systemd service) and Claudefiles (hooks, skills).

**Rejected because:** Creates a cross-repo dependency where running `install.py` alone doesn't guarantee a working setup. Self-containing everything in Claudefiles means one repo, one install, one source of truth.

## Test Strategy

### Existing Tests to Adapt

- `tests/test_install.py:TestCcrecallPlugin` (8 tests, lines 1106-1243) — remove entirely. Replace with `TestCassBinary` testing the new `ensure_cass()` function.
- `tests/test_install.py:TestPackageInstall` (9 tests, lines 1244-1375) — remove 6 cases — 3 ccrecall-specific (`test_skips_ccrecall_when_present`, `test_installs_ccrecall_when_absent`, `test_install_failure_increments_errors`) and 3 legacy-claude-memory-specific (`test_uninstalls_legacy_claude_memory_when_present`, `test_no_uninstall_when_claude_memory_absent`, `test_keeps_legacy_when_ccrecall_install_fails`). The claude-memory legacy cleanup tests are intentionally not replaced — all machines have already migrated, and the `LEGACY_MEMORY_PACKAGE` constant is being removed. The 3 non-ccrecall tests remain (`test_base_packages_installed`, `test_base_package_failure_increments_errors`, `test_base_packages_skip_only_already_present`).
- `tests/test_install.py:TestDoUninstall` (lines 1376-1413) — update to verify cass-related cleanup instead of ccrecall.
- `tests/test_install.py:_stub_ccrecall_side_effects` fixture (lines 48-74) — remove. Replace with a cass-specific fixture that stubs `shutil.which("cass")` and the download subprocess.
- V1-to-V2 migration test data (lines 1757-1803) — remove `"memory": True/False` from old format fixtures and the paired `"claude-memory": True/False` from the `packages` block (both dropped during migration as a matched pair).

### New Test Coverage

- **`TestCassBinary`** — `ensure_cass()` skips when `cass` is on PATH (FR#1), installs when absent (FR#1), handles download failure gracefully (FR#1), removes ccrecall only after cass is confirmed installed (FR#1), keeps ccrecall if cass install fails (FR#1, safety invariant)
- **`TestCassUpdate`** — bootstrap path downloads and verifies checksum when cass is not on PATH (FR#2), bootstrap aborts on checksum mismatch leaving no binary (edge case), update path delegates to `cass upgrade --yes` when cass is on PATH (FR#2), `--if-stale` exits early when timestamp is <24h old (FR#2), timestamp file is written after any completed check (FR#2, AC#12)
- **Hook tests** — SessionStart hook exits silently when cass is not installed (edge case), SessionStart hook spawns background `cass index` process (FR#3), SessionStart hook triggers `cass-update --if-stale` in background (FR#11), context injection produces output for indexed projects (FR#4), context injection exits 0 on timeout (edge case), SessionEnd hook writes handoff file with session ID and project path (FR#5)
- **Pricing parity** — extracted pricing module produces identical costs to ccrecall's `token_parser` for all model tiers on identical token inputs (FR#9, behavioral invariant)
- **`TestDoUninstall`** — cass binary and state directory removed on uninstall (FR#12)

### Tests to Remove

- All `TestCcrecallPlugin` tests (8 tests) — functionality being removed
- ccrecall-specific `TestPackageInstall` cases — ccrecall package install no longer exists
- `_stub_ccrecall_side_effects` fixture — no longer needed

## Documentation Updates

- **`REFERENCE.md`** — Update the Plugins table to remove ccrecall (or remove the table entirely if no plugins remain). Add cass-recall, cass-context, cass-resume to the Skills table. Update the Hooks table to list cass-session-start.sh and cass-clear-handoff.sh. Remove the prose paragraph below the Hooks table about ccrecall plugin hooks not being wired in settings.json (they are now wired directly). Remove the note about conversation memory skills being plugin-provided. Update the `orchestrate-cost` tool description (currently "Reuses `ccrecall` pricing via PEP 723") to reflect the inlined pricing module. Update the package installation prose (currently "`ccrecall` is installed unconditionally from PyPI") to describe cass binary installation instead.
- **`ONBOARDING.md`** — Update the "I want conversation memory" path to reference `/cass-recall`, `/cass-context`, `/cass-resume` instead of plugin skills. Update the Plugins glossary entry (currently "Currently: `ccrecall`...") — either remove it if no plugins remain or update to reflect the new state. Update the Bundles glossary parenthetical (currently "it's now the `ccrecall` plugin") to reflect that conversation memory is now built-in via cass skills/hooks. Update the "Path C: Everything" daily workflow pattern (currently claims SessionStart hook auto-warns about unanswered questions) to reflect that this is now manual via `/cass-resume`. Note that initial `cass index` is a manual first-run step.
- **`rules/common/capabilities-core.md`** — Add `/cass-recall`, `/cass-context`, and `/cass-resume` trigger phrases to the Intent Routing table. Add `cass-update` to CLI Tools if warranted. (Note: this file contains no ccrecall references to remove — those live in the Dotfiles capabilities file below.)
- **`~/Dotfiles/config/claude/rules/personal/capabilities.md`** *(cross-repo)* — Update the Memory Recall table to reference `/cass-recall` instead of `/cm-recall-conversations` (note: this reference is already orphaned — the `cm-*` name predates the ccrecall plugin rename and was never updated). Update the Proactive Memory Recall section to reference `/cass-recall`.
- **`~/Dotfiles/CLAUDE.md`** *(cross-repo)* — Update the orchestrator reset recipe reference from `/ccrecall:ccr-resume` to `/cass-resume`.
- **`~/Dotfiles/config/claude/orchestrator/CLAUDE.md`** *(cross-repo)* — Update `rc-send` command from `/ccrecall:ccr-resume` to `/cass-resume`.
- **`~/Dotfiles` (`home/bin/orchestrator/orchestrator-tick`)** *(cross-repo)* — Update heartbeat warning message from `/ccrecall:ccr-resume` to `/cass-resume`.
- **`CLAUDE.md`** — Add `cass-*` to the Naming Conventions section alongside `mine-*`, `i-*`, and `cli-*`. Update the "Making Changes" section's capabilities-file mapping to route `cass-*` trigger phrases to `capabilities-core.md`.

## Impact

### Changed Files

- **create** `bin/cass-update` — bash script for cass binary install/update from GitHub releases
- **create** `scripts/hooks/cass-session-start.sh` — SessionStart hook: background index + context injection + update check
- **create** `scripts/hooks/cass-clear-handoff.sh` — SessionEnd hook: clear-handoff file writer
- **create** `skills/cass-recall/SKILL.md` — direct search skill
- **create** `skills/cass-context/SKILL.md` — task-oriented context assembly skill
- **create** `skills/cass-resume/SKILL.md` — session resume skill
- **modify** `install.py` — remove ccrecall install/plugin code, add `ensure_cass()` calling `bin/cass-update`
- **modify** `settings.json` — remove `extraKnownMarketplaces` and `enabledPlugins`, add SessionStart and SessionEnd hook entries
- **modify** `bin/orchestrate-cost` — inline pricing module, remove ccrecall dependency from PEP 723 metadata
- **modify** `skills/mine-tool-gaps/SKILL.md` — replace `ccrecall --json search` with `cass search --robot`
- **modify** `tests/test_install.py` — remove ccrecall tests, add cass binary tests
- **modify** `tests/test_hooks.py` — add SessionStart and SessionEnd hook tests (cass guard, background index spawn, `cass-update --if-stale` trigger, context injection output, context injection timeout, handoff file write) and `TestCassUpdate` tests for `bin/cass-update` (bootstrap download/checksum, `cass upgrade` delegation, `--if-stale` early-exit, timestamp write)
- **modify** `REFERENCE.md` — update skills, hooks, and plugins tables
- **modify** `ONBOARDING.md` — update conversation memory paths
- **modify** `rules/common/capabilities-core.md` — update trigger phrases
- **modify** `CLAUDE.md` — add `cass-*` to Naming Conventions
- **modify** `~/Dotfiles/config/claude/rules/personal/capabilities.md` *(cross-repo)* — update Memory Recall and Proactive Memory Recall references from `/cm-recall-conversations` to `/cass-recall`
- **modify** `~/Dotfiles/CLAUDE.md` *(cross-repo)* — update orchestrator reset recipe from `/ccrecall:ccr-resume` to `/cass-resume`
- **modify** `~/Dotfiles/config/claude/orchestrator/CLAUDE.md` *(cross-repo)* — update `rc-send` command from `/ccrecall:ccr-resume` to `/cass-resume`
- **modify** `~/Dotfiles` (`home/bin/orchestrator/orchestrator-tick`) *(cross-repo)* — update heartbeat warning from `/ccrecall:ccr-resume` to `/cass-resume`

### Behavioral Invariants

- `install.py --uninstall` must still clean up conversation-search-related artifacts (cass binary instead of ccrecall package)
- `orchestrate-cost` must produce identical pricing calculations — the extracted pricing module is a copy, not a rewrite
- The SessionStart context injection must produce output in the same conversation position as ccrecall's `ccrecall-context` hook (early in session, before user's first message is processed)
- `/cass-resume` must preserve the core invariant from `/ccr-resume`: surface open decisions, never auto-resolve them

### Blast Radius

- All 5 machines need to run `install.py` after this change to transition from ccrecall to cass
- `install.py` explicitly uninstalls the ccrecall plugin during migration (gated on cass install success per FR#1).
- The Dotfiles orchestrator (`claude-orchestrator` on jessica-desktop) hard-codes `/ccrecall:ccr-resume` in three places — once the ccrecall plugin is removed, the automated reset recipe silently fails. The cross-repo Dotfiles updates must land before or alongside this migration.
- `~/source/claude-code-recall/` can be archived after migration is confirmed working on all machines
- The ccrecall database at `~/.ccrecall/` becomes unused — can be deleted after confirming cass indexes the same sessions

## Open Questions

None — all design decisions resolved during discovery.
