#!/usr/bin/env python3
"""
token_analytics — Session import and token_snapshots backfill
for the token ingest pipeline.
"""

import json
import sqlite3

from claude_memory.token_parser import (
    JnlFile,
    ParsedSession,
    compute_session_analytics,
)


# ── DB Import ─────────────────────────────────────────────────���───────


def import_session(
    conn: sqlite3.Connection, session: ParsedSession, jnl: JnlFile
) -> None:
    sid = session.session_id

    # Append-only: insert new turns, skip existing (JSONL source expires after 30 days)
    analytics = compute_session_analytics(session)

    # Prefetch existing turn indices to avoid N+1 queries on reimport
    existing_indices = {
        row[0]
        for row in conn.execute(
            "SELECT turn_index FROM turns WHERE session_id = ?", (sid,)
        )
    }
    for turn in session.turns:
        if turn.index in existing_indices:
            continue

        conn.execute(
            """INSERT INTO turns (session_id, turn_index, timestamp, model,
               input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
               ephem_5m_tokens, ephem_1h_tokens, thinking_tokens, stop_reason,
               turn_duration_ms, user_gap_ms, is_sidechain, cache_read_ratio)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sid,
                turn.index,
                turn.timestamp,
                turn.model,
                turn.input_tokens,
                turn.output_tokens,
                turn.cache_read_tokens,
                turn.cache_creation_tokens,
                turn.ephem_5m_tokens,
                turn.ephem_1h_tokens,
                turn.thinking_tokens,
                turn.stop_reason,
                turn.turn_duration_ms,
                turn.user_gap_ms,
                1 if jnl.is_sidechain else 0,
                turn.cache_read_ratio,
            ),
        )
        turn_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert tool calls only for newly inserted turns
        for tc in turn.tool_calls:
            conn.execute(
                """INSERT INTO turn_tool_calls (turn_id, session_id, tool_name, tool_use_id,
                   file_path, command, is_error, error_text, agent_id,
                   skill_name, subagent_type, agent_model)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    turn_id,
                    sid,
                    tc.tool_name,
                    tc.tool_use_id,
                    tc.file_path,
                    tc.command,
                    tc.is_error,
                    tc.error_text,
                    tc.agent_id,
                    tc.skill_name,
                    tc.subagent_type,
                    tc.agent_model,
                ),
            )

    # Upsert session_metrics — summary recalculated from full data on each pass
    first_ts = session.turns[0].timestamp if session.turns else None
    last_ts = session.turns[-1].timestamp if session.turns else None

    conn.execute(
        """INSERT OR REPLACE INTO session_metrics (session_id, project_path, git_branch, cc_version,
           slug, entrypoint, is_sidechain, parent_session_id,
           first_turn_ts, last_turn_ts, turn_count, user_msg_count,
           total_input_tokens, total_output_tokens, total_cache_read, total_cache_creation,
           total_ephem_5m, total_ephem_1h, total_thinking,
           total_turn_ms, total_hook_ms, api_error_count,
           cache_cliff_count, tool_error_count, max_tokens_stops,
           uses_agent, models_used, model_switch_count)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            sid,
            session.project_path,
            session.git_branch,
            session.cc_version,
            session.slug,
            session.entrypoint,
            1 if jnl.is_sidechain else 0,
            jnl.parent_session_id,
            first_ts,
            last_ts,
            len(session.turns),
            session.user_msg_count,
            sum(t.input_tokens for t in session.turns),
            sum(t.output_tokens for t in session.turns),
            sum(t.cache_read_tokens for t in session.turns),
            sum(t.cache_creation_tokens for t in session.turns),
            sum(t.ephem_5m_tokens for t in session.turns),
            sum(t.ephem_1h_tokens for t in session.turns),
            sum(t.thinking_tokens for t in session.turns),
            analytics["total_turn_ms"],
            session.total_hook_ms,
            session.api_error_count,
            analytics["cache_cliff_count"],
            analytics["tool_error_count"],
            analytics["max_tokens_stops"],
            1 if session.uses_agent else 0,
            json.dumps(analytics["models_used"]),
            analytics["model_switch_count"],
        ),
    )

    # Insert hook executions only if none exist for this session. Intentional trade-off: on
    # re-import (JSONL file grown since first ingest), session_metrics.total_hook_ms is
    # recomputed from the full file, but hook_executions stays frozen at the first-import
    # count. This avoids duplicate rows for hooks that were already recorded; the aggregate
    # metric stays accurate while per-row hook analytics may undercount later hooks.
    has_hooks = conn.execute(
        "SELECT 1 FROM hook_executions WHERE session_id = ? LIMIT 1", (sid,)
    ).fetchone()
    if not has_hooks:
        for hc in session.hook_calls:
            conn.execute(
                """INSERT INTO hook_executions (session_id, hook_command, duration_ms, is_error)
                   VALUES (?,?,?,?)""",
                (sid, hc["hook_command"], hc["duration_ms"], hc["is_error"]),
            )


# ── Backfill token_snapshots ─────────────────────────────────────────


def backfill_token_snapshots(conn: sqlite3.Connection) -> None:
    """Upsert quantitative data from session_metrics into token_snapshots.
    Preserves AI-generated facet columns (outcome, session_type, etc.)."""

    # Build tool_counts JSON per session from turn_tool_calls
    tool_counts_by_session: dict[str, dict[str, int]] = {}
    cur = conn.execute(
        "SELECT session_id, tool_name, COUNT(*) FROM turn_tool_calls GROUP BY session_id, tool_name"
    )
    for sid, tool, cnt in cur:
        if sid not in tool_counts_by_session:
            tool_counts_by_session[sid] = {}
        tool_counts_by_session[sid][tool] = cnt

    rows = conn.execute(
        """SELECT session_id, project_path, first_turn_ts, turn_count, user_msg_count,
                  total_input_tokens, total_output_tokens, total_cache_read, total_cache_creation,
                  tool_error_count, uses_agent, total_turn_ms
           FROM session_metrics WHERE is_sidechain = 0"""
    ).fetchall()

    for row in rows:
        (
            sid,
            project,
            first_ts,
            turns,
            user_msgs,
            inp,
            out,
            cr,
            cc,
            tool_errs,
            uses_agent,
            turn_ms,
        ) = row

        duration_min = round(turn_ms / 60000, 1) if turn_ms else None
        tc_json = json.dumps(tool_counts_by_session.get(sid, {}))

        conn.execute(
            """INSERT INTO token_snapshots (session_uuid, project_path, start_time,
                   duration_minutes, user_message_count, assistant_message_count,
                   input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens,
                   tool_counts, tool_errors, uses_task_agent, data_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'jsonl_v3')
               ON CONFLICT(session_uuid) DO UPDATE SET
                   input_tokens = excluded.input_tokens,
                   output_tokens = excluded.output_tokens,
                   cache_read_tokens = excluded.cache_read_tokens,
                   cache_creation_tokens = excluded.cache_creation_tokens,
                   tool_counts = excluded.tool_counts,
                   tool_errors = excluded.tool_errors,
                   duration_minutes = excluded.duration_minutes,
                   user_message_count = excluded.user_message_count,
                   assistant_message_count = excluded.assistant_message_count,
                   uses_task_agent = excluded.uses_task_agent,
                   data_source = 'jsonl_v3'
            """,
            (
                sid,
                project,
                first_ts,
                duration_min,
                user_msgs,
                turns,
                inp,
                out,
                cr,
                cc,
                tc_json,
                tool_errs,
                1 if uses_agent else 0,
            ),
        )
    conn.commit()
