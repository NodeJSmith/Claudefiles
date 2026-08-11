---
task_id: "T05"
title: "Update documentation and roadmap"
status: "done"
depends_on: ["T04"]
implements: ["FR#2"]
---

## Summary

Update REFERENCE.md, ONBOARDING.md, and the OpenCode integration roadmap to reflect the Python rewrite, the new `--lint-only` flag, the config.json/opencode.jsonc split, worker agent mechanism, and the SQLite verification query. Mark Spec 2 complete and Spec 3 partially complete in the roadmap.

## Target Files

- modify: `REFERENCE.md` — update the `opencode-sync` entry, add SQLite verification query
- modify: `ONBOARDING.md` — update OpenCode support section
- modify: `design/opencode-integration-roadmap.md` — mark Spec 2 complete, Spec 3 partially complete

## Prompt

### REFERENCE.md

Find the `opencode-sync` entry in the bin scripts table (currently at line 239). Replace it with an updated description reflecting:

- Python rewrite (no longer bash)
- New capabilities: dispatch rewriting (not just model name remapping), worker agent generation, `config.json` generation with model enforcement, compatibility lint
- Updated CLI flags: `--dry-run`, `--verbose`, `--allow-worktree`, `--check`, `--lint-only` (new)
- Still not wired into `install.py`
- Reference to the roadmap for remaining work

Add a new section or entry documenting the SQLite child-session verification query. **Before documenting, verify the actual schema** by running `sqlite3 ~/.local/share/opencode/opencode.db '.schema sessions' '.schema agents'` (or equivalent) — the column names below are provisional and must be confirmed against the real database. The query is run manually after exercising a workflow to verify model routing:

```sql
-- Run against ~/.local/share/opencode/opencode.db
-- Open with PRAGMA busy_timeout = 5000 to avoid lock contention
-- IMPORTANT: verify column names against actual schema before documenting
SELECT s.id, s.model_id, a.name as agent_name
FROM sessions s
LEFT JOIN agents a ON s.agent_id = a.id
WHERE s.parent_id IS NOT NULL
ORDER BY s.created_at DESC
LIMIT 20;
```

Document this as a manual verification step, not an automated sync subcommand. If the real schema differs from the query above, update the query to match before writing it into REFERENCE.md.

### ONBOARDING.md

Find the OpenCode support paragraph (currently at line 205). Update it to reflect:

- `opencode-sync` now generates worker agents and a `config.json` that enforces model routing
- The config.json/opencode.jsonc split — generated config vs user-managed config
- Dispatch rewriting converts Claude Code dispatch patterns to OpenCode-native equivalents
- `--lint-only` checks for residual Claude-only constructs
- After the first sync with the new version, remove the manual `agent` block from `opencode.jsonc` if present (the July 30 quick-fix pins are now superseded by `config.json`)
- Still provisional — roadmap Specs 3-5 remain

### Roadmap

In `design/opencode-integration-roadmap.md`:

1. Under Spec 2 (### 2. Native Agents and Model Enforcement), add a completion note at the end of the scope list: `**Status: Complete** — shipped in PR #<N> (opencode-sync Python rewrite with worker agents, config.json model enforcement, dispatch rewriter, and compatibility lint). Two originally-scoped items were dropped: permission.task allowlists (FR#8 removed — blanket allow in opencode.jsonc makes per-agent gating inert) and deprecated tool declaration replacement (no applicable declarations identified).` Leave the PR number as `#<N>` — it will be filled in at PR creation time.

2. Under Spec 3 (### 3. Skill Compatibility Adapter), add a partial completion note: `**Status: Partially complete** — dispatch rewriting and the compatibility lint shipped in the Spec 2 PR. Remaining: interactive question syntax conversion, vertical-slice-first validation, and skill classification as portable/adapter-required/harness-specific.`

### FR#2 documentation coverage

The REFERENCE.md update must document `config.json` content and the `subagent_depth` setting — a user reading REFERENCE.md should understand what `config.json` contains and why.

## Focus

- The current REFERENCE.md entry for `opencode-sync` is a single table row. The updated entry will be longer — consider whether it still fits in the table format or should be split into a table entry plus a subsection. Follow whatever pattern the file uses for other complex entries.
- The SQLite query documentation belongs in REFERENCE.md near the `opencode-sync` entry, as a "Verification" subsection or similar. It's a manual step, not a sync subcommand.
- The ONBOARDING.md paragraph is dense. Keep it concise but accurate — new users need to understand the two-file config split and that `opencode.jsonc` wins on conflicts.
- The roadmap uses a consistent format for scope lists under each spec. Follow the existing style for the completion notes.
- Do not add CHANGELOG entries — those are added at PR creation time per the workflow conventions.

## Verify

- [ ] FR#2: REFERENCE.md documents config.json content including `subagent_depth` and the SQLite verification query (verifiable: `grep -q 'subagent_depth' REFERENCE.md` and `grep -q 'PRAGMA busy_timeout' REFERENCE.md`)
- [ ] ONBOARDING.md mentions config.json/opencode.jsonc split and worker agents (verifiable: `grep -q 'config.json' ONBOARDING.md && grep -q 'worker' ONBOARDING.md`)
- [ ] Roadmap marks Spec 2 complete and Spec 3 partially complete (verifiable: `grep -q 'Status: Complete' design/opencode-integration-roadmap.md && grep -q 'Partially complete' design/opencode-integration-roadmap.md`)
