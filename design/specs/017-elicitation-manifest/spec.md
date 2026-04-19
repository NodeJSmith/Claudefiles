# Spec: MCP Elicitation Manifest Review

**Date:** 2026-04-18
**Status:** draft
**Predecessor:** 015-per-finding-resolution-manifest (the manifest system this replaces the editor for)

## Problem

The resolution manifest editor (`bin/edit-manifest`) requires tmux + nvim and presents findings as a markdown file where users edit `**Verb:**` lines. This has three issues:

1. **Dependency chain** — tmux + nvim must be available; the tertiary fallback (manual file editing) is poor UX and undermines the per-finding discipline the manifest was designed to enforce.
2. **Error-prone editing** — users must locate and edit verb strings in a long markdown document, risking typos and missed findings.
3. **No input validation** — the editor accepts any text; validation happens after save, triggering re-edit loops.

## Success Criteria

1. Users review findings one at a time via dropdown verb selection in the Claude Code terminal — no external editor needed.
2. Each finding presents only its valid verbs as dropdown options with human-readable labels.
3. Default verbs are pre-selected per the existing default verb selection rules.
4. The MCP server stays connected across multiple challenge runs in a session (no `/mcp` between uses).
5. The existing consent gate, commit gate, and execution phases are unchanged.
6. `bin/edit-manifest` remains as a fallback for environments where the MCP server is unavailable.

## Scope

### In Scope

- MCP server (`packages/manifest-review`) with `review_findings` tool
- Findings.md parser (format-version 2)
- Per-finding-type elicitation schemas with dropdown verbs
- Dual transport: stdio (testing/fallback) and streamable-http (primary)
- Systemd user service for persistent HTTP mode
- Integration with `findings-protocol.md` as the primary review path
- `.mcp.json` configuration for the HTTP transport

### Out of Scope

- Changes to critic phases, synthesis logic, or findings file format
- Changes to execution phases
- Migration of visual-qa or tool-gaps to this flow
- Removing `bin/edit-manifest` — it stays as fallback
- Crash recovery for mid-review service restarts (accepted regression; deferred)

## Non-Goals

- No bulk triage or finding grouping — one finding at a time is the point
- No web UI or external browser — all interaction happens in the terminal
- No changes to the verb vocabulary or default selection rules

### In Scope (added post-challenge)

- Partial review handling with "Continue from F{N+1}" recovery
- Typed error taxonomy (connectivity vs server errors in fallback detection)
- Consent gate text updated to mechanism-agnostic language
- Re-edit with pre-populated verb defaults (`current_resolutions` parameter)
- `caller-protocol.md` integration for mine.define doc-edit callers
- `resolutions.md` write procedure specification
- API stability: mcp version pinning, startup probe, upstream bug filing
- Observability: structured logging, SyslogIdentifier, journalctl docs

## Edge Cases

1. **0 findings** — return immediately with empty manifest (consent gate already handles this)
2. **User cancels mid-review** — return partial results with unreviewed IDs; skill presents "Continue / Start over / Abandon"
3. **User declines a finding** — maps to `skip` verb
4. **MCP tool call fails (connection)** — fall back to `bin/edit-manifest`
5. **MCP returns error status** — surface error inline, do NOT fall back
6. **Very long finding text** — truncate problem text with "..." if over ~300 chars
7. **Format-version 1 findings** — degrade gracefully; missing `recommendation:` defaults verb to `ask`
8. **findings_path doesn't exist** — return structured error, not exception
9. **Elicitation timeout (30 min)** — return partial status with collected resolutions
