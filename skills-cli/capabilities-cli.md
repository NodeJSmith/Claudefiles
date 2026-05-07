# CLI Design Skills

**BLOCKING REQUIREMENT**: When a user request matches a trigger phrase below, you MUST invoke the corresponding skill **before** responding. Do NOT perform the task directly — dispatch to the skill. This applies even if you could answer inline.

## Intent Routing

| User says something like... | Invoke |
|---|---|
| "harden this CLI", "CLI edge cases", "make this CLI resilient", "handle CLI errors", "CLI robustness" | `/cli-harden` |
