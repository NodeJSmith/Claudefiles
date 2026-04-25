#!/usr/bin/env python3
"""
token_insights — Trend analysis, insight generation, and findings/recommendations
for the token ingest pipeline.
"""

import sqlite3

from claude_memory.token_parser import (
    _BASH_ANTIPATTERN_PREDICATE,
    _get_pricing,
    _project_slug,
    _turn_cost,
)


# ── Public API ─────────────────────────────────────────────────────────


def build_insights_and_trends(
    conn: sqlite3.Connection,
    *,
    total_output: int,
    total_input: int,
    cache_cliffs: int,
    max_token_stops: int,
    total_bash_antipatterns: int,
    redundant_reads_count: int,
    edit_retries_count: int,
    total_thinking: int,
    total_tool_errors: int,
    global_cache_ratio: float,
    total_sessions: int,
    response_time_dist: dict,
    bash_antipattern_projects: list[dict],
    top_redundant_files: list[dict],
    edit_retry_projects: list[dict],
    cost_by_project: list[dict],
    total_cost_usd: float,
    context_seg_summary: dict,
    dominant_cache_tier: str,
    model_split: list[dict],
) -> dict:
    """Run root-cause queries, build insights, and compute trends."""
    cur = conn.cursor()

    # Root-cause detail: cache cliffs by project
    cache_cliff_projects = []
    for row in cur.execute("""
        SELECT project_path, SUM(cache_cliff_count) as cliffs, COUNT(*) as sessions
        FROM session_metrics WHERE is_sidechain = 0 AND cache_cliff_count > 0
        GROUP BY project_path ORDER BY cliffs DESC LIMIT 5
    """):
        cache_cliff_projects.append(
            {"project": _project_slug(row[0]), "cliffs": row[1], "sessions": row[2]}
        )

    # Root-cause detail: top antipattern commands
    top_bash_cmds = []
    for row in cur.execute(f"""
        SELECT SUBSTR(tc.command, 1, 60) as cmd, COUNT(*) as cnt
        FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id AND sm.is_sidechain = 0
        WHERE {_BASH_ANTIPATTERN_PREDICATE}
        GROUP BY cmd ORDER BY cnt DESC LIMIT 5
    """):
        top_bash_cmds.append({"command": row[0], "count": row[1]})

    # Weighted average cost rates for waste-to-dollar conversion
    avg_input_cpm = 5.0
    avg_output_cpm = 25.0
    if model_split:
        weighted_in = sum(
            m["input_tokens"] * _get_pricing(m["model"])["input"] for m in model_split
        )
        weighted_out = sum(
            m["output_tokens"] * _get_pricing(m["model"])["output"] for m in model_split
        )
        total_in = sum(m["input_tokens"] for m in model_split) or 1
        total_out = sum(m["output_tokens"] for m in model_split) or 1
        avg_input_cpm = weighted_in / total_in
        avg_output_cpm = weighted_out / total_out

    insights = _build_insights(
        total_output=total_output,
        total_input=total_input,
        cache_cliffs=cache_cliffs,
        max_token_stops=max_token_stops,
        bash_antipatterns=total_bash_antipatterns,
        redundant_reads=redundant_reads_count,
        edit_retries=edit_retries_count,
        total_thinking=total_thinking,
        total_tool_errors=total_tool_errors,
        global_cache_ratio=global_cache_ratio,
        total_sessions=total_sessions,
        response_time_dist=response_time_dist,
        bash_antipattern_projects=bash_antipattern_projects,
        top_bash_antipattern_cmds=top_bash_cmds,
        cache_cliff_projects=cache_cliff_projects,
        top_redundant_files=top_redundant_files,
        edit_retry_projects=edit_retry_projects,
        cost_by_project=cost_by_project,
        total_cost_usd=total_cost_usd,
        avg_input_cost_per_mtok=avg_input_cpm,
        avg_output_cost_per_mtok=avg_output_cpm,
        context_seg_summary=context_seg_summary,
        dominant_cache_tier=dominant_cache_tier,
    )

    findings = _insights_to_findings(insights)
    recommendations = _insights_to_recommendations(insights)
    trends = build_trends(conn)

    return {
        "insights": insights,
        "findings": findings,
        "recommendations": recommendations,
        "trends": trends,
    }


