# Memory Skills

**BLOCKING REQUIREMENT**: When a user request matches a trigger phrase below, you MUST invoke the corresponding skill **before** responding. Do NOT perform the task directly — dispatch to the skill. This applies even if you could answer inline.

## Intent Routing

| User says something like... | Invoke |
|---|---|
| "what did we discuss", "continue where we left off", "remember when", "search my conversations", "what did we work on", "find the conversation where" | `/cm-recall-conversations` |
| "extract learnings", "save this for next time", "remember this pattern", "consolidate memories", "dream", "clean up memories" | `/cm-extract-learnings` |
| "analyze Claude token usage", "how much am I spending on Claude", "token insights", "cache hit rates", "cost optimization" | `/cm-get-token-insights` |
