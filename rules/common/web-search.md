# Web Search

## Principle

Search before retrying. When stuck on an error, unfamiliar API, or repeated failure, search the web or fetch documentation before the next attempt. Searching is cheaper than guessing.

## When to Search

**Search immediately** when any of these are true:

- The same error has recurred **2 or more times** after different fix attempts
- Working with an **unfamiliar API or library** — one you haven't used before in this session or that isn't well-represented in the codebase
- The error message contains **version numbers, deprecation warnings, or migration references** — these signal that training data may be stale
- The stack trace points into **third-party internals** — the fix is almost certainly in the library's docs or issue tracker, not in guessing

## Search Strategy

Pick the right tool for the situation:

| Situation | Tool | Why |
|-----------|------|-----|
| Library usage, API signatures, configuration options | **Context7** (`resolve-library-id` → `query-docs`) | Returns current, structured documentation |
| Error messages, stack traces, known bugs | **WebSearch** | Surfaces Stack Overflow, GitHub issues, release notes |
| API usage patterns with unclear errors | **Both** — Context7 for the docs, WebSearch for community solutions | Docs show the right way; search shows what goes wrong |

### Context7 workflow

1. `resolve-library-id` with the library name to get the ID
2. `query-docs` with the ID and a focused question about the specific API or error

### WebSearch tips

- Include the **exact error message** (or its most distinctive substring) in quotes
- Add the **library name and version** if known
- Prefer recent results — add the current year if the error seems version-specific

## When NOT to Search

Do not search for things derivable from the current codebase:

- Project-specific patterns, conventions, or architecture — use Grep/Glob/Read
- How a function in this repo works — read the source
- Git history or recent changes — use `git log` / `git blame`
- Internal configuration — read the config files directly

The rule is: **search externally for external knowledge, read internally for internal knowledge.**
