#!/usr/bin/env python3
"""
Production Environment Validator
"""

import os
import sys
from typing import Dict, List, Tuple

def validate_production_environment() -> Tuple[bool, List[str], List[str]]:
    """Validate production environment variables"""
    
    critical_vars = {
        "DATABASE_URL": "Database connection string",
        "JWT_SECRET": "JWT signing secret (or SECRET_KEY)",
        "OPENAI_API_KEY": "OpenAI API key for AI features",
    }
    
    recommended_vars = {
        "SENTRY_DSN": "Error monitoring",
        "UPSTASH_REDIS_URL": "Redis for caching and sessions", 
        "SMTP_PASSWORD": "Email notifications",
    }
    
    missing_critical = []
    missing_recommended = []
    
    # Check critical variables
    for var, description in critical_vars.items():
        if var == "JWT_SECRET":
            # JWT_SECRET or SECRET_KEY is required
            if not os.getenv("JWT_SECRET") and not os.getenv("SECRET_KEY"):
                missing_critical.append(f"{var} (or SECRET_KEY): {description}")
        else:
            if not os.getenv(var):
                missing_critical.append(f"{var}: {description}")
    
    # Check recommended variables  
    for var, description in recommended_vars.items():
        if not os.getenv(var):
            missing_recommended.append(f"{var}: {description}")
    
    is_valid = len(missing_critical) == 0
    
    return is_valid, missing_critical, missing_recommended

def print_environment_status():
    """Print environment validation status"""
    is_valid, missing_critical, missing_recommended = validate_production_environment()
    
    print("=" * 70)
    print("🌍 PRODUCTION ENVIRONMENT VALIDATION")
    print("=" * 70)
    
    if is_valid:
        print("✅ All critical environment variables are set")
    else:
        print("❌ CRITICAL: Missing required environment variables:")
        for var in missing_critical:
            print(f"  • {var}")
    
    if missing_recommended:
        print("⚠️ Missing recommended environment variables:")
        for var in missing_recommended:
            print(f"  • {var}")
    
    print("=" * 70)
    
    # Print instructions
    if not is_valid or missing_recommended:
        print("📝 SETUP INSTRUCTIONS:")
        print("1. Set environment variables in your deployment platform:")
        print("   - Render: Dashboard > Environment Variables")  
        print("   - Heroku: heroku config:set VAR_NAME=value")
        print("   - Docker: Use .env file or -e flags")
        print("2. Use the values from .env.production.template")
        print("3. Restart your application after setting variables")
    
    return is_valid

if __name__ == "__main__":
    is_valid = print_environment_status()
    sys.exit(0 if is_valid else 1)
