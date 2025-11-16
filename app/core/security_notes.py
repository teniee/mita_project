"""
MITA API Security Architecture Notes
=====================================

This file documents critical security architecture decisions for MITA API.
Read this before implementing any authentication or session management changes.

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
If MITA were to add any of these features:
- Cookie-based session authentication
- JWT tokens stored in cookies (instead of Authorization header)
- OAuth callbacks using session-based state management
- Any set_cookie() calls for authentication purposes

Then CSRF protection MUST be implemented using one of:
- Double-submit cookie pattern
- Synchronizer token pattern (with fastapi-csrf-protect)
- SameSite cookie attributes (strict mode)

IMPLEMENTATION EXAMPLE (IF NEEDED):
```python
# Only implement if cookies are introduced!
from fastapi_csrf_protect import CsrfProtect

@CsrfProtect.load_config
def get_csrf_config():
    return {
        "secret_key": settings.SECRET_KEY,
        "cookie_name": "csrftoken",
        "header_name": "X-CSRF-Token",
        "cookie_samesite": "strict",
        "cookie_secure": True
    }

@router.post("/protected-endpoint")
async def protected_endpoint(csrf_protect: CsrfProtect = Depends()):
    await csrf_protect.validate_csrf()
    # ... endpoint logic
```

ARCHITECTURE CONSTRAINTS
------------------------

1. DO NOT add SessionMiddleware without implementing CSRF protection
2. DO NOT use response.set_cookie() for authentication tokens
3. DO NOT store JWT tokens in cookies (use Authorization header only)
4. DO maintain stateless authentication architecture

COMPLIANCE NOTES
----------------
- OWASP: CSRF protection recommended for cookie-based auth only
  https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

- RFC 6750: Bearer tokens in Authorization header don't require CSRF protection
  https://datatracker.ietf.org/doc/html/rfc6750

- PCI DSS: Focused on data encryption and access control (covered by JWT)
  MITA complies via HTTPS enforcement, token rotation, and audit logging

SECURITY LAYERS IN MITA
------------------------

Layer 1: Transport Security
- HTTPS enforcement with TLS 1.3
- HSTS header (max-age=63072000; includeSubDomains)
- Secure cipher suite configuration

Layer 2: Authentication & Authorization
- JWT with OAuth 2.0 scopes (read:*, write:*, manage:budget, etc.)
- Short-lived access tokens (2 hours)
- Refresh token rotation
- Token blacklisting on logout
- Token version tracking for revocation
- Role-based access control (RBAC)

Layer 3: Input Validation & Sanitization
- Pydantic schema validation
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via content sanitization
- Email validation and normalization
- Password strength validation

Layer 4: Rate Limiting & Anti-Abuse
- Progressive rate limiting (stricter after failures)
- Per-endpoint rate limits
- Sliding window algorithm
- IP-based tracking
- Redis-based rate limit storage

Layer 5: Audit & Monitoring
- Comprehensive security event logging
- Authentication attempt tracking
- Failed login monitoring
- Suspicious activity detection
- Sentry integration for error tracking
- Prometheus metrics for performance

Layer 6: CORS & Headers
- Strict origin allowlist
- Security headers (X-Frame-Options, CSP, etc.)
- Referrer policy enforcement
- XSS protection header

WHAT'S NOT IMPLEMENTED (by design)
-----------------------------------

1. CSRF Protection
   - Reason: No cookie-based authentication
   - See: ADR-20251115-csrf-protection-analysis.md

2. Session Management
   - Reason: Stateless API design with JWT tokens
   - All state stored client-side

3. Server-Side Session Store
   - Reason: Stateless architecture for horizontal scaling
   - Redis used only for caching and rate limiting

CODE REVIEW CHECKLIST
----------------------

When reviewing PRs, REJECT changes that:
1. Add SessionMiddleware without CSRF protection
2. Use response.set_cookie() for authentication
3. Store JWT tokens in cookies
4. Implement OAuth state management using cookies
5. Add any cookie-based authentication mechanism

When reviewing PRs, APPROVE changes that:
1. Maintain Authorization header for all auth tokens
2. Use secure storage for tokens (Flutter secure storage)
3. Return tokens in JSON response body only
4. Follow stateless architecture patterns
5. Document security decisions in ADRs

MOBILE APP INTEGRATION
-----------------------

Flutter app security requirements:
1. Store tokens in flutter_secure_storage (encrypted)
2. Send tokens via Authorization: Bearer <token>
3. Never store tokens in plain SharedPreferences
4. Implement biometric authentication for token access
5. Handle token expiration gracefully with refresh flow
6. Clear tokens on logout/uninstall

TESTING SECURITY
----------------

Security tests to run:
1. Verify no cookies in auth responses
   - Check /api/auth/register response headers
   - Check /api/auth/login response headers
   - Check /api/auth/refresh response headers

2. Verify Authorization header requirement
   - Protected endpoints return 401 without header
   - Invalid tokens return 401
   - Expired tokens return 401

3. Verify CORS protection
   - Cross-origin requests from untrusted domains blocked
   - Preflight OPTIONS requests handled correctly
   - Credentials policy enforced

4. Verify rate limiting
   - Excessive login attempts blocked
   - Rate limit headers present
   - 429 status code returned on limit

5. Verify audit logging
   - Authentication events logged
   - Failed login attempts tracked
   - Security events have user context

INCIDENT RESPONSE
------------------

If cookie-based auth is accidentally introduced:

1. IMMEDIATE ACTION
   - Revert the PR that introduced cookies
   - Notify security team
   - Audit logs for any exploitation attempts

2. ASSESSMENT
   - Check if CSRF tokens were implemented
   - Review all endpoints using cookies
   - Assess exposure window

3. REMEDIATION
   - Remove all cookie-based authentication
   - Implement CSRF protection if cookies must stay
   - Update security documentation
   - Add automated tests to prevent regression

FUTURE CONSIDERATIONS
---------------------

If MITA adds a web browser client:
1. MUST maintain header-based authentication
2. DO NOT use cookie-based sessions
3. Store tokens in localStorage or sessionStorage (with XSS protection)
4. Implement Content Security Policy
5. Consider OAuth PKCE flow for public clients

If MITA integrates with third-party OAuth providers (Google, Apple):
1. Use state parameter for CSRF protection in OAuth flow
2. Validate state parameter on callback
3. Do NOT store state in session cookies
4. Use cryptographically secure random state values
5. Implement nonce for additional security

REFERENCES
----------
- ADR: docs/adr/ADR-20251115-csrf-protection-analysis.md
- OWASP CSRF: https://owasp.org/www-community/attacks/csrf
- RFC 6750: https://datatracker.ietf.org/doc/html/rfc6750
- FastAPI Security: https://fastapi.tiangolo.com/tutorial/security/
- MITA README: README.md (Architecture Overview)

Last Updated: 2025-11-15
Maintained By: CTO & Principal Engineer
Review Frequency: Quarterly or before major security changes
"""
