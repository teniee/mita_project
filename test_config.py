#!/usr/bin/env python3
"""Simple configuration test"""
import os
import sys
from pathlib import Path

# Set environment for testing
os.environ['ENVIRONMENT'] = 'development'

try:
    # Test original config
    print("Testing original configuration...")
    from app.core.config import get_settings as get_original_settings
    original_settings = get_original_settings()
    print(f"✅ Original config loaded: {original_settings.ENVIRONMENT}")
    print(f"   ALLOWED_ORIGINS: {original_settings.ALLOWED_ORIGINS}")
except Exception as e:
    print(f"❌ Original config failed: {e}")

try:
    # Test clean config
    print("\nTesting clean configuration...")
    
    # Simple version without complex validation
    import os
    from functools import lru_cache
    
    try:
        from pydantic_settings import BaseSettings
    except ModuleNotFoundError:
        from pydantic import BaseSettings
    
    class SimpleSettings(BaseSettings):
        ENVIRONMENT: str = "development"
        DEBUG: bool = False
        LOG_LEVEL: str = "INFO"
        DATABASE_URL: str = ""
        JWT_SECRET: str = ""
        SECRET_KEY: str = ""
        ALLOWED_ORIGINS: str = ""  # Keep as string for now
        
        class Config:
            env_file = ".env.development"
            validate_assignment = False
            extra = "ignore"
    
    @lru_cache
    def get_simple_settings():
        return SimpleSettings()
    
    simple_settings = get_simple_settings()
    print(f"✅ Simple config loaded: {simple_settings.ENVIRONMENT}")
    print(f"   ALLOWED_ORIGINS: {simple_settings.ALLOWED_ORIGINS}")
    
    # Convert ALLOWED_ORIGINS to list
    if simple_settings.ALLOWED_ORIGINS:
        origins_list = [o.strip() for o in simple_settings.ALLOWED_ORIGINS.split(",") if o.strip()]
        print(f"   ALLOWED_ORIGINS as list: {origins_list}")
    
except Exception as e:
    print(f"❌ Simple config failed: {e}")
    import traceback
    traceback.print_exc()

print("\nConfiguration test complete.")