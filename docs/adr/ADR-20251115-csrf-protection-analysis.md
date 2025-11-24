# ADR-20251115: CSRF Protection Analysis for MITA API

**Date:** 2025-11-15
**Status:** DECIDED - CSRF Protection NOT Required
**Decision Maker:** CTO & Principal Engineer
**Impact:** Security Architecture

---

## Context & Problem Statement

CSRF (Cross-Site Request Forgery) protection is a critical security measure for web applications that use cookie-based authentication. This ADR analyzes whether MITA API requires CSRF protection based on its authentication architecture and usage patterns.

### CSRF Attack Overview

CSRF attacks exploit browser behavior where cookies are automatically sent with every request to the same domain. If an application uses cookie-based sessions for authentication, a malicious site can trick a user's browser into making unwanted authenticated requests.

**CSRF is required when:**
- Session cookies are used for authentication
- JWT tokens are stored in cookies (not Authorization header)
- OAuth callbacks use session-based state management

**CSRF is NOT required when:**
- JWT tokens are sent exclusively via Authorization header
- No session cookies are used for authentication
- API is stateless and token-based

---

## Analysis of MITA API Authentication

### 1. Cookie Usage Investigation

**Search Results:**
```bash
# No SessionMiddleware found
grep -r "SessionMiddleware" app/ => No matches

# No set_cookie usage found
grep -r "set_cookie|cookie_secure|httponly" app/ => No matches

# No session cookies in responses
grep -r "response.cookies" app/ => No matches
```

**Finding:** MITA API does NOT use cookies for authentication or session management.

---

### 2. JWT Token Implementation

**Backend Implementation (app/api/dependencies.py):**
```python
# OAuth2 with Bearer token (Authorization header only)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db)
):
    # Token extracted from Authorization header only
    payload = await verify_token(token, token_type="access_token")
    ...
```

**Key Observations:**
- Uses `OAuth2PasswordBearer` which requires `Authorization: Bearer <token>` header
- No fallback to cookies
- Tokens stored in request headers only

**Frontend Implementation (mobile_app/lib/services/api_service.dart):**
```dart
// Flutter app sends JWT in Authorization header
onRequest: (options, handler) async {
  final token = await getToken();
  if (token != null) {
    options.headers['Authorization'] = 'Bearer $token';
  }
  handler.next(options);
}
```

**Key Observations:**
- Flutter mobile app stores tokens in secure storage
- Tokens sent exclusively via Authorization header
- No cookie-based authentication mechanism

---

### 3. Middleware & Security Headers

**app/main.py Analysis:**

**Present Security Middleware:**
```python
# HTTPS enforcement
app.add_middleware(HTTPSRedirectMiddleware)

# CORS with credentials support
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,  # For Authorization header, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers
response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "DENY"
response.headers["Content-Security-Policy"] = "default-src 'self'; ..."
response.headers["Referrer-Policy"] = "same-origin"
response.headers["X-XSS-Protection"] = "1; mode=block"
```

**Missing Middleware:**
- No `SessionMiddleware` (Starlette)
- No `CsrfProtect` or equivalent
- No cookie-based session management

**Finding:** Security headers present and properly configured. No session-based authentication infrastructure.

---

### 4. Authentication Flow Analysis

**Registration Flow (app/api/auth/routes.py):**
```python
@router.post("/register", response_model=TokenOut)
async def register_user_standardized(
    request: Request,
    registration_data: RegisterIn,
    db: AsyncSession = Depends(get_async_db)
):
    # Returns JWT tokens in response body
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
```

**Login Flow:**
```python
@router.post("/login", response_model=TokenOut)
async def login_user_standardized(...):
    # Returns JWT tokens in response body
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
```

**Token Refresh Flow:**
```python
@router.post("/refresh")
async def refresh_token(token: str = Depends(oauth2_refresh_scheme)):
    # Accepts refresh token via Authorization header
    # Returns new tokens in response body
    payload = await verify_token(token, token_type="refresh_token")
    ...
```

**Finding:** All authentication endpoints return tokens in JSON response body. No cookies are set.

---

### 5. OAuth & Third-Party Authentication

**Search for OAuth Callbacks:**
```bash
grep -r "oauth_callback|OAuth|callback" app/api/auth/routes.py
=> Found references but no cookie-based state management
```

**Google Authentication (app/api/auth/routes.py):**
```python
@router.post("/google")
async def google_auth(...):
    # Accepts Google ID token in request body
    # Returns MITA JWT tokens in response body
    # No session cookies used
    ...
```

**Finding:** OAuth flows do not use session-based state. All state passed via request/response bodies.

---

## Security Considerations

### Why MITA Doesn't Need CSRF Protection

1. **Stateless Authentication**
   - JWT tokens stored client-side (Flutter secure storage)
   - No server-side sessions
   - No cookies containing authentication credentials

2. **Authorization Header Only**
   - Browsers don't automatically send Authorization headers
   - CSRF attacks rely on automatic cookie transmission
   - Cannot forge Authorization header from malicious site

3. **Mobile-First Architecture**
   - Primary client is Flutter mobile app
   - No web browser-based authentication flows
   - No cookie jar to exploit

4. **CORS Protection**
   - Strict CORS policy with allowlist of origins
   - Prevents cross-origin requests from untrusted domains
   - Additional layer of protection

### Existing Security Measures (Sufficient)

1. **JWT Token Security**
   - Short-lived access tokens (2 hours)
   - Refresh token rotation
   - Token blacklisting on logout
   - Token version tracking for revocation

2. **Rate Limiting**
   - Progressive rate limiting on auth endpoints
   - Prevents brute force attacks
   - Sliding window algorithm

3. **Audit Logging**
   - Comprehensive security event tracking
   - Authentication attempt logging
   - Suspicious activity detection

4. **Input Validation**
   - Multi-layer validation with Pydantic
   - SQL injection prevention via ORM
   - XSS prevention via content sanitization

5. **HTTPS Enforcement**
   - TLS 1.3 with strong ciphers
   - HSTS header enforcement
   - Secure token transmission

---

## Decision

**CSRF Protection is NOT required for MITA API.**

### Rationale

1. **No Cookie-Based Authentication**
   - MITA uses exclusively header-based JWT authentication
   - No session cookies are set or used
   - CSRF attacks cannot exploit Authorization headers

2. **Architecture Alignment**
   - Stateless API design incompatible with CSRF concerns
   - Mobile-first approach doesn't expose cookie vulnerabilities
   - Existing security measures provide comprehensive protection

3. **RFC Best Practices**
   - RFC 6750 (OAuth 2.0 Bearer Token) doesn't require CSRF protection for header-based tokens
   - OWASP guidelines confirm CSRF protection unnecessary for stateless APIs without cookies

### Code Documentation

Add explicit comment to codebase documenting this architectural decision:

**Location:** `/Users/mikhail/StudioProjects/mita_project/app/core/security_notes.py` (new file)

```python
"""
MITA API Security Architecture Notes
=====================================

CSRF Protection Status: NOT IMPLEMENTED (by design)
---------------------------------------------------

MITA API does NOT implement CSRF (Cross-Site Request Forgery) protection
because it is not vulnerable to CSRF attacks. Here's why:

1. STATELESS JWT AUTHENTICATION
   - All authentication uses JWT tokens sent via Authorization header
   - No session cookies or cookie-based authentication
   - Browsers do not automatically send Authorization headers with requests

2. NO COOKIE USAGE
   - No SessionMiddleware or cookie-based sessions
   - No response.set_cookie() calls in the codebase
   - OAuth flows use header-based state, not session cookies

3. CSRF ATTACK VECTOR NOT APPLICABLE
   - CSRF attacks exploit automatic cookie transmission by browsers
   - Since MITA doesn't use cookies for auth, this vector is closed
   - Malicious sites cannot forge Authorization headers

4. EXISTING SECURITY MEASURES
   - CORS protection with strict origin allowlist
   - JWT token rotation and blacklisting
   - Comprehensive rate limiting
   - HTTPS enforcement with HSTS
   - Audit logging for security events

WHEN WOULD CSRF BE NEEDED?
---------------------------
If MITA were to add:
- Cookie-based session authentication
- JWT tokens stored in cookies (instead of Authorization header)
- OAuth callbacks using session-based state management

Then CSRF protection would need to be implemented using:
- Double-submit cookie pattern
- Synchronizer token pattern
- SameSite cookie attributes

COMPLIANCE NOTES
----------------
- OWASP: CSRF protection recommended for cookie-based auth only
- RFC 6750: Bearer tokens in Authorization header don't require CSRF protection
- PCI DSS: Focused on data encryption and access control (covered by JWT)

Last Updated: 2025-11-15
Decision Reference: ADR-20251115-csrf-protection-analysis.md
"""
```

---

## Consequences

### Positive

1. **No Additional Complexity**
   - Avoids unnecessary middleware overhead
   - Maintains clean stateless architecture
   - No performance impact from CSRF token validation

2. **Clear Security Model**
   - Documented decision prevents future confusion
   - Architecture constraints enforced by design
   - Mobile-first approach naturally immune to CSRF

3. **Development Efficiency**
   - No CSRF token management in frontend
   - No synchronization between client/server tokens
   - Simplified authentication flow

