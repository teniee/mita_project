#!/usr/bin/env python3
"""
Quick validation script to verify API configuration system is working correctly
"""

import sys
import os
from pathlib import Path

def main():
    print("🔍 MITA Finance API Configuration Validation")
    print("=" * 50)
    
    # Check if core files exist
    core_files = [
        "app/core/api_key_manager.py",
        "app/core/external_services.py",
        "app/api/health/external_services_routes.py",
        "scripts/configure_production_apis.py",
        "scripts/api_key_rotation.py",
        "docs/API_KEY_SETUP_GUIDE.md",
        ".env.production.final",
        "API_CONFIGURATION_SUMMARY.md"
    ]
    
    print("📁 Checking core files:")
    all_files_exist = True
    for file_path in core_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
            all_files_exist = False
    
    print()
    
    # Test imports
    print("📦 Testing module imports:")
    try:
        sys.path.insert(0, '.')
        from app.core.api_key_manager import api_key_manager, APIKeyStatus, ServiceType
        print("  ✅ API Key Manager")
        
        from app.core.external_services import external_services, ServiceHealth
        print("  ✅ External Services Manager")
        
        from app.api.health.external_services_routes import router
        print("  ✅ Health Monitoring Routes")
        
        print()
        print("🔧 System Components:")
        print(f"  📊 Configured services: {len(external_services.services)}")
        print(f"  🔑 Service types: {len(ServiceType)}")
        print(f"  📈 Health states: {len(ServiceHealth)}")
        print(f"  🎯 API key states: {len(APIKeyStatus)}")
        
    except Exception as e:
        print(f"  ❌ Import error: {str(e)}")
        all_files_exist = False
    
    print()
    
    # Check environment variables template
    print("🌍 Environment configuration:")
    env_file = Path(".env.production.final")
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
            critical_vars = [
                'OPENAI_API_KEY',
                'SENTRY_DSN', 
                'SENDGRID_API_KEY',
                'UPSTASH_REDIS_URL',
                'FIREBASE_JSON',
                'AWS_ACCESS_KEY_ID'
            ]
            
            for var in critical_vars:
                if var in content:
                    print(f"  ✅ {var} template configured")
                else:
                    print(f"  ❌ {var} missing from template")
    
    print()
    
    # Final status
    if all_files_exist:
        print("🎉 VALIDATION SUCCESSFUL")
        print("✅ All API configuration components are properly installed")
        print("✅ System is ready for production API key configuration")
        print()
        print("📋 Next steps:")
        print("1. Replace placeholder values in .env.production.final")
        print("2. Set environment variables in Render.com dashboard") 
        print("3. Run: python scripts/configure_production_apis.py")
        print("4. Deploy to production")
        return True
    else:
        print("❌ VALIDATION FAILED")
        print("Some components are missing or misconfigured")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)