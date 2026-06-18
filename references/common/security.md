# Security

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->
## Input Validation at Boundaries

Validate and parse external data at system boundaries — user input, API responses, file reads, environment variables. Internal code trusts what the boundary layer already validated.

Don't scatter validation throughout internal code. One validated parse at the edge (e.g., `RequestModel.model_validate(raw)`), then pass typed objects.

Two diagnostic tests:
- "Is this data crossing a system boundary right now?" If not, validation is redundant.
- "Can this logic be a pure function that the boundary shell just calls?" If yes, extract it. Business logic belongs in pure functions with no framework dependencies, making it testable without the framework.

## Injection Prevention

Never interpolate untrusted data into SQL, shell commands, HTML, or template strings. Use parameterized queries, subprocess argument lists (never `os.system` with f-strings), and template engines.

## Secrets

Never hardcode secrets, tokens, or credentials. Load from environment variables or a secrets manager. Never log secrets — not even at DEBUG level.

If a secret accidentally appears in a log or error message, treat it as compromised and rotate immediately.

## Error Leakage

Internal errors (stack traces, database errors, file paths, SQL queries) must not reach external consumers. Return generic error responses to external callers; log the full detail server-side.

Don't include exception messages in user-facing responses — they often contain table names, column names, or connection strings.

## Auth Checks at the Handler

Authorization checks belong at the request handler level, not buried in service methods. If a service method can be called from multiple handlers, each handler is responsible for its own auth gate.
