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

**Running via Claude's Bash tool:** The `$(printenv ...)` syntax above works in your terminal but fails inside Claude's Bash tool due to the `eval` wrapper mangling command substitution. Use this form instead:

```bash
ANTHROPIC_API_KEY=$(printenv MY_ANTHROPIC_API_KEY) node_modules/.bin/promptfoo eval \
  -c evals/compliance/tools/gh-pr-reply.yaml --no-cache
```

**Note:** Use `node_modules/.bin/promptfoo` directly — `npx` can re-download the package instead of using the local install.

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
| `tools/skill-cross-reference.yaml` | "See skill:" cross-references teach correct tool usage | `gh-pr-reply` with correct flags; cross-ref loads skill; no-docs baseline fumbles |
| `rules/dedicated-tools.yaml` | Use Grep/Glob/Read not Bash cat/grep/find | Dedicated tools present; no Bash file-op violations |

## Interpreting Results

**Always use `--output` for structured results.** The terminal table truncates both Claude's response and assertion details — it's easy to misread a passing test as failing (or vice versa) from the table alone. Write JSON and parse it:

```bash
ANTHROPIC_API_KEY=$(printenv MY_ANTHROPIC_API_KEY) node_modules/.bin/promptfoo eval \
  -c evals/compliance/tools/gh-pr-reply.yaml --no-cache \
  --output /tmp/eval-results.json

# Check assertion results per variant
python3 -c "
import json
with open('/tmp/eval-results.json') as f:
    data = json.load(f)
for result in data['results']['results']:
    desc = result['testCase'].get('description', '?')
    tool_calls = result['response']['metadata'].get('toolCalls', [])
    print(f'\n=== {desc} ===')
    for tc in tool_calls:
        name = tc['name']
        if name == 'Bash':
            print(f'  Bash: {tc[\"input\"].get(\"command\", \"?\")[:120]}')
        elif name == 'Skill':
            print(f'  Skill: {json.dumps(tc[\"input\"])[:120]}')
        else:
            print(f'  {name}')
    for gr in result['gradingResult']['componentResults']:
        status = 'PASS' if gr['pass'] else 'FAIL'
        print(f'  [{status}] {gr[\"reason\"][:120]}')
"
```

Each assertion checks `metadata.toolCalls` from the Claude Agent SDK provider — the actual tool calls Claude made during the session, in order. Failures include the list of tools actually called so you can see what went wrong.

**A failing test means Claude is not following a rule.** That's either a prompt engineering fix (update the rule in rules/) or a signal that the rule needs to be stated more explicitly.

## Adding Tests

1. Create a YAML in the appropriate `compliance/` subdirectory
2. Set `working_dir` appropriately — `.` for repo root, or a fixture path like `../../../evals/fixtures/python-api`
3. For skill routing tests, include `setting_sources: ['user']` and `append_allowed_tools: ['Skill']` — without these, skills are invisible to eval sessions
4. Write `type: javascript` assertions against `context.providerResponse?.metadata?.toolCalls`
5. Add a row to the table above
