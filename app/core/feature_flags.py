"""
Centralized Feature Flag System for MITA Financial Platform.

This module provides a production-ready feature flag system that replaces
temporary disabled code paths and provides runtime configuration of features.
"""

import os
import json
import redis
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from functools import lru_cache

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class FeatureFlagType(str, Enum):
    """Feature flag types."""
    BOOLEAN = "boolean"
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    JSON = "json"
    PERCENTAGE = "percentage"


class FeatureFlagEnvironment(str, Enum):
    """Environment types for feature flags."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    ALL = "all"


@dataclass
class FeatureFlag:
    """Feature flag configuration."""
    key: str
    name: str
    description: str
    flag_type: FeatureFlagType
    default_value: Any
    environments: List[FeatureFlagEnvironment]
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


class FeatureFlagManager:
    """Centralized feature flag management system."""
    
    def __init__(self, redis_conn: Optional[redis.Redis] = None):
        """Initialize the feature flag manager."""
        self.redis_conn = redis_conn
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_update = {}
        
        # Initialize with default flags
        self._initialize_default_flags()
        
        logger.info("Feature flag manager initialized")

    def _initialize_default_flags(self):
        """Initialize default feature flags for MITA."""
        default_flags = {
            # Admin features
            "admin_endpoints_enabled": FeatureFlag(
                key="admin_endpoints_enabled",
                name="Admin Endpoints",
                description="Enable admin-only endpoints with proper role validation",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                environments=[FeatureFlagEnvironment.PRODUCTION, FeatureFlagEnvironment.STAGING],
                metadata={"category": "security", "priority": "high"}
            ),
            
            # OCR features
            "advanced_ocr_enabled": FeatureFlag(
                key="advanced_ocr_enabled",
                name="Advanced OCR Processing",
                description="Enable advanced OCR processing with machine learning enhancement",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                environments=[FeatureFlagEnvironment.ALL],
                metadata={"category": "processing", "priority": "medium"}
            ),
            
            # AI features
            "ai_budget_analysis_enabled": FeatureFlag(
                key="ai_budget_analysis_enabled",
                name="AI Budget Analysis",
                description="Enable AI-powered budget analysis and recommendations",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                environments=[FeatureFlagEnvironment.ALL],
                metadata={"category": "ai", "priority": "high"}
            ),
            
            # Performance features
            "circuit_breaker_enabled": FeatureFlag(
                key="circuit_breaker_enabled",
                name="Circuit Breaker Pattern",
                description="Enable circuit breaker for external service calls",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                environments=[FeatureFlagEnvironment.PRODUCTION, FeatureFlagEnvironment.STAGING],
                metadata={"category": "reliability", "priority": "high"}
            ),
            
            # Security features
            "enhanced_rate_limiting": FeatureFlag(
                key="enhanced_rate_limiting",
                name="Enhanced Rate Limiting",
                description="Enable enhanced rate limiting with user tiers",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                environments=[FeatureFlagEnvironment.PRODUCTION, FeatureFlagEnvironment.STAGING],
                metadata={"category": "security", "priority": "critical"}
            ),
            
            "jwt_rotation_enabled": FeatureFlag(
                key="jwt_rotation_enabled",
                name="JWT Token Rotation",
                description="Enable automatic JWT token rotation",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                environments=[FeatureFlagEnvironment.PRODUCTION],
                metadata={"category": "security", "priority": "high"}
            ),
            
            # Notification features
            "push_notifications_enabled": FeatureFlag(
                key="push_notifications_enabled",
                name="Push Notifications",
                description="Enable push notification delivery",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                environments=[FeatureFlagEnvironment.ALL],
                metadata={"category": "notifications", "priority": "medium"}
            ),
            
            # Analytics features
            "detailed_analytics_enabled": FeatureFlag(
                key="detailed_analytics_enabled",
                name="Detailed Analytics",
                description="Enable detailed user behavior analytics",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                environments=[FeatureFlagEnvironment.PRODUCTION, FeatureFlagEnvironment.STAGING],
                metadata={"category": "analytics", "priority": "medium"}
            ),
            
            # Debug features (should be disabled in production)
            "debug_logging_enabled": FeatureFlag(
                key="debug_logging_enabled",
                name="Debug Logging",
                description="Enable verbose debug logging",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=False,
                environments=[FeatureFlagEnvironment.DEVELOPMENT],
                metadata={"category": "debugging", "priority": "low"}
            ),
            
            # Feature rollout percentages
            "new_budget_engine_rollout": FeatureFlag(
                key="new_budget_engine_rollout",
                name="New Budget Engine Rollout",
                description="Percentage of users to receive new budget engine features",
                flag_type=FeatureFlagType.PERCENTAGE,
                default_value=100,
                environments=[FeatureFlagEnvironment.PRODUCTION],
                metadata={"category": "rollout", "priority": "high"}
            ),
        }
        
        # Store default flags
        for flag_key, flag in default_flags.items():
            self._store_flag_definition(flag)

    def is_enabled(self, flag_key: str, user_id: Optional[int] = None, default: bool = False) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag_key: The feature flag key
            user_id: Optional user ID for user-specific flags
            default: Default value if flag is not found
        
        Returns:
            True if the flag is enabled, False otherwise
        """
        try:
            flag = self._get_flag(flag_key)
            if not flag:
                logger.warning(f"Feature flag '{flag_key}' not found, using default: {default}")
                return default
            
            # Check if flag is enabled for current environment
            current_env = self._get_current_environment()
            if not self._is_flag_enabled_for_environment(flag, current_env):
                return False
            
            # Get flag value
            value = self._get_flag_value(flag, user_id)
            
            # Handle different flag types
            if flag.flag_type == FeatureFlagType.BOOLEAN:
                return bool(value)
            elif flag.flag_type == FeatureFlagType.PERCENTAGE:
                return self._evaluate_percentage_flag(value, user_id or 0)
            else:
                # For non-boolean flags, consider them enabled if they have a value
                return value is not None
        
        except Exception as e:
            logger.error(f"Error checking feature flag '{flag_key}': {str(e)}")
            return default

    def get_value(self, flag_key: str, user_id: Optional[int] = None, default: Any = None) -> Any:
        """
        Get the value of a feature flag.
        
        Args:
            flag_key: The feature flag key
            user_id: Optional user ID for user-specific flags
            default: Default value if flag is not found
        
        Returns:
            The flag value or default
        """
        try:
            flag = self._get_flag(flag_key)
            if not flag:
                logger.warning(f"Feature flag '{flag_key}' not found, using default: {default}")
                return default
            
            # Check if flag is enabled for current environment
            current_env = self._get_current_environment()
            if not self._is_flag_enabled_for_environment(flag, current_env):
                return default
            
            return self._get_flag_value(flag, user_id)
        
        except Exception as e:
            logger.error(f"Error getting feature flag value '{flag_key}': {str(e)}")
            return default

    def set_flag_value(self, flag_key: str, value: Any, user_id: Optional[int] = None) -> bool:
        """
        Set the value of a feature flag.
        
        Args:
            flag_key: The feature flag key
            value: The new value
            user_id: Optional user ID for user-specific overrides
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.redis_conn:
                redis_key = f"feature_flag_value:{flag_key}"
                if user_id:
                    redis_key += f":user:{user_id}"
                
                self.redis_conn.setex(
                    redis_key,
                    self.cache_ttl,
                    json.dumps(value)
                )
                
                # Clear cache
                self._clear_cache(flag_key)
                
                logger.info(f"Feature flag '{flag_key}' value updated: {value}")
                return True
            else:
                # Store in memory cache if no Redis
                cache_key = f"{flag_key}:{user_id}" if user_id else flag_key
                self.cache[cache_key] = {
                    'value': value,
                    'expires_at': datetime.utcnow() + timedelta(seconds=self.cache_ttl)
                }
                return True
        
        except Exception as e:
            logger.error(f"Error setting feature flag value '{flag_key}': {str(e)}")
            return False

    def get_all_flags(self, environment: Optional[FeatureFlagEnvironment] = None) -> Dict[str, Dict[str, Any]]:
        """
        Get all feature flags for the current or specified environment.
        
        Args:
            environment: Optional specific environment filter
        
        Returns:
            Dictionary of all flags with their current values
        """
        try:
            flags = {}
            current_env = environment or self._get_current_environment()
            
            # Get all flag definitions
            all_flags = self._get_all_flag_definitions()
            
            for flag_key, flag in all_flags.items():
                if self._is_flag_enabled_for_environment(flag, current_env):
                    flags[flag_key] = {
                        'name': flag.name,
                        'description': flag.description,
                        'type': flag.flag_type.value,
                        'enabled': flag.enabled,
                        'value': self._get_flag_value(flag),
                        'environments': [env.value for env in flag.environments],
                        'metadata': flag.metadata
                    }
            
            return flags
        
        except Exception as e:
            logger.error(f"Error getting all feature flags: {str(e)}")
            return {}

    def _get_flag(self, flag_key: str) -> Optional[FeatureFlag]:
        """Get a feature flag definition."""
        try:
            if self.redis_conn:
                redis_key = f"feature_flag_def:{flag_key}"
                data = self.redis_conn.get(redis_key)
                if data:
                    flag_dict = json.loads(data)
                    # Convert datetime strings back to datetime objects
                    if flag_dict.get('created_at'):
                        flag_dict['created_at'] = datetime.fromisoformat(flag_dict['created_at'])
                    if flag_dict.get('updated_at'):
                        flag_dict['updated_at'] = datetime.fromisoformat(flag_dict['updated_at'])
                    # Convert enums
                    flag_dict['flag_type'] = FeatureFlagType(flag_dict['flag_type'])
                    flag_dict['environments'] = [FeatureFlagEnvironment(env) for env in flag_dict['environments']]
                    return FeatureFlag(**flag_dict)
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting feature flag definition '{flag_key}': {str(e)}")
            return None

    def _get_flag_value(self, flag: FeatureFlag, user_id: Optional[int] = None) -> Any:
        """Get the current value of a feature flag."""
        try:
            # Check for user-specific override first
            if user_id and self.redis_conn:
                user_redis_key = f"feature_flag_value:{flag.key}:user:{user_id}"
                user_value = self.redis_conn.get(user_redis_key)
                if user_value:
                    return json.loads(user_value)
            
            # Check for global override
            if self.redis_conn:
                redis_key = f"feature_flag_value:{flag.key}"
                value = self.redis_conn.get(redis_key)
                if value:
                    return json.loads(value)
            
            # Check memory cache
            cache_key = f"{flag.key}:{user_id}" if user_id else flag.key
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if cached['expires_at'] > datetime.utcnow():
                    return cached['value']
                else:
                    del self.cache[cache_key]
            
            # Return default value
            return flag.default_value
        
        except Exception as e:
            logger.error(f"Error getting flag value for '{flag.key}': {str(e)}")
            return flag.default_value

    def _store_flag_definition(self, flag: FeatureFlag):
        """Store a feature flag definition."""
        try:
            if self.redis_conn:
                redis_key = f"feature_flag_def:{flag.key}"
                flag_dict = asdict(flag)
                # Convert datetime objects to strings for JSON serialization
                if flag_dict.get('created_at'):
                    flag_dict['created_at'] = flag_dict['created_at'].isoformat()
                if flag_dict.get('updated_at'):
                    flag_dict['updated_at'] = flag_dict['updated_at'].isoformat()
                # Convert enums to strings
                flag_dict['flag_type'] = flag.flag_type.value
                flag_dict['environments'] = [env.value for env in flag.environments]
                
                self.redis_conn.setex(
                    redis_key,
                    7 * 24 * 3600,  # 7 days TTL
                    json.dumps(flag_dict)
                )
        
        except Exception as e:
            logger.error(f"Error storing feature flag definition '{flag.key}': {str(e)}")

    def _get_all_flag_definitions(self) -> Dict[str, FeatureFlag]:
        """Get all feature flag definitions."""
        flags = {}
        
        try:
            if self.redis_conn:
                cursor = 0
                while True:
                    cursor, keys = self.redis_conn.scan(
                        cursor=cursor,
                        match="feature_flag_def:*",
                        count=100
                    )
                    
                    for key in keys:
                        flag_key = key.decode().replace('feature_flag_def:', '')
                        flag = self._get_flag(flag_key)
                        if flag:
                            flags[flag_key] = flag
                    
                    if cursor == 0:
                        break
        
        except Exception as e:
            logger.error(f"Error getting all feature flag definitions: {str(e)}")
        
        return flags

    def _get_current_environment(self) -> FeatureFlagEnvironment:
        """Get the current environment."""
        env = os.getenv('ENVIRONMENT', 'development').lower()
        try:
            return FeatureFlagEnvironment(env)
        except ValueError:
            return FeatureFlagEnvironment.DEVELOPMENT

    def _is_flag_enabled_for_environment(self, flag: FeatureFlag, environment: FeatureFlagEnvironment) -> bool:
        """Check if a flag is enabled for the specified environment."""
        return (
            flag.enabled and (
                FeatureFlagEnvironment.ALL in flag.environments or
                environment in flag.environments
            )
        )

    def _evaluate_percentage_flag(self, percentage: Union[int, float], user_id: int) -> bool:
        """Evaluate a percentage-based feature flag."""
        if percentage >= 100:
            return True
        if percentage <= 0:
            return False
        
        # Use user ID to deterministically decide if they're in the percentage
        # This ensures consistent experience for the same user
        user_hash = hash(str(user_id)) % 100
        return user_hash < percentage

    def _clear_cache(self, flag_key: str):
        """Clear cache for a specific flag."""
        keys_to_remove = [key for key in self.cache.keys() if key.startswith(flag_key)]
        for key in keys_to_remove:
            del self.cache[key]


# Global feature flag manager instance
feature_flag_manager: Optional[FeatureFlagManager] = None


@lru_cache(maxsize=1)
def get_feature_flag_manager() -> FeatureFlagManager:
    """Get or create the global feature flag manager."""
    global feature_flag_manager
    
    if feature_flag_manager is None:
        try:
            # Try to create Redis connection
            redis_conn = None
            if settings.REDIS_URL:
                import redis
                redis_conn = redis.from_url(settings.REDIS_URL)
        except Exception as e:
            logger.warning(f"Could not connect to Redis for feature flags: {e}")
            redis_conn = None
        
        feature_flag_manager = FeatureFlagManager(redis_conn)
    
    return feature_flag_manager


def is_feature_enabled(flag_key: str, user_id: Optional[int] = None, default: bool = False) -> bool:
    """
    Convenience function to check if a feature flag is enabled.
    
    Args:
        flag_key: The feature flag key
        user_id: Optional user ID for user-specific flags
        default: Default value if flag is not found
    
    Returns:
        True if the flag is enabled, False otherwise
    """
    return get_feature_flag_manager().is_enabled(flag_key, user_id, default)


def get_feature_value(flag_key: str, user_id: Optional[int] = None, default: Any = None) -> Any:
    """
    Convenience function to get the value of a feature flag.
    
    Args:
        flag_key: The feature flag key
        user_id: Optional user ID for user-specific flags
        default: Default value if flag is not found
    
    Returns:
        The flag value or default
    """
    return get_feature_flag_manager().get_value(flag_key, user_id, default)