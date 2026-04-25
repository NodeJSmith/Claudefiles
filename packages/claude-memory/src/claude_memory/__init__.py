"""
claude_memory — conversation memory package for Claude Code.

Submodules:
  db                — Database connection, schema, settings, logging
  content           — Message content extraction and tool detection
  parsing           — JSONL parsing, branch detection, metadata extraction
  formatting        — Session formatting, time/path utilities
  project_ops       — Shared project upsert logic (cwd strategy + JSONL-probe strategy)
  session_ops       — Shared session import logic (used by sync and import pipelines)
  token_schema      — Token ingest schema definitions, ensure_schema(), version management
  token_parser      — Token JSONL parsing, data classes, session parsing, file discovery
  token_analytics   — Session import and token_snapshots backfill
  token_output      — Dashboard JSON output assembly (chart queries)
  token_insights    — Trend analysis, insight generation, findings/recommendations
  token_dashboard   — Token dashboard deployment and main() entry point
"""
