from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set
from enum import Enum

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import ALGORITHM, settings
from app.core.upstash import blacklist_token as upstash_blacklist_token
from app.core.upstash import is_token_blacklisted
from app.core.audit_logging import log_security_event

logger = logging.getLogger(__name__)

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT issuer and audience for MITA financial application
JWT_ISSUER = "mita-finance-api"
JWT_AUDIENCE = "mita-finance-app"


class TokenScope(Enum):
    """OAuth 2.0 style scopes for MITA financial application."""
    # Profile scopes
    READ_PROFILE = "read:profile"
    WRITE_PROFILE = "write:profile"
    
    # Transaction scopes
    READ_TRANSACTIONS = "read:transactions"
    WRITE_TRANSACTIONS = "write:transactions"
    DELETE_TRANSACTIONS = "delete:transactions"
    
    # Financial data scopes
    READ_FINANCIAL_DATA = "read:financial_data"
    WRITE_FINANCIAL_DATA = "write:financial_data"
    
    # Budget scopes
    READ_BUDGET = "read:budget"
    WRITE_BUDGET = "write:budget"
    MANAGE_BUDGET = "manage:budget"
    
    # Analytics scopes
    READ_ANALYTICS = "read:analytics"
    ADVANCED_ANALYTICS = "advanced:analytics"
    
    # Administrative scopes
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"
    ADMIN_AUDIT = "admin:audit"
    
    # Premium features
    PREMIUM_FEATURES = "premium:features"
    PREMIUM_AI_INSIGHTS = "premium:ai_insights"
    
    # OCR and receipt processing
    PROCESS_RECEIPTS = "process:receipts"
    OCR_ANALYSIS = "ocr:analysis"
    
    @classmethod
    def get_scope_groups(cls) -> Dict[str, List[str]]:
        """Get predefined scope groups for different user roles."""
        basic_scopes = [
            cls.READ_PROFILE.value,
            cls.WRITE_PROFILE.value,
            cls.READ_TRANSACTIONS.value,
            cls.WRITE_TRANSACTIONS.value,
            cls.READ_FINANCIAL_DATA.value,
            cls.READ_BUDGET.value,
            cls.WRITE_BUDGET.value,
            cls.READ_ANALYTICS.value,
            cls.PROCESS_RECEIPTS.value,
        ]
        
        premium_scopes = basic_scopes + [
            cls.DELETE_TRANSACTIONS.value,
            cls.WRITE_FINANCIAL_DATA.value,
            cls.MANAGE_BUDGET.value,
            cls.ADVANCED_ANALYTICS.value,
            cls.PREMIUM_FEATURES.value,
            cls.PREMIUM_AI_INSIGHTS.value,
            cls.OCR_ANALYSIS.value,
        ]
        
        admin_scopes = premium_scopes + [
            cls.ADMIN_USERS.value,
            cls.ADMIN_SYSTEM.value,
            cls.ADMIN_AUDIT.value,
        ]
        
        return {
            "basic_user": basic_scopes,
            "premium_user": premium_scopes,
            "admin": admin_scopes,
        }


class UserRole(Enum):
    """User roles for MITA financial application."""
    BASIC_USER = "basic_user"
    PREMIUM_USER = "premium_user"
    ADMIN = "admin"


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def _current_secret() -> str:
    return settings.SECRET_KEY


def _previous_secret() -> str | None:
    return settings.JWT_PREVIOUS_SECRET


def _create_token(data: dict, expires_delta: timedelta, token_type: str, scopes: List[str] = None) -> str:
    """Create JWT token with comprehensive security claims and OAuth 2.0 scopes.
    
    Args:
        data: Token payload data
        expires_delta: Token expiration time
        token_type: Type of token (access_token, refresh_token)
        scopes: List of OAuth 2.0 scopes
    """
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + expires_delta
    
    # Standard JWT claims (RFC 7519)
    standard_claims = {
        "exp": int(expire.timestamp()),         # Expiration time
        "iat": int(now.timestamp()),            # Issued at
        "nbf": int(now.timestamp()),            # Not before
        "jti": str(uuid.uuid4()),               # JWT ID
        "iss": JWT_ISSUER,                      # Issuer
        "aud": JWT_AUDIENCE,                    # Audience
    }
    
    # Token-specific claims
    token_claims = {
        "token_type": token_type,
        "scope": " ".join(scopes) if scopes else "",  # OAuth 2.0 scope format
    }
    
    # Financial application specific claims
    financial_claims = {}
    if "user_id" in data:
        financial_claims["user_id"] = str(data["user_id"])  # Ensure string format
    if "role" in data:
        financial_claims["role"] = data["role"]
    if "is_premium" in data:
        financial_claims["is_premium"] = bool(data["is_premium"])
    if "country" in data:
        financial_claims["country"] = data["country"]
        
    # Security metadata
    security_claims = {
        "token_version": "2.0",                # Token format version
        "security_level": "high",             # Security level indicator
    }
    
    # Combine all claims
    to_encode.update(standard_claims)
    to_encode.update(token_claims)
    to_encode.update(financial_claims)
    to_encode.update(security_claims)
    
    # Log token creation for audit
    logger.debug(f"Creating {token_type} with scopes: {scopes or []} for user: {data.get('user_id', 'unknown')}")
    
    return jwt.encode(to_encode, _current_secret(), algorithm=ALGORITHM)


def revoke_user_tokens(user_id: str) -> int:
    """Revoke all tokens for a specific user.
    
    Note: This implementation requires storing active JTIs per user.
    For now, we'll implement user-level revocation by updating user's token_version.
    """
    logger.warning(f"User token revocation requested for user {user_id}")
    log_security_event("user_token_revocation_requested", {"user_id": user_id})
    
    # TODO: Implement user-level token revocation
    # This could be done by:
    # 1. Storing active JTIs per user in Redis
    # 2. Or adding a token_version field to User model
    # 3. Or maintaining a user blacklist with timestamp
    
    return 0


def get_token_info(token: str) -> Optional[Dict[str, Any]]:
    """Get information about a token without validating blacklist."""
    secrets = [_current_secret()]
    prev = _previous_secret()
    if prev:
        secrets.append(prev)

    for secret in secrets:
        try:
            payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
            return {
                "jti": payload.get("jti"),
                "user_id": payload.get("sub"),
                "scope": payload.get("scope"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
                "is_expired": payload.get("exp", 0) < time.time()
            }
        except JWTError:
            continue
    
    return None


def validate_token_security(token: str) -> Dict[str, Any]:
    """Validate token security properties for audit purposes."""
    info = get_token_info(token)
    if not info:
        return {"valid": False, "reason": "invalid_token"}
    
    now = time.time()
    
    validation = {
        "valid": True,
        "jti_present": bool(info.get("jti")),
        "user_id_present": bool(info.get("user_id")),
        "scope_valid": info.get("scope") in ["access_token", "refresh_token"],
        "not_expired": info.get("exp", 0) > now,
        "issued_recently": (now - info.get("iat", 0)) < 86400 * 30,  # 30 days
        "time_to_expiry": max(0, info.get("exp", 0) - now)
    }
    
    # Check if token is blacklisted
    jti = info.get("jti")
    if jti:
        try:
            validation["is_blacklisted"] = is_token_blacklisted(jti)
        except Exception as e:
            validation["blacklist_check_error"] = str(e)
            validation["is_blacklisted"] = None
    
    return validation


def create_access_token(
    data: dict, 
    expires_delta: timedelta | None = None, 
    scopes: List[str] = None,
    user_role: str = None
) -> str:
    """Create access token with OAuth 2.0 scopes and comprehensive security validation.
    
    Args:
        data: Token payload data (must include 'sub' for user ID)
        expires_delta: Optional custom expiration time
        scopes: List of OAuth 2.0 scopes for this token
        user_role: User role for automatic scope assignment
    """
    if not data.get("sub"):
        raise ValueError("Token data must include 'sub' (user ID)")
    
    # Determine scopes based on user role if not explicitly provided
    if not scopes and user_role:
        scope_groups = TokenScope.get_scope_groups()
        scopes = scope_groups.get(user_role, scope_groups["basic_user"])
    elif not scopes:
        # Default to basic user scopes
        scopes = TokenScope.get_scope_groups()["basic_user"]
    
    # Validate scopes
    valid_scopes = [scope.value for scope in TokenScope]
    invalid_scopes = [s for s in scopes if s not in valid_scopes]
    if invalid_scopes:
        raise ValueError(f"Invalid scopes: {invalid_scopes}")
    
    # Add security metadata
    enhanced_data = data.copy()
    enhanced_data["user_id"] = data["sub"]  # Duplicate for clarity
    if user_role:
        enhanced_data["role"] = user_role
    
    token = _create_token(
        enhanced_data,
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "access_token",
        scopes
    )
    
    # Log token creation for security audit
    log_security_event("access_token_created", {
        "user_id": data["sub"],
        "scopes": scopes,
        "role": user_role,
        "expires_in_minutes": (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).total_seconds() / 60
    })
    
    logger.debug(f"Created access token for user {data.get('sub')} with scopes: {scopes}")
    return token


def create_refresh_token(data: dict, user_role: str = None) -> str:
    """Create refresh token with security validation.
    
    Args:
        data: Token payload data (must include 'sub' for user ID)
        user_role: User role for metadata
    """
    if not data.get("sub"):
        raise ValueError("Token data must include 'sub' (user ID)")
    
    # Add security metadata
    enhanced_data = data.copy()
    enhanced_data["user_id"] = data["sub"]  # Duplicate for clarity
    if user_role:
        enhanced_data["role"] = user_role
    
    # Refresh tokens have minimal scopes - just for token refresh
    refresh_scopes = ["refresh:token"]
    
    token = _create_token(
        enhanced_data,
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh_token",
        refresh_scopes
    )
    
    # Log token creation for security audit
    log_security_event("refresh_token_created", {
        "user_id": data["sub"],
        "role": user_role,
        "expires_in_days": REFRESH_TOKEN_EXPIRE_DAYS
    })
    
    logger.debug(f"Created refresh token for user {data.get('sub')}")
    return token


def verify_token(
    token: str, 
    token_type: str = "access_token", 
    required_scopes: List[str] = None
) -> Dict[str, Any] | None:
    """Verify JWT token with comprehensive security checks.
    
    Args:
        token: JWT token string
        scope: Expected token scope (access_token or refresh_token)
        
    Returns:
        Token payload if valid, None otherwise
    """
    if not token or len(token) < 10:
        logger.warning("Invalid token format received")
        return None
    
    secrets = [_current_secret()]
    prev = _previous_secret()
    if prev:
        secrets.append(prev)

    last_error = None
    for i, secret in enumerate(secrets):
        try:
            payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
            
            # Validate token type
            if payload.get("token_type") != token_type:
                logger.warning(f"Token type mismatch: expected {token_type}, got {payload.get('token_type')}")
                log_security_event("token_type_mismatch", {
                    "expected_type": token_type,
                    "actual_type": payload.get("token_type")
                })
                raise JWTError("Invalid token type")
            
            # Validate issuer (iss) and audience (aud)
            if payload.get("iss") != JWT_ISSUER:
                logger.warning(f"Token issuer mismatch: expected {JWT_ISSUER}, got {payload.get('iss')}")
                log_security_event("token_issuer_mismatch", {
                    "expected_issuer": JWT_ISSUER,
                    "actual_issuer": payload.get("iss")
                })
                raise JWTError("Invalid token issuer")
            
            if payload.get("aud") != JWT_AUDIENCE:
                logger.warning(f"Token audience mismatch: expected {JWT_AUDIENCE}, got {payload.get('aud')}")
                log_security_event("token_audience_mismatch", {
                    "expected_audience": JWT_AUDIENCE,
                    "actual_audience": payload.get("aud")
                })
                raise JWTError("Invalid token audience")
            
            # Validate required scopes if specified
            if required_scopes:
                token_scopes = payload.get("scope", "").split()
                missing_scopes = [scope for scope in required_scopes if scope not in token_scopes]
                if missing_scopes:
                    logger.warning(f"Token missing required scopes: {missing_scopes}")
                    log_security_event("insufficient_token_scopes", {
                        "required_scopes": required_scopes,
                        "token_scopes": token_scopes,
                        "missing_scopes": missing_scopes,
                        "user_id": payload.get("sub")
                    })
                    raise JWTError(f"Insufficient token scopes: {missing_scopes}")
            
            # Check expiration
            exp = payload.get("exp")
            if exp and exp < time.time():
                logger.debug("Token has expired")
                raise JWTError("Token expired")
            
            # Check blacklist
            jti = payload.get("jti")
            if jti:
                try:
                    if is_token_blacklisted(jti):
                        logger.warning(f"Blacklisted token access attempt: {jti[:8]}...")
                        log_security_event("blacklisted_token_usage_attempt", {
                            "jti": jti[:8] + "...",
                            "scope": scope
                        })
                        raise JWTError("Token is blacklisted")
                except Exception as blacklist_error:
                    logger.error(f"Error checking token blacklist: {blacklist_error}")
                    # Fail-open for blacklist checks to maintain availability
                    # but log the security concern
                    log_security_event("blacklist_check_failed", {
                        "jti": jti[:8] + "...",
                        "error": str(blacklist_error)
                    })
            
            # Validate required claims (enhanced for financial application)
            required_claims = ["sub", "exp", "jti", "iss", "aud", "token_type"]
            for claim in required_claims:
                if not payload.get(claim):
                    logger.warning(f"Missing required claim: {claim}")
                    raise JWTError(f"Missing claim: {claim}")
            
            # Validate not-before (nbf) claim if present
            nbf = payload.get("nbf")
            if nbf and nbf > time.time():
                logger.warning("Token not yet valid (nbf claim)")
                raise JWTError("Token not yet valid")
            
            logger.debug(f"Token verified successfully with secret {i + 1}")
            return payload
            
        except JWTError as e:
            last_error = e
            continue
    
    if last_error:
        logger.debug(f"Token verification failed: {last_error}")
    return None


def blacklist_token(token: str) -> bool:
    """Blacklist a JWT token with enhanced security and monitoring.
    
    Args:
        token: JWT token string to blacklist
        
    Returns:
        bool: True if successfully blacklisted, False otherwise
    """
    if not token:
        logger.warning("Attempted to blacklist empty token")
        return False
    
    secrets = [_current_secret()]
    prev = _previous_secret()
    if prev:
        secrets.append(prev)

    for secret in secrets:
        try:
            payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp")
            user_id = payload.get("sub")
            token_scopes = payload.get("scope", "")
            token_type = payload.get("token_type", "unknown")
            
            if not jti:
                logger.warning("Token missing JTI, cannot blacklist")
                return False
                
            if not exp:
                logger.warning("Token missing expiration, cannot determine TTL")
                return False
            
            # Calculate TTL with safety bounds
            ttl = max(1, int(exp - time.time()))
            if ttl > 86400 * 7:  # Max 7 days
                logger.warning(f"Token TTL too long ({ttl}s), capping at 7 days")
                ttl = 86400 * 7
            
            logger.info(f"Blacklisting {token_type} token for user {user_id}: {jti[:8]}... (TTL: {ttl}s)")
            
            try:
                upstash_blacklist_token(jti, ttl)
                log_security_event("token_blacklisted", {
                    "jti": jti[:8] + "...",
                    "user_id": user_id,
                    "token_type": token_type,
                    "scopes": token_scopes,
                    "ttl": ttl
                })
                return True
            except Exception as blacklist_error:
                logger.error(f"Failed to blacklist token {jti[:8]}...: {blacklist_error}")
                log_security_event("token_blacklist_failed", {
                    "jti": jti[:8] + "...",
                    "user_id": user_id,
                    "error": str(blacklist_error)
                })
                # Re-raise for critical failures
                raise
            
        except JWTError as jwt_error:
            logger.debug(f"Could not decode token with secret: {jwt_error}")
            continue
    
    logger.warning("Failed to decode token for blacklisting")
    return False


# Additional utility functions for scope management

def get_user_scopes(user_role: str, is_premium: bool = False) -> List[str]:
    """Get appropriate scopes for a user based on role and premium status.
    
    Args:
        user_role: User role (basic_user, premium_user, admin)
        is_premium: Whether the user has premium features
    
    Returns:
        List of OAuth 2.0 scopes
    """
    scope_groups = TokenScope.get_scope_groups()
    
    # Determine role based on premium status if not explicitly admin
    if user_role == "admin":
        return scope_groups["admin"]
    elif is_premium or user_role == "premium_user":
        return scope_groups["premium_user"]
    else:
        return scope_groups["basic_user"]


def validate_scope_access(token_scopes: List[str], required_scope: str) -> bool:
    """Validate if token has the required scope.
    
    Args:
        token_scopes: List of scopes from the token
        required_scope: Required scope for the operation
    
    Returns:
        True if access is granted, False otherwise
    """
    return required_scope in token_scopes


def has_any_scope(token_scopes: List[str], required_scopes: List[str]) -> bool:
    """Check if token has any of the required scopes.
    
    Args:
        token_scopes: List of scopes from the token
        required_scopes: List of acceptable scopes
    
    Returns:
        True if token has at least one required scope
    """
    return any(scope in token_scopes for scope in required_scopes)


def has_all_scopes(token_scopes: List[str], required_scopes: List[str]) -> bool:
    """Check if token has all required scopes.
    
    Args:
        token_scopes: List of scopes from the token
        required_scopes: List of required scopes
    
    Returns:
        True if token has all required scopes
    """
    return all(scope in token_scopes for scope in required_scopes)


def get_scope_description(scope: str) -> str:
    """Get human-readable description of a scope.
    
    Args:
        scope: OAuth 2.0 scope string
    
    Returns:
        Human-readable description
    """
    scope_descriptions = {
        TokenScope.READ_PROFILE.value: "Read user profile information",
        TokenScope.WRITE_PROFILE.value: "Modify user profile information",
        TokenScope.READ_TRANSACTIONS.value: "Read transaction history",
        TokenScope.WRITE_TRANSACTIONS.value: "Create new transactions",
        TokenScope.DELETE_TRANSACTIONS.value: "Delete transactions",
        TokenScope.READ_FINANCIAL_DATA.value: "Access financial reports and data",
        TokenScope.WRITE_FINANCIAL_DATA.value: "Modify financial data",
        TokenScope.READ_BUDGET.value: "View budget information",
        TokenScope.WRITE_BUDGET.value: "Modify budget settings",
        TokenScope.MANAGE_BUDGET.value: "Full budget management access",
        TokenScope.READ_ANALYTICS.value: "View basic analytics",
        TokenScope.ADVANCED_ANALYTICS.value: "Access advanced analytics features",
        TokenScope.ADMIN_USERS.value: "Manage users (admin only)",
        TokenScope.ADMIN_SYSTEM.value: "System administration access",
        TokenScope.ADMIN_AUDIT.value: "Access audit logs (admin only)",
        TokenScope.PREMIUM_FEATURES.value: "Access premium features",
        TokenScope.PREMIUM_AI_INSIGHTS.value: "Access AI-powered insights",
        TokenScope.PROCESS_RECEIPTS.value: "Upload and process receipts",
        TokenScope.OCR_ANALYSIS.value: "Advanced OCR receipt analysis",
    }
    
    return scope_descriptions.get(scope, f"Unknown scope: {scope}")


def create_token_pair(user_data: dict, user_role: str = None) -> Dict[str, str]:
    """Create both access and refresh tokens for a user.
    
    Args:
        user_data: User data dictionary (must include 'sub' for user ID)
        user_role: User role for scope assignment
    
    Returns:
        Dictionary with access_token and refresh_token
    """
    if not user_data.get("sub"):
        raise ValueError("User data must include 'sub' (user ID)")
    
    # Create access token with appropriate scopes
    access_token = create_access_token(user_data, user_role=user_role)
    
    # Create refresh token
    refresh_token = create_refresh_token(user_data, user_role=user_role)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer"
    }