# ── Trends Engine (week-on-week comparison) ───────────────────────────


def build_trends(conn: sqlite3.Connection) -> dict:
    """Compute week-on-week deltas for key metrics.

    Splits data into two 7-day windows: 'current' (last 7 days) and
    'prior' (7-14 days ago). Returns per-metric current/prior/change_pct
    plus classified improved/regressed/new/retired lists.
    """
    cur = conn.cursor()

    def _window_kpis(where_clause: str) -> dict | None:
        """Compute KPIs for a time window defined by where_clause on session_metrics.first_turn_ts."""
        row = cur.execute(f"""
            SELECT COUNT(*), SUM(turn_count),
                   SUM(total_cache_read), SUM(total_cache_creation),
                   SUM(cache_cliff_count), SUM(tool_error_count),
                   SUM(total_hook_ms)
            FROM session_metrics sm
            WHERE is_sidechain = 0 AND {where_clause}
        """).fetchone()
        sessions = row[0] or 0
        if sessions == 0:
            return None
        turns = row[1] or 0
        cache_read = row[2] or 0
        cache_creation = row[3] or 0
        cliffs = row[4] or 0
        tool_errors = row[5] or 0
        hook_ms = row[6] or 0

        cache_denom = cache_read + cache_creation
        cache_ratio = round(cache_read / cache_denom, 4) if cache_denom > 0 else 0.0

        total_tool_calls = (
            cur.execute(f"""
            SELECT COUNT(*) FROM turn_tool_calls tc
            JOIN session_metrics sm ON tc.session_id = sm.session_id
            WHERE sm.is_sidechain = 0 AND {where_clause}
        """).fetchone()[0]
            or 0
        )

        bash_antipatterns = (
            cur.execute(f"""
            SELECT SUM(CASE WHEN {_BASH_ANTIPATTERN_PREDICATE} THEN 1 ELSE 0 END)
            FROM turn_tool_calls tc
            JOIN session_metrics sm ON tc.session_id = sm.session_id
            WHERE sm.is_sidechain = 0 AND {where_clause}
        """).fetchone()[0]
            or 0
        )

        window_cost = 0.0
        for crow in cur.execute(f"""
            SELECT t.model,
                   SUM(t.input_tokens), SUM(t.output_tokens),
                   SUM(t.cache_read_tokens), SUM(t.cache_creation_tokens),
                   SUM(t.ephem_5m_tokens), SUM(t.ephem_1h_tokens)
            FROM turns t
            JOIN session_metrics sm ON t.session_id = sm.session_id
            WHERE sm.is_sidechain = 0 AND {where_clause}
            GROUP BY t.model
        """):
            pricing = _get_pricing(crow[0])
            window_cost += _turn_cost(
                crow[1] or 0,
                crow[2] or 0,
                crow[3] or 0,
                crow[4] or 0,
                crow[5] or 0,
                crow[6] or 0,
                pricing,
            )

        return {
            "sessions": sessions,
            "turns": turns,
            "cost_usd": round(window_cost, 2),
            "cost_per_session": round(window_cost / sessions, 2),
            "cache_ratio": cache_ratio,
            "cliffs_per_session": round(cliffs / sessions, 3),
            "antipatterns_per_session": round(bash_antipatterns / sessions, 2),
            "tool_error_rate": round(tool_errors / total_tool_calls, 4)
            if total_tool_calls
            else 0,
            "hook_avg_ms": round(hook_ms / turns, 1) if turns else 0,
        }

    current = _window_kpis("datetime(sm.first_turn_ts) >= datetime('now', '-7 days')")
    prior = _window_kpis(
        "datetime(sm.first_turn_ts) >= datetime('now', '-14 days') AND datetime(sm.first_turn_ts) < datetime('now', '-7 days')"
    )

    if not current:
        return {}

    metrics = {}
    compare_keys = [
        ("cost_per_session", "Cost/Session", True),
        ("cache_ratio", "Cache Ratio", False),
        ("cliffs_per_session", "Cache Cliffs/Session", True),
        ("antipatterns_per_session", "Bash Antipatterns/Session", True),
        ("tool_error_rate", "Tool Error Rate", True),
        ("hook_avg_ms", "Hook Avg Latency", True),
    ]

    improved = []
    regressed = []

    for key, label, lower_is_better in compare_keys:
        cur_val = current.get(key, 0)
        pri_val = prior.get(key, 0) if prior else None
        change_pct = None
        if pri_val is not None and pri_val != 0:
            change_pct = round((cur_val - pri_val) / abs(pri_val) * 100, 1)
        elif pri_val == 0 and cur_val != 0:
            change_pct = 100.0

        metrics[key] = {
            "label": label,
            "current": cur_val,
            "prior": pri_val,
            "change_pct": change_pct,
        }

        if change_pct is not None and abs(change_pct) > 5:
            got_better = (change_pct < 0) if lower_is_better else (change_pct > 0)
            if got_better:
                improved.append(f"{label}: {change_pct:+.1f}%")
            else:
                regressed.append(f"{label}: {change_pct:+.1f}%")

    # New/retired skills
    current_skills = set()
    prior_skills = set()
    for row in cur.execute("""
        SELECT tc.skill_name FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id
        WHERE sm.is_sidechain = 0 AND tc.skill_name IS NOT NULL
          AND sm.first_turn_ts >= datetime('now', '-7 days')
        GROUP BY tc.skill_name
    """):
        current_skills.add(row[0])
    for row in cur.execute("""
        SELECT tc.skill_name FROM turn_tool_calls tc
        JOIN session_metrics sm ON tc.session_id = sm.session_id
        WHERE sm.is_sidechain = 0 AND tc.skill_name IS NOT NULL
          AND sm.first_turn_ts >= datetime('now', '-14 days')
          AND sm.first_turn_ts < datetime('now', '-7 days')
        GROUP BY tc.skill_name
    """):
        prior_skills.add(row[0])
    new_skills = sorted(current_skills - prior_skills)
    retired_skills = sorted(prior_skills - current_skills)

    # New/retired hooks
    current_hooks = set()
    prior_hooks = set()
    for row in cur.execute("""
        SELECT he.hook_command FROM hook_executions he
        JOIN session_metrics sm ON he.session_id = sm.session_id
        WHERE sm.is_sidechain = 0
          AND sm.first_turn_ts >= datetime('now', '-7 days')
        GROUP BY he.hook_command
    """):
        current_hooks.add(row[0])
    for row in cur.execute("""
        SELECT he.hook_command FROM hook_executions he
        JOIN session_metrics sm ON he.session_id = sm.session_id
        WHERE sm.is_sidechain = 0
          AND sm.first_turn_ts >= datetime('now', '-14 days')
          AND sm.first_turn_ts < datetime('now', '-7 days')
        GROUP BY he.hook_command
    """):
        prior_hooks.add(row[0])
    new_hooks = sorted(current_hooks - prior_hooks)
    retired_hooks = sorted(prior_hooks - current_hooks)

    # Hook performance comparison (per-hook avg ms, current vs prior)
    hook_trends = []
    current_hook_perf = {}
    prior_hook_perf = {}
    for row in cur.execute("""
        SELECT he.hook_command, CAST(AVG(he.duration_ms) AS INT)
        FROM hook_executions he
        JOIN session_metrics sm ON he.session_id = sm.session_id
        WHERE sm.is_sidechain = 0 AND sm.first_turn_ts >= datetime('now', '-7 days')
        GROUP BY he.hook_command
    """):
        current_hook_perf[row[0]] = row[1]
    for row in cur.execute("""
        SELECT he.hook_command, CAST(AVG(he.duration_ms) AS INT)
        FROM hook_executions he
        JOIN session_metrics sm ON he.session_id = sm.session_id
        WHERE sm.is_sidechain = 0
          AND sm.first_turn_ts >= datetime('now', '-14 days')
          AND sm.first_turn_ts < datetime('now', '-7 days')
        GROUP BY he.hook_command
    """):
        prior_hook_perf[row[0]] = row[1]

    all_hooks = set(current_hook_perf) | set(prior_hook_perf)
    for h in sorted(all_hooks):
        cur_ms = current_hook_perf.get(h)
        pri_ms = prior_hook_perf.get(h)
        chg = None
        if cur_ms is not None and pri_ms is not None and pri_ms > 0:
            chg = round((cur_ms - pri_ms) / pri_ms * 100, 1)
        hook_trends.append(
            {
                "hook": h,
                "current_ms": cur_ms,
                "prior_ms": pri_ms,
                "change_pct": chg,
            }
        )

    return {
        "window_days": 7,
        "current_window": current,
        "prior_window": prior,
        "metrics": metrics,
        "improved": improved,
        "regressed": regressed,
        "new_skills": new_skills,
        "retired_skills": retired_skills,
        "new_hooks": new_hooks,
        "retired_hooks": retired_hooks,
        "hook_trends": hook_trends,
    }


