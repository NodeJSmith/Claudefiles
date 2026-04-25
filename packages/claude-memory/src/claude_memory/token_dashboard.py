#!/usr/bin/env python3
"""
token_dashboard — Dashboard deployment and main() entry point
for the token ingest pipeline.
"""

import json
import sys
from pathlib import Path

from claude_memory.db import get_db_path
from claude_memory.token_analytics import backfill_token_snapshots, import_session
from claude_memory.token_output import build_output
from claude_memory.token_parser import (
    BATCH_SIZE,
    PROGRESS_INTERVAL,
    discover_jsonl_files,
    parse_session,
    record_import,
    should_skip_file,
)
from claude_memory.token_schema import connect_token_db, ensure_schema

DASHBOARD_TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"


# ── Dashboard Deploy ──────────────────────────────────────────────────


def deploy_dashboard(json_str: str, dashboard_out_path: Path) -> None:
    try:
        html = DASHBOARD_TEMPLATE_PATH.read_text(encoding="utf-8")
        html = html.replace(
            "/* __INLINE_DATA_PLACEHOLDER__ */",
            f"const _INLINE_DATA = {json_str};",
            1,
        )
        dashboard_out_path.write_text(html, encoding="utf-8")
    except Exception as e:
        print(f"Warning: could not deploy dashboard: {e}", file=sys.stderr)


# ── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    db_path = get_db_path()
    dashboard_out_path = db_path.parent / "dashboard.html"

    conn = connect_token_db(db_path)

    ensure_schema(conn)

    # Discover files
    files = discover_jsonl_files()
    print(f"Discovered {len(files)} JSONL files", file=sys.stderr)

    # Filter to files needing import
    to_import = [f for f in files if not should_skip_file(conn, f.path)]
    print(
        f"Files to import: {len(to_import)} (skipping {len(files) - len(to_import)} unchanged)",
        file=sys.stderr,
    )

    # Parse and import
    imported = 0
    errors = 0
    for i, jnl in enumerate(to_import):
        if i > 0 and i % PROGRESS_INTERVAL == 0:
            print(f"  Parsing {i}/{len(to_import)} files...", file=sys.stderr)
        try:
            session = parse_session(jnl.path, jnl)
            if session:
                import_session(conn, session, jnl)
                record_import(conn, jnl.path, session.session_id, len(session.turns))
                imported += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error parsing {jnl.path.name}: {e}", file=sys.stderr)

        if (i + 1) % BATCH_SIZE == 0:
            conn.commit()

    conn.commit()
    print(f"Imported {imported} sessions ({errors} errors)", file=sys.stderr)

    # Backfill token_snapshots
    print("Backfilling token_snapshots...", file=sys.stderr)
    backfill_token_snapshots(conn)

    # Run ANALYZE for query planner optimization
    conn.execute("ANALYZE")
    conn.commit()

    # Build output
    output = build_output(conn)
    conn.close()

    # Full JSON for dashboard (all chart data)
    full_json = json.dumps(output, default=str)
    full_kb = len(full_json) / 1024
    print(f"Full JSON: {full_kb:.0f}KB", file=sys.stderr)

    deploy_dashboard(full_json, dashboard_out_path)
    print(f"Dashboard deployed to {dashboard_out_path}", file=sys.stderr)

    # Slim JSON for stdout (only what Claude needs for analysis)
    slim_keys = {
        "generated_at",
        "total_sessions",
        "date_range",
        "kpis",
        "insights",
        "cost_by_project",
        "model_split",
        "context_seg_summary",
        "skill_usage",
        "agent_delegation",
        "hook_performance",
        "trends",
    }
    slim = {k: v for k, v in output.items() if k in slim_keys}
    slim_json = json.dumps(slim, default=str)
    slim_kb = len(slim_json) / 1024
    print(f"Slim stdout: {slim_kb:.0f}KB (full: {full_kb:.0f}KB)", file=sys.stderr)
    print(slim_json)


if __name__ == "__main__":
    main()
