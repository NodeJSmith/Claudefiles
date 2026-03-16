# Evals

Promptfoo-based instruction compliance tests. These verify that Claude follows the rules, conventions, and tool preferences configured in this repo — not just that it produces correct output, but that it *behaves correctly*.

## Setup

Requires Node >= 20.20.

```bash
npm install
```

Requires `ANTHROPIC_API_KEY` in your environment.

## Running

Always run from the repo root (`~/Claudefiles`, not a worktree).

The API key lives in `$MY_ANTHROPIC_API_KEY` (not `$ANTHROPIC_API_KEY`), so pass it explicitly:

```bash
cd ~/Claudefiles

# Run a single compliance test
ANTHROPIC_API_KEY="$(printenv MY_ANTHROPIC_API_KEY)" node_modules/.bin/promptfoo eval \
  -c evals/compliance/routing/intent-to-skill-confusion.yaml

# Run all routing evals
ANTHROPIC_API_KEY="$(printenv MY_ANTHROPIC_API_KEY)" node_modules/.bin/promptfoo eval \
  -c evals/compliance/routing/

# Run a specific category
ANTHROPIC_API_KEY="$(printenv MY_ANTHROPIC_API_KEY)" node_modules/.bin/promptfoo eval \
  -c evals/compliance/tools/
ANTHROPIC_API_KEY="$(printenv MY_ANTHROPIC_API_KEY)" node_modules/.bin/promptfoo eval \
  -c evals/compliance/rules/

# View results in browser
node_modules/.bin/promptfoo view
```

**Note:** Use `node_modules/.bin/promptfoo` directly — `npx` can re-download the package instead of using the local install. The `$(printenv ...)` syntax works in your terminal but will fail inside Claude's Bash tool — set the env var first if running via Claude.

## Structure

```
evals/
  lib/
    assert-tool-called.js     Reusable assertion helpers for tool call checks
  compliance/
    routing/                  Intent → skill/agent/CLI routing (266 tests)
    tools/                    gh helper script preference (gh-pr-reply, gh-pr-threads, etc.)
    rules/                    General rule compliance (Grep over Bash, git -C, etc.)
```

## What the Tests Cover

### Routing

Tests that natural-language user prompts trigger the correct skill, agent, or CLI tool. Each positive test has 3 prompt variations (direct trigger phrase, natural language, contextual/indirect) to diagnose whether failures are narrow trigger phrases vs deeper routing issues. Also includes confusion-pair tests (ambiguous prompts between competing skills) and negative tests (should NOT trigger).

### Tools & Rules

| File | Rule | Assertion |
|------|------|-----------|
| `tools/gh-pr-reply.yaml` | Use `gh-pr-reply` for PR comment replies | `gh-pr-reply` in Bash call; no raw `gh api` |
| `rules/dedicated-tools.yaml` | Use Grep/Glob/Read not Bash cat/grep/find | Dedicated tools present; no Bash file-op violations |

## Interpreting Results

Each assertion checks `metadata.toolCalls` from the Claude Agent SDK provider — the actual tool calls Claude made during the session, in order. Failures include the list of tools actually called so you can see what went wrong.

**A failing test means Claude is not following a rule.** That's either a prompt engineering fix (update the rule in rules/) or a signal that the rule needs to be stated more explicitly.

## Adding Tests

1. Create a YAML in the appropriate `compliance/` subdirectory
2. Set `working_dir` appropriately — `.` for repo root, or a fixture path like `../../../evals/fixtures/python-api`
3. For skill routing tests, include `setting_sources: ['user']` and `append_allowed_tools: ['Skill']` — without these, skills are invisible to eval sessions
4. Write `type: javascript` assertions against `context.providerResponse?.metadata?.toolCalls`
5. Add a row to the table above
