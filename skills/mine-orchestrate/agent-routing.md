# Agent Routing Table

Match WP content against this table to select the executor agent type. **First match wins** — stop at the first row that applies. More-specific rows are listed first.

<!-- SYNC CHECKLIST — when adding a new specialist agent:
  1. Add a row here (WP content signals → subagent_type)
  2. Add the matching intent row to references/common/agents.md
  3. Create agents/<name>.md with the executor note
  4. Update the SKILL.md routing reference if the subagent_type is new
-->

| WP content signals | Use `subagent_type` |
|---|---|
| FastAPI endpoint reading from Databricks via `databricks-sql-connector` | `engineering-backend-developer` |
| React, Vue, Angular, CSS, frontend components, UI implementation | `engineering-frontend-developer` |
| PySpark, Delta Lake, DeltaTable, cloudFiles/Auto Loader, medallion layers (raw/bronze/silver/gold), dbt models, Databricks workflows | `engineering-data-engineer` |
| FastAPI, REST API endpoints, Pydantic request/response models, async backend service | `engineering-backend-developer` |
| API docs, README, tutorials, developer documentation | `engineering-technical-writer` |
| Database schema, migrations, query optimization, ORM setup | `general-purpose`, `model: sonnet` |

If the WP does not clearly match a row, use `general-purpose`, `model: sonnet`.
