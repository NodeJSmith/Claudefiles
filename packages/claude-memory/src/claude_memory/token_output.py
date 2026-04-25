#!/usr/bin/env python3
"""
token_output — Dashboard JSON output assembly.
Queries the token analytics database and builds the full output dict
consumed by the HTML dashboard and the slim JSON printed to stdout.
"""

import sqlite3
from datetime import datetime, timezone
from itertools import groupby

from claude_memory.token_insights import build_insights_and_trends
from claude_memory.token_parser import (
    _BASH_ANTIPATTERN_PREDICATE,
    _get_pricing,
    _project_slug,
    _turn_cost,
)


# ── Build Output ──────────────────────────────────────────────────────


def build_output(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()

    # ── KPI totals (top-level sessions only) ──
    kpis = cur.execute("""
        SELECT COUNT(*), SUM(turn_count), SUM(total_output_tokens),
               SUM(total_cache_read), SUM(total_cache_creation),
               SUM(cache_cliff_count), SUM(max_tokens_stops),
               SUM(tool_error_count), SUM(total_input_tokens),
               SUM(total_thinking),
               SUM(total_ephem_5m), SUM(total_ephem_1h)
        FROM session_metrics WHERE is_sidechain = 0
    """).fetchone()
    total_sessions = kpis[0] or 0
    total_turns = kpis[1] or 0
    total_output = kpis[2] or 0
    total_cache_read = kpis[3] or 0
    total_cache_creation = kpis[4] or 0
    total_cache_cliffs = kpis[5] or 0
    total_max_token_stops = kpis[6] or 0
    total_tool_errors = kpis[7] or 0
    total_input = kpis[8] or 0
    total_thinking = kpis[9] or 0
    total_ephem_5m = kpis[10] or 0
    total_ephem_1h = kpis[11] or 0

    if total_ephem_5m > 0 or total_ephem_1h > 0:
        dominant_cache_tier = "5m" if total_ephem_5m > total_ephem_1h else "1h"
    else:
        dominant_cache_tier = "5m"

    cache_denom = total_cache_read + total_cache_creation
    global_cache_ratio = (
        round(total_cache_read / cache_denom, 4) if cache_denom > 0 else 0.0
    )

    total_tool_calls = (
        cur.execute("""
        SELECT COUNT(*) FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
    """).fetchone()[0]
        or 0
    )

    # Date range
    dr = cur.execute("""
        SELECT MIN(first_turn_ts), MAX(last_turn_ts)
        FROM session_metrics WHERE is_sidechain = 0
    """).fetchone()

    # ── Chart 1: Sessions by day ──
    sessions_by_day = []
    for row in cur.execute("""
        SELECT DATE(first_turn_ts) as day, COUNT(*),
               SUM(total_input_tokens), SUM(total_output_tokens),
               SUM(total_cache_read), SUM(total_cache_creation)
        FROM session_metrics WHERE is_sidechain = 0 AND first_turn_ts IS NOT NULL
        GROUP BY day ORDER BY day
    """):
        sessions_by_day.append(
            {
                "date": row[0],
                "session_count": row[1],
                "input_tokens": row[2],
                "output_tokens": row[3],
                "cache_read": row[4],
                "cache_creation": row[5],
            }
        )

    # ── Chart 3: Top 10 tools ──
    top_tools = []
    for row in cur.execute("""
        SELECT tool_name, COUNT(*) as cnt
        FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
        GROUP BY tool_name ORDER BY cnt DESC LIMIT 15
    """):
        top_tools.append({"tool": row[0], "count": row[1]})

    # ── Chart 4: Model cost split (with dollar costs) ──
    model_split = []
    for row in cur.execute("""
        SELECT model, SUM(input_tokens) as inp, SUM(output_tokens) as out,
               SUM(thinking_tokens) as think,
               SUM(cache_read_tokens) as cr, SUM(cache_creation_tokens) as cc,
               SUM(ephem_5m_tokens) as e5, SUM(ephem_1h_tokens) as e1
        FROM turns t
        JOIN session_metrics sm ON t.session_id = sm.session_id AND sm.is_sidechain = 0
        WHERE model IS NOT NULL
        GROUP BY model ORDER BY inp + out DESC
    """):
        pricing = _get_pricing(row[0])
        cost = _turn_cost(row[1], row[2], row[4], row[5], row[6], row[7], pricing)
        model_split.append(
            {
                "model": row[0],
                "input_tokens": row[1],
                "output_tokens": row[2],
                "thinking_tokens": row[3],
                "cost_usd": round(cost, 4),
            }
        )

    # ── Dollar cost: total, by day, by project ──
    total_cost_usd = sum(m["cost_usd"] for m in model_split)

    cost_by_day: dict[str, float] = {}
    for row in cur.execute("""
        SELECT DATE(t.timestamp) as day, t.model,
               SUM(t.input_tokens), SUM(t.output_tokens),
               SUM(t.cache_read_tokens), SUM(t.cache_creation_tokens),
               SUM(t.ephem_5m_tokens), SUM(t.ephem_1h_tokens)
        FROM turns t
        JOIN session_metrics sm ON t.session_id = sm.session_id AND sm.is_sidechain = 0
        WHERE t.timestamp IS NOT NULL
        GROUP BY day, t.model
    """):
        day = row[0]
        pricing = _get_pricing(row[1])
        day_cost = _turn_cost(row[2], row[3], row[4], row[5], row[6], row[7], pricing)
        cost_by_day[day] = cost_by_day.get(day, 0.0) + day_cost

    cost_by_day_list = [
        {"date": d, "cost_usd": round(c, 4)} for d, c in sorted(cost_by_day.items())
    ]

    cost_by_project: dict[str, float] = {}
    for row in cur.execute("""
        SELECT sm.project_path, t.model,
               SUM(t.input_tokens), SUM(t.output_tokens),
               SUM(t.cache_read_tokens), SUM(t.cache_creation_tokens),
               SUM(t.ephem_5m_tokens), SUM(t.ephem_1h_tokens)
        FROM turns t
        JOIN session_metrics sm ON t.session_id = sm.session_id AND sm.is_sidechain = 0
        GROUP BY sm.project_path, t.model
    """):
        slug = _project_slug(row[0])
        pricing = _get_pricing(row[1])
        proj_cost = _turn_cost(row[2], row[3], row[4], row[5], row[6], row[7], pricing)
        cost_by_project[slug] = cost_by_project.get(slug, 0.0) + proj_cost

    cost_by_project_list = sorted(
        [{"project": p, "cost_usd": round(c, 4)} for p, c in cost_by_project.items()],
        key=lambda x: x["cost_usd"],
        reverse=True,
    )[:10]

    # ── Chart 5: Cache trajectory (5 sample sessions with most cache data) ──
    cache_trajectory = []
    trajectory_sessions = cur.execute("""
        SELECT session_id FROM session_metrics
        WHERE is_sidechain = 0 AND total_cache_read + total_cache_creation > 0
        ORDER BY total_cache_read + total_cache_creation DESC LIMIT 5
    """).fetchall()
    for (tsid,) in trajectory_sessions:
        turns_data = []
        for row in cur.execute(
            """
            SELECT turn_index, cache_read_ratio, cache_read_tokens, cache_creation_tokens, user_gap_ms
            FROM turns WHERE session_id = ? ORDER BY turn_index LIMIT 30
        """,
            (tsid,),
        ):
            turns_data.append(
                {
                    "turn": row[0],
                    "ratio": row[1],
                    "read": row[2],
                    "creation": row[3],
                    "gap_ms": row[4],
                }
            )
        proj = cur.execute(
            "SELECT project_path FROM session_metrics WHERE session_id = ?", (tsid,)
        ).fetchone()
        cache_trajectory.append(
            {
                "session_id": tsid[:8],
                "project": _project_slug(proj[0] if proj else None),
                "turns": turns_data,
            }
        )

    # ── Chart 5b: Context Segmentation (aggregate across all sessions) ──
    def _compute_seg_curve(
        session_ids: list[str], max_turns: int = 60, min_sessions: int = 3
    ) -> list[dict]:
        if not session_ids:
            return []
        placeholders = ",".join("?" * len(session_ids))
        all_turns = cur.execute(
            f"""
            SELECT session_id, turn_index,
                   input_tokens + cache_read_tokens + cache_creation_tokens as total_ctx,
                   output_tokens
            FROM turns
            WHERE session_id IN ({placeholders})
            ORDER BY session_id, turn_index
        """,
            session_ids,
        ).fetchall()

        buckets: dict[int, dict[str, list[float]]] = {}
        for sid, session_turns in groupby(all_turns, key=lambda r: r[0]):
            rows = list(session_turns)
            if not rows or rows[0][2] <= 0:
                continue
            base_ctx = rows[0][2]
            cumul_output = 0
            for _, turn_idx, total_ctx, out_tok in rows:
                if total_ctx <= 0:
                    cumul_output += out_tok
                    continue
                base = min(base_ctx, total_ctx)
                history = min(cumul_output, total_ctx - base)
                tool_user = max(0, total_ctx - base - history)
                bucket = buckets.setdefault(
                    turn_idx, {"base": [], "hist": [], "tool": []}
                )
                bucket["base"].append(base / total_ctx * 100)
                bucket["hist"].append(history / total_ctx * 100)
                bucket["tool"].append(tool_user / total_ctx * 100)
                cumul_output += out_tok
        curve = []
        for t_idx in sorted(buckets.keys())[:max_turns]:
            b = buckets[t_idx]
            n = len(b["base"])
            if n < min_sessions:
                continue
            curve.append(
                {
                    "turn": t_idx,
                    "sessions": n,
                    "base_pct": round(sum(b["base"]) / n, 1),
                    "history_pct": round(sum(b["hist"]) / n, 1),
                    "tool_user_pct": round(sum(b["tool"]) / n, 1),
                }
            )
        return curve

    all_seg_sids = [
        r[0]
        for r in cur.execute("""
        SELECT session_id FROM session_metrics
        WHERE is_sidechain = 0 AND turn_count >= 8
    """).fetchall()
    ]
    context_segments = _compute_seg_curve(all_seg_sids)

    recent_seg_sids = [
        r[0]
        for r in cur.execute("""
        SELECT session_id FROM session_metrics
        WHERE is_sidechain = 0 AND turn_count >= 8
              AND first_turn_ts >= datetime('now', '-7 days')
    """).fetchall()
    ]
    context_segments_recent = _compute_seg_curve(recent_seg_sids, min_sessions=2)

    # ── Tool context footprint (avg tokens added per call by tool type) ──
    tool_footprint = []
    for row in cur.execute("""
        WITH single_tool_turns AS (
            SELECT tc.turn_id, tc.tool_name, tc.session_id
            FROM turn_tool_calls tc
            GROUP BY tc.turn_id
            HAVING COUNT(*) = 1
        )
        SELECT stt.tool_name, COUNT(*) as cnt,
               ROUND(AVG(
                 (tn.input_tokens + tn.cache_read_tokens + tn.cache_creation_tokens) -
                 (t.input_tokens + t.cache_read_tokens + t.cache_creation_tokens) -
                 t.output_tokens
               )) as avg_footprint
        FROM single_tool_turns stt
        JOIN turns t ON stt.turn_id = t.id
        JOIN turns tn ON tn.session_id = t.session_id AND tn.turn_index = t.turn_index + 1
        JOIN session_metrics sm ON stt.session_id = sm.session_id AND sm.is_sidechain = 0
        GROUP BY stt.tool_name
        HAVING cnt >= 10 AND avg_footprint > 0
        ORDER BY avg_footprint DESC LIMIT 12
    """):
        tool_footprint.append(
            {"tool": row[0], "calls": row[1], "avg_tokens": int(row[2])}
        )

    seg_agg = cur.execute("""
        SELECT
            SUM(t1_ctx * tc),
            SUM(total_all_ctx),
            COUNT(*),
            AVG(t1_ctx)
        FROM (
            SELECT sm.session_id, sm.turn_count as tc,
                   (SELECT input_tokens + cache_read_tokens + cache_creation_tokens
                    FROM turns WHERE session_id = sm.session_id AND turn_index = 1) as t1_ctx,
                   (SELECT SUM(input_tokens + cache_read_tokens + cache_creation_tokens)
                    FROM turns WHERE session_id = sm.session_id) as total_all_ctx
            FROM session_metrics sm
            WHERE sm.is_sidechain = 0 AND sm.turn_count >= 8
        )
        WHERE t1_ctx > 0 AND total_all_ctx > 0
    """).fetchone()
    base_overhead_paid = seg_agg[0] or 0
    total_ctx_paid = seg_agg[1] or 1
    context_seg_summary = {
        "sessions_analyzed": seg_agg[2] or 0,
        "avg_base_ctx": round(seg_agg[3] or 0),
        "base_overhead_pct": round(base_overhead_paid / total_ctx_paid * 100, 1),
        "recent_sessions_count": len(recent_seg_sids),
    }

    # ── Chart 6: Ephemeral cache tier split by project ──
    ephem_split = []
    for row in cur.execute("""
        SELECT sm.project_path, SUM(t.ephem_5m_tokens) as e5, SUM(t.ephem_1h_tokens) as e1
        FROM turns t
        JOIN session_metrics sm ON t.session_id = sm.session_id AND sm.is_sidechain = 0
        GROUP BY sm.project_path
        HAVING e5 + e1 > 0
        ORDER BY e5 + e1 DESC LIMIT 8
    """):
        ephem_split.append(
            {"project": _project_slug(row[0]), "ephem_5m": row[1], "ephem_1h": row[2]}
        )

    # ── Chart 7: Bash antipattern rate by project (computed at query time) ──
    bash_antipatterns = []
    for row in cur.execute(f"""
        SELECT sm.project_path,
               SUM(CASE WHEN {_BASH_ANTIPATTERN_PREDICATE} THEN 1 ELSE 0 END) as antipatterns,
               SUM(CASE WHEN tc.tool_name = 'Bash' THEN 1 ELSE 0 END) as total_bash
        FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
        GROUP BY sm.project_path
        HAVING antipatterns > 0
        ORDER BY antipatterns DESC LIMIT 10
    """):
        bash_antipatterns.append(
            {
                "project": _project_slug(row[0]),
                "antipatterns": row[1],
                "total_bash": row[2],
            }
        )
    total_bash_antipatterns = (
        cur.execute(f"""
        SELECT SUM(CASE WHEN {_BASH_ANTIPATTERN_PREDICATE} THEN 1 ELSE 0 END)
        FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
    """).fetchone()[0]
        or 0
    )

    # ── Chart 8: Tool error rate by tool ──
    tool_errors_by_tool = []
    for row in cur.execute("""
        SELECT tool_name, SUM(is_error) as errors, COUNT(*) as total
        FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
        GROUP BY tool_name
        HAVING errors > 0
        ORDER BY errors DESC LIMIT 10
    """):
        tool_errors_by_tool.append(
            {
                "tool": row[0],
                "errors": row[1],
                "total": row[2],
                "rate": round(row[1] / row[2], 4) if row[2] else 0,
            }
        )

    # ── Chart 9: Redundant read hotspots (computed at query time) ──
    redundant_reads = []
    for row in cur.execute("""
        SELECT tc.session_id, tc.file_path, COUNT(*) as cnt
        FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
        WHERE tc.tool_name = 'Read' AND tc.file_path IS NOT NULL
        GROUP BY tc.session_id, tc.file_path
        HAVING cnt > 2
        ORDER BY cnt DESC LIMIT 20
    """):
        redundant_reads.append(
            {
                "session_id": row[0][:8],
                "file": row[1].rsplit("/", 1)[-1] if row[1] else "?",
                "count": row[2],
            }
        )
    total_redundant_reads = (
        cur.execute("""
        SELECT SUM(cnt - 1) FROM (
            SELECT COUNT(*) as cnt
            FROM turn_tool_calls tc
            JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
            WHERE tc.tool_name = 'Read' AND tc.file_path IS NOT NULL
            GROUP BY tc.session_id, tc.file_path
            HAVING cnt > 2
        )
    """).fetchone()[0]
        or 0
    )

    # ── Chart 10: Edit retry chains by project ──
    edit_retries = []
    for row in cur.execute("""
        SELECT sm.project_path, COUNT(*) as retries
        FROM turn_tool_calls tc1
        JOIN turns t1 ON tc1.turn_id = t1.id
        JOIN turns t2 ON t1.session_id = t2.session_id AND t2.turn_index = t1.turn_index + 1
        JOIN turn_tool_calls tc2 ON tc2.turn_id = t2.id
            AND tc2.file_path = tc1.file_path
            AND tc1.tool_name IN ('Edit', 'Write')
            AND tc2.tool_name IN ('Edit', 'Write')
            AND tc1.is_error = 1
        JOIN session_metrics sm ON tc1.session_id = sm.session_id AND sm.is_sidechain = 0
        GROUP BY sm.project_path
        HAVING retries > 0
        ORDER BY retries DESC LIMIT 10
    """):
        edit_retries.append({"project": _project_slug(row[0]), "retries": row[1]})
    total_edit_retries = (
        cur.execute("""
        SELECT COUNT(*)
        FROM turn_tool_calls tc1
        JOIN turns t1 ON tc1.turn_id = t1.id
        JOIN turns t2 ON t1.session_id = t2.session_id AND t2.turn_index = t1.turn_index + 1
        JOIN turn_tool_calls tc2 ON tc2.turn_id = t2.id
            AND tc2.file_path = tc1.file_path
            AND tc1.tool_name IN ('Edit', 'Write')
            AND tc2.tool_name IN ('Edit', 'Write')
            AND tc1.is_error = 1
        JOIN session_metrics sm ON tc1.session_id = sm.session_id AND sm.is_sidechain = 0
    """).fetchone()[0]
        or 0
    )

    # ── Chart 11: Agent cost attribution ──
    agent_cost = []
    for row in cur.execute("""
        SELECT parent.project_path,
               SUM(CASE WHEN child.is_sidechain = 0 THEN child.total_input_tokens + child.total_cache_creation ELSE 0 END) as parent_cost,
               SUM(CASE WHEN child.is_sidechain = 1 THEN child.total_input_tokens + child.total_cache_creation ELSE 0 END) as agent_cost
        FROM session_metrics parent
        JOIN session_metrics child ON child.parent_session_id = parent.session_id OR child.session_id = parent.session_id
        WHERE parent.is_sidechain = 0 AND parent.uses_agent = 1
        GROUP BY parent.project_path
        ORDER BY agent_cost DESC LIMIT 10
    """):
        agent_cost.append(
            {
                "project": _project_slug(row[0]),
                "parent_cost": row[1],
                "agent_cost": row[2],
            }
        )

    # ── Chart 12: Turn complexity distribution ──
    turn_complexity = {"minimal": 0, "light": 0, "medium": 0, "heavy": 0, "runaway": 0}
    thinking_sum_complexity = {
        "minimal": 0,
        "light": 0,
        "medium": 0,
        "heavy": 0,
        "runaway": 0,
    }
    for row in cur.execute("""
        SELECT t.output_tokens, t.thinking_tokens
        FROM turns t
        JOIN session_metrics sm ON t.session_id = sm.session_id AND sm.is_sidechain = 0
    """):
        out, think = row[0] or 0, row[1] or 0
        if out < 100:
            bucket = "minimal"
        elif out < 500:
            bucket = "light"
        elif out < 2000:
            bucket = "medium"
        elif out < 8000:
            bucket = "heavy"
        else:
            bucket = "runaway"
        turn_complexity[bucket] += 1
        thinking_sum_complexity[bucket] += think
    thinking_in_complexity = {
        k: round(thinking_sum_complexity[k] / turn_complexity[k])
        if turn_complexity[k] > 0
        else 0
        for k in turn_complexity
    }

    # ── Chart 13: User response time distribution ──
    response_time_dist = {
        "under_30s": 0,
        "30s_2m": 0,
        "2m_5m": 0,
        "5m_15m": 0,
        "15m_1h": 0,
        "over_1h": 0,
    }
    for row in cur.execute("""
        SELECT user_gap_ms FROM turns t
        JOIN session_metrics sm ON t.session_id = sm.session_id AND sm.is_sidechain = 0
        WHERE user_gap_ms IS NOT NULL AND user_gap_ms > 0
    """):
        gap_s = (row[0] or 0) / 1000
        if gap_s < 30:
            response_time_dist["under_30s"] += 1
        elif gap_s < 120:
            response_time_dist["30s_2m"] += 1
        elif gap_s < 300:
            response_time_dist["2m_5m"] += 1
        elif gap_s < 900:
            response_time_dist["5m_15m"] += 1
        elif gap_s < 3600:
            response_time_dist["15m_1h"] += 1
        else:
            response_time_dist["over_1h"] += 1

    # ── Chart 14: Hook overhead top 10 ──
    hook_overhead = []
    for row in cur.execute("""
        SELECT project_path, SUM(total_hook_ms) as hook_ms, COUNT(*) as sessions
        FROM session_metrics WHERE is_sidechain = 0 AND total_hook_ms > 0
        GROUP BY project_path
        ORDER BY hook_ms DESC LIMIT 10
    """):
        hook_overhead.append(
            {
                "project": _project_slug(row[0]),
                "hook_ms": row[1],
                "sessions": row[2],
                "avg_hook_ms": round(row[1] / row[2]) if row[2] else 0,
            }
        )

    # ── Chart 15: Per-project token spend ──
    project_spend = []
    for row in cur.execute("""
        SELECT project_path,
               SUM(total_input_tokens) as inp,
               SUM(total_output_tokens) as out,
               SUM(total_cache_creation) as cc,
               SUM(total_cache_read) as cr,
               COUNT(*) as sessions
        FROM session_metrics WHERE is_sidechain = 0
        GROUP BY project_path
        ORDER BY inp + cc DESC LIMIT 10
    """):
        project_spend.append(
            {
                "project": _project_slug(row[0]),
                "input_tokens": row[1],
                "output_tokens": row[2],
                "cache_creation": row[3],
                "cache_read": row[4],
                "sessions": row[5],
            }
        )

    # ── Chart 16: Per-project tool profile ──
    project_tool_profile = []
    top5_projects = [p["project"] for p in project_spend[:5]]
    if top5_projects:
        project_paths = {}
        for row in cur.execute("""
            SELECT project_path, SUM(total_input_tokens + total_cache_creation) as cost
            FROM session_metrics WHERE is_sidechain = 0
            GROUP BY project_path ORDER BY cost DESC LIMIT 5
        """):
            project_paths[_project_slug(row[0])] = row[0]

        for proj_slug, proj_path in project_paths.items():
            tools = {}
            for row in cur.execute(
                """
                SELECT tc.tool_name, COUNT(*)
                FROM turn_tool_calls tc
                JOIN session_metrics sm ON tc.session_id = sm.session_id
                WHERE sm.project_path = ? AND sm.is_sidechain = 0
                GROUP BY tc.tool_name
                ORDER BY COUNT(*) DESC LIMIT 8
            """,
                (proj_path,),
            ):
                tools[row[0]] = row[1]
            project_tool_profile.append({"project": proj_slug, "tools": tools})

    # ── Chart 17: Skill usage ──
    skill_usage = []
    for row in cur.execute("""
        SELECT skill_name, COUNT(*) as cnt, SUM(is_error) as errs
        FROM turn_tool_calls
        WHERE skill_name IS NOT NULL
        GROUP BY skill_name ORDER BY cnt DESC
    """):
        skill_usage.append({"skill": row[0], "count": row[1], "errors": row[2]})

    skill_usage_by_day = []
    for row in cur.execute("""
        SELECT DATE(t.timestamp) as day, tc.skill_name, COUNT(*) as cnt
        FROM turn_tool_calls tc
        JOIN turns t ON tc.turn_id = t.id
        WHERE tc.skill_name IS NOT NULL
        GROUP BY day, tc.skill_name ORDER BY day
    """):
        skill_usage_by_day.append({"date": row[0], "skill": row[1], "count": row[2]})

    # ── Chart 18: Agent delegation ──
    agent_delegation = []
    for row in cur.execute("""
        SELECT tc.subagent_type, COUNT(*) as cnt, SUM(tc.is_error) as errs
        FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
        WHERE tc.subagent_type IS NOT NULL
        GROUP BY tc.subagent_type ORDER BY cnt DESC
    """):
        agent_delegation.append(
            {"subagent_type": row[0], "count": row[1], "errors": row[2]}
        )

    agent_model_dist = []
    for row in cur.execute("""
        SELECT tc.agent_model, COUNT(*) as cnt
        FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
        WHERE tc.agent_model IS NOT NULL
        GROUP BY tc.agent_model ORDER BY cnt DESC
    """):
        agent_model_dist.append({"model": row[0], "count": row[1]})

    # ── Chart 19: Hook performance ──
    hook_performance = []
    for row in cur.execute("""
        SELECT he.hook_command, COUNT(*) as runs,
               SUM(he.duration_ms) as total_ms,
               ROUND(AVG(he.duration_ms)) as avg_ms,
               SUM(he.is_error) as errs
        FROM hook_executions he
        JOIN session_metrics sm ON he.session_id = sm.session_id AND sm.is_sidechain = 0
        GROUP BY he.hook_command ORDER BY total_ms DESC
    """):
        hook_performance.append(
            {
                "hook_command": row[0],
                "runs": row[1],
                "total_ms": row[2],
                "avg_ms": row[3],
                "errors": row[4],
            }
        )

    # ── Insights, findings, recommendations, trends ──
    insight_data = build_insights_and_trends(
        conn,
        total_output=total_output,
        total_input=total_input,
        cache_cliffs=total_cache_cliffs,
        max_token_stops=total_max_token_stops,
        total_bash_antipatterns=total_bash_antipatterns,
        redundant_reads_count=total_redundant_reads,
        edit_retries_count=total_edit_retries,
        total_thinking=total_thinking,
        total_tool_errors=total_tool_errors,
        global_cache_ratio=global_cache_ratio,
        total_sessions=total_sessions,
        response_time_dist=response_time_dist,
        bash_antipattern_projects=bash_antipatterns[:3],
        top_redundant_files=redundant_reads[:3],
        edit_retry_projects=edit_retries[:3],
        cost_by_project=cost_by_project_list,
        total_cost_usd=total_cost_usd,
        context_seg_summary=context_seg_summary,
        dominant_cache_tier=dominant_cache_tier,
        model_split=model_split,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_sessions": total_sessions,
        "date_range": {
            "earliest": dr[0][:10] if dr and dr[0] else None,
            "latest": dr[1][:10] if dr and dr[1] else None,
        },
        "kpis": {
            "total_sessions": total_sessions,
            "total_turns": total_turns,
            "total_output_tokens": total_output,
            "global_cache_ratio": global_cache_ratio,
            "cache_cliffs": total_cache_cliffs,
            "max_token_stops": total_max_token_stops,
            "bash_antipatterns": total_bash_antipatterns,
            "tool_error_rate": round(total_tool_errors / total_tool_calls, 4)
            if total_tool_calls
            else 0,
            "total_cost_usd": round(total_cost_usd, 2),
        },
        "sessions_by_day": sessions_by_day,
        "top_tools": top_tools,
        "model_split": model_split,
        "cost_by_day": cost_by_day_list,
        "cost_by_project": cost_by_project_list,
        "cache_trajectory": cache_trajectory,
        "context_segments": context_segments,
        "context_segments_recent": context_segments_recent,
        "tool_footprint": tool_footprint,
        "context_seg_summary": context_seg_summary,
        "ephem_split": ephem_split,
        "bash_antipatterns": bash_antipatterns,
        "tool_errors_by_tool": tool_errors_by_tool,
        "redundant_reads": redundant_reads,
        "edit_retries": edit_retries,
        "agent_cost": agent_cost,
        "turn_complexity": turn_complexity,
        "thinking_in_complexity": thinking_in_complexity,
        "response_time_dist": response_time_dist,
        "hook_overhead": hook_overhead,
        "project_spend": project_spend,
        "project_tool_profile": project_tool_profile,
        "skill_usage": skill_usage,
        "skill_usage_by_day": skill_usage_by_day,
        "agent_delegation": agent_delegation,
        "agent_model_dist": agent_model_dist,
        "hook_performance": hook_performance,
        **insight_data,
    }
