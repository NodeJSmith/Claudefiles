# Web Search

Search before retrying. When stuck on an error or unfamiliar API, search before the next attempt.

## When to Search

- Same error recurred **2+ times** after different fix attempts
- **Unfamiliar API or library** not well-represented in the codebase
- Error contains **version numbers or deprecation warnings** (training data may be stale)
- Stack trace points into **third-party internals**

## Search Strategy

| Situation | Tool |
|-----------|------|
| Library docs, API signatures | **Context7** (`resolve-library-id` → `query-docs`) |
| Error messages, stack traces, bugs | **WebSearch** |
| API patterns with unclear errors | **Both** |
