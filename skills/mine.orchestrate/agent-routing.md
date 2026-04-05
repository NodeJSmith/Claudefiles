# Agent Routing Table

Match WP content against this table to select the executor agent type. **First match wins** — stop at the first row that applies. More-specific rows are listed first.

<!-- SYNC CHECKLIST — when adding a new specialist agent:
  1. Add a row to this table (WP content signals → subagent_type)
  2. Add a row to rules/common/agents.md (user intent → subagent_type)
  3. Create the agent definition in agents/<name>.md with executor note
  4. Add to SKILL.md Step 3 routing table reference (if using a new subagent_type)
  Signal wording differs intentionally: this table uses WP content signals; agents.md uses user intent phrases.
-->

| WP content signals | Use `subagent_type` |
|---|---|
| FastAPI endpoint reading from Databricks via `databricks-sql-connector` | `engineering-backend-developer` |
| React, Vue, Angular, CSS, frontend components, UI implementation | `engineering-frontend-developer` |
| PySpark, Delta Lake, DeltaTable, cloudFiles/Auto Loader, medallion layers (raw/bronze/silver/gold), dbt models, Databricks workflows | `engineering-data-engineer` |
| FastAPI, REST API endpoints, Pydantic request/response models, async backend service | `engineering-backend-developer` |
| API docs, README, tutorials, developer documentation | `engineering-technical-writer` |
| Database schema, migrations, query optimization, ORM setup | `general-purpose` |

If the WP doesn't clearly match any row, use `general-purpose` (the default). When in doubt, prefer `general-purpose` — a wrong specialist is worse than a capable generalist.
