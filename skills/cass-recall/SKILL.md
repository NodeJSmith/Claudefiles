---
name: cass-recall
description: "Use when the user says: \"what did we discuss\", \"continue where we left off\", \"remember when\", \"as I mentioned\", \"you suggested\", \"we decided\", \"search my conversations\", \"find the conversation where\", \"what did we work on\", or uses implicit signals like past-tense references, possessives without context, or assumptive questions. Direct search over past Claude Code sessions via cass."
user-invocable: true
---

# Recall

Direct search over past Claude Code (and other agent) sessions, backed by `cass` (coding_agent_session_search) — a Rust search engine with HNSW approximate nearest-neighbor search and Tantivy BM25 lexical search. No lens taxonomy: this is the plain "find it and tell me" path.

## Tools

`cass search "<query>" --robot` — the only command this skill needs. `--robot` suppresses cass's interactive TUI and emits structured JSON instead; without it, cass launches a full-screen terminal UI that isn't useful here.

```bash
cass search "rate limiting middleware" --robot --limit 10
```

**Key flags:**

| Flag | Effect |
|---|---|
| `--workspace <path>` | Scope results to a project directory (use `"$(pwd)"` for "this project") |
| `--days <n>` | Lookback window in days |
| `--limit <n>` | Max results returned |
| `--fields minimal` | Compact output — fewer fields per hit, faster to parse |
| `--agent claude` | Filter to Claude Code sessions only (cass indexes 22+ agent providers) |

**Output format** — a JSON envelope:

```json
{
  "count": 4,
  "hits": [
    {
      "source_path": "/home/user/.claude/projects/.../abc123.jsonl",
      "agent": "claude",
      "score": 0.87,
      "snippet": "...matched excerpt...",
      "workspace": "/home/user/myproject",
      "title": "..."
    }
  ]
}
```

Not every field is guaranteed on every hit (especially under `--fields minimal`) — read what's present and degrade gracefully when a field is missing.

## Workflow

1. **Extract content-bearing keywords** from the user's query — specific nouns, technologies, project names, unique phrases. Drop generic verbs ("discuss", "talk"), time markers ("yesterday"), vague nouns ("thing", "stuff"), and meta-conversation words ("conversation", "chat") — these appear in nearly every session and add noise, not signal.

2. **Run the search:**
   ```bash
   cass search "<keywords>" --robot --limit 10
   ```

3. **Scope when it helps:**
   - Project-specific: add `--workspace "$(pwd)"`
   - Recent-only: add `--days 30`
   - Combine both when the user's ask implies "here, recently"

4. **Deepen if results are thin.** If the first pass returns few or clearly irrelevant hits, try a second pass with adjusted keywords (broader terms, or a specific phrase that surfaced from a partial match) before giving up. Two rounds is enough — synthesize from whatever you have rather than looping indefinitely.

5. **Read into a hit when needed.** A `source_path` is a real Claude Code (or other agent) transcript JSONL on disk — read it directly with the Read tool to pull more context than the snippet gives.

## Synthesis

Structure the response as:

```markdown
### Summary
[2-3 sentences]

### Findings
[3-5 key findings, organized by relevance — each specific: file paths, dates, project names]

### Recommendations
[Actionable next steps]
```

Default 300-500 words. Expand only when the data genuinely warrants it. Every finding should be actionable, not just descriptive — if a finding surfaces a past decision or approach, say what it implies for the current ask.

If the search returns no relevant hits, say so plainly rather than padding with generic findings to reach the 3-5 target.
