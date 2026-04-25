#!/usr/bin/env python3
"""
token_parser — JSONL parsing, data classes, session parsing, and file discovery
for the token ingest pipeline.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"

BATCH_SIZE = 50
PROGRESS_INTERVAL = 100
COMMAND_TRUNCATE = 200

# SQL fragment: true Bash antipatterns — standalone cat/grep/find/ls that have
# a dedicated tool equivalent. Excludes legitimate patterns:
#   - cat <<EOF / cat > file  (heredoc/write — no Write-tool equivalent via stdin)
#   - cat file | ...          (pipe feeder — intent is the downstream command)
#   - ls -l / ls -la / ls -lt (stat/time-sort — Glob can't do this)
#   - ls ... 2>/dev/null      (existence check — conditional shell pattern)
#   - ls ... || / ls ... &&   (conditional existence — shell idiom)
#   - head/tail ... | ...     (pipe terminator — legit pipeline use)
_BASH_ANTIPATTERN_PREDICATE = """
    tc.tool_name = 'Bash' AND (
        tc.command LIKE 'cat %' OR tc.command LIKE 'head %' OR
        tc.command LIKE 'tail %' OR tc.command LIKE 'grep %' OR
        tc.command LIKE 'find %' OR tc.command LIKE 'ls %'
    )
    AND tc.command NOT LIKE 'cat <<%'
    AND tc.command NOT LIKE 'cat >%'
    AND tc.command NOT LIKE 'cat % | %'
    AND tc.command NOT LIKE 'ls -l%'
    AND tc.command NOT LIKE 'ls -[Ralt]%'
    AND tc.command NOT LIKE 'ls %2>/dev/null%'
    AND tc.command NOT LIKE 'ls %||%'
    AND tc.command NOT LIKE 'ls %&&%'
    AND tc.command NOT LIKE 'head % | %'
    AND tc.command NOT LIKE 'tail % | %'
