# CLI Design Skills

**BLOCKING REQUIREMENT**: When a user request matches a trigger phrase below, you MUST invoke the corresponding skill **before** responding. Do NOT perform the task directly — dispatch to the skill. This applies even if you could answer inline.

## Intent Routing

| User says something like... | Invoke |
|---|---|
| "harden this CLI", "CLI edge cases", "make this CLI resilient", "handle CLI errors", "CLI robustness" | `/cli-harden` |
| "fix CLI output", "CLI output formatting", "improve CLI output", "CLI readability", "CLI table formatting" | `/cli-output` |
| "fix CLI messages", "improve CLI help text", "CLI error messages", "CLI UX writing", "confusing CLI output" | `/cli-clarify` |
| "improve CLI discoverability", "CLI help UX", "CLI flag design", "CLI affordances", "CLI command structure" | `/cli-affordances` |
| "simplify this CLI", "too many flags", "CLI too complex", "reduce CLI complexity", "streamline CLI" | `/cli-distill` |
| "audit this CLI", "CLI quality check", "full CLI review", "CLI UX audit" | `/cli-audit` |