# ── Insights Engine (findings + root causes + solutions) ──────────────


def _build_insights(**kw) -> list[dict]:
    """Build unified insights: finding + root cause + solution + dollar cost.

    Each insight is a complete diagnosis-to-action unit. Severity is
    rate-normalized (per-session) not absolute count.
    """
    insights = []
    sessions = kw["total_sessions"] or 1
    avg_input_rate = kw.get("avg_input_cost_per_mtok", 5.0)
    avg_output_rate = kw.get("avg_output_cost_per_mtok", 25.0)

    def _waste_usd(tokens: int, is_output: bool = False) -> float:
        rate = avg_output_rate if is_output else avg_input_rate
        return round(tokens * rate / 1_000_000, 2)

    def _severity(count: int, high_rate: float, crit_rate: float) -> str:
        rate = count / sessions
        if rate >= crit_rate:
            return "CRITICAL"
        if rate >= high_rate:
            return "WARNING"
        return "INFO"

    # ── Cache Cliffs ──
    tier = kw.get("dominant_cache_tier", "1h")
    ttl_label = "5 minutes" if tier == "5m" else "1 hour"
    if kw["cache_cliffs"] > 0:
        waste_tok = kw["cache_cliffs"] * 15000
        waste_dollars = _waste_usd(waste_tok)
        cliff_projects = kw.get("cache_cliff_projects", [])
        top_proj = cliff_projects[0] if cliff_projects else None
        root_cause = (
            f"Worst: {top_proj['project']} ({top_proj['cliffs']} cliffs across {top_proj['sessions']} sessions)"
            if top_proj
            else "Distributed across projects"
        )
        insights.append(
            {
                "title": "Cache Cliffs",
                "severity": _severity(kw["cache_cliffs"], 0.1, 0.4),
                "finding": f"{kw['cache_cliffs']} cache cliffs detected — cache_read_ratio dropped >50% "
                f"after {ttl_label}+ idle gaps.",
                "root_cause": f"When you're idle >{ttl_label}, Anthropic's prompt cache expires ({tier} tier). "
                f"The next turn re-creates the entire cache from scratch. {root_cause}.",
                "waste_tokens": waste_tok,
                "waste_usd": waste_dollars,
                "solution": {
                    "action": "Run /compact before stepping away from a session",
                    "detail": "Compacting reduces context size so cache re-creation is cheaper when you return. "
                    "For planned breaks, also consider ending the session and starting fresh.",
                    "claudemd_rule": None,
                    "estimated_savings_usd": round(waste_dollars * 0.6, 2),
                },
            }
        )

    # ── Context Pressure (max_tokens) ──
    if kw["max_token_stops"] > 0:
        waste_tok = kw["max_token_stops"] * 5000
        waste_dollars = _waste_usd(waste_tok, is_output=True)
        insights.append(
            {
                "title": "Context Pressure",
                "severity": _severity(kw["max_token_stops"], 0.02, 0.1),
                "finding": f"{kw['max_token_stops']} turns hit max_tokens — model was cut off mid-response.",
                "root_cause": "The conversation context exceeded the model's output budget. This typically "
                "happens in long sessions with many tool calls, large file reads, or when "
                "CLAUDE.md/hooks inject significant context every turn.",
                "waste_tokens": waste_tok,
                "waste_usd": waste_dollars,
                "solution": {
                    "action": "Run /compact proactively when sessions exceed ~40 turns, or split into smaller sessions",
                    "detail": "Monitor turn count. If you're doing a large refactor, break it into focused sessions "
                    "(one per file/module) rather than one marathon session.",
                    "claudemd_rule": None,
                    "estimated_savings_usd": round(waste_dollars * 0.8, 2),
                },
            }
        )

    # ── Bash Antipatterns ──
    if kw["bash_antipatterns"] > 0:
        waste_tok = kw["bash_antipatterns"] * 200
        waste_dollars = _waste_usd(waste_tok, is_output=True)
        bash_projects = kw.get("bash_antipattern_projects", [])
        top_cmds = kw.get("top_bash_antipattern_cmds", [])

        proj_detail = (
            "; ".join(f"{b['project']}: {b['antipatterns']}" for b in bash_projects[:3])
            if bash_projects
            else "unknown"
        )

        cmd_detail = (
            ", ".join(f"`{c['command'][:50]}` ({c['count']}x)" for c in top_cmds[:3])
            if top_cmds
            else "various cat/grep/find/ls calls"
        )

        tool_map = {
            "cat": "Read",
            "head": "Read (with offset+limit)",
            "tail": "Read (with offset+limit)",
            "grep": "Grep",
            "find": "Glob",
            "ls": "Glob or Bash(ls)",
        }
        suggested_rules = []
        seen_prefixes = set()
        for cmd in top_cmds[:3]:
            prefix = cmd["command"].split()[0] if cmd.get("command") else ""
            replacement = tool_map.get(prefix)
            if replacement and prefix not in seen_prefixes:
                suggested_rules.append(
                    f"Use {replacement} instead of `{prefix}` command"
                )
                seen_prefixes.add(prefix)

        insights.append(
            {
                "title": "Bash Antipatterns",
                "severity": _severity(kw["bash_antipatterns"], 0.5, 2.0),
                "finding": f"{kw['bash_antipatterns']} Bash calls use standalone cat/grep/find/ls where a "
                f"dedicated tool (Read, Grep, Glob) exists. Legitimate pipeline feeders, "
                f"existence checks, and time-sorted ls are excluded.",
                "root_cause": f"Claude is choosing Bash for standalone file reads/searches. "
                f"Top projects: {proj_detail}. Top commands: {cmd_detail}.",
                "waste_tokens": waste_tok,
                "waste_usd": waste_dollars,
                "solution": {
                    "action": "Reinforce CLAUDE.md rule for standalone tool use",
                    "detail": "Dedicated tools return structured output with fewer tokens than raw shell. "
                    "A blanket PreToolUse enforcement hook would have high false-positive rate — "
                    "pipelines, existence checks, and stat operations are legitimate Bash uses. "
                    "CLAUDE.md guidance is sufficient for standalone cases.",
                    "claudemd_rule": "\n".join(suggested_rules)
                    if suggested_rules
                    else "Use Read instead of standalone cat/head/tail. Use Grep instead of standalone grep. Use Glob instead of standalone find/ls.",
                    "estimated_savings_usd": round(waste_dollars * 0.7, 2),
                },
            }
        )

    # ── Redundant Reads ──
    if kw["redundant_reads"] > 0:
        waste_tok = kw["redundant_reads"] * 500
        waste_dollars = _waste_usd(waste_tok)
        top_files = kw.get("top_redundant_files", [])
        file_detail = (
            "; ".join(
                f"`{f['file']}` read {f['count']}x in session {f['session_id']}"
                for f in top_files[:3]
            )
            if top_files
            else "various files"
        )

        insights.append(
            {
                "title": "Redundant Reads",
                "severity": _severity(kw["redundant_reads"], 0.3, 1.0),
                "finding": f"{kw['redundant_reads']} extra file reads (same file read 3+ times in a session).",
                "root_cause": f"Claude is re-reading files it already has in context. This happens when earlier "
                f"context gets compressed away or when Claude doesn't trust its cached knowledge. "
                f"Worst offenders: {file_detail}.",
                "waste_tokens": waste_tok,
                "waste_usd": waste_dollars,
                "solution": {
                    "action": "Add a CLAUDE.md rule: 'After reading a file, reference it from context — do not re-read unless the file was modified since last read'",
                    "detail": "Each redundant read re-ingests the file as input tokens. For large files (1K+ lines) "
                    "this adds significant cost. The Read tool output note already says 'content unchanged since last read' but Claude sometimes ignores it.",
                    "claudemd_rule": "After reading a file, reference it from context. Only re-read if the file was modified since last read.",
                    "estimated_savings_usd": round(waste_dollars * 0.5, 2),
                },
            }
        )

    # ── Edit Retry Chains ──
    if kw["edit_retries"] > 0:
        waste_tok = kw["edit_retries"] * 300
        waste_dollars = _waste_usd(waste_tok, is_output=True)
        retry_projects = kw.get("edit_retry_projects", [])
        proj_detail = (
            "; ".join(f"{r['project']}: {r['retries']}x" for r in retry_projects[:3])
            if retry_projects
            else "various projects"
        )

        insights.append(
            {
                "title": "Edit Retry Chains",
                "severity": _severity(kw["edit_retries"], 0.2, 0.5),
                "finding": f"{kw['edit_retries']} failed-edit retry chains detected.",
                "root_cause": f"An Edit call fails (usually unique-match failure), then Claude retries on the same "
                f"file next turn. The failure means Claude's mental model of the file diverged from "
                f"reality — typically after a prior edit changed the file. Projects: {proj_detail}.",
                "waste_tokens": waste_tok,
                "waste_usd": waste_dollars,
                "solution": {
                    "action": "Add a CLAUDE.md rule: 'Always read a file before editing if more than 2 turns have passed since last read'",
                    "detail": "The root cause is stale context. Claude edits based on what it remembers, not "
                    "the current file state. A fresh read before each edit is cheap (~500 input tokens) "
                    "compared to the cost of a failed edit + retry (~300 output tokens wasted).",
                    "claudemd_rule": "Read file before editing if >2 turns since last read, to avoid stale-context edit failures.",
                    "estimated_savings_usd": round(waste_dollars * 0.7, 2),
                },
            }
        )

    # ── Thinking Token Overhead ──
    if kw["total_thinking"] > 0:
        pct = (
            round(kw["total_thinking"] / kw["total_output"] * 100, 1)
            if kw["total_output"]
            else 0
        )
        thinking_dollars = _waste_usd(kw["total_thinking"], is_output=True)
        insights.append(
            {
                "title": "Thinking Token Overhead",
                "severity": "INFO",
                "finding": f"~{pct}% of output tokens went to extended thinking ({kw['total_thinking'] // 1000}K tokens, "
                f"~${thinking_dollars}).",
                "root_cause": "Extended thinking is Opus's reasoning mode — it produces internal chain-of-thought "
                "tokens that are billed as output but not visible to you. This is expected for complex "
                "tasks but can be excessive for simple ones.",
                "waste_tokens": 0,
                "waste_usd": 0,
                "solution": {
                    "action": "Use Sonnet for routine tasks (file reads, simple edits, git operations) and reserve Opus for complex reasoning",
                    "detail": f"Thinking tokens cost ${thinking_dollars} at output rates. If you're using Opus for "
                    f"everything, switching routine tasks to Sonnet (which doesn't use extended thinking) "
                    f"could save 50-70% of this cost.",
                    "claudemd_rule": None,
                    "estimated_savings_usd": round(thinking_dollars * 0.3, 2),
                },
            }
        )

    # ── Idle Gap Impact ──
    tier = kw.get("dominant_cache_tier", "1h")
    ttl_label = "5 minutes" if tier == "5m" else "1 hour"
    rtd = kw["response_time_dist"]
    if tier == "5m":
        idle_over_ttl = (
            rtd.get("5m_15m", 0) + rtd.get("15m_1h", 0) + rtd.get("over_1h", 0)
        )
    else:
        idle_over_ttl = rtd.get("over_1h", 0)
    if idle_over_ttl > 0:
        total_gaps = sum(rtd.values())
        pct = round(idle_over_ttl / total_gaps * 100, 1) if total_gaps else 0
        waste_tok = idle_over_ttl * 2000
        waste_dollars = _waste_usd(waste_tok)
        insights.append(
            {
                "title": "Idle Gap Impact",
                "severity": _severity(idle_over_ttl, 0.3, 1.0),
                "finding": f"{pct}% of turns follow {ttl_label}+ idle gaps ({idle_over_ttl} of {total_gaps}).",
                "root_cause": f"Anthropic's prompt cache has a {ttl_label} TTL ({tier} tier). After "
                f"{ttl_label} of inactivity, the cached context expires and must be "
                f"re-created from scratch on the next turn.",
                "waste_tokens": waste_tok,
                "waste_usd": waste_dollars,
                "solution": {
                    "action": "Run /compact before stepping away from a session",
                    "detail": f"Compacting reduces context size so cache re-creation is cheaper when you return "
                    f"after {ttl_label}+ of inactivity. For planned breaks, also consider ending the "
                    f"session and starting fresh.",
                    "claudemd_rule": None,
                    "estimated_savings_usd": round(waste_dollars * 0.4, 2),
                },
            }
        )

    # ── Cost Concentration ──
    cost_by_project = kw.get("cost_by_project", [])
    total_cost = kw.get("total_cost_usd", 0)
    if cost_by_project and total_cost > 0:
        top = cost_by_project[0]
        top_pct = round(top["cost_usd"] / total_cost * 100, 1)
        if top_pct > 40:
            insights.append(
                {
                    "title": "Cost Concentration",
                    "severity": "INFO",
                    "finding": f"{top['project']} accounts for {top_pct}% of total spend (${top['cost_usd']:.2f} of ${total_cost:.2f}).",
                    "root_cause": "This project dominates your usage. Either it has the most sessions, uses "
                    "the most expensive model, or both. Review whether all work in this project "
                    "requires the current model tier.",
                    "waste_tokens": 0,
                    "waste_usd": 0,
                    "solution": {
                        "action": f"Audit {top['project']} sessions — could routine tasks use Sonnet instead of Opus?",
                        "detail": f"Switching from Opus ($5/$25 per MTok) to Sonnet ($3/$15 per MTok) for 50% of "
                        f"{top['project']} work would save ~${top['cost_usd'] * 0.2:.2f}.",
                        "claudemd_rule": None,
                        "estimated_savings_usd": round(top["cost_usd"] * 0.2, 2),
                    },
                }
            )

    # ── Context Overhead ──
    seg = kw.get("context_seg_summary", {})
    base_pct = seg.get("base_overhead_pct", 0)
    avg_base = seg.get("avg_base_ctx", 0)
    if base_pct > 30 and avg_base > 0:
        reducible_base = max(0, avg_base - 20000)
        waste_tok = reducible_base * sessions
        waste_dollars = _waste_usd(waste_tok)
        insights.append(
            {
                "title": "Context Overhead",
                "severity": "WARNING" if base_pct > 40 else "INFO",
                "finding": f"{base_pct}% of all context tokens are base overhead repeated every turn. "
                f"Average base context: {avg_base:,} tokens.",
                "root_cause": "Every turn rebuilds the full prompt: system instructions, tool schemas, "
                "CLAUDE.md, memory injections, skill descriptions, and MCP schemas. "
                "This base payload is cached when cache hits, but counts against rate limits "
                "and pays full price whenever cache expires.",
                "waste_tokens": waste_tok,
                "waste_usd": waste_dollars,
                "solution": {
                    "action": "Enable ENABLE_TOOL_SEARCH to defer tool schemas, trim CLAUDE.md, and disable unused skills",
                    "detail": f"Your avg base is {avg_base:,} tokens. Tool schemas typically account for 14-20K of that. "
                    f"With deferred loading + pruning unused skills, base can drop to ~20K. "
                    f"Every 1K tokens trimmed from base saves that amount on every turn of every session.",
                    "claudemd_rule": None,
                    "estimated_savings_usd": round(waste_dollars * 0.4, 2),
                },
            }
        )

    # Sort by waste (dollar) descending, with zero-waste items last
    insights.sort(key=lambda i: (i["waste_usd"] > 0, i["waste_usd"]), reverse=True)

    for i, ins in enumerate(insights):
        if i < 2:
            ins["priority"] = "P0"
        elif i < 5:
            ins["priority"] = "P1"
        else:
            ins["priority"] = "P2"

    return insights


def _insights_to_findings(insights: list[dict]) -> list[dict]:
    return [
        {
            "title": i["title"],
            "severity": i["severity"],
            "text": f"{i['finding']} {i['root_cause']}",
            "waste": i["waste_tokens"],
        }
        for i in insights
    ]


def _insights_to_recommendations(insights: list[dict]) -> list[dict]:
    return [
        {
            "text": f"{i['solution']['action']}. {i['solution']['detail']}",
            "impact": i["waste_tokens"],
            "priority": i["priority"],
        }
        for i in insights
        if i.get("solution")
    ]
