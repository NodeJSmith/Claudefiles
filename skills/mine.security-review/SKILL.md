---
name: mine.security-review
description: "Use when the user says: \"security review\", \"check for vulnerabilities\", or is adding authentication, handling user input, working with secrets, or creating API endpoints. Comprehensive security checklist and patterns."
user-invokable: true
---

# Security Review Skill

This skill ensures all code follows security best practices and identifies potential vulnerabilities.

## When to Activate

- Implementing authentication or authorization
- Handling user input or file uploads
- Creating new API endpoints
- Working with secrets or credentials
- Implementing payment features
- Storing or transmitting sensitive data
- Integrating third-party APIs

## Security Checklist

### 1. Secrets Management

#### NEVER Do This
```python
api_key = "sk-proj-xxxxx"  # Hardcoded secret
db_password = "password123"  # In source code
```

#### ALWAYS Do This
```python
import os

api_key = os.environ["OPENAI_API_KEY"]  # Raises KeyError if missing
db_url = os.environ["DATABASE_URL"]
```

#### Using pydantic-settings (Recommended)
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    database_url: str
    debug: bool = False

    model_config = {"env_file": ".env"}


settings = Settings()  # Validates all required vars at startup
```

#### Verification Steps
- [ ] No hardcoded API keys, tokens, or passwords
- [ ] All secrets in environment variables
- [ ] `.env` in .gitignore
- [ ] No secrets in git history
- [ ] Production secrets in hosting platform or secrets manager

### 2. Input Validation

#### Always Validate User Input
```python
from pydantic import BaseModel, EmailStr, Field


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    age: int | None = Field(default=None, ge=0, le=150)


def create_user(data: dict) -> dict:
    try:
        validated = CreateUserRequest.model_validate(data)
        return {"success": True, "user": save_user(validated)}
    except ValidationError as e:
        return {"success": False, "errors": e.errors()}
```

#### File Upload Validation
```python
import magic
from pathlib import Path

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
ALLOWED_MIMETYPES = {"image/jpeg", "image/png", "image/gif"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_file_upload(filename: str, content: bytes) -> None:
    # Size check
    if len(content) > MAX_SIZE_BYTES:
        raise ValueError("File too large (max 5 MB)")

    # Extension check
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid file extension: {ext}")

    # Content-type check (don't trust client headers)
    detected = magic.from_buffer(content, mime=True)
    if detected not in ALLOWED_MIMETYPES:
        raise ValueError(f"Invalid file type: {detected}")
```

#### Verification Steps
- [ ] All user inputs validated with schemas
- [ ] File uploads restricted (size, type, extension)
- [ ] No direct use of user input in queries
- [ ] Whitelist validation (not blacklist)
- [ ] Error messages don't leak sensitive info

### 3. SQL Injection Prevention

#### NEVER Concatenate SQL
```python
# DANGEROUS - SQL Injection vulnerability
query = f"SELECT * FROM users WHERE email = '{user_email}'"
cursor.execute(query)
```

#### ALWAYS Use Parameterized Queries
```python
# Safe - parameterized query (raw SQL)
cursor.execute(
    "SELECT * FROM users WHERE email = %s",
    (user_email,),
)

# Safe - SQLAlchemy ORM
user = session.query(User).filter(User.email == user_email).first()

# Safe - SQLAlchemy Core
from sqlalchemy import select, text

stmt = select(users_table).where(users_table.c.email == user_email)
result = session.execute(stmt)

# Safe - text() with bound parameters
result = session.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": user_email},
)
```

#### Verification Steps
- [ ] All database queries use parameterized queries
- [ ] No string concatenation/f-strings in SQL
- [ ] ORM/query builder used correctly
- [ ] Raw SQL uses bound parameters

### 4. Authentication & Authorization

#### JWT Token Handling
```python
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET_KEY = os.environ["JWT_SECRET_KEY"]
ALGORITHM = "HS256"

security = HTTPBearer()


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def set_token_cookie(response: Response, token: str) -> None:
    """Set JWT as httpOnly cookie (not localStorage — vulnerable to XSS)."""
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=3600,
    )
