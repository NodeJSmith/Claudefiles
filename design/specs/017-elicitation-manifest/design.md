# Design: MCP Elicitation Manifest Review

**Date:** 2026-04-18
**Status:** draft
**Spec:** design/specs/017-elicitation-manifest/spec.md
**Research:** Spike results (2026-04-17), architecture sketch at /tmp/claude-manifest-review-design-SpkzpH/architecture.md
**Challenge:** Findings at /tmp/claude-mine-challenge-Sgpgpi/findings.md; 19 findings resolved.

## Prerequisite: Scale Validation (F1)

Before implementation begins, run the spike against a real 10+ finding challenge output. If sequential elicitation handles 10+ findings reliably, document the validated boundary and proceed. If it fails, this design needs a different approach.

## Architecture

### Core Insight

The resolution manifest (design 015) moved per-finding decisions out of the LLM's interactive loop and into a user-edited file. This design keeps that structural guarantee while replacing the file-editing mechanism with MCP elicitation — the user still makes every decision directly, but via dropdown prompts instead of editing markdown.

The LLM calls one MCP tool (`review_findings`). The MCP server internally loops through findings, issuing one elicitation request per finding. The LLM never sees the per-finding loop — it gets back a complete manifest as structured data.

### Component Overview

```
┌─────────────────────┐
│ mine.challenge       │
│ findings-protocol.md │
│                     │
│ 1. Consent Gate     │──→ AskUserQuestion (unchanged)
│ 2. Review Findings  │──→ MCP tool call: review_findings(path)
│ 3. Commit Gate      │──→ AskUserQuestion (unchanged)
│ 4. Execution        │    (unchanged)
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ manifest-review      │
│ MCP server          │
│                     │
│ parse findings.md   │
│ for each finding:   │
│   build schema      │
│   elicit verb       │
│ return manifest JSON│
└─────────────────────┘
```

### Tool: `review_findings`

```
Input:
  findings_path: str  — absolute path to findings.md (format-version 2)
  current_resolutions: dict | None = None  — pre-populate dropdowns on re-edit (F9)

Output (JSON):
  {
    "status": "complete" | "partial" | "cancelled" | "error",
    "resolutions": {
      "F1": {"verb": "fix"},
      "F2": {"verb": "A"},
      ...
    },
    "reviewed_count": 8,
    "total_count": 8,
    "error": null | {"code": "parse_error" | "findings_not_found", "message": "..."}
  }
```

**Input validation (F19):** Before parsing, validate that `findings_path` exists and is readable. If not, return `{"status": "error", "error": {"code": "findings_not_found", "message": "No findings file at <path>"}}`.

**Status values:**
- `complete` — all findings reviewed
- `partial` — user cancelled mid-review; `resolutions` contains reviewed findings plus `unreviewed_ids` listing remaining finding IDs
- `cancelled` — user cancelled on the first finding; `resolutions` is empty
- `error` — server-side error; `error` field contains structured error with code and message

**Partial status handling (F2):** When the server returns `partial`, the calling skill presents:

```
AskUserQuestion:
  question: "You reviewed N of M findings. What would you like to do?"
  header: "Partial review"
  options:
    - label: "Continue from F{N+1} (Recommended)"
      description: "Resume reviewing from where you left off"
    - label: "Start over"
      description: "Re-review all findings from the beginning"
    - label: "Abandon"
      description: "Stop — findings will not be resolved this session"
```

"Continue" calls `review_findings` again with the partial resolutions as `current_resolutions` and an additional `start_from` parameter. "Abandon" follows existing Consent Gate "No" semantics.

### Elicitation Flow Per Finding