### Negative

1. **Future Constraint**
   - If cookie-based auth is added later, CSRF protection will be required
   - Must document this constraint in cookie implementation ADRs

2. **Web Client Considerations**
   - If web browser client is added, must maintain header-based auth
   - Cannot use cookie-based sessions without implementing CSRF

### Monitoring & Review

1. **Code Review Checklist**
   - Reject PRs that introduce `SessionMiddleware` without CSRF protection
   - Reject PRs that use `response.set_cookie()` for authentication
   - Flag any OAuth state management using cookies

2. **Security Audit Points**
   - Verify no cookies in authentication responses
   - Confirm Authorization header requirement in all protected endpoints
   - Check no session-based state in OAuth flows

---

## Implementation

### 1. Add Security Documentation

**File:** `/Users/mikhail/StudioProjects/mita_project/app/core/security_notes.py`

Create comprehensive documentation file explaining CSRF architecture decision.

### 2. Update API Documentation

**File:** `/Users/mikhail/StudioProjects/mita_project/app/main.py`

Add to OpenAPI documentation:

```python
description="""
...

### Security Architecture

**CSRF Protection:** Not implemented. MITA uses stateless JWT authentication
via Authorization headers only. CSRF protection is not required for header-based
authentication as browsers do not automatically send Authorization headers.

For details, see: app/core/security_notes.py
"""
```

### 3. Add Code Comment in Main Middleware Section

**File:** `/Users/mikhail/StudioProjects/mita_project/app/main.py`

Add comment after CORS middleware:

```python
# ---- Middlewares ----

# Add standardized error handling middleware (first for comprehensive coverage)
app.add_middleware(StandardizedErrorMiddleware, include_request_details=settings.DEBUG)
app.add_middleware(ResponseValidationMiddleware, validate_success_responses=settings.DEBUG)
app.add_middleware(RequestContextMiddleware)

# Security and CORS middlewares
app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: CSRF Protection NOT implemented by design
# MITA uses stateless JWT authentication via Authorization headers only.
# CSRF protection is not required because:
# 1. No session cookies or cookie-based authentication
# 2. Browsers don't automatically send Authorization headers (CSRF attack vector closed)
# 3. All tokens sent via header, returned in response body (never in cookies)
# See: app/core/security_notes.py and docs/adr/ADR-20251115-csrf-protection-analysis.md
```

---

## References

- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [RFC 6750: OAuth 2.0 Bearer Token Usage](https://datatracker.ietf.org/doc/html/rfc6750)
- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [MITA Architecture: README.md](/Users/mikhail/StudioProjects/mita_project/README.md)

---

## Appendix: CSRF Protection Implementation (If Needed in Future)

If MITA adds cookie-based authentication in the future, implement CSRF using:

### Option 1: fastapi-csrf-protect

```python
# requirements.txt
fastapi-csrf-protect==0.3.4

# app/core/config.py
class CsrfSettings(BaseSettings):
    secret_key: str = settings.SECRET_KEY
    cookie_name: str = "csrftoken"
    header_name: str = "X-CSRF-Token"
    cookie_samesite: str = "strict"
    cookie_secure: bool = True

# app/main.py
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()

app.add_exception_handler(CsrfProtectError, csrf_protect_exception_handler)

# Usage in endpoints
@router.post("/cookie-based-endpoint")
async def protected_endpoint(
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf()
    # ... endpoint logic
```

### Option 2: Custom Double-Submit Cookie Pattern

```python
import secrets
from fastapi import Cookie, Header, HTTPException

def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)

async def verify_csrf_token(
    csrf_token_cookie: str = Cookie(None, alias="csrf_token"),
    csrf_token_header: str = Header(None, alias="X-CSRF-Token")
):
    if not csrf_token_cookie or not csrf_token_header:
        raise HTTPException(status_code=403, detail="CSRF token missing")

    if csrf_token_cookie != csrf_token_header:
        raise HTTPException(status_code=403, detail="CSRF token mismatch")

    return True

# Usage
@router.post("/cookie-endpoint", dependencies=[Depends(verify_csrf_token)])
async def cookie_endpoint(...):
    ...
```

**Note:** Only implement if cookies are added to authentication flow.

---

## Summary

**Decision:** CSRF protection NOT required for MITA API

**Reason:** Stateless JWT authentication via Authorization headers only; no cookies used

**Action Items:**
1. Create security documentation file explaining this decision
2. Add inline comments in main.py middleware section
3. Update OpenAPI documentation with security architecture notes
4. Add to code review checklist: reject cookie-based auth without CSRF

**Impact:** Zero - maintains current secure architecture with clear documentation for future developers

