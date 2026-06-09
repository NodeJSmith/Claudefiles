# Security

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->
## Input Validation at Boundaries

Validate and parse external data at system boundaries — user input, API responses, file reads, environment variables. Internal code trusts what the boundary layer already validated.

```python
# good: validate at the boundary, trust internally
def handle_request(raw: dict[str, Any]) -> Response:
    request = RequestModel.model_validate(raw)  # boundary
    return process(request)  # internal code trusts the model

def process(request: RequestModel) -> Response:
    # no re-validation needed — RequestModel guarantees shape
    ...
```

Don't scatter validation throughout internal code. One validated parse at the edge, then pass typed objects.

Two diagnostic tests:
- "Is this data crossing a system boundary right now?" If not, validation is redundant.
- "Can this logic be a pure function that the boundary shell just calls?" If yes, extract it. Business logic belongs in pure functions with no framework dependencies, making it testable without the framework.

## Injection Prevention

Never interpolate untrusted data into SQL, shell commands, HTML, or template strings. Use parameterized queries, subprocess argument lists, and template engines.

```python
# BAD — SQL injection
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")

# GOOD — parameterized
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

# BAD — shell injection
os.system(f"convert {filename} output.png")

# GOOD — argument list
subprocess.run(["convert", filename, "output.png"], check=True)
```

## Secrets

Never hardcode secrets, tokens, or credentials. Load from environment variables or a secrets manager. Never log secrets — not even at DEBUG level.

```python
# good
api_key = os.environ["STRIPE_API_KEY"]

# bad — even in "debug" logging
logger.debug("Using key: %s", api_key)
```

If a secret accidentally appears in a log or error message, treat it as compromised and rotate immediately.

## Error Leakage

Internal errors (stack traces, database errors, file paths, SQL queries) must not reach external consumers. Return generic error responses to external callers; log the full detail server-side.

```python
# good: generic to the client, detailed in the log
try:
    result = db.execute(query)
except DatabaseError as e:
    logger.exception("Query failed: %s", query)
    raise HTTPException(status_code=500, detail="Internal server error")
```

Don't include exception messages in user-facing responses — they often contain table names, column names, or connection strings.

## Auth Checks at the Handler

Authorization checks belong at the request handler level, not buried in service methods. If a service method can be called from multiple handlers, each handler is responsible for its own auth gate.

```python
@router.get("/admin/users")
async def list_users(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403)
    return await user_service.list_all()
```
