# claude-memory

Persistent conversation memory for Claude Code. Stores your Claude sessions in a local SQLite database so you can recall past conversations, search across them, and get automatic context on session start.

## What it does

Every time you end a Claude Code session, the conversation is synced to `~/.claude-memory/conversations.db`. On your next session start, Claude automatically gets a summary of what you were last working on. You can also search past sessions by keyword or pull recent ones at any time.

## Install

```bash
uv tool install -e packages/claude-memory
```

The hooks are wired in `settings.json` with graceful degradation — they silently no-op if the package isn't installed, so nothing breaks for users who skip this step.

## First-run setup

On your first session after installing, Claude will notice that `~/.claude-memory/config.json` doesn't exist and walk you through a brief onboarding. It will ask one question:

1. **Session context injection** — should Claude automatically recall what you were working on last session?

Your choice gets written to `~/.claude-memory/config.json`. You can edit that file directly at any time to change settings.

To skip the walkthrough and use recommended defaults immediately:

```bash
cm-write-config --defaults
```

## Semantic search

Search results are fused from two signals: keyword full-text search (FTS5 → FTS4 → LIKE fallback) and vector similarity from a locally-running embedding model. The two ranked lists are merged with Reciprocal Rank Fusion (RRF), so results that rank well in both signals appear first.

The embedding model is [bge-m3 (int8-quantized ONNX)](https://huggingface.co/gpahal/bge-m3-onnx-int8), running entirely on your machine via onnxruntime. No data leaves your machine.

### One-time backfill

After installing, run the backfill once to embed your existing conversations:

```bash
cm-backfill-embeddings
```

This takes roughly 20 minutes for a large history (~10k branches). Progress is printed to stderr (one line per batch). Subsequent runs are fast — only unembedded branches are processed.

### Flags

| Flag | Effect |
|------|--------|
| `--keyword-only` | Skip the embedding step entirely, use keyword search only |
| `--status` | Print diagnostic info (vec extension loaded, model path, embedded vs. total summarized (embeddable) branch count) and exit 0 |

### Runtime deps

The semantic search path requires four extra packages beyond the base install:

- `sqlite-vec` — SQLite extension for vector KNN queries
- `onnxruntime` — runs the ONNX embedding model
- `tokenizers` — tokenizes text before embedding
- `numpy` — vector math (normalization)

These are included in the package dependencies. If onnxruntime or tokenizers fail to import (e.g. ABI mismatch on an unusual platform), search falls back silently to keyword-only mode.

### Degradation

Semantic fusion is automatically disabled when:
- The model snapshot is not present (`~/.cache/huggingface/hub/models--gpahal--bge-m3-onnx-int8/`)
- `onnxruntime` or `tokenizers` cannot be imported
- `sqlite-vec` cannot be loaded on the connection (e.g. Python built without loadable extensions)

In all cases, search falls back to keyword-only and returns results normally. Use `cm-search-conversations --status` to check which path is active.

## Entry points

### Hooks (run automatically — don't call these manually)

These are wired into `settings.json` and fire on their respective Claude Code events.

| Entry point | Event | What it does |
|---|---|---|
| `cm-memory-setup` | SessionStart | Creates `~/.claude-memory/` if needed, opens the DB to apply any pending migrations, then spawns `cm-import-conversations` and `cm-backfill-summaries` as background processes |
| `cm-onboarding` | SessionStart (startup only) | One-time first-run onboarding. Injects setup instructions into Claude's context if `config.json` is missing or onboarding hasn't been completed. Silent no-op after that |
| `cm-memory-context` | SessionStart (startup + clear) | Injects a summary of your most recent session into Claude's context so it knows what you were working on. On `/clear`, reads a handoff file to link directly to the session you just cleared from |
| `cm-clear-handoff` | SessionEnd (clear only) | Writes a small handoff file so the next session start knows which session to link to after a `/clear`. Without this, context injection falls back to "most recent session" heuristic |
| `cm-memory-sync` | Stop | Syncs the current session to the DB in a detached background process. Runs on every session end |

### Internal helpers (spawned by hooks — don't call these manually)

| Entry point | What it does |
|---|---|
| `cm-sync-current` | Syncs a single session file to the DB. Called by `cm-memory-sync` with the session ID from stdin |
| `cm-import-conversations` | Full import of all JSONL files in `~/.claude/projects/`. Skips files that haven't changed since last import (file hash check). Run on first install and whenever new sessions need backfilling |
| `cm-backfill-summaries` | Generates context summaries for any DB branches that don't have one yet. Runs in the background after `cm-memory-setup` |
| `cm-backfill-embeddings` | Embeds all un-embedded branches using bge-m3 (int8 ONNX). Run once after first install; subsequent runs skip already-embedded branches |
| `cm-write-config` | Writes `~/.claude-memory/config.json`. Called by Claude during onboarding to persist your settings choices. You can also call it directly — run `cm-write-config --help` for flags |

### Skill CLIs (called from skill files — can also be used directly)

These are the entry points that the `cm-*` skills invoke. You can run them from the terminal too.

| Entry point | What it does |
|---|---|
| `cm-recent-chats` | Prints recent sessions from the DB in markdown (default) or JSON. Used by `/cm-recall-conversations` |
| `cm-search-conversations` | Searches sessions by keyword fused with vector similarity (FTS5 → FTS4 → LIKE fallback, RRF-fused with bge-m3 embeddings when available). Used by `/cm-recall-conversations` |
| `cm-ingest-token-data` | Parses JSONL files for token usage analytics — cost, cache hits, model mix, skill/agent/hook patterns. Populates analytics tables and builds `~/.claude-memory/dashboard.html`. Used by `/cm-get-token-insights` |

## Skills

| Skill | Trigger | What it does |
|---|---|---|
| `/cm-recall-conversations` | "what did we discuss", "continue where we left off", "search my conversations" | Lets Claude search or browse your past sessions on demand |
| `/cm-get-token-insights` | "analyze Claude token usage", "how much am I spending on Claude" | Full cost + workflow analytics report with an interactive HTML dashboard |

## Data flow

```
Session ends
  └─ cm-memory-sync (Stop hook)
       └─ cm-sync-current (background)
            └─ writes to ~/.claude-memory/conversations.db
            └─ embeds branch via bge-m3 if model available (drops silently on failure)

Session starts
  └─ cm-memory-setup (SessionStart)
  │    └─ cm-import-conversations (background, first run / new files)
  │         └─ embeds each new branch via bge-m3 if model available
  │    └─ cm-backfill-summaries (background, if summaries missing)
  ├─ cm-onboarding (SessionStart, startup only — one-time)
  └─ cm-memory-context (SessionStart, startup + clear)
       └─ injects last session summary into Claude's context
```

## Config file

`~/.claude-memory/config.json` — written by `cm-write-config` during onboarding:

```json
{
  "onboarding_completed": true,
  "onboarding_version": 1,
  "auto_inject_context": true
}
```

## Database

`~/.claude-memory/conversations.db` — SQLite, WAL mode. Schema v3:

- `sessions` — one row per conversation session
- `branches` — one row per conversation branch (rewinding creates new branches)
- `messages` — all messages, stored once per session regardless of branch
- `branch_messages` — join table linking messages to branches
- `import_log` — tracks which JSONL files have been imported and their hashes
- `branch_vec` — vec0 virtual table (sqlite-vec) storing 1024-dim bge-m3 embeddings for each branch, used for KNN search
- `token_snapshots`, `turns`, `turn_tool_calls`, `session_metrics` — analytics tables populated by `cm-ingest-token-data`

## Running tests

```bash
uv run --group dev pytest
```
