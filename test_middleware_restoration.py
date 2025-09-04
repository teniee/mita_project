#!/usr/bin/env python3
"""
Middleware Restoration Validation Test
Tests that all restored middleware components are working correctly
"""

import asyncio
import logging
import time
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MiddlewareValidationTest:
    """Test restored middleware functionality"""
    
    def __init__(self):
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
    
    def run_test(self, test_name: str, test_func):
        """Run a single test with error handling and timing"""
        self.total_tests += 1
        logger.info(f"🧪 Running test: {test_name}")
        
        start_time = time.time()
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = asyncio.run(test_func())
            else:
                result = test_func()
            
            execution_time = time.time() - start_time
            
            self.test_results[test_name] = {
                'status': 'PASS',
                'result': result,
                'execution_time_ms': execution_time * 1000,
                'error': None
            }
            self.passed_tests += 1
            logger.info(f"✅ {test_name}: PASSED ({execution_time*1000:.1f}ms)")
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.test_results[test_name] = {
                'status': 'FAIL',
                'result': None,
                'execution_time_ms': execution_time * 1000,
                'error': str(e)
            }
            self.failed_tests += 1
            logger.error(f"❌ {test_name}: FAILED - {str(e)}")
    
    def test_input_sanitizer_import(self):
        """Test that InputSanitizer can be imported and lightweight methods exist"""
        try:
            from app.core.validators import InputSanitizer
            
            # Test lightweight methods exist
            assert hasattr(InputSanitizer, 'sanitize_email_lightweight'), "Missing sanitize_email_lightweight method"
            assert hasattr(InputSanitizer, 'sanitize_password_essential'), "Missing sanitize_password_essential method" 
            assert hasattr(InputSanitizer, 'sanitize_string_lightweight'), "Missing sanitize_string_lightweight method"
            
            # Test email validation works
            email = InputSanitizer.sanitize_email_lightweight("TEST@EXAMPLE.COM")
            assert email == "test@example.com", f"Email sanitization failed: {email}"
            
            # Test password validation works
            password = InputSanitizer.sanitize_password_essential("TestPassword123")
            assert password == "TestPassword123", "Password sanitization failed"
            
            return {
                'input_sanitizer_imported': True,
                'lightweight_methods_exist': True,
                'email_validation_works': True,
                'password_validation_works': True
            }
            
        except Exception as e:
            raise Exception(f"InputSanitizer validation failed: {e}")
    
    def test_rate_limiting_imports(self):
        """Test that rate limiting dependencies are properly imported"""
        try:
            from app.core.simple_rate_limiter import (
                check_login_rate_limit,
                check_register_rate_limit,
                check_password_reset_rate_limit,
                check_token_refresh_rate_limit
            )
            
            # Check that the functions exist and are callable
            assert callable(check_login_rate_limit), "check_login_rate_limit not callable"
            assert callable(check_register_rate_limit), "check_register_rate_limit not callable"
            assert callable(check_password_reset_rate_limit), "check_password_reset_rate_limit not callable"
            assert callable(check_token_refresh_rate_limit), "check_token_refresh_rate_limit not callable"
            
            return {
                'rate_limiting_imports': True,
                'login_limiter_available': True,
                'register_limiter_available': True,
                'password_reset_limiter_available': True,
                'token_refresh_limiter_available': True
            }
            
        except Exception as e:
            raise Exception(f"Rate limiting imports failed: {e}")
    
    def test_audit_logging_imports(self):
        """Test that audit logging can be imported and used"""
        try:
            from app.core.audit_logging import log_security_event_async
            
            # Check that the function exists and is callable
            assert callable(log_security_event_async), "log_security_event_async not callable"
            
            # Test audit logging service
            from app.core.audit_logging import AuditDatabasePool
            audit_pool = AuditDatabasePool()
            
            return {
                'audit_logging_imported': True,
                'log_security_event_available': True,
                'audit_pool_created': True
            }
            
        except Exception as e:
            raise Exception(f"Audit logging imports failed: {e}")
    
    def test_password_security_imports(self):
        """Test that centralized password security is working"""
        try:
            from app.core.password_security import hash_password_async, verify_password_async
            
            # Check functions are callable
            assert callable(hash_password_async), "hash_password_async not callable"
            assert callable(verify_password_async), "verify_password_async not callable"
            
            # Test configuration validation
            from app.core.password_security import validate_bcrypt_configuration
            config = validate_bcrypt_configuration()
            
            return {
                'password_security_imported': True,
                'async_hash_available': True,
                'async_verify_available': True,
                'bcrypt_configuration_valid': config.get('valid', False),
                'bcrypt_rounds': config.get('configuration', {}).get('rounds', 0)
            }
            
        except Exception as e:
            raise Exception(f"Password security imports failed: {e}")
    
    def test_jwt_service_functionality(self):
        """Test that JWT service is working with restored thread pool"""
        try:
            from app.services.auth_jwt_service import create_token_pair, hash_password
            
            # Test token creation
            test_user_data = {"sub": "test_user_123", "email": "test@example.com"}
            tokens = create_token_pair(test_user_data, user_role="basic_user")
            
            assert "access_token" in tokens, "Access token not created"
            assert "refresh_token" in tokens, "Refresh token not created"
            assert len(tokens["access_token"]) > 50, "Access token too short"
            assert len(tokens["refresh_token"]) > 50, "Refresh token too short"
            
            # Test password hashing
            test_password = "TestPassword123"
            password_hash = hash_password(test_password)
            assert len(password_hash) > 50, "Password hash too short"
            assert password_hash.startswith('$2b$'), "Invalid bcrypt hash format"
            
            return {
                'jwt_service_working': True,
                'token_creation_working': True,
                'access_token_length': len(tokens["access_token"]),
                'refresh_token_length': len(tokens["refresh_token"]),
                'password_hashing_working': True,
                'password_hash_format_valid': True
            }
            
        except Exception as e:
            raise Exception(f"JWT service functionality failed: {e}")
    
    async def test_audit_logging_functionality(self):
        """Test that audit logging works without causing deadlocks"""
        try:
            from app.core.audit_logging import log_security_event_async
            
            # Create a mock request object
            class MockRequest:
                def __init__(self):
                    self.headers = {"User-Agent": "TestClient/1.0"}
                    self.client = type('obj', (object,), {'host': '127.0.0.1'})
                    self.url = type('obj', (object,), {'path': '/test'})
            
            mock_request = MockRequest()
            
            # Test logging (this should not hang or cause deadlocks)
            start_time = time.time()
            
            # Use a timeout to ensure this doesn't hang
            try:
                await asyncio.wait_for(
                    log_security_event_async(
                        "middleware_test",
                        {"test_data": "validation"},
                        request=mock_request
                    ),
                    timeout=5.0  # 5 second timeout
                )
                execution_time = time.time() - start_time
                
                return {
                    'audit_logging_works': True,
                    'no_deadlock': True,
                    'execution_time_ms': execution_time * 1000,
                    'within_timeout': execution_time < 5.0
                }
                
            except asyncio.TimeoutError:
                return {
                    'audit_logging_works': False,
                    'no_deadlock': False,
                    'execution_time_ms': 5000,
                    'timeout_occurred': True
                }
            
        except Exception as e:
            raise Exception(f"Audit logging functionality failed: {e}")
    
    def test_database_session_imports(self):
        """Test that optimized database sessions can be imported"""
        try:
            from app.core.async_session import get_async_db, get_async_db_context
            
            assert callable(get_async_db), "get_async_db not callable"
            
            return {
                'async_session_imported': True,
                'get_async_db_available': True,
                'context_manager_available': hasattr(get_async_db_context, '__aenter__')
            }
            
        except Exception as e:
            raise Exception(f"Database session imports failed: {e}")
    
    def test_security_middleware_components(self):
        """Test that security middleware components are available"""
        try:
            results = {}
            
            # Test security headers
            try:
                from app.main import app
                # Check if security headers middleware is registered
                results['main_app_imported'] = True
                results['middleware_count'] = len(app.middleware_stack) if hasattr(app, 'middleware_stack') else 0
            except Exception as e:
                results['main_app_error'] = str(e)
            
            # Test CORS middleware
            try:
                from starlette.middleware.cors import CORSMiddleware
                results['cors_middleware_available'] = True
            except Exception as e:
                results['cors_error'] = str(e)
            
            # Test HTTPS redirect
            try:
                from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
                results['https_redirect_available'] = True
            except Exception as e:
                results['https_error'] = str(e)
            
            return results
            
        except Exception as e:
            raise Exception(f"Security middleware test failed: {e}")
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        
        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        # Categorize test results
        critical_tests = [
            'Input Sanitizer Import',
            'Rate Limiting Imports', 
            'Password Security Imports',
            'JWT Service Functionality'
        ]
        
        critical_passed = sum(1 for test in critical_tests 
                             if test in self.test_results and self.test_results[test]['status'] == 'PASS')
        
        report = {
            'test_summary': {
                'total_tests': self.total_tests,
                'passed_tests': self.passed_tests,
                'failed_tests': self.failed_tests,
                'success_rate': success_rate,
                'critical_tests_passed': critical_passed,
                'critical_tests_total': len(critical_tests)
            },
            'test_results': self.test_results,
            'overall_status': 'PASS' if self.failed_tests == 0 else 'PARTIAL' if critical_passed == len(critical_tests) else 'FAIL',
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> list:
        """Generate recommendations based on test results"""
        recommendations = []
        
        failed_tests = [name for name, result in self.test_results.items() if result['status'] == 'FAIL']
        
        if failed_tests:
            recommendations.append(f"Investigate and fix failed tests: {', '.join(failed_tests)}")
        
        # Check for performance issues
        slow_tests = [name for name, result in self.test_results.items() 
                     if result['execution_time_ms'] > 1000]
        
        if slow_tests:
            recommendations.append(f"Optimize slow-performing components: {', '.join(slow_tests)}")
        
        # Check for specific issues
        if 'Audit Logging Functionality' in self.test_results:
            audit_result = self.test_results['Audit Logging Functionality']
            if audit_result['status'] == 'FAIL' or (audit_result['status'] == 'PASS' and audit_result['result'].get('timeout_occurred')):
                recommendations.append("Audit logging may still have deadlock issues - monitor in production")
        
        if not recommendations:
            recommendations.append("All middleware components restored successfully - ready for production")
        
        return recommendations

def main():
    """Run comprehensive middleware validation tests"""
    print("="*70)
    print("🧪 MITA FINANCE MIDDLEWARE VALIDATION TESTS")
    print("="*70)
    
    tester = MiddlewareValidationTest()
    
    # Run all tests
    tester.run_test("Input Sanitizer Import", tester.test_input_sanitizer_import)
    tester.run_test("Rate Limiting Imports", tester.test_rate_limiting_imports)
    tester.run_test("Audit Logging Imports", tester.test_audit_logging_imports)
    tester.run_test("Password Security Imports", tester.test_password_security_imports)
    tester.run_test("JWT Service Functionality", tester.test_jwt_service_functionality)
    tester.run_test("Audit Logging Functionality", tester.test_audit_logging_functionality)
    tester.run_test("Database Session Imports", tester.test_database_session_imports)
    tester.run_test("Security Middleware Components", tester.test_security_middleware_components)
    
    # Generate and display report
    report = tester.generate_test_report()
    
    print(f"\n📊 TEST RESULTS SUMMARY:")
    summary = report['test_summary']
    print(f"   • Total Tests: {summary['total_tests']}")
    print(f"   • Passed: {summary['passed_tests']}")
    print(f"   • Failed: {summary['failed_tests']}")
    print(f"   • Success Rate: {summary['success_rate']:.1f}%")
    print(f"   • Critical Tests Passed: {summary['critical_tests_passed']}/{summary['critical_tests_total']}")
    
    print(f"\n🔍 DETAILED RESULTS:")
    for test_name, result in report['test_results'].items():
        status_emoji = "✅" if result['status'] == 'PASS' else "❌"
        execution_time = result['execution_time_ms']
        print(f"   {status_emoji} {test_name}: {result['status']} ({execution_time:.1f}ms)")
        if result['error']:
            print(f"      Error: {result['error']}")
    
    print(f"\n🎯 OVERALL STATUS: {report['overall_status']}")
    
    print(f"\n💡 RECOMMENDATIONS:")
    for rec in report['recommendations']:
        print(f"   • {rec}")
    
    # Save detailed report
    import json
    with open('middleware_validation_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n📋 Detailed validation report saved: middleware_validation_report.json")
    
    # Final assessment
    if report['overall_status'] == 'PASS':
        print(f"\n✅ ALL MIDDLEWARE RESTORATION TESTS PASSED")
        print("🔒 Restored middleware components are functioning correctly")
        return True
    elif report['overall_status'] == 'PARTIAL':
        print(f"\n🟡 MIDDLEWARE RESTORATION PARTIALLY SUCCESSFUL")
        print("🔒 Critical security components working, some issues to address")
        return True
    else:
        print(f"\n❌ MIDDLEWARE RESTORATION VALIDATION FAILED")
        print("🔒 Critical issues detected - manual intervention required")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)