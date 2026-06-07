# Memory Skills

**BLOCKING REQUIREMENT**: When a user request matches a trigger phrase below, you MUST invoke the corresponding skill **before** responding. Do NOT perform the task directly — dispatch to the skill. This applies even if you could answer inline.

## Intent Routing

| User says something like... | Invoke |
|---|---|
| "what did we discuss", "continue where we left off", "remember when", "search my conversations", "what did we work on", "find the conversation where", "what did we decide about X", "why did we do Y", "have I seen this before", "look this up in memory" | Both `/cm-recall-conversations` AND `memsearch:memory-recall` — run in parallel |
| "analyze Claude token usage", "how much am I spending on Claude", "token insights", "cache hit rates", "cost optimization" | `/cm-get-token-insights` |

## Proactive Memory Recall

The `UserPromptSubmit` hook injects `[memsearch] Memory available` on every prompt. When that hint is present and any of these conditions apply, run both `/cm-recall-conversations` and `memsearch:memory-recall` in parallel before answering:

- The user references past work, a prior decision, or earlier context not in the current session
- The cold-start injection has session headings for the topic but no bullet detail
- The question is answerable from memory but you have no current-session context for it

**Named failure mode:** Both tools are available but go unused because nothing in the routing table says to act on the `[memsearch] Memory available` hint. When in doubt, search — under-recall is the consistent failure mode, not over-recall.
