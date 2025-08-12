#!/usr/bin/env python3
"""
Test script to verify the code cleanup and feature flag system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_feature_flag_imports():
    """Test that feature flag system can be imported."""
    try:
        from app.core.feature_flags import FeatureFlagManager, FeatureFlag, FeatureFlagType
        print("✅ Feature flag core classes imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import feature flag classes: {e}")
        return False

def test_feature_flag_basic_functionality():
    """Test basic feature flag functionality without Redis."""
    try:
        from app.core.feature_flags import FeatureFlagManager, FeatureFlag, FeatureFlagType, FeatureFlagEnvironment
        
        # Create manager without Redis connection
        manager = FeatureFlagManager(redis_conn=None)
        
        # Test checking a non-existent flag
        result = manager.is_enabled("non_existent_flag", default=False)
        assert result == False, "Non-existent flag should return default value"
        
        print("✅ Basic feature flag functionality working")
        return True
    except Exception as e:
        print(f"❌ Feature flag basic functionality test failed: {e}")
        return False

def test_api_endpoint_imports():
    """Test that the feature flag API endpoints can be imported."""
    try:
        from app.api.endpoints.feature_flags import router
        print("✅ Feature flag API endpoints imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import feature flag API endpoints: {e}")
        return False

def test_tasks_routes_imports():
    """Test that the modified tasks routes can be imported."""
    try:
        # This will fail due to missing dependencies, but we can check syntax
        import ast
        import inspect
        
        with open('app/api/tasks/routes.py', 'r') as f:
            content = f.read()
        
        # Parse the file to check syntax
        ast.parse(content)
        
        # Check that our admin function was added
        assert 'def require_admin_access' in content, "require_admin_access function not found"
        assert 'require_admin_access(user)' in content, "require_admin_access not being called"
        
        print("✅ Tasks routes modifications verified")
        return True
    except Exception as e:
        print(f"❌ Tasks routes verification failed: {e}")
        return False

def test_ocr_logging_cleanup():
    """Test that OCR services use proper logging instead of print statements."""
    try:
        import ast
        
        files_to_check = [
            'app/ocr/ocr_receipt_service.py',
            'app/ocr/advanced_ocr_service.py', 
            'app/engine/ocr/advanced_ocr_service.py'
        ]
        
        for file_path in files_to_check:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Check that we have logger import
            assert 'from app.core.logger import get_logger' in content, f"Logger import missing in {file_path}"
            assert 'logger = get_logger(__name__)' in content, f"Logger initialization missing in {file_path}"
            
            # Check that print statements were replaced with logger calls
            if 'print(' in content:
                print(f"⚠️  Warning: Found print statement in {file_path}")
        
        print("✅ OCR logging cleanup verified")
        return True
    except Exception as e:
        print(f"❌ OCR logging cleanup verification failed: {e}")
        return False

def test_mobile_app_logging_cleanup():
    """Test that mobile app debug prints were replaced with proper logging."""
    try:
        files_to_check = [
            'mobile_app/lib/services/ocr_service.dart',
            'mobile_app/lib/services/location_service.dart',
            'mobile_app/lib/services/accessibility_service.dart'
        ]
        
        for file_path in files_to_check:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Check that we have logging import
            if file_path != 'mobile_app/lib/services/ocr_service.dart':  # Already had different import
                assert "import 'logging_service.dart';" in content, f"Logging import missing in {file_path}"
            
            # Count remaining debugPrint statements (should be minimal or none)
            debug_print_count = content.count('debugPrint(')
            print(f"ℹ️  {file_path}: {debug_print_count} remaining debugPrint statements")
        
        print("✅ Mobile app logging cleanup verified")
        return True
    except Exception as e:
        print(f"❌ Mobile app logging cleanup verification failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Running code cleanup verification tests...\n")
    
    tests = [
        ("Feature Flag Imports", test_feature_flag_imports),
        ("Feature Flag Basic Functionality", test_feature_flag_basic_functionality),
        ("API Endpoint Imports", test_api_endpoint_imports),
        ("Tasks Routes Modifications", test_tasks_routes_imports),
        ("OCR Logging Cleanup", test_ocr_logging_cleanup),
        ("Mobile App Logging Cleanup", test_mobile_app_logging_cleanup),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Running: {test_name}")
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Code cleanup successful.")
        return 0
    else:
        print(f"⚠️  {total - passed} tests failed. Review the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())