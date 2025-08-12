"""
Feature Flag Management API endpoints.
Provides endpoints to manage and monitor feature flags in the MITA platform.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.core.feature_flags import get_feature_flag_manager, FeatureFlagEnvironment
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


class FeatureFlagValueRequest(BaseModel):
    """Request model for updating feature flag values."""
    value: Any
    user_id: Optional[int] = None


@router.get("", response_model=Dict[str, Any])
async def get_all_feature_flags(
    environment: Optional[str] = None,
    user=Depends(get_current_user)
):
    """
    Get all feature flags for the current environment.
    
    Args:
        environment: Optional specific environment filter
        user: Current authenticated user
    
    Returns:
        Dictionary of all feature flags with their current values
    """
    try:
        # Admin access required for this endpoint
        if not hasattr(user, 'is_admin') or not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        feature_manager = get_feature_flag_manager()
        
        env_filter = None
        if environment:
            try:
                env_filter = FeatureFlagEnvironment(environment.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid environment: {environment}"
                )
        
        flags = feature_manager.get_all_flags(env_filter)
        
        return success_response({
            "feature_flags": flags,
            "environment": environment or "current",
            "total_flags": len(flags)
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving feature flags: {str(e)}"
        )


@router.get("/{flag_key}", response_model=Dict[str, Any])
async def get_feature_flag(
    flag_key: str,
    user=Depends(get_current_user)
):
    """
    Get details for a specific feature flag.
    
    Args:
        flag_key: The feature flag key
        user: Current authenticated user
    
    Returns:
        Feature flag details including current value
    """
    try:
        # Admin access required for this endpoint
        if not hasattr(user, 'is_admin') or not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        feature_manager = get_feature_flag_manager()
        
        # Check if flag is enabled
        is_enabled = feature_manager.is_enabled(flag_key, getattr(user, 'id', None))
        
        # Get flag value
        value = feature_manager.get_value(flag_key, getattr(user, 'id', None))
        
        return success_response({
            "flag_key": flag_key,
            "enabled": is_enabled,
            "value": value,
            "user_id": getattr(user, 'id', None)
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving feature flag '{flag_key}': {str(e)}"
        )


@router.post("/{flag_key}/set", response_model=Dict[str, Any])
async def set_feature_flag_value(
    flag_key: str,
    request: FeatureFlagValueRequest,
    user=Depends(get_current_user)
):
    """
    Set the value of a feature flag.
    
    Args:
        flag_key: The feature flag key
        request: The new value and optional user ID
        user: Current authenticated user
    
    Returns:
        Success response with updated flag details
    """
    try:
        # Admin access required for this endpoint
        if not hasattr(user, 'is_admin') or not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        feature_manager = get_feature_flag_manager()
        
        # Set the flag value
        success = feature_manager.set_flag_value(
            flag_key, 
            request.value, 
            request.user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update feature flag '{flag_key}'"
            )
        
        return success_response({
            "flag_key": flag_key,
            "value": request.value,
            "user_id": request.user_id,
            "updated_by": getattr(user, 'id', None),
            "message": "Feature flag value updated successfully"
        })
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating feature flag '{flag_key}': {str(e)}"
        )


@router.get("/{flag_key}/check", response_model=Dict[str, Any])
async def check_feature_flag(
    flag_key: str,
    user_id: Optional[int] = None,
    user=Depends(get_current_user)
):
    """
    Check if a feature flag is enabled for a specific user.
    
    Args:
        flag_key: The feature flag key
        user_id: Optional user ID to check (defaults to current user)
        user: Current authenticated user
    
    Returns:
        Flag status and value for the specified user
    """
    try:
        feature_manager = get_feature_flag_manager()
        
        # Use provided user_id or fall back to current user
        check_user_id = user_id or getattr(user, 'id', None)
        
        # Check if flag is enabled
        is_enabled = feature_manager.is_enabled(flag_key, check_user_id)
        
        # Get flag value
        value = feature_manager.get_value(flag_key, check_user_id)
        
        return success_response({
            "flag_key": flag_key,
            "enabled": is_enabled,
            "value": value,
            "user_id": check_user_id,
            "checked_by": getattr(user, 'id', None)
        })
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking feature flag '{flag_key}': {str(e)}"
        )