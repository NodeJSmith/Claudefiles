#!/usr/bin/env python3
"""
token_schema — Schema definitions, ensure_schema(), and version management
for the token ingest pipeline.
"""

import sqlite3
import sys
from pathlib import Path

SCHEMA_VERSION = 4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS turns (
  id                    INTEGER PRIMARY KEY,
  session_id            TEXT NOT NULL,
  turn_index            INTEGER NOT NULL,
  timestamp             TEXT NOT NULL,
  model                 TEXT,
  input_tokens          INTEGER DEFAULT 0,
  output_tokens         INTEGER DEFAULT 0,
  cache_read_tokens     INTEGER DEFAULT 0,
  cache_creation_tokens INTEGER DEFAULT 0,
  ephem_5m_tokens       INTEGER DEFAULT 0,
  ephem_1h_tokens       INTEGER DEFAULT 0,
  thinking_tokens       INTEGER DEFAULT 0,
  stop_reason           TEXT,
  turn_duration_ms      INTEGER,
  user_gap_ms           INTEGER,
  is_sidechain          INTEGER DEFAULT 0,
  cache_read_ratio      REAL,
  UNIQUE(session_id, turn_index)
);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_turns_ts ON turns(timestamp);

CREATE TABLE IF NOT EXISTS turn_tool_calls (
  id          INTEGER PRIMARY KEY,
  turn_id     INTEGER NOT NULL REFERENCES turns(id) ON DELETE CASCADE,
  session_id  TEXT NOT NULL,
  tool_name   TEXT NOT NULL,
  tool_use_id TEXT,
  file_path   TEXT,
  command     TEXT,
  is_error    INTEGER DEFAULT 0,
  error_text  TEXT,
  agent_id       TEXT,
  skill_name     TEXT,
  subagent_type  TEXT,
  agent_model    TEXT
);
CREATE INDEX IF NOT EXISTS idx_ttc_turn ON turn_tool_calls(turn_id);
CREATE INDEX IF NOT EXISTS idx_ttc_session ON turn_tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_ttc_tool ON turn_tool_calls(tool_name);
CREATE TABLE IF NOT EXISTS session_metrics (
  session_id          TEXT PRIMARY KEY,
  project_path        TEXT,
  git_branch          TEXT,
  cc_version          TEXT,
  slug                TEXT,
  entrypoint          TEXT,
  is_sidechain        INTEGER DEFAULT 0,
  parent_session_id   TEXT,
  first_turn_ts       TEXT,
  last_turn_ts        TEXT,
  turn_count          INTEGER DEFAULT 0,
  user_msg_count      INTEGER DEFAULT 0,
  total_input_tokens  INTEGER DEFAULT 0,
  total_output_tokens INTEGER DEFAULT 0,
  total_cache_read    INTEGER DEFAULT 0,
  total_cache_creation INTEGER DEFAULT 0,
  total_ephem_5m      INTEGER DEFAULT 0,
  total_ephem_1h      INTEGER DEFAULT 0,
  total_thinking      INTEGER DEFAULT 0,
  total_turn_ms       INTEGER DEFAULT 0,
  total_hook_ms       INTEGER DEFAULT 0,
  api_error_count     INTEGER DEFAULT 0,
  cache_cliff_count   INTEGER DEFAULT 0,
  tool_error_count    INTEGER DEFAULT 0,
  max_tokens_stops    INTEGER DEFAULT 0,
  uses_agent          INTEGER DEFAULT 0,
  models_used         TEXT,
  model_switch_count  INTEGER DEFAULT 0,
  imported_at         TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sm_project ON session_metrics(project_path);
CREATE INDEX IF NOT EXISTS idx_sm_ts ON session_metrics(first_turn_ts);
CREATE INDEX IF NOT EXISTS idx_sm_sidechain ON session_metrics(is_sidechain);

CREATE TABLE IF NOT EXISTS hook_executions (
  id           INTEGER PRIMARY KEY,
  session_id   TEXT NOT NULL,
  hook_command TEXT NOT NULL,
  duration_ms  INTEGER DEFAULT 0,
  is_error     INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_he_session ON hook_executions(session_id);
CREATE INDEX IF NOT EXISTS idx_he_command ON hook_executions(hook_command);

CREATE TABLE IF NOT EXISTS token_import_log (
  id INTEGER PRIMARY KEY,
  file_path TEXT UNIQUE NOT NULL,
  session_id TEXT,
  imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  turn_count INTEGER DEFAULT 0,
  mtime_ns INTEGER
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    # Ensure token_snapshots table exists (for backfill target)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS token_snapshots (
      id INTEGER PRIMARY KEY,
      session_uuid TEXT UNIQUE NOT NULL,
      project_path TEXT,
      start_time DATETIME,
      duration_minutes INTEGER,
      user_message_count INTEGER,
      assistant_message_count INTEGER,
      input_tokens INTEGER DEFAULT 0,
      output_tokens INTEGER DEFAULT 0,
      cache_read_tokens INTEGER DEFAULT 0,
      cache_creation_tokens INTEGER DEFAULT 0,
      tool_counts TEXT,
      tool_errors INTEGER DEFAULT 0,
      uses_task_agent INTEGER DEFAULT 0,
      uses_web_search INTEGER DEFAULT 0,
      uses_web_fetch INTEGER DEFAULT 0,
      user_response_times TEXT,
      lines_added INTEGER DEFAULT 0,
      lines_removed INTEGER DEFAULT 0,
      goal_categories TEXT,
      outcome TEXT,
      session_type TEXT,
      friction_counts TEXT,
      brief_summary TEXT,
      imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # Add data_source column if missing
    for col, typedef in [
        ("data_source", "TEXT"),
        ("cache_read_tokens", "INTEGER DEFAULT 0"),
        ("cache_creation_tokens", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE token_snapshots ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError:
            pass
    # Add new workflow-analytics columns if missing (v2 schema)
    for col, typedef in [
        ("skill_name", "TEXT"),
        ("subagent_type", "TEXT"),
        ("agent_model", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE turn_tool_calls ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError:
            pass
    # Create indexes for new columns (safe after ALTER TABLE)
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_ttc_skill ON turn_tool_calls(skill_name)",
        "CREATE INDEX IF NOT EXISTS idx_ttc_subagent ON turn_tool_calls(subagent_type)",
    ]:
        conn.execute(idx_sql)
    # Schema version tracking + auto re-import on upgrade
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    current = row[0] if row else 0
    if current < SCHEMA_VERSION:
        print(
            f"Schema upgraded to v{SCHEMA_VERSION} — full re-import required",
            file=sys.stderr,
        )
        conn.execute("DELETE FROM token_import_log")
        if current == 0:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )
        else:
            conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    conn.commit()


def connect_token_db(db_path: Path) -> sqlite3.Connection:
    """Open a connection to the token analytics database with standard PRAGMAs."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
