# Research Escalation

When stuck on an error or unfamiliar behavior, escalate through search and research rather than guessing repeatedly.

## Escalation Ladder

1. **Search first** — before retrying a failed fix, search for the answer:
   - Library docs, API signatures → **Context7** (`resolve-library-id` → `query-docs`)
   - Error messages, stack traces, bugs → **WebSearch**
   - API patterns with unclear errors → **both**
2. **Research subagent** — if search didn't resolve it, dispatch a subagent (see below)
3. **Present to user** — if the subagent doesn't yield a clear fix, stop and present the error, what's been tried, and the research findings

## When to Escalate to a Subagent

Dispatch a research subagent when **any** of the following apply:

- A search-informed fix attempt still failed
- You're changing code without a clear hypothesis for why it will work
- You're reading the same files repeatedly without new insight
- The error doesn't match your mental model of the code

Don't wait for a specific attempt count — if you recognize you're guessing, escalate immediately.

## How to Dispatch

Note in your response what you're stuck on and that you're dispatching a research subagent — then dispatch immediately. Don't wait for acknowledgment.

Include the session error file contents in the subagent prompt (see `error-tracking.md` for the path) so prior failed approaches aren't rediscovered.

### Which subagent type

Use `researcher` unless you're certain no external knowledge is needed — it can read the codebase and search the web. Use `Explore` only for pure codebase navigation where web search is irrelevant (read-only, no web access).

When dispatching `researcher`, fill in the caller prompt checklist from `agents/researcher.md`.

## After the Subagent Returns

- If findings clearly resolve the issue → apply the fix
- If findings are inconclusive or the fix still fails → present to the user with a summary of what's blocking
- **Do not dispatch a second research subagent** for the same issue unless the user explicitly asks for more investigation
- Update the error file with the outcome