Each finding produces one `session.elicit_form()` call (bypassing FastMCP's validator which incorrectly blocks enum types — see Stability section below). The schema is built dynamically per finding type.

**Message format** (plain text — markdown doesn't render):

```
F3: Conflicting performance targets (TENSION)  [3/8]

NFR-1 says "sub-100ms p99" but AC-7 implies complex aggregation.

The disagreement:
  Side A: Relax the latency target to p95
  Side B: Pre-compute aggregations to meet both

Deciding factor: Whether real-time aggregation is a hard requirement
```

The `[3/8]` counter in the title line provides position context. Full problem text is included — the user needs context to make an informed verb choice. Truncate at ~300 chars with "..." only if text is extremely long.

**Per-elicitation timeout (F8):** Each `elicit_form()` call is wrapped in `anyio.fail_after(1800)` (30 minutes). On timeout, return partial status with resolutions collected so far.

### Verb Schemas Per Finding Type

**Auto-apply findings:**

```json
{
  "type": "object",
  "properties": {
    "verb": {
      "type": "string",
      "enum": ["fix", "file", "defer", "skip"],
      "enumNames": [
        "Fix — apply the better approach",
        "File — create a GitHub issue",
        "Defer — revisit later",
        "Skip — not a real issue"
      ],
      "default": "fix"
    }
  },
  "required": ["verb"]
}
```

**User-directed findings (with options):**

Verb enum is built dynamically from the finding's options list:

```json
{
  "enum": ["A", "B", "C", "ask", "file", "defer", "skip"],
  "enumNames": [
    "A — Use dependency injection (Recommended)",
    "B — Keep current approach with retry wrapper",
    "C — Extract to a separate service",
    "Ask — decide at execution time",
    "File — create a GitHub issue",
    "Defer — revisit later",
    "Skip — not a real issue"
  ],
  "default": "A"
}
```

The default is set from the finding's `recommendation:` field. Option labels include a truncated summary of each option's text. `(Recommended)` is appended to the recommended option's label.

When `current_resolutions` is provided (re-edit), the `default` is set to the previously chosen verb instead (F9).

**TENSION findings:**

```json
{
  "enum": ["defer", "fix", "file", "skip"],
  "enumNames": [
    "Defer — revisit later",
    "Fix — apply the recommendation",
    "File — create a GitHub issue",
    "Skip — not a real issue"
  ],
  "default": "defer"
}
```

**Verb co-change annotation (F6):** The verb enums in `schemas.py` duplicate the canonical table in `findings-protocol.md`. Add a comment at the top of `schemas.py`: `# MUST match findings-protocol.md Verb Vocabulary table — update both on any verb change`.

### Decline and Cancel Mapping

- **Accept** — user filled in verb, submitted the form
- **Decline** — maps to `skip` verb (fast dismiss path)
- **Cancel (Esc)** — return partial status with resolutions collected so far; trigger partial-status handling in calling skill (F2)

### Progress Reporting (F17)

`ctx.report_progress(progress=i+1, total=N)` immediately before each elicitation call. Uses 1-indexed count so the status line shows "Reviewing finding 3/8" when finding 3 is displayed.

## Findings Parser

Module: `manifest_review/parser.py`

Parses findings.md format-version 2. Extracts per finding:

| Field | Source | Used For |
|---|---|---|
| `id` | `## Finding N:` heading → `F{N}` | Finding identifier |
| `title` | Heading text after number | Elicitation message title |
| `severity` | `severity:` contract tag | Verb schema selection, message display |
| `type` | `type:` contract tag | Message display |
| `resolution` | `resolution:` contract tag | Verb schema selection (Auto-apply vs User-directed) |
| `recommendation` | `recommendation:` contract tag | Default verb selection |
| `problem` | `summary:` contract tag | Elicitation message body |
| `better_approach` | `better-approach:` contract tag (Auto-apply only) | Message display |
| `options` | `options:` contract tag (User-directed only) | Dynamic verb enum + labels |
| `side_a`, `side_b` | `side-a:`, `side-b:` contract tags (TENSION only) | Message display |
| `deciding_factor` | `deciding-factor:` contract tag (TENSION only) | Message display |
| `raised_by` | `raised-by:` presentation field | Message display |

Contract tags are inline markers in the format `- field-name: value` appearing after the finding heading. They are the structured data layer.

### Parser Strategy

Regex-based section splitting, not a full markdown AST:

1. Split on `## Finding \d+:` headings
2. Extract contract tags via `r"^- ([\w-]+):\s*(.+)"` patterns from list items after the heading
3. Extract options from the `options:` field value (format: `Option A: [text] / Option B: [text]`)

This is intentionally simple — findings.md is generated by the challenge skill with a rigid template, not hand-authored. A full markdown parser would be overengineered.

## Transport and Lifecycle

### Dual Transport

The server supports both transports via `MCP_TRANSPORT` env var:

```python
VALID_TRANSPORTS = {"stdio", "streamable-http"}

def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport not in VALID_TRANSPORTS:
        raise ValueError(
            f"Invalid MCP_TRANSPORT={transport!r}. "
            f"Valid options: {', '.join(sorted(VALID_TRANSPORTS))}"
        )
    logger.info("starting with transport=%s pid=%d", transport, os.getpid())
    mcp.run(transport=transport)
```

- **stdio** (default) — for testing and environments without systemd
- **streamable-http** — primary mode, persistent HTTP service

### Systemd User Service

`~/.config/systemd/user/manifest-review.service`:

```ini
[Unit]
Description=Manifest Review MCP Server
After=default.target

[Service]
ExecStart=%h/.local/bin/manifest-review
Environment=MCP_TRANSPORT=streamable-http
Environment=MCP_PORT=19847
Restart=on-failure
RestartSec=5
SyslogIdentifier=manifest-review

[Install]
WantedBy=default.target
```

Port 19847 chosen from dynamic/private range (49152–65535) to avoid conflicts with common dev servers (F10). Configurable via `MCP_PORT` env var.

### MCP Configuration

`.mcp.json` (or user-level `~/.claude.json`):

```json
{
  "mcpServers": {
    "manifest-review": {
      "type": "http",
      "url": "http://localhost:19847/mcp"
    }
  }
}
```

### Fallback Chain (F3)

1. MCP `review_findings` tool available → use elicitation flow
2. MCP returns `error` status → surface error message inline, do NOT fall back
3. MCP tool call fails (connection refused, timeout) → fall back to `bin/edit-manifest`
4. tmux unavailable → tertiary fallback (manual file edit)

The skill distinguishes between **connectivity failures** (tool call itself fails — server not running) and **server errors** (tool returns `error` status — parse failure, bad input). Only connectivity failures trigger fallback. Server errors are surfaced to the user so they can diagnose and fix.

### Signal Handling (F15)

Do not install custom signal handlers. FastMCP and uvicorn handle SIGTERM/SIGINT natively for graceful shutdown. The spike's no-op handlers that logged and returned without stopping the event loop are removed.

## Observability (F16)

### Structured Logging

Log at INFO level with structured events:

```
elicitation_sent finding={id} n={i} total={N}
elicitation_result finding={id} action={action} elapsed_ms={elapsed}
review_complete status={status} reviewed={reviewed_count} total={total_count}
```

### Log Retrieval

With `SyslogIdentifier=manifest-review` in the systemd unit, logs are retrievable via:

```bash
journalctl --user -u manifest-review -f        # live tail
journalctl --user -u manifest-review --since today  # today's logs
```

The installer (`bin/install-manifest-review`) prints this command on successful setup.

## API Stability (F4)

The `session.elicit_form()` bypass is necessary because FastMCP's validator incorrectly rejects enum types that the MCP spec supports. To mitigate instability:

1. **Pin dependency**: `mcp>=1.9.0,<2.0.0` in `pyproject.toml`
2. **Startup probe**: At import time, verify `ctx.request_context.session` has an `elicit_form` method. If missing, raise a clear error: `"mcp SDK version incompatible — elicit_form() not found. Pin to mcp>=1.9.0,<2.0.0"`
3. **Upstream bug**: File a bug on the mcp Python SDK for the enum validation issue. If fixed upstream, switch back to `ctx.elicit()` with Pydantic Literal types and remove the bypass.

## Integration with findings-protocol.md

### Changes to findings-protocol.md

The Editor Session section gets a new primary path:

**Before:** Consent Gate → generate manifest → `bin/edit-manifest` → Detection Logic → Validation → Commit Gate

**After:** Consent Gate → call `review_findings` MCP tool → write `resolutions.md` from response → Commit Gate

The MCP path skips Detection Logic (hash comparison) and Validation (verb check) because:
- Dropdowns enforce valid verbs — no typos possible
- Required fields prevent missing verbs
- The server returns structured data — no parsing needed

The Commit Gate remains unchanged — it presents the manifest summary and asks for execution confirmation.

### Consent Gate Update (F5)

Change the Consent Gate label from "Yes — open editor (Recommended)" to mechanism-agnostic language:

```
- label: "Yes — review findings (Recommended)"
  description: "Review each finding and choose a resolution"
```

Remove the post-gate emission "your editor will open momentarily" — replace with "Preparing findings for review."

### Manifest File Compatibility

The skill still writes `resolutions.md` in the existing format after receiving MCP results. This is a **compatibility shim** (F13) — execution logic currently reads `**Verb:**` lines from markdown. The shim is temporary; a future design should update execution logic to accept structured JSON directly and deprecate the markdown serialization.

### `resolutions.md` Write Procedure (F7)

When writing `resolutions.md` from the MCP response, the calling skill:

1. Reads `findings.md` to get per-finding context (problem, options, severity, etc.)
2. For each finding ID in the MCP response, writes the corresponding manifest section using the existing template (from findings-protocol.md)
3. Sets the `**Verb:**` line to the verb from the MCP response
4. Includes the manifest header with verb legend
5. Does NOT include the pre-hash comment (no hash detection needed on the MCP path)

### Re-edit via MCP (F9)

When the user selects "Revise" at the Commit Gate, re-run `review_findings` with the same findings path AND the current resolutions as `current_resolutions`. The server pre-selects previously chosen verbs in the dropdown defaults, so users confirm existing choices and change only what they want.

### Integration with caller-protocol.md (F12)

Add a parallel section to `caller-protocol.md` mirroring the findings-protocol.md changes. When the calling skill is mine.define (or any doc-edit caller), `review_findings` accepts an optional `caller` parameter. When `caller="mine.define"`, the elicitation message includes the `doc_target` field for each finding, enabling users to verify and correct finding-to-document-section routing.

## File Structure

```
packages/manifest-review/
  pyproject.toml           — existing, pin mcp>=1.9.0,<2.0.0
  src/manifest_review/
    __init__.py             — existing
    server.py               — FastMCP server, review_findings tool, transport config
    parser.py               — NEW: findings.md parser
    schemas.py              — NEW: per-finding-type schema builders (co-change with findings-protocol.md verbs)
```

Supporting files:
```
systemd/manifest-review.service  — NEW: systemd unit file
bin/install-manifest-review      — NEW: installer script (systemd enable + .mcp.json)
```

## Alternatives Considered

### A: Keep bin/edit-manifest, improve UX

Rejected. The tmux+nvim dependency is fundamental to the approach, and the markdown editing UX cannot be improved beyond what it is. The tertiary fallback demonstrates how poor the non-editor experience is.

### B: AskUserQuestion loop in the skill

Rejected in design 015 with empirical evidence. The LLM collapses per-item AskUserQuestion loops — this is the core problem that motivated the manifest system.

### C: Web-based form via elicitation URL mode

MCP elicitation supports a URL mode that could open a custom web form. Rejected as overengineered — the terminal dropdown UI is sufficient and avoids the complexity of a web server + form UI.

## Resolved Questions

1. **Notes field (F11):** Removed from elicitation schema. Notes would be silently dropped when writing resolutions.md (no notes field in the format, execution logic doesn't read them). If notes are needed, add them only for `ask` verbs in a future iteration with a defined execution contract.

2. **Re-edit with pre-selected verbs (F9):** Included in initial scope via `current_resolutions` parameter. Low complexity, prevents UX regression vs editor path.

3. **Port selection (F10):** Port 19847 from dynamic/private range. Hardcoded in both systemd unit and .mcp.json.

4. **Doc target display (F12):** Handled via `caller` parameter on `review_findings`. Only shown when `caller="mine.define"`.

5. **Crash recovery (F18):** Accepted as a regression vs editor's shadow file. With re-edit pre-population (F9), restarting a review after a crash is less painful. Full crash recovery (writing partial state to disk) deferred until base flow is validated.