""".strip()

# ── Pricing (USD per million tokens) ─────────────────────────────────
# Source: https://docs.anthropic.com/en/docs/about-claude/pricing
# Keys are substrings matched against model IDs (checked in order).
# cache_write_5m = 1.25x input, cache_write_1h = 2x input, cache_read = 0.1x input.

MODEL_PRICING: list[tuple[str, dict[str, float]]] = [
    (
        "opus-4-6",
        {
            "input": 5.0,
            "output": 25.0,
            "cache_write_5m": 6.25,
            "cache_write_1h": 10.0,
            "cache_read": 0.50,
        },
    ),
    (
        "opus-4-5",
        {
            "input": 5.0,
            "output": 25.0,
            "cache_write_5m": 6.25,
            "cache_write_1h": 10.0,
            "cache_read": 0.50,
        },
    ),
    (
        "opus-4-1",
        {
            "input": 15.0,
            "output": 75.0,
            "cache_write_5m": 18.75,
            "cache_write_1h": 30.0,
            "cache_read": 1.50,
        },
    ),
    (
        "opus-4",
        {
            "input": 15.0,
            "output": 75.0,
            "cache_write_5m": 18.75,
            "cache_write_1h": 30.0,
            "cache_read": 1.50,
        },
    ),
    (
        "sonnet",
        {
            "input": 3.0,
            "output": 15.0,
            "cache_write_5m": 3.75,
            "cache_write_1h": 6.0,
            "cache_read": 0.30,
        },
    ),
    (
        "haiku",
        {
            "input": 1.0,
            "output": 5.0,
            "cache_write_5m": 1.25,
            "cache_write_1h": 2.0,
            "cache_read": 0.10,
        },
    ),
]


def _get_pricing(model: str | None) -> dict[str, float]:
    """Return pricing dict for a model ID, falling back to Sonnet rates."""
    if model:
        m = model.lower()
        for substr, rates in MODEL_PRICING:
            if substr in m:
                return rates
    return MODEL_PRICING[4][1]  # default: sonnet


def _turn_cost(
    input_tok: int,
    output_tok: int,
    cache_read: int,
    cache_creation: int,
    ephem_5m: int,
    ephem_1h: int,
    pricing: dict[str, float],
) -> float:
    """Compute dollar cost for a single turn."""
    # Cache creation split: use exact tier amounts where available,
    # attribute remainder to 5m tier (cheaper, conservative estimate).
    unclassified_creation = max(0, cache_creation - ephem_5m - ephem_1h)
    cost = (
        input_tok * pricing["input"]
        + output_tok * pricing["output"]
        + cache_read * pricing["cache_read"]
        + (ephem_5m + unclassified_creation) * pricing["cache_write_5m"]
        + ephem_1h * pricing["cache_write_1h"]
    ) / 1_000_000
    return cost


# ── File Discovery ────────────────────────────────────────────────────


@dataclass
class JnlFile:
    path: Path
    project_cwd: str
    is_sidechain: bool
    parent_session_id: str | None


def _decode_project_cwd(dirname: str) -> str:
    """Convert '-Users-samarthgupta-repos-foo' to '/Users/samarthgupta/repos/foo'.

    Detects Windows drive letter pattern (e.g. 'C-Users-...' → 'C:/Users/...').
    """
    parts = dirname.lstrip("-").replace("-", "/")
    # Windows drive letter: single letter followed by /
    if len(parts) >= 2 and parts[0].isalpha() and parts[1] == "/":
        return parts[0].upper() + ":/" + parts[2:].lstrip("/")
    return "/" + parts.lstrip("/")


def discover_jsonl_files() -> list[JnlFile]:
    results: list[JnlFile] = []
    if not PROJECTS_DIR.exists():
        return results
    for proj_dir in PROJECTS_DIR.iterdir():
        if not proj_dir.is_dir():
            continue
        project_cwd = _decode_project_cwd(proj_dir.name)
        # Top-level session files
        for jf in proj_dir.glob("*.jsonl"):
            results.append(JnlFile(jf, project_cwd, False, None))
        # Subagent files
        for jf in proj_dir.glob("*/subagents/*.jsonl"):
            parent_id = jf.parent.parent.name  # the session UUID directory
            results.append(JnlFile(jf, project_cwd, True, parent_id))
    return results


def should_skip_file(conn: sqlite3.Connection, filepath: Path) -> bool:
    try:
        mtime_ns = filepath.stat().st_mtime_ns
    except OSError:
        return True
    cur = conn.execute(
        "SELECT mtime_ns FROM token_import_log WHERE file_path = ?", (str(filepath),)
    )
    row = cur.fetchone()
    if row and row[0] == mtime_ns:
        return True
    return False


def record_import(
    conn: sqlite3.Connection, filepath: Path, session_id: str, turn_count: int
) -> None:
    mtime_ns = filepath.stat().st_mtime_ns
    conn.execute(
        """INSERT OR REPLACE INTO token_import_log (file_path, session_id, imported_at, turn_count, mtime_ns)
           VALUES (?, ?, datetime('now'), ?, ?)""",
        (str(filepath), session_id, turn_count, mtime_ns),
    )


# ── JSONL Parser ──────────────────────────────────────────────────────


@dataclass
class ToolCall:
    tool_name: str
    tool_use_id: str
    file_path: str | None = None
    command: str | None = None
    is_error: int = 0
    error_text: str | None = None
    agent_id: str | None = None
    skill_name: str | None = None
    subagent_type: str | None = None
    agent_model: str | None = None


@dataclass
class Turn:
    index: int
    message_id: str
    timestamp: str
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    ephem_5m_tokens: int = 0
    ephem_1h_tokens: int = 0
    thinking_tokens: int = 0
    stop_reason: str | None = None
    turn_duration_ms: int | None = None
    user_gap_ms: int | None = None
    cache_read_ratio: float | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Pending tool_use IDs awaiting results
    _pending_tools: dict[str, ToolCall] = field(default_factory=dict)


@dataclass
class ParsedSession:
    session_id: str
    project_path: str | None = None
    git_branch: str | None = None
    cc_version: str | None = None
    slug: str | None = None
    entrypoint: str | None = None
    turns: list[Turn] = field(default_factory=list)
    user_msg_count: int = 0
    api_error_count: int = 0
    total_hook_ms: int = 0
    uses_agent: bool = False
    hook_calls: list[dict] = field(default_factory=list)


def _parse_timestamp(line: dict) -> str | None:
    return line.get("timestamp")


def _extract_usage(msg: dict) -> dict:
    usage = msg.get("usage", {}) or {}
    cache_creation = usage.get("cache_creation", {}) or {}
    return {
        "input_tokens": usage.get("input_tokens", 0) or 0,
        "output_tokens": usage.get("output_tokens", 0) or 0,
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0) or 0,
        "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0) or 0,
        "ephem_5m_tokens": cache_creation.get("ephemeral_5m_input_tokens", 0) or 0,
        "ephem_1h_tokens": cache_creation.get("ephemeral_1h_input_tokens", 0) or 0,
    }


def parse_session(filepath: Path, jnl: JnlFile) -> ParsedSession | None:
    session = ParsedSession(session_id="", project_path=jnl.project_cwd)

    current_turn: Turn | None = None
    turn_index = 0
    last_assistant_ts: str | None = None
    metadata_captured = False

    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None

    for raw_line in lines:
        if not raw_line.strip():
            continue
        try:
            line = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        line_type = line.get("type")
        subtype = line.get("subtype", "")
        ts = _parse_timestamp(line)

        # Capture session metadata from any line that has it
        if not metadata_captured:
            sid = line.get("sessionId")
            if sid:
                session.session_id = sid
                metadata_captured = True
        if line.get("sessionId") and not session.session_id:
            session.session_id = line["sessionId"]
        if line.get("version") and not session.cc_version:
            session.cc_version = line["version"]
        if line.get("slug") and not session.slug:
            session.slug = line["slug"]
        if line.get("entrypoint") and not session.entrypoint:
            session.entrypoint = line["entrypoint"]
        # Take LAST observed branch (can change mid-session)
        if line.get("gitBranch"):
            session.git_branch = line["gitBranch"]

        # ── Assistant events (grouped by message.id) ──
        if line_type == "assistant":
            msg = line.get("message", {}) or {}
            mid = msg.get("id", "")
            if not mid:
                continue

            # Same logical turn?
            if current_turn and current_turn.message_id == mid:
                # Merge: accumulate tool_use blocks, update usage to latest
                pass
            else:
                # Finalize previous turn
                if current_turn:
                    session.turns.append(current_turn)
                # Start new turn
                turn_index += 1
                current_turn = Turn(
                    index=turn_index,
                    message_id=mid,
                    timestamp=ts or "",
                    model=msg.get("model"),
                )
                # Compute user gap from last assistant finish
                if last_assistant_ts and ts:
                    try:
                        prev = datetime.fromisoformat(
                            last_assistant_ts.replace("Z", "+00:00")
                        )
                        curr = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        current_turn.user_gap_ms = int(
                            (curr - prev).total_seconds() * 1000
                        )
                    except (ValueError, TypeError):
                        pass

            # Always update usage from the latest event for this message.id
            u = _extract_usage(msg)
            current_turn.input_tokens = u["input_tokens"]
            current_turn.output_tokens = u["output_tokens"]
            current_turn.cache_read_tokens = u["cache_read_tokens"]
            current_turn.cache_creation_tokens = u["cache_creation_tokens"]
            current_turn.ephem_5m_tokens = u["ephem_5m_tokens"]
            current_turn.ephem_1h_tokens = u["ephem_1h_tokens"]

            stop = msg.get("stop_reason")
            if stop:
                current_turn.stop_reason = stop

            if msg.get("model"):
                current_turn.model = msg["model"]

            # Extract content blocks
            content = msg.get("content", []) or []
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")

                if btype == "thinking":
                    # Count thinking text length as proxy (actual token count not in JSONL)
                    thinking_text = block.get("thinking", "")
                    # Rough estimate: 1 token ≈ 4 chars
                    current_turn.thinking_tokens += len(thinking_text) // 4

                elif btype == "tool_use":
                    tc = ToolCall(
                        tool_name=block.get("name", "unknown"),
                        tool_use_id=block.get("id", ""),
                    )
                    inp = block.get("input", {}) or {}
                    # Extract file_path from various tool input formats
                    tc.file_path = (
                        inp.get("file_path")
                        or inp.get("path")
                        or inp.get("file")
                        or None
                    )
                    if "command" in inp:
                        tc.command = str(inp["command"])[:COMMAND_TRUNCATE]

                    # Extract workflow-specific metadata
                    if tc.tool_name == "Skill":
                        raw_skill = inp.get("skill") or None
                        # Normalize: strip "claude-<plugin>:" prefix so
                        # "claude-memory:recall-conversations" and "recall-conversations"
                        # count as the same skill. Guard: only strip when prefix matches
                        # "claude-*:" to preserve third-party namespaces like
                        # "visual-explainer:generate-web-diagram".
                        if raw_skill and ":" in raw_skill:
                            prefix, _, bare = raw_skill.partition(":")
                            if prefix.startswith("claude-"):
                                raw_skill = bare
                        tc.skill_name = raw_skill
                    elif tc.tool_name == "Agent":
                        session.uses_agent = True
                        tc.subagent_type = inp.get("subagent_type") or None
                        tc.agent_model = inp.get("model") or None
                        # Store agent description as command if no command set
                        if not tc.command:
                            desc = inp.get("description") or ""
                            if desc:
                                tc.command = str(desc)[:COMMAND_TRUNCATE]

                    current_turn.tool_calls.append(tc)
                    current_turn._pending_tools[tc.tool_use_id] = tc

        # ── User events ──
        elif line_type == "user":
            session.user_msg_count += 1

            msg = line.get("message", {}) or {}
            content = msg.get("content", []) or []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    tuid = block.get("tool_use_id", "")
                    is_err = block.get("is_error", False)
                    # Match to pending tool call (pop to avoid re-matching)
                    if current_turn:
                        tc = current_turn._pending_tools.pop(tuid, None)
                        if tc:
                            tc.is_error = 1 if is_err else 0
                            if is_err:
                                # Extract error text
                                result_content = block.get("content", "")
                                if isinstance(result_content, list):
                                    texts = [
                                        c.get("text", "")
                                        for c in result_content
                                        if isinstance(c, dict)
                                    ]
                                    result_content = " ".join(texts)
                                tc.error_text = (
                                    str(result_content)[:200]
                                    if result_content
                                    else None
                                )

        # ── System events ──
        elif line_type == "system":
            if subtype == "turn_duration":
                duration_ms = line.get("durationMs")
                if duration_ms is not None and current_turn:
                    current_turn.turn_duration_ms = duration_ms
                    if ts:
                        last_assistant_ts = ts
            elif subtype in ("stop_hook_summary", "hook_summary"):
                hook_infos = line.get("hookInfos", []) or []
                hook_errors = line.get("hookErrors", []) or []
                error_commands = {
                    e.get("command") for e in hook_errors if isinstance(e, dict)
                }
                for h in hook_infos:
                    dur = h.get("durationMs", 0) or 0
                    session.total_hook_ms += dur
                    cmd = h.get("command") or h.get("hook_command") or "unknown"
                    session.hook_calls.append(
                        {
                            "hook_command": str(cmd)[:COMMAND_TRUNCATE],
                            "duration_ms": dur,
                            "is_error": 1 if cmd in error_commands else 0,
                        }
                    )
            elif subtype == "api_error":
                session.api_error_count += 1

        # Skip: progress, file-history-snapshot, local_command, etc.

    # Finalize last turn
    if current_turn:
        session.turns.append(current_turn)

    if not session.session_id:
        # Derive from filename
        session.session_id = filepath.stem

    # Subagent JSONL files inherit the parent's sessionId — use the filename
    # as a unique ID to avoid overwriting the parent session's data.
    if jnl.is_sidechain:
        session.session_id = filepath.stem

    return session if session.turns else None


# ── Session Analytics ─────────────────────────────────────────────────


def _detect_cache_ttl_ms(session: ParsedSession) -> tuple[int, str]:
    """Detect the dominant cache tier from ephemeral token data.

    Returns (ttl_ms, tier_label).  Falls back to 1h when no tier
    breakdown is available (the common case for Claude Code JSONL).
    """
    total_5m = sum(t.ephem_5m_tokens for t in session.turns)
    total_1h = sum(t.ephem_1h_tokens for t in session.turns)
    if total_5m > 0 or total_1h > 0:
        if total_5m > total_1h:
            return 300_000, "5m"
        return 3_600_000, "1h"
    # No tier breakdown — default to 5m (Claude Code switched to ephemeral_5m ~Apr 3 2026)
    return 300_000, "5m"


def compute_session_analytics(session: ParsedSession) -> dict:
    """Compute cache cliffs, max_tokens stops, model switches."""
    cache_cliff_count = 0
    max_tokens_stops = 0
    model_switch_count = 0
    prev_model = None
    prev_cache_ratio = None

    models_seen: list[str] = []
    total_turn_ms = 0
    total_tool_errors = 0

    cache_ttl_ms, _ = _detect_cache_ttl_ms(session)

    for turn in session.turns:
        # Cache cliff detection
        denom = turn.cache_read_tokens + turn.cache_creation_tokens
        ratio = turn.cache_read_tokens / denom if denom > 0 else None
        turn.cache_read_ratio = ratio

        if ratio is not None and prev_cache_ratio is not None:
            drop = prev_cache_ratio - ratio
            if drop > 0.5 and turn.user_gap_ms and turn.user_gap_ms > cache_ttl_ms:
                cache_cliff_count += 1
        if ratio is not None:
            prev_cache_ratio = ratio

        # Max tokens stops
        if turn.stop_reason == "max_tokens":
            max_tokens_stops += 1

        # Model switches
        if turn.model:
            if prev_model and turn.model != prev_model:
                model_switch_count += 1
            prev_model = turn.model
            if turn.model not in models_seen:
                models_seen.append(turn.model)

        # Accumulate
        if turn.turn_duration_ms:
            total_turn_ms += turn.turn_duration_ms
        for tc in turn.tool_calls:
            if tc.is_error:
                total_tool_errors += 1

    return {
        "cache_cliff_count": cache_cliff_count,
        "max_tokens_stops": max_tokens_stops,
        "model_switch_count": model_switch_count,
        "models_used": models_seen,
        "total_turn_ms": total_turn_ms,
        "tool_error_count": total_tool_errors,
    }


# ── Helpers ───────────────────────────────────────────────────────────


def _project_slug(path: str | None) -> str:
    """Build a short but unique project label from the full path.

    Uses the last 2-3 meaningful path segments, skipping common prefixes
    like /Users/<user>/repos/*, to produce labels like 'meta-ads-cli'
    instead of just 'cli'.
    """
    if not path:
        return "unknown"
    path = path.rstrip("/")
    parts = path.split("/")
    # Drop common path prefixes to find the meaningful suffix
    # e.g. /Users/samarthgupta/repos/forks/meta/ads/cli → meta/ads/cli
    skip_prefixes = {"Users", "home", "repos", "myrepos", "forks", "projects"}
    meaningful = []
    for p in parts:
        if not p or p in skip_prefixes or p.startswith("."):
            continue
        # Skip the username segment (first non-empty after /Users/)
        if len(meaningful) == 0 and len(parts) > 3 and parts[1] in ("Users", "home"):
            # This is the username — skip it
            if p == parts[2]:
                continue
        meaningful.append(p)
    # Take last 2-3 segments depending on length
    if len(meaningful) <= 2:
        slug = "-".join(meaningful) if meaningful else "unknown"
    else:
        slug = "-".join(meaningful[-3:])
    # Cap length for chart labels
    return slug[:30] if slug else "unknown"
