# Context: ccrecall to cass Migration

## Problem & Motivation
The conversation search backend (ccrecall) uses brute-force KNN vector search via sqlite-vec, which scales linearly and degrades as history grows. cass (coding_agent_session_search) is a mature Rust search engine with HNSW approximate nearest neighbor search, two-tier progressive retrieval, sub-60ms BM25 lexical search, secret redaction, and production-grade recovery tooling. This migration replaces ccrecall with cass as the search backend, self-contained within Claudefiles — one repo, one install, one source of truth.

## Visual Artifacts
None.

## Key Decisions
1. CLI-only integration via `cass search --robot` — no MCP server, no cass_memory_system dependency. Structured JSON output is sufficient.
2. Binary installed from GitHub releases, not brew or cargo. `cass-update` handles both bootstrap (custom download) and updates (`cass upgrade --yes` delegation).
3. SessionStart hooks trigger indexing and context injection. No systemd watch daemon, no Stop hook for per-turn sync.
4. Three skills replace ccrecall's plugin skills: `/cass-recall` (direct search), `/cass-context` (task-oriented context assembly), `/cass-resume` (session resume). Simplified — no lens taxonomy.
5. Two accepted trade-offs: (a) automatic unanswered-question warnings become manual via `/cass-resume`; (b) intra-session index freshness reduced (SessionStart-only indexing). `cass search --refresh` can mitigate (b) if needed.
6. Pricing functions (~100 lines) inlined into `orchestrate-cost` to remove the ccrecall PyPI dependency entirely.
7. ccrecall removal is gated on cass install success — never leave a machine with neither search tool.
8. Claudefiles bookkeeping (`~/.local/share/claudefiles-cass/`) is distinct from cass's own index data (`~/.local/share/coding-agent-search/`). Uninstall removes the former, not the latter.

## Constraints & Anti-Patterns
- Do NOT use brew or cargo for installation — GitHub releases only, `cass-linux-amd64.tar.gz` asset.
- Do NOT block session startup with indexing or update checks — they run in detached background processes. Context injection is the deliberate synchronous exception (3-second timeout).
- Do NOT implement procedural memory, playbook rules, or the learning layer — out of scope.
- Do NOT implement token analytics — `/ccr-tokens` is dropped.
- Do NOT add a systemd watch daemon or a Stop hook for sync.
- Skills call `cass search --robot` via Bash tool and parse JSON — no MCP server dependency.
- The clear-handoff mechanism writes a file, not a database record.
- Cross-repo Dotfiles updates must land before or alongside this migration (orchestrator hard-codes `/ccrecall:ccr-resume` in three places).

## Design Doc References
- `## Architecture` — binary lifecycle (bootstrap vs update), hook architecture (SessionStart + SessionEnd), skill architecture (three skills), pricing extraction, removal scope
- `## Functional Requirements` — FR#1-FR#12 covering install, update, hooks, skills, pricing, docs
- `## Edge Cases` — GitHub unavailability, missing binary, index failures, checksum mismatches, timeouts
- `## Replacement Targets` — table mapping every ccrecall component to its cass replacement or drop
- `## Test Strategy` — existing tests to adapt (with line ranges), new test coverage (per FR), tests to remove
- `## Documentation Updates` — specific changes per file (REFERENCE.md, ONBOARDING.md, capabilities-core.md, CLAUDE.md, 4 cross-repo Dotfiles files)
- `## Convention Examples` — SessionStart hook pattern, settings.json hook wiring, install.py binary detection, test pattern, PEP 723 structure

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

### Hook test pattern

**Source:** `tests/test_hooks.py`

```python
# Hooks are tested via subprocess invocation
# run_hook() wraps subprocess.run with env setup, JSON stdin, capture_output=True
# Tests assert on returncode (always 0) and stdout content (empty for silent, JSON for emitting)
# tempfile.TemporaryDirectory() used for isolation
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
