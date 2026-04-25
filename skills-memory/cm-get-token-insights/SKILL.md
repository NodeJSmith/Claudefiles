---
name: cm-get-token-insights
user-invocable: true
description: >
  Use when the user asks about Claude token usage, wants to see how much they are
  spending on Claude, understand cache hit rates, review Claude Code workflow
  patterns, or get cost optimization recommendations.
---

# Get Token Insights

Parse JSONL conversation files from `~/.claude/projects/*/` into per-turn analytics tables, then analyze both cost-optimization opportunities and Claude Code workflow patterns (skills, agents, hooks).

## Step 1: Ingest

```bash
cm-ingest-token-data
```

First run processes all files (~100s for ~2500 files) — warn the user about the wait before running. Incremental runs complete in under 5s. The script populates analytics tables, deploys an interactive dashboard to `~/.claude-memory/dashboard.html` (built from `templates/dashboard.html`), and prints a slim JSON blob to stdout (full data goes to dashboard only).

If the script exits non-zero, report the error and stop.

## Step 1.5: Claude Code Feature Enrichment

After parsing the JSON stdout from Step 1, construct a personalized prompt for a `claude-code-guide` agent using the actual data — not generic descriptions. For each of the top 3 insights (by `waste_usd`), include verbatim: the `finding` text, `root_cause` text, `waste_usd` value, `solution.action`, and `solution.detail`. Also include the specific project names, counts, and numbers mentioned in the insight (e.g. "meta-ads-cli: 75 cliffs across 53 sessions") so the agent's response is grounded in the user's real usage patterns.

Spawn the agent with `subagent_type: "claude-code-guide"` in **foreground** (do not use `run_in_background`). Wait for the agent to return before proceeding to Step 2. Weave its suggestions into the analysis in Step 2.

## Step 2: Analyze

Capture the JSON stdout from Step 1 as the analysis input. Analyze across four areas:

1. **Cost optimization** — top insights by dollar waste: finding, root cause, concrete solution (show exact CLAUDE.md rule text if suggested), estimated savings. Include relevant Claude Code feature suggestions from Step 1.5. Add a top-line summary (total spend, session count, date range, avg cost/session) and model economics (cost by model, savings from switching routine tasks to cheaper models).
2. **Workflow patterns** — skill usage and error rates, agent delegation patterns (subagent types, model overrides, unnecessary general-purpose usage), hook performance (slowest by total runtime, high error rates).
3. **Week-on-week trends** — if the `trends` object is non-empty, compare current vs prior window: improved/regressed metrics with likely causes, new/retired skills and hooks, hook latency deltas. Skip if `trends` is empty.
4. **Project cost ranking** — top 3 projects by spend; for the most expensive, identify what drives the cost.

Structure the analysis naturally based on what the data shows — don't force empty sections. Ask the user if they want to dive deeper into any specific project, skill, or insight.

## Step 3: Open Dashboard

```bash
python3 -c "import webbrowser, pathlib; webbrowser.open((pathlib.Path.home() / '.claude-memory' / 'dashboard.html').as_uri())"
```

Note the dashboard is available for deeper exploration — Section 6 (Claude Code Ecosystem) has the new skill, agent, and hook charts.
