"""
JWT Security Configuration for MITA Finance Application
Provides secure JWT token configuration and validation
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import uuid

logger = logging.getLogger(__name__)

# ============================================================================
# SECURE JWT CONFIGURATION
# ============================================================================

def get_jwt_secret() -> str:
    """
    Get JWT secret with security validation
    Prevents use of fallback/development secrets in production
    """
    secret = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
    
    # Security validation - prevent insecure fallback secrets
    insecure_secrets = [
        "fallback-secret-key",
        "emergency-jwt-secret", 
        "dev-secret",
        "test-secret",
        "secret",
        "jwt-secret"
    ]
    
    if not secret:
        raise ValueError(
            "JWT_SECRET environment variable not configured. "
            "This is required for secure token generation."
        )
    
    if secret in insecure_secrets or len(secret) < 32:
        raise ValueError(
            f"Insecure JWT secret detected. "
            f"JWT secrets must be at least 32 characters and cryptographically random. "
            f"Current secret length: {len(secret)}"
        )
    
    return secret

def create_secure_access_token(user_data: Dict[str, Any]) -> str:
    """
    Create secure access token with proper expiration and claims
    """
    now = datetime.utcnow()
    
    payload = {
        'sub': str(user_data.get('sub', user_data.get('user_id', ''))),
        'iat': now,
        'exp': now + timedelta(minutes=15),  # Short-lived access token
        'jti': str(uuid.uuid4()),  # Unique token ID for revocation
        'aud': 'mita-api',         # Audience validation
        'iss': 'mita-auth',        # Issuer validation
        'token_type': 'access_token',
        'is_premium': user_data.get('is_premium', False),
        'country': user_data.get('country', 'US')
    }
    
    # Remove sensitive data from payload (email should not be in JWT)
    # JWTs are base64-encoded and readable
    
    return jwt.encode(payload, get_jwt_secret(), algorithm='HS256')

def create_secure_refresh_token(user_data: Dict[str, Any]) -> str:
    """
    Create secure refresh token with longer expiration
    """
    now = datetime.utcnow()
    
    payload = {
        'sub': str(user_data.get('sub', user_data.get('user_id', ''))),
        'iat': now,
        'exp': now + timedelta(days=30),  # Longer-lived refresh token
        'jti': str(uuid.uuid4()),  # Unique token ID for revocation
        'aud': 'mita-api',
        'iss': 'mita-auth',
        'token_type': 'refresh_token'
    }
    
    return jwt.encode(payload, get_jwt_secret(), algorithm='HS256')

def validate_jwt_token(token: str, token_type: str = 'access_token') -> Optional[Dict[str, Any]]:
    """
    Validate JWT token with comprehensive security checks
    """
    try:
        payload = jwt.decode(
            token, 
            get_jwt_secret(), 
            algorithms=['HS256'],
            audience='mita-api',
            issuer='mita-auth'
        )
        
        # Validate token type
        if payload.get('token_type') != token_type:
            logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('token_type')}")
            return None
            
        # Additional security validations
        if not payload.get('sub'):
            logger.warning("Token missing subject (sub) claim")
            return None
            
        if not payload.get('jti'):
            logger.warning("Token missing JWT ID (jti) claim")
            return None
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.info("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None

def create_secure_token_pair(user_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Create secure access and refresh token pair
    """
    access_token = create_secure_access_token(user_data)
    refresh_token = create_secure_refresh_token(user_data)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

# ============================================================================
# SECURITY VALIDATION
# ============================================================================

def validate_jwt_security_config() -> Dict[str, Any]:
    """
    Validate JWT security configuration
    """
    validation_result = {
        "valid": True,
        "issues": [],
        "warnings": [],
        "config": {
            "secret_configured": False,
            "secret_length": 0,
            "algorithm": "HS256",
            "audience_validation": True,
            "issuer_validation": True
        }
    }
    
    try:
        secret = get_jwt_secret()
        validation_result["config"]["secret_configured"] = True
        validation_result["config"]["secret_length"] = len(secret)
        
        if len(secret) < 64:
            validation_result["warnings"].append(
                f"JWT secret length ({len(secret)}) below recommended minimum (64 characters)"
            )
        
    except ValueError as e:
        validation_result["valid"] = False
        validation_result["issues"].append(str(e))
        
    except Exception as e:
        validation_result["valid"] = False
        validation_result["issues"].append(f"JWT configuration error: {e}")
    
    return validation_result