#!/usr/bin/env python3
"""
MITA Finance Authentication Production Diagnostic Script

This script diagnoses the exact cause of production authentication failures:
- SYSTEM_8001 errors during registration
- AUTH_1001 errors during login

Run this script to identify and fix authentication issues in production.
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, '/Users/mikhail/StudioProjects/mita_project')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class AuthDiagnostic:
    """Comprehensive authentication system diagnostic"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "status": "running",
            "issues_found": [],
            "critical_issues": [],
            "warnings": [],
            "components_tested": [],
            "recommendations": []
        }
    
    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run comprehensive authentication diagnostic"""
        logger.info("🚀 Starting MITA Finance Authentication Diagnostic")
        
        try:
            # Test 1: Environment and Configuration
            await self.test_environment_config()
            
            # Test 2: Database Connection and Schema
            await self.test_database_connection()
            
            # Test 3: Password Security Configuration
            await self.test_password_security()
            
            # Test 4: Authentication Components
            await self.test_auth_components()
            
            # Test 5: Error Handling System
            await self.test_error_handling()
            
            # Test 6: Production Database Schema
            await self.test_production_schema()
            
            # Test 7: Rate Limiting System
            await self.test_rate_limiting()
            
            # Test 8: End-to-End Registration Flow
            await self.test_registration_flow()
            
            # Test 9: End-to-End Login Flow  
            await self.test_login_flow()
            
            self.results["status"] = "completed"
            
        except Exception as e:
            self.results["status"] = "failed"
            self.results["critical_issues"].append(f"Diagnostic failed: {str(e)}")
            logger.error(f"Diagnostic failed: {e}", exc_info=True)
        
        # Generate report
        await self.generate_diagnostic_report()
        
        return self.results
    
    async def test_environment_config(self):
        """Test environment configuration"""
        logger.info("🔧 Testing environment configuration...")
        self.results["components_tested"].append("environment_config")
        
        try:
            from app.core.config import settings
            
            # Check critical environment variables
            critical_vars = {
                "DATABASE_URL": settings.DATABASE_URL,
                "JWT_SECRET": settings.JWT_SECRET or settings.SECRET_KEY,
                "ENVIRONMENT": settings.ENVIRONMENT
            }
            
            missing_vars = []
            for var_name, var_value in critical_vars.items():
                if not var_value:
                    missing_vars.append(var_name)
            
            if missing_vars:
                self.results["critical_issues"].append(
                    f"Missing critical environment variables: {', '.join(missing_vars)}"
                )
                logger.error(f"❌ Missing environment variables: {missing_vars}")
            else:
                logger.info("✅ All critical environment variables are set")
            
            # Check database URL format
            db_url = settings.DATABASE_URL
            if db_url and not db_url.startswith(("postgresql://", "postgres://", "postgresql+asyncpg://")):
                self.results["issues_found"].append("DATABASE_URL format appears invalid")
                
            # Check JWT secret strength
            jwt_secret = settings.JWT_SECRET or settings.SECRET_KEY
            if jwt_secret and len(jwt_secret) < 32:
                self.results["warnings"].append("JWT secret may be too short (< 32 characters)")
                
        except Exception as e:
            self.results["critical_issues"].append(f"Environment config test failed: {str(e)}")
            logger.error(f"❌ Environment config test failed: {e}")
    
    async def test_database_connection(self):
        """Test database connection and basic operations"""
        logger.info("🗄️ Testing database connection...")
        self.results["components_tested"].append("database_connection")
        
        try:
            from app.core.async_session import get_async_db
            from sqlalchemy import text
            
            # Test async database connection
            async for db in get_async_db():
                try:
                    # Basic connectivity test
                    start_time = time.time()
                    result = await db.execute(text("SELECT 1 as test"))
                    connection_time = (time.time() - start_time) * 1000
                    
                    if connection_time > 1000:  # > 1 second
                        self.results["warnings"].append(f"Slow database connection: {connection_time:.0f}ms")
                    else:
                        logger.info(f"✅ Database connection successful: {connection_time:.0f}ms")
                    
                    # Test user table access
                    try:
                        result = await db.execute(text("SELECT COUNT(*) FROM users LIMIT 1"))
                        user_count = result.scalar()
                        logger.info(f"✅ Users table accessible, {user_count} users found")
                    except Exception as e:
                        self.results["critical_issues"].append(f"Cannot access users table: {str(e)}")
                        logger.error(f"❌ Cannot access users table: {e}")
                    
                    break  # Exit after first successful connection
                    
                except Exception as e:
                    self.results["critical_issues"].append(f"Database connection failed: {str(e)}")
                    logger.error(f"❌ Database connection failed: {e}")
                    
        except Exception as e:
            self.results["critical_issues"].append(f"Database test setup failed: {str(e)}")
            logger.error(f"❌ Database test setup failed: {e}")
    
    async def test_password_security(self):
        """Test password security configuration"""
        logger.info("🔐 Testing password security...")
        self.results["components_tested"].append("password_security")
        
        try:
            from app.core.password_security import (
                validate_bcrypt_configuration,
                test_password_performance,
                hash_password_async,
                verify_password_async
            )
            
            # Validate bcrypt configuration
            config_validation = validate_bcrypt_configuration()
            if not config_validation["valid"]:
                self.results["critical_issues"].extend(config_validation["issues"])
                logger.error(f"❌ BCrypt configuration invalid: {config_validation['issues']}")
            else:
                logger.info("✅ BCrypt configuration valid")
            
            if config_validation["warnings"]:
                self.results["warnings"].extend(config_validation["warnings"])
                logger.warning(f"⚠️ BCrypt warnings: {config_validation['warnings']}")
            
            # Test password operations
            test_password = "TestPassword123!"
            try:
                start_time = time.time()
                password_hash = await hash_password_async(test_password)
                hash_time = (time.time() - start_time) * 1000
                
                # Test verification
                start_time = time.time()
                is_valid = await verify_password_async(test_password, password_hash)
                verify_time = (time.time() - start_time) * 1000
                
                if not is_valid:
                    self.results["critical_issues"].append("Password hash/verify cycle failed")
                    logger.error("❌ Password hash/verify cycle failed")
                else:
                    logger.info(f"✅ Password operations working: hash={hash_time:.0f}ms, verify={verify_time:.0f}ms")
                
                if hash_time > 1000 or verify_time > 1000:
                    self.results["warnings"].append(f"Slow password operations: hash={hash_time:.0f}ms, verify={verify_time:.0f}ms")
                    
            except Exception as e:
                self.results["critical_issues"].append(f"Password operations test failed: {str(e)}")
                logger.error(f"❌ Password operations test failed: {e}")
                
        except Exception as e:
            self.results["critical_issues"].append(f"Password security test failed: {str(e)}")
            logger.error(f"❌ Password security test failed: {e}")
    
    async def test_auth_components(self):
        """Test authentication service components"""
        logger.info("🔑 Testing authentication components...")
        self.results["components_tested"].append("auth_components")
        
        try:
            from app.services.auth_jwt_service import create_token_pair, verify_token
            
            # Test token creation
            test_user_data = {
                "sub": "test-user-id",
                "is_premium": False,
                "country": "US"
            }
            
            try:
                tokens = create_token_pair(test_user_data, user_role="basic_user")
                
                if not tokens.get("access_token") or not tokens.get("refresh_token"):
                    self.results["critical_issues"].append("Token creation failed - missing tokens")
                    logger.error("❌ Token creation failed - missing tokens")
                else:
                    logger.info("✅ Token creation successful")
                    
                    # Test token verification
                    try:
                        payload = await verify_token(tokens["access_token"])
                        if payload and payload.get("sub") == "test-user-id":
                            logger.info("✅ Token verification successful")
                        else:
                            self.results["critical_issues"].append("Token verification failed")
                            logger.error("❌ Token verification failed")
                    except Exception as e:
                        self.results["critical_issues"].append(f"Token verification failed: {str(e)}")
                        logger.error(f"❌ Token verification failed: {e}")
                        
            except Exception as e:
                self.results["critical_issues"].append(f"Token creation failed: {str(e)}")
                logger.error(f"❌ Token creation failed: {e}")
                
        except Exception as e:
            self.results["critical_issues"].append(f"Auth components test failed: {str(e)}")
            logger.error(f"❌ Auth components test failed: {e}")
    
    async def test_error_handling(self):
        """Test error handling system"""
        logger.info("⚠️ Testing error handling system...")
        self.results["components_tested"].append("error_handling")
        
        try:
            from app.core.standardized_error_handler import (
                ErrorCode,
                StandardizedAPIException,
                AuthenticationError,
                ValidationError,
                ErrorResponse
            )
            
            # Test error creation
            try:
                test_error = AuthenticationError("Test authentication error", ErrorCode.AUTH_INVALID_CREDENTIALS)
                response = ErrorResponse.create(test_error)
                
                if not response.get("success") == False:
                    self.results["issues_found"].append("Error response format incorrect")
                    logger.warning("⚠️ Error response format incorrect")
                elif not response.get("error", {}).get("code") == ErrorCode.AUTH_INVALID_CREDENTIALS:
                    self.results["issues_found"].append("Error code not properly set")
                    logger.warning("⚠️ Error code not properly set")
                else:
                    logger.info("✅ Error handling system working")
                    
            except Exception as e:
                self.results["issues_found"].append(f"Error handling test failed: {str(e)}")
                logger.warning(f"⚠️ Error handling test failed: {e}")
                
        except Exception as e:
            self.results["issues_found"].append(f"Error handling system test failed: {str(e)}")
            logger.warning(f"⚠️ Error handling system test failed: {e}")
    
    async def test_production_schema(self):
        """Test production database schema"""
        logger.info("📊 Testing production database schema...")
        self.results["components_tested"].append("database_schema")
        
        try:
            from app.core.async_session import get_async_db
            from sqlalchemy import text, inspect
            
            async for db in get_async_db():
                try:
                    # Check users table columns
                    inspector = inspect(db.bind)
                    columns = inspector.get_columns('users')
                    column_names = [col['name'] for col in columns]
                    
                    required_columns = [
                        'id', 'email', 'password_hash', 'country', 
                        'annual_income', 'is_premium', 'created_at',
                        'updated_at', 'token_version', 'timezone'
                    ]
                    
                    missing_columns = [col for col in required_columns if col not in column_names]
                    
                    if missing_columns:
                        self.results["critical_issues"].append(f"Missing required columns in users table: {missing_columns}")
                        logger.error(f"❌ Missing columns: {missing_columns}")
                    else:
                        logger.info("✅ All required user table columns present")
                    
                    # Check for password reset fields
                    password_reset_columns = [
                        'password_reset_token', 'password_reset_expires', 'password_reset_attempts',
                        'email_verified', 'email_verification_token', 'email_verification_expires'
                    ]
                    
                    missing_auth_columns = [col for col in password_reset_columns if col not in column_names]
                    if missing_auth_columns:
                        self.results["warnings"].append(f"Missing auth enhancement columns: {missing_auth_columns}")
                        logger.warning(f"⚠️ Missing auth columns: {missing_auth_columns}")
                    else:
                        logger.info("✅ All authentication enhancement columns present")
                    
                    break
                    
                except Exception as e:
                    self.results["issues_found"].append(f"Schema inspection failed: {str(e)}")
                    logger.warning(f"⚠️ Schema inspection failed: {e}")
                    
        except Exception as e:
            self.results["issues_found"].append(f"Schema test failed: {str(e)}")
            logger.warning(f"⚠️ Schema test failed: {e}")
    
    async def test_rate_limiting(self):
        """Test rate limiting system"""
        logger.info("🚦 Testing rate limiting system...")
        self.results["components_tested"].append("rate_limiting")
        
        try:
            from app.core.simple_rate_limiter import (
                check_login_rate_limit,
                check_register_rate_limit
            )
            
            # Test rate limiter functions exist and work
            try:
                check_login_rate_limit("test-ip")
                check_register_rate_limit("test-ip")
                logger.info("✅ Rate limiting functions operational")
            except Exception as e:
                # Rate limiting errors are expected during normal operation
                if "rate limit" in str(e).lower():
                    logger.info("✅ Rate limiting working (rate limit triggered)")
                else:
                    self.results["warnings"].append(f"Rate limiting may have issues: {str(e)}")
                    logger.warning(f"⚠️ Rate limiting warning: {e}")
                    
        except ImportError as e:
            self.results["warnings"].append(f"Rate limiting module not available: {str(e)}")
            logger.warning(f"⚠️ Rate limiting not available: {e}")
        except Exception as e:
            self.results["warnings"].append(f"Rate limiting test failed: {str(e)}")
            logger.warning(f"⚠️ Rate limiting test failed: {e}")
    
    async def test_registration_flow(self):
        """Test complete registration flow"""
        logger.info("📝 Testing registration flow...")
        self.results["components_tested"].append("registration_flow")
        
        try:
            from app.api.auth.schemas import RegisterIn
            from app.core.password_security import hash_password_async
            from app.core.async_session import get_async_db
            from app.db.models.user import User
            from sqlalchemy import select
            
            test_email = f"test-{int(time.time())}@test.com"
            test_password = "TestPassword123!"
            
            # Test registration data validation
            try:
                registration_data = RegisterIn(
                    email=test_email,
                    password=test_password,
                    country="US",
                    annual_income=50000,
                    timezone="UTC"
                )
                logger.info("✅ Registration data validation successful")
            except Exception as e:
                self.results["issues_found"].append(f"Registration data validation failed: {str(e)}")
                logger.warning(f"⚠️ Registration validation failed: {e}")
                return
            
            # Test user creation flow (without actually saving)
            try:
                async for db in get_async_db():
                    # Check if test user already exists
                    existing_user_query = select(User).where(User.email == test_email)
                    result = await db.execute(existing_user_query)
                    existing_user = result.scalar_one_or_none()
                    
                    if existing_user:
                        logger.info("✅ Duplicate user check working")
                    
                    # Test password hashing
                    password_hash = await hash_password_async(test_password)
                    
                    # Test user model creation (without saving)
                    test_user = User(
                        email=test_email,
                        password_hash=password_hash,
                        country=registration_data.country,
                        annual_income=registration_data.annual_income,
                        timezone=registration_data.timezone
                    )
                    
                    # Validate user object
                    if not test_user.email or not test_user.password_hash:
                        self.results["issues_found"].append("User model creation failed")
                        logger.warning("⚠️ User model creation failed")
                    else:
                        logger.info("✅ User model creation successful")
                    
                    break
                    
            except Exception as e:
                self.results["issues_found"].append(f"Registration flow test failed: {str(e)}")
                logger.warning(f"⚠️ Registration flow test failed: {e}")
                
        except Exception as e:
            self.results["issues_found"].append(f"Registration flow test setup failed: {str(e)}")
            logger.warning(f"⚠️ Registration flow test setup failed: {e}")
    
    async def test_login_flow(self):
        """Test complete login flow"""
        logger.info("🔓 Testing login flow...")
        self.results["components_tested"].append("login_flow")
        
        try:
            from app.api.auth.schemas import LoginIn
            from app.core.password_security import verify_password_async
            from app.services.auth_jwt_service import create_token_pair
            
            # Test login data validation
            try:
                login_data = LoginIn(
                    email="test@example.com",
                    password="TestPassword123!"
                )
                logger.info("✅ Login data validation successful")
            except Exception as e:
                self.results["issues_found"].append(f"Login data validation failed: {str(e)}")
                logger.warning(f"⚠️ Login validation failed: {e}")
                return
            
            # Test password verification flow
            try:
                # Create a test hash to verify against
                test_password = "TestPassword123!"
                from app.core.password_security import hash_password_async
                test_hash = await hash_password_async(test_password)
                
                # Test verification
                is_valid = await verify_password_async(test_password, test_hash)
                if not is_valid:
                    self.results["issues_found"].append("Password verification failed in login flow")
                    logger.warning("⚠️ Password verification failed in login flow")
                else:
                    logger.info("✅ Password verification in login flow successful")
                
                # Test token creation for login
                user_data = {
                    "sub": "test-user-id",
                    "is_premium": False,
                    "country": "US"
                }
                tokens = create_token_pair(user_data, user_role="basic_user")
                
                if tokens.get("access_token") and tokens.get("refresh_token"):
                    logger.info("✅ Login token creation successful")
                else:
                    self.results["issues_found"].append("Login token creation failed")
                    logger.warning("⚠️ Login token creation failed")
                    
            except Exception as e:
                self.results["issues_found"].append(f"Login flow test failed: {str(e)}")
                logger.warning(f"⚠️ Login flow test failed: {e}")
                
        except Exception as e:
            self.results["issues_found"].append(f"Login flow test setup failed: {str(e)}")
            logger.warning(f"⚠️ Login flow test setup failed: {e}")
    
    async def generate_diagnostic_report(self):
        """Generate comprehensive diagnostic report"""
        
        # Generate recommendations based on findings
        if self.results["critical_issues"]:
            self.results["recommendations"].append(
                "🚨 CRITICAL: Address critical issues immediately - authentication system is broken"
            )
            
        if "database_connection" in [issue for issue in self.results["critical_issues"] if "database" in issue.lower()]:
            self.results["recommendations"].append(
                "🔧 Check DATABASE_URL environment variable and database server availability"
            )
            
        if "password" in str(self.results["critical_issues"]).lower():
            self.results["recommendations"].append(
                "🔐 Review password security configuration and bcrypt setup"
            )
            
        if "Missing required columns" in str(self.results["critical_issues"]):
            self.results["recommendations"].append(
                "📊 Run database migrations: python -m alembic upgrade head"
            )
            
        if not self.results["critical_issues"] and not self.results["issues_found"]:
            self.results["recommendations"].append(
                "✅ Authentication system appears healthy - check production environment variables and network connectivity"
            )
        
        # Summary statistics
        self.results["summary"] = {
            "total_tests": len(self.results["components_tested"]),
            "critical_issues": len(self.results["critical_issues"]),
            "issues_found": len(self.results["issues_found"]),
            "warnings": len(self.results["warnings"]),
            "overall_status": "CRITICAL" if self.results["critical_issues"] else "OK" if not self.results["issues_found"] else "NEEDS_ATTENTION"
        }


async def main():
    """Run authentication diagnostic"""
    print("=" * 80)
    print("🔍 MITA Finance Authentication Production Diagnostic")
    print("=" * 80)
    
    diagnostic = AuthDiagnostic()
    results = await diagnostic.run_full_diagnostic()
    
    # Save results to file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_file = f"auth_diagnostic_report_{timestamp}.json"
    
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "=" * 80)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 80)
    
    summary = results.get("summary", {})
    print(f"Overall Status: {summary.get('overall_status', 'UNKNOWN')}")
    print(f"Tests Run: {summary.get('total_tests', 0)}")
    print(f"Critical Issues: {summary.get('critical_issues', 0)}")
    print(f"Issues Found: {summary.get('issues_found', 0)}")
    print(f"Warnings: {summary.get('warnings', 0)}")
    
    if results["critical_issues"]:
        print("\n🚨 CRITICAL ISSUES:")
        for issue in results["critical_issues"]:
            print(f"  ❌ {issue}")
    
    if results["issues_found"]:
        print("\n⚠️ ISSUES FOUND:")
        for issue in results["issues_found"]:
            print(f"  ⚠️ {issue}")
    
    if results["warnings"]:
        print("\n⚠️ WARNINGS:")
        for warning in results["warnings"]:
            print(f"  ⚠️ {warning}")
    
    if results["recommendations"]:
        print("\n💡 RECOMMENDATIONS:")
        for rec in results["recommendations"]:
            print(f"  {rec}")
    
    print(f"\n📄 Full report saved to: {report_file}")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())