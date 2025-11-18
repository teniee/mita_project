from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set, Union
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

import jwt
from jwt import InvalidTokenError
from app.core.config import ALGORITHM, settings
from app.core.audit_logging import log_security_event
# UPDATED: Use centralized password security configuration
from app.core.password_security import (
    hash_password_sync,
    hash_password_async, 
    verify_password_sync,
    verify_password_async,
    validate_bcrypt_configuration
)

logger = logging.getLogger(__name__)

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = 7

# SECURITY UPDATE: Validate bcrypt configuration on startup
try:
    validation_result = validate_bcrypt_configuration()
    if not validation_result["valid"]:
        logger.error(f"Bcrypt configuration validation failed: {validation_result['issues']}")
    elif validation_result["warnings"]:
        logger.warning(f"Bcrypt configuration warnings: {validation_result['warnings']}")
    else:
        logger.info(f"Bcrypt configuration validated successfully with {validation_result['configuration']['rounds']} rounds")
except Exception as e:
    logger.error(f"Failed to validate bcrypt configuration: {e}")

# Token operation cache to reduce JWT decoding overhead
_token_cache: Dict[str, Dict[str, Any]] = {}
_cache_max_size = 200  # Reduced for Render memory constraints
_cache_cleanup_interval = 180  # 3 minutes - more frequent cleanup

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
    """
    Synchronous password hashing using centralized secure configuration
    UPDATED: Now uses 12 rounds (production) for proper security
    """
    return hash_password_sync(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Synchronous password verification using centralized configuration
    UPDATED: Maintains compatibility with existing hashes while using secure settings
    """
    return verify_password_sync(plain, hashed)


async def async_hash_password(plain: str) -> str:
    """
    Asynchronous password hashing using centralized secure configuration
    UPDATED: Now uses proper async implementation with thread pool to prevent blocking
    """
    return await hash_password_async(plain)


async def async_verify_password(plain: str, hashed: str) -> bool:
    """
    Asynchronous password verification using centralized configuration
    UPDATED: Uses proper async implementation while maintaining backward compatibility
    """
    return await verify_password_async(plain, hashed)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def _current_secret() -> str:
    return settings.SECRET_KEY


def _previous_secret() -> Optional[str]:
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
        
    # Security metadata (include user's current token_version for revocation tracking)
    security_claims = {
        "token_version": "2.0",                # Token format version
        "security_level": "high",             # Security level indicator
        "token_version_id": data.get("token_version_id", 1),  # User's token version for revocation
    }
    
    # Combine all claims
    to_encode.update(standard_claims)
    to_encode.update(token_claims)
    to_encode.update(financial_claims)
    to_encode.update(security_claims)
    
    # Log token creation for audit
    logger.debug(f"Creating {token_type} with scopes: {scopes or []} for user: {data.get('user_id', 'unknown')}")
    
    return jwt.encode(to_encode, _current_secret(), algorithm=ALGORITHM)


async def revoke_user_tokens(
    user_id: str,
    reason: str = "security",
    revoked_by: Optional[str] = None
) -> int:
    """Revoke all tokens for a specific user.
    
    Args:
        user_id: User ID whose tokens should be revoked
        reason: Reason for mass revocation
        revoked_by: ID of admin who initiated the revocation
        
    Returns:
        Number of tokens revoked
    """
    try:
        logger.info(f"User token revocation requested for user {user_id}")
        log_security_event("user_token_revocation_requested", {
            "user_id": user_id,
            "reason": reason,
            "revoked_by": revoked_by
        })
        
        # Import here to avoid circular imports
        from app.services.token_blacklist_service import get_blacklist_service, BlacklistReason, TokenType
        
        # Map reason strings to enum values
        reason_mapping = {
            "logout": BlacklistReason.LOGOUT,
            "revoke": BlacklistReason.REVOKE,
            "admin": BlacklistReason.ADMIN_REVOKE,
            "security": BlacklistReason.SECURITY_INCIDENT,
            "rotation": BlacklistReason.TOKEN_ROTATION,
            "suspicious": BlacklistReason.SUSPICIOUS_ACTIVITY
        }
        
        blacklist_reason = reason_mapping.get(reason, BlacklistReason.SECURITY_INCIDENT)
        blacklist_service = await get_blacklist_service()
        
        revoked_count = await blacklist_service.blacklist_user_tokens(
            user_id=user_id,
            token_type=TokenType.ALL,
            reason=blacklist_reason,
            revoked_by=revoked_by
        )
        
        logger.info(f"Revoked {revoked_count} tokens for user {user_id}")
        log_security_event("user_token_revocation_completed", {
            "user_id": user_id,
            "tokens_revoked": revoked_count,
            "reason": reason
        })
        
        return revoked_count
        
    except Exception as e:
        logger.error(f"Failed to revoke user tokens for {user_id}: {e}")
        log_security_event("user_token_revocation_failed", {
            "user_id": user_id,
            "error": str(e)
        })
        return 0


def _cleanup_token_cache():
    """Clean up expired entries from token cache"""
    global _token_cache
    current_time = time.time()
    
    # Remove expired entries
    expired_keys = [
        token_hash for token_hash, cache_entry in _token_cache.items()
        if cache_entry.get("cache_expiry", 0) < current_time
    ]
    
    for key in expired_keys:
        _token_cache.pop(key, None)
    
    # If cache is still too large, remove oldest entries
    if len(_token_cache) > _cache_max_size:
        sorted_items = sorted(_token_cache.items(), key=lambda x: x[1].get("cache_time", 0))
        to_remove = len(_token_cache) - _cache_max_size
        for i in range(to_remove):
            _token_cache.pop(sorted_items[i][0], None)


def get_token_info(token: str) -> Optional[Dict[str, Any]]:
    """Get information about a token without validating blacklist - with caching for performance."""
    # Create cache key (first 16 chars of token hash for security)
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
    current_time = time.time()
    
    # Check cache first
    if token_hash in _token_cache:
        cache_entry = _token_cache[token_hash]
        if cache_entry.get("cache_expiry", 0) > current_time:
            return cache_entry["token_info"]
    
    # Clean up cache periodically
    if len(_token_cache) > _cache_max_size or current_time % _cache_cleanup_interval < 1:
        _cleanup_token_cache()
    
    secrets = [_current_secret()]
    prev = _previous_secret()
    if prev:
        secrets.append(prev)

    for secret in secrets:
        try:
            payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
            token_info = {
                "jti": payload.get("jti"),
                "user_id": payload.get("sub"),
                "scope": payload.get("scope"),
                "token_type": payload.get("token_type"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
                "is_expired": payload.get("exp", 0) < time.time()
            }
            
            # Cache the result for 5 minutes or until token expiry, whichever is shorter
            cache_expiry = min(
                current_time + 300,  # 5 minutes
                payload.get("exp", current_time + 300)  # Token expiry
            )
            
            _token_cache[token_hash] = {
                "token_info": token_info,
                "cache_time": current_time,
                "cache_expiry": cache_expiry
            }
            
            return token_info
        except InvalidTokenError:
            continue
    
    return None


async def validate_token_security(token: str) -> Dict[str, Any]:
    """Validate token security properties for audit purposes."""
    info = get_token_info(token)
    if not info:
        return {"valid": False, "reason": "invalid_token"}
    
    now = time.time()
    
    validation = {
        "valid": True,
        "jti_present": bool(info.get("jti")),
        "user_id_present": bool(info.get("user_id")),
        "token_type_valid": info.get("token_type") in ["access_token", "refresh_token"],
        "not_expired": info.get("exp", 0) > now,
        "issued_recently": (now - info.get("iat", 0)) < 86400 * 30,  # 30 days
        "time_to_expiry": max(0, info.get("exp", 0) - now)
    }
    
    # Check if token is blacklisted using new service
    jti = info.get("jti")
    if jti:
        try:
            from app.services.token_blacklist_service import get_blacklist_service
            blacklist_service = await get_blacklist_service()
            validation["is_blacklisted"] = await blacklist_service.is_token_blacklisted(jti)
        except Exception as e:
            validation["blacklist_check_error"] = str(e)
            validation["is_blacklisted"] = None
    
    return validation


def create_access_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None, 
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


async def verify_token(
    token: str, 
    token_type: str = "access_token", 
    required_scopes: List[str] = None
) -> Optional[Dict[str, Any]]:
    """Verify JWT token with comprehensive security checks.
    
    Args:
        token: JWT token string
        token_type: Expected token type (access_token or refresh_token)
        required_scopes: List of required OAuth 2.0 scopes
        
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
                raise InvalidTokenError("Invalid token type")
            
            # Validate issuer (iss) and audience (aud)
            if payload.get("iss") != JWT_ISSUER:
                logger.warning(f"Token issuer mismatch: expected {JWT_ISSUER}, got {payload.get('iss')}")
                log_security_event("token_issuer_mismatch", {
                    "expected_issuer": JWT_ISSUER,
                    "actual_issuer": payload.get("iss")
                })
                raise InvalidTokenError("Invalid token issuer")
            
            if payload.get("aud") != JWT_AUDIENCE:
                logger.warning(f"Token audience mismatch: expected {JWT_AUDIENCE}, got {payload.get('aud')}")
                log_security_event("token_audience_mismatch", {
                    "expected_audience": JWT_AUDIENCE,
                    "actual_audience": payload.get("aud")
                })
                raise InvalidTokenError("Invalid token audience")
            
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
                    raise InvalidTokenError(f"Insufficient token scopes: {missing_scopes}")
            
            # Check expiration
            exp = payload.get("exp")
            if exp and exp < time.time():
                logger.debug("Token has expired")
                raise InvalidTokenError("Token expired")

            # Get jti early for logging (used in token version check)
            jti = payload.get("jti")

            # Check token version against user's current token version
            user_id = payload.get("sub")
            if user_id:
                try:
                    # Import here to avoid circular imports
                    from app.core.async_session import get_async_db
                    from app.db.models import User
                    from sqlalchemy import select

                    async for db in get_async_db():
                        user_query = select(User).where(User.id == user_id)
                        result = await db.execute(user_query)
                        user = result.scalar_one_or_none()

                        if user:
                            # Token version in payload
                            # For backwards compatibility: default to user's current version if missing
                            token_version_id = payload.get("token_version_id", user.token_version)

                            # Check if token version is outdated (only if token has explicit version)
                            # This allows old tokens without version_id to work during migration
                            if "token_version_id" in payload and token_version_id < user.token_version:
                                logger.warning(f"Token version mismatch for user {user_id}: token={token_version_id}, user={user.token_version}")
                                log_security_event("token_version_mismatch", {
                                    "user_id": user_id,
                                    "token_version": token_version_id,
                                    "current_version": user.token_version,
                                    "jti": jti[:8] + "..." if jti else "unknown"
                                })
                                raise InvalidTokenError("Token has been revoked")
                        break
                except InvalidTokenError:
                    raise
                except Exception as version_check_error:
                    logger.error(f"Error checking token version: {version_check_error}")
                    # Fail-open for version checks but log the security concern
                    log_security_event("token_version_check_failed", {
                        "user_id": user_id,
                        "error": str(version_check_error)
                    })

            # Check blacklist using new blacklist service (jti already defined above)
            if jti:
                try:
                    # Import here to avoid circular imports
                    from app.services.token_blacklist_service import get_blacklist_service
                    blacklist_service = await get_blacklist_service()

                    if await blacklist_service.is_token_blacklisted(jti):
                        logger.warning(f"Blacklisted token access attempt: {jti[:8]}...")
                        log_security_event("blacklisted_token_usage_attempt", {
                            "jti": jti[:8] + "...",
                            "token_type": token_type
                        })
                        raise InvalidTokenError("Token is blacklisted")
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
                    raise InvalidTokenError(f"Missing claim: {claim}")
            
            # Validate not-before (nbf) claim if present
            nbf = payload.get("nbf")
            if nbf and nbf > time.time():
                logger.warning("Token not yet valid (nbf claim)")
                raise InvalidTokenError("Token not yet valid")
            
            logger.debug(f"Token verified successfully with secret {i + 1}")
            return payload
            
        except InvalidTokenError as e:
            last_error = e
            continue
    
    if last_error:
        logger.debug(f"Token verification failed: {last_error}")
    return None


async def blacklist_token(
    token: str,
    reason: str = "logout",
    revoked_by: Optional[str] = None
) -> bool:
    """Blacklist a JWT token with enhanced security and monitoring.
    
    Args:
        token: JWT token string to blacklist
        reason: Reason for blacklisting (logout, revoke, admin, etc.)
        revoked_by: ID of user/admin who revoked the token
        
    Returns:
        bool: True if successfully blacklisted, False otherwise
    """
    if not token:
        logger.warning("Attempted to blacklist empty token")
        return False
    
    try:
        # Import here to avoid circular imports
        from app.services.token_blacklist_service import get_blacklist_service, BlacklistReason
        
        # Map reason strings to enum values
        reason_mapping = {
            "logout": BlacklistReason.LOGOUT,
            "revoke": BlacklistReason.REVOKE,
            "admin": BlacklistReason.ADMIN_REVOKE,
            "security": BlacklistReason.SECURITY_INCIDENT,
            "rotation": BlacklistReason.TOKEN_ROTATION,
            "suspicious": BlacklistReason.SUSPICIOUS_ACTIVITY
        }
        
        blacklist_reason = reason_mapping.get(reason, BlacklistReason.LOGOUT)
        blacklist_service = await get_blacklist_service()
        
        success = await blacklist_service.blacklist_token(
            token=token,
            reason=blacklist_reason,
            revoked_by=revoked_by
        )
        
        if success:
            logger.info(f"Token successfully blacklisted (reason: {reason})")
        else:
            logger.warning(f"Failed to blacklist token (reason: {reason})")
        
        return success
        
    except Exception as e:
        logger.error(f"Error blacklisting token: {e}")
        log_security_event("token_blacklist_error", {
            "error": str(e),
            "reason": reason
        })
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
    """Create both access and refresh tokens for a user with performance monitoring.
    
    Args:
        user_data: User data dictionary (must include 'sub' for user ID)
        user_role: User role for scope assignment
    
    Returns:
        Dictionary with access_token and refresh_token
    """
    import time
    start_time = time.time()
    
    if not user_data.get("sub"):
        raise ValueError("User data must include 'sub' (user ID)")
    
    # Create access token with appropriate scopes
    access_token = create_access_token(user_data, user_role=user_role)
    
    # Create refresh token
    refresh_token = create_refresh_token(user_data, user_role=user_role)
    
    elapsed = time.time() - start_time
    if elapsed > 1.0:  # Log if token creation takes more than 1 second
        logger.warning(f"Slow token creation: {elapsed:.2f}s for user {user_data.get('sub', 'unknown')}")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer"
    }
