"""
JWT Scope-based Authorization Middleware for MITA Financial Application

This middleware provides comprehensive OAuth 2.0 style scope-based authorization
with production-ready security features for financial applications.
"""

import logging
from typing import List, Optional, Callable, Dict, Any
from functools import wraps

from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.auth_jwt_service import (
    verify_token, 
    validate_scope_access, 
    has_any_scope, 
    has_all_scopes,
    TokenScope
)
from app.core.audit_logging import log_security_event

logger = logging.getLogger(__name__)

security = HTTPBearer()


class ScopeRequirement:
    """Class to define scope requirements for API endpoints."""
    
    def __init__(
        self, 
        required_scopes: List[str] = None,
        any_of: List[str] = None,
        all_of: List[str] = None,
        description: str = None
    ):
        """
        Initialize scope requirement.
        
        Args:
            required_scopes: Legacy single scope list (deprecated)
            any_of: User must have at least one of these scopes
            all_of: User must have all of these scopes
            description: Human-readable description of the requirement
        """
        self.any_of = any_of or required_scopes or []
        self.all_of = all_of or []
        self.description = description or "Access to protected resource"
        
        if not self.any_of and not self.all_of:
            raise ValueError("Must specify either any_of or all_of scopes")


def require_scopes(
    any_of: List[str] = None,
    all_of: List[str] = None,
    description: str = None
) -> Callable:
    """
    Decorator to require specific OAuth 2.0 scopes for endpoint access.
    
    Args:
        any_of: User must have at least one of these scopes
        all_of: User must have all of these scopes
        description: Human-readable description for audit logs
    
    Returns:
        FastAPI dependency function
    
    Example:
        @router.get("/transactions")
        @require_scopes(any_of=["read:transactions", "admin:system"])
        async def get_transactions():
            pass
    """
    requirement = ScopeRequirement(any_of=any_of, all_of=all_of, description=description)
    
    def scope_dependency(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        request: Request = None
    ) -> Dict[str, Any]:
        """Validate token and required scopes."""
        
        if not credentials or not credentials.credentials:
            logger.warning("Authorization required but no token provided")
            log_security_event("unauthorized_access_attempt", {
                "endpoint": getattr(request, "url", {}).path if request else "unknown",
                "reason": "no_token"
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization token required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify the token
        payload = verify_token(credentials.credentials, token_type="access_token")
        if not payload:
            logger.warning("Invalid or expired token provided")
            log_security_event("invalid_token_access_attempt", {
                "endpoint": getattr(request, "url", {}).path if request else "unknown",
                "reason": "invalid_token"
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Extract token scopes
        token_scopes = payload.get("scope", "").split()
        user_id = payload.get("sub")
        
        # Check scope requirements
        access_granted = True
        missing_scopes = []
        
        if requirement.any_of:
            if not has_any_scope(token_scopes, requirement.any_of):
                access_granted = False
                missing_scopes = requirement.any_of
        
        if requirement.all_of:
            missing_all = [scope for scope in requirement.all_of if scope not in token_scopes]
            if missing_all:
                access_granted = False
                missing_scopes.extend(missing_all)
        
        if not access_granted:
            logger.warning(
                f"User {user_id} attempted to access endpoint without required scopes. "
                f"Required: {requirement.any_of or requirement.all_of}, "
                f"Has: {token_scopes}, "
                f"Missing: {missing_scopes}"
            )
            
            log_security_event("insufficient_scope_access_attempt", {
                "user_id": user_id,
                "endpoint": getattr(request, "url", {}).path if request else "unknown",
                "required_scopes_any": requirement.any_of,
                "required_scopes_all": requirement.all_of,
                "token_scopes": token_scopes,
                "missing_scopes": missing_scopes,
                "description": requirement.description
            })
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_scope",
                    "error_description": f"The request requires higher privileges than provided by the access token.",
                    "required_scopes": requirement.any_of or requirement.all_of,
                    "missing_scopes": missing_scopes
                }
            )
        
        # Log successful authorization
        logger.debug(f"User {user_id} authorized for endpoint with scopes: {token_scopes}")
        log_security_event("scope_authorization_success", {
            "user_id": user_id,
            "endpoint": getattr(request, "url", {}).path if request else "unknown",
            "token_scopes": token_scopes,
            "description": requirement.description
        })
        
        return payload
    
    return Depends(scope_dependency)


# Predefined scope requirements for common financial operations

def require_profile_read():
    """Require read access to user profile."""
    return require_scopes(
        any_of=[TokenScope.READ_PROFILE.value],
        description="Read user profile information"
    )


def require_profile_write():
    """Require write access to user profile."""
    return require_scopes(
        any_of=[TokenScope.WRITE_PROFILE.value],
        description="Modify user profile information"
    )


def require_transactions_read():
    """Require read access to transaction data."""
    return require_scopes(
        any_of=[TokenScope.READ_TRANSACTIONS.value, TokenScope.ADMIN_SYSTEM.value],
        description="Read transaction history"
    )


def require_transactions_write():
    """Require write access to transaction data."""
    return require_scopes(
        any_of=[TokenScope.WRITE_TRANSACTIONS.value, TokenScope.ADMIN_SYSTEM.value],
        description="Create or modify transactions"
    )


def require_transactions_delete():
    """Require delete access to transaction data."""
    return require_scopes(
        any_of=[TokenScope.DELETE_TRANSACTIONS.value, TokenScope.ADMIN_SYSTEM.value],
        description="Delete transactions"
    )


def require_budget_read():
    """Require read access to budget data."""
    return require_scopes(
        any_of=[TokenScope.READ_BUDGET.value, TokenScope.ADMIN_SYSTEM.value],
        description="View budget information"
    )


def require_budget_write():
    """Require write access to budget data."""
    return require_scopes(
        any_of=[TokenScope.WRITE_BUDGET.value, TokenScope.MANAGE_BUDGET.value, TokenScope.ADMIN_SYSTEM.value],
        description="Modify budget settings"
    )


def require_budget_manage():
    """Require full budget management access."""
    return require_scopes(
        any_of=[TokenScope.MANAGE_BUDGET.value, TokenScope.ADMIN_SYSTEM.value],
        description="Full budget management access"
    )


def require_analytics_basic():
    """Require basic analytics access."""
    return require_scopes(
        any_of=[TokenScope.READ_ANALYTICS.value, TokenScope.ADVANCED_ANALYTICS.value, TokenScope.ADMIN_SYSTEM.value],
        description="View basic analytics"
    )


def require_analytics_advanced():
    """Require advanced analytics access (premium feature)."""
    return require_scopes(
        any_of=[TokenScope.ADVANCED_ANALYTICS.value, TokenScope.ADMIN_SYSTEM.value],
        description="Access advanced analytics features"
    )


def require_premium_features():
    """Require premium feature access."""
    return require_scopes(
        any_of=[TokenScope.PREMIUM_FEATURES.value, TokenScope.ADMIN_SYSTEM.value],
        description="Access premium features"
    )


def require_premium_ai_insights():
    """Require premium AI insights access."""
    return require_scopes(
        any_of=[TokenScope.PREMIUM_AI_INSIGHTS.value, TokenScope.ADMIN_SYSTEM.value],
        description="Access AI-powered insights"
    )


def require_receipt_processing():
    """Require receipt processing access."""
    return require_scopes(
        any_of=[TokenScope.PROCESS_RECEIPTS.value, TokenScope.ADMIN_SYSTEM.value],
        description="Upload and process receipts"
    )


def require_ocr_analysis():
    """Require OCR analysis access."""
    return require_scopes(
        any_of=[TokenScope.OCR_ANALYSIS.value, TokenScope.ADMIN_SYSTEM.value],
        description="Advanced OCR receipt analysis"
    )


def require_admin_users():
    """Require user administration access."""
    return require_scopes(
        any_of=[TokenScope.ADMIN_USERS.value],
        description="Manage users (admin only)"
    )


def require_admin_system():
    """Require system administration access."""
    return require_scopes(
        any_of=[TokenScope.ADMIN_SYSTEM.value],
        description="System administration access"
    )


def require_admin_audit():
    """Require audit log access."""
    return require_scopes(
        any_of=[TokenScope.ADMIN_AUDIT.value],
        description="Access audit logs (admin only)"
    )


# Combined scope requirements for complex operations

def require_financial_data_access():
    """Require access to read financial data."""
    return require_scopes(
        any_of=[
            TokenScope.READ_FINANCIAL_DATA.value,
            TokenScope.WRITE_FINANCIAL_DATA.value,
            TokenScope.ADMIN_SYSTEM.value
        ],
        description="Access financial reports and data"
    )


def require_financial_data_write():
    """Require access to modify financial data."""
    return require_scopes(
        any_of=[TokenScope.WRITE_FINANCIAL_DATA.value, TokenScope.ADMIN_SYSTEM.value],
        description="Modify financial data"
    )


def require_comprehensive_financial_access():
    """Require comprehensive financial access (multiple scopes)."""
    return require_scopes(
        all_of=[
            TokenScope.READ_FINANCIAL_DATA.value,
            TokenScope.READ_TRANSACTIONS.value,
            TokenScope.READ_BUDGET.value
        ],
        description="Comprehensive financial data access"
    )


# Utility functions for scope checking within endpoints

def check_scope_in_endpoint(token_payload: Dict[str, Any], required_scope: str) -> bool:
    """
    Check if token has required scope within an endpoint.
    
    Args:
        token_payload: JWT payload from verified token
        required_scope: Required scope
    
    Returns:
        True if scope is present
    """
    token_scopes = token_payload.get("scope", "").split()
    return validate_scope_access(token_scopes, required_scope)


def ensure_scope_or_admin(token_payload: Dict[str, Any], required_scope: str) -> bool:
    """
    Check if token has required scope or admin privileges.
    
    Args:
        token_payload: JWT payload from verified token
        required_scope: Required scope
    
    Returns:
        True if scope or admin access is present
    """
    token_scopes = token_payload.get("scope", "").split()
    return (
        validate_scope_access(token_scopes, required_scope) or
        validate_scope_access(token_scopes, TokenScope.ADMIN_SYSTEM.value)
    )


# Scope validation decorator for functions
def validate_scopes(required_scopes: List[str]):
    """
    Decorator to validate scopes for any function.
    
    Args:
        required_scopes: List of required scopes
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract token payload from arguments
            token_payload = None
            for arg in args:
                if isinstance(arg, dict) and "scope" in arg:
                    token_payload = arg
                    break
            
            if not token_payload:
                for value in kwargs.values():
                    if isinstance(value, dict) and "scope" in value:
                        token_payload = value
                        break
            
            if not token_payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No valid token payload found"
                )
            
            token_scopes = token_payload.get("scope", "").split()
            if not has_any_scope(token_scopes, required_scopes):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required scopes: {required_scopes}"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator