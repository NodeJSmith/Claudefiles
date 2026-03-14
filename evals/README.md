# Evals

Promptfoo-based instruction compliance tests. These verify that Claude follows the rules, conventions, and tool preferences configured in this repo — not just that it produces correct output, but that it *behaves correctly*.

## Setup

```bash
npm install
```

Requires `ANTHROPIC_API_KEY` in your environment.

## Running

Always run from the repo root:

```bash
# Run a single compliance test
npx promptfoo eval -c evals/compliance/memory/shodh-context-summary.yaml
npx promptfoo eval -c evals/compliance/tools/gh-pr-reply.yaml
npx promptfoo eval -c evals/compliance/rules/dedicated-tools.yaml

# Run a category
npx promptfoo eval -c evals/compliance/memory/
npx promptfoo eval -c evals/compliance/tools/
npx promptfoo eval -c evals/compliance/rules/

# View results in browser
npx promptfoo view
```

## Structure

```
evals/
  lib/
    assert-tool-called.js     Reusable assertion helpers for tool call checks
  compliance/
    memory/                   Shodh memory MCP utilization
    tools/                    gh helper script preference (gh-pr-reply, gh-pr-threads, etc.)
    rules/                    General rule compliance (Grep over Bash, git -C, etc.)
```

## What These Test

| File | Rule | Assertion |
|------|------|-----------|
| `memory/shodh-context-summary.yaml` | Call `context_summary` at session start | `mcp__shodh-memory__context_summary` in toolCalls |
| `tools/gh-pr-reply.yaml` | Use `gh-pr-reply` for PR comment replies | `gh-pr-reply` in Bash call; no raw `gh api` |
| `rules/dedicated-tools.yaml` | Use Grep/Glob/Read not Bash cat/grep/find | Dedicated tools present; no Bash file-op violations |

## Interpreting Results

Each assertion checks `metadata.toolCalls` from the Claude Agent SDK provider — the actual tool calls Claude made during the session, in order. Failures include the list of tools actually called so you can see what went wrong.

**A failing test means Claude is not following a rule.** That's either a prompt engineering fix (update the rule in rules/) or a signal that the rule needs to be stated more explicitly.

## Adding Tests

1. Create a YAML in the appropriate `compliance/` subdirectory
2. Set `working_dir: .` (run from repo root)
3. Write `type: javascript` assertions against `context.providerResponse?.metadata?.toolCalls`
4. Add a row to the table above
