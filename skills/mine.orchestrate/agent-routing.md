# Agent Routing Table

Match WP content against this table to select the executor agent type. **First match wins** — stop at the first row that applies. More-specific rows are listed first.

<!-- PARALLEL: rules/common/agents.md also routes to these agents by user intent (not WP content) — add new agents to both, but signal wording differs intentionally -->

| WP content signals | Use `subagent_type` |
|---|---|
| FastAPI endpoint reading from Databricks via `databricks-sql-connector` | `engineering-backend-developer` |
| React, Vue, Angular, CSS, frontend components, UI implementation | `engineering-frontend-developer` |
| PySpark, Delta Lake, DeltaTable, cloudFiles/Auto Loader, medallion layers (raw/bronze/silver/gold), dbt models, Databricks workflows | `engineering-data-engineer` |
| FastAPI, REST API endpoints, Pydantic request/response models, async backend service | `engineering-backend-developer` |
| API docs, README, tutorials, developer documentation | `engineering-technical-writer` |
| Database schema, migrations, query optimization, ORM setup | `general-purpose` |

If the WP doesn't clearly match any row, use `general-purpose` (the default). When in doubt, prefer `general-purpose` — a wrong specialist is worse than a capable generalist.