```

#### Authorization Checks
```python
from fastapi import Depends, HTTPException

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user = await get_user(payload["sub"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(require_admin)):
    await db.users.delete(user_id)
    return {"success": True}
```

#### Row Level Security (Database)
```sql
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Users can only view their own data
CREATE POLICY "Users view own data"
  ON users FOR SELECT
  USING (auth.uid() = id);

-- Users can only update their own data
CREATE POLICY "Users update own data"
  ON users FOR UPDATE
  USING (auth.uid() = id);
```

#### Verification Steps
- [ ] Tokens stored in httpOnly cookies (not client-side storage)
- [ ] Authorization checks before sensitive operations
- [ ] Row Level Security enabled where applicable
- [ ] Role-based access control implemented
- [ ] Session management secure

### 5. XSS Prevention

#### Sanitize HTML
```python
import bleach

# ALWAYS sanitize user-provided HTML
def sanitize_user_content(html: str) -> str:
    return bleach.clean(
        html,
        tags=["b", "i", "em", "strong", "p"],
        attributes={},
        strip=True,
    )
```

#### Jinja2 Autoescaping
```python
from jinja2 import Environment, select_autoescape

# ALWAYS enable autoescaping in templates
env = Environment(autoescape=select_autoescape(["html", "xml"]))

# In templates: {{ user_input }} is auto-escaped
# Only use {{ content | safe }} for pre-sanitized content
```

#### Content Security Policy
```python
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' https://api.example.com"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response


app.add_middleware(SecurityHeadersMiddleware)
```

#### Verification Steps
- [ ] User-provided HTML sanitized with bleach
- [ ] CSP headers configured
- [ ] Jinja2 autoescaping enabled
- [ ] No unvalidated dynamic content rendering

### 6. CSRF Protection

#### CSRF Middleware
```python
from starlette_csrf import CSRFMiddleware

app.add_middleware(
    CSRFMiddleware,
    secret="your-csrf-secret",
    cookie_secure=True,
    cookie_samesite="strict",
)
```

#### Manual CSRF Token Verification
```python
import secrets

from fastapi import HTTPException, Request


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


async def verify_csrf(request: Request) -> None:
    token = request.headers.get("X-CSRF-Token")
    expected = request.cookies.get("csrf_token")
    if not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
```

#### SameSite Cookies
```python
response.set_cookie(
    key="session",
    value=session_id,
    httponly=True,
    secure=True,
    samesite="strict",
)
```

#### Verification Steps
- [ ] CSRF tokens on state-changing operations
- [ ] SameSite=Strict on all cookies
- [ ] Double-submit cookie pattern implemented

### 7. Rate Limiting

#### API Rate Limiting (slowapi)
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/api/markets")
@limiter.limit("100/15minutes")
async def list_markets(request: Request):
    ...
```

#### Expensive Operations
```python
@app.get("/api/search")
@limiter.limit("10/minute")
async def search(request: Request, q: str):
    ...
```

#### Verification Steps
- [ ] Rate limiting on all API endpoints
- [ ] Stricter limits on expensive operations
- [ ] IP-based rate limiting
- [ ] User-based rate limiting (authenticated)

### 8. Sensitive Data Exposure

#### Logging
```python
import logging

logger = logging.getLogger(__name__)

# WRONG: Logging sensitive data
logger.info("User login: email=%s password=%s", email, password)
logger.info("Payment: card=%s cvv=%s", card_number, cvv)

# CORRECT: Redact sensitive data
logger.info("User login: email=%s user_id=%s", email, user_id)
logger.info("Payment: last4=%s user_id=%s", card.last4, user_id)
```

#### Error Messages
```python
from fastapi import HTTPException

# WRONG: Exposing internal details
@app.get("/api/data")
async def get_data():
    try:
        return await fetch_data()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # Leaks internals!

# CORRECT: Generic error messages
@app.get("/api/data")
async def get_data():
    try:
        return await fetch_data()
    except Exception:
        logger.exception("Failed to fetch data")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")
```

#### Verification Steps
- [ ] No passwords, tokens, or secrets in logs
- [ ] Error messages generic for users
- [ ] Detailed errors only in server logs
- [ ] No stack traces exposed to users

### 9. Dependency Security

#### Regular Updates
```bash
# Check for known vulnerabilities
pip-audit

# Alternative: safety check
safety check

# Update dependencies
uv lock --upgrade

# Check for outdated packages
pip list --outdated
```

#### Lock Files
```bash
# ALWAYS commit lock files
git add uv.lock  # or requirements.txt / poetry.lock

# Use in CI/CD for reproducible builds
uv sync --frozen  # Instead of uv sync
```

#### Verification Steps
- [ ] Dependencies up to date
- [ ] No known vulnerabilities (`pip-audit` clean)
- [ ] Lock files committed
- [ ] Dependabot or Renovate enabled on GitHub
- [ ] Regular security updates

## Security Testing

### Automated Security Tests
```python
import pytest
from fastapi.testclient import TestClient

from myapp.main import app

client = TestClient(app)


def test_requires_authentication():
    response = client.get("/api/protected")
    assert response.status_code == 401


def test_requires_admin_role(user_token):
    response = client.get(
        "/api/admin",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_rejects_invalid_input():
    response = client.post(
        "/api/users",
        json={"email": "not-an-email"},
    )
    assert response.status_code == 422


def test_enforces_rate_limits():
    responses = [client.get("/api/endpoint") for _ in range(101)]
    too_many = [r for r in responses if r.status_code == 429]
    assert len(too_many) > 0
```

## Pre-Deployment Security Checklist

Before ANY production deployment:

- [ ] **Secrets**: No hardcoded secrets, all in env vars
- [ ] **Input Validation**: All user inputs validated
- [ ] **SQL Injection**: All queries parameterized
- [ ] **XSS**: User content sanitized
- [ ] **CSRF**: Protection enabled
- [ ] **Authentication**: Proper token handling
- [ ] **Authorization**: Role checks in place
- [ ] **Rate Limiting**: Enabled on all endpoints
- [ ] **HTTPS**: Enforced in production
- [ ] **Security Headers**: CSP, X-Frame-Options configured
- [ ] **Error Handling**: No sensitive data in errors
- [ ] **Logging**: No sensitive data logged
- [ ] **Dependencies**: Up to date, no vulnerabilities
- [ ] **Row Level Security**: Enabled where applicable
- [ ] **CORS**: Properly configured
- [ ] **File Uploads**: Validated (size, type, content)

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Web Security Academy](https://portswigger.net/web-security)
- [Python Security Best Practices](https://python-security.readthedocs.io/)

---

**Remember**: Security is not optional. One vulnerability can compromise the entire platform. When in doubt, err on the side of caution.
