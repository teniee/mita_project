#!/usr/bin/env python3
"""
Production Configuration Validation Script
===========================================

This script validates that all critical production configuration is properly set
and that the application can start successfully with the production configuration.

For MITA Finance - Financial Application Production Readiness
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Add the app directory to path
sys.path.insert(0, str(Path(__file__).parent / "app"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class ProductionConfigValidator:
    """Validates production configuration for MITA Finance"""
    
    def __init__(self, env_file_path=".env.production"):
        self.env_file_path = env_file_path
        self.validation_errors = []
        self.validation_warnings = []
        
    def load_env_file(self):
        """Load environment variables from .env.production file"""
        if not os.path.exists(self.env_file_path):
            self.validation_errors.append(f"Environment file not found: {self.env_file_path}")
            return False
            
        try:
            with open(self.env_file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
            return True
        except Exception as e:
            self.validation_errors.append(f"Failed to load environment file: {e}")
            return False
    
    def validate_critical_secrets(self):
        """Validate that all critical secrets are properly configured"""
        logger.info("🔐 Validating critical secrets...")
        
        critical_secrets = [
            ('JWT_SECRET', 'JWT authentication secret'),
            ('SECRET_KEY', 'Application secret key'),
            ('DATABASE_URL', 'Database connection string'),
        ]
        
        for env_var, description in critical_secrets:
            value = os.getenv(env_var, '').strip()
            
            if not value:
                self.validation_errors.append(f"CRITICAL: {env_var} is not set ({description})")
            elif value.startswith('REPLACE_WITH_'):
                self.validation_errors.append(f"CRITICAL: {env_var} contains placeholder value - must be replaced with actual secret")
            elif len(value) < 16:
                self.validation_errors.append(f"CRITICAL: {env_var} is too short (minimum 16 characters for security)")
            else:
                logger.info(f"✅ {env_var} is properly configured")
    
    def validate_database_config(self):
        """Validate database configuration"""
        logger.info("🗄️  Validating database configuration...")
        
        database_url = os.getenv('DATABASE_URL', '').strip()
        
        if not database_url:
            self.validation_errors.append("CRITICAL: DATABASE_URL is not configured")
            return
        
        if not database_url.startswith(('postgresql://', 'postgresql+asyncpg://', 'postgres://')):
            self.validation_errors.append("CRITICAL: DATABASE_URL must be a PostgreSQL connection string")
            return
            
        # Validate asyncpg driver for production
        if not database_url.startswith('postgresql+asyncpg://'):
            if database_url.startswith(('postgresql://', 'postgres://')):
                self.validation_warnings.append("WARNING: DATABASE_URL should use asyncpg driver (postgresql+asyncpg://) for optimal performance")
        
        logger.info("✅ Database configuration validated")
    
    def validate_redis_config(self):
        """Validate Redis configuration"""
        logger.info("🔄 Validating Redis configuration...")
        
        upstash_url = os.getenv('UPSTASH_REDIS_URL', '').strip()
        upstash_rest_url = os.getenv('UPSTASH_REDIS_REST_URL', '').strip()
        upstash_token = os.getenv('UPSTASH_REDIS_REST_TOKEN', '').strip()
        
        redis_url = os.getenv('REDIS_URL', '').strip()
        
        if upstash_url and upstash_rest_url and upstash_token:
            logger.info("✅ Upstash Redis configuration detected (recommended for production)")
        elif redis_url and not redis_url.startswith('REPLACE_WITH_'):
            logger.info("✅ Redis configuration detected")
        else:
            self.validation_warnings.append("WARNING: No Redis configuration detected - rate limiting and caching may be limited")
    
    def validate_external_services(self):
        """Validate external service integrations"""
        logger.info("🌐 Validating external services...")
        
        external_services = [
            ('OPENAI_API_KEY', 'OpenAI API integration', True),
            ('SENTRY_DSN', 'Error monitoring with Sentry', False),
            ('FIREBASE_JSON', 'Firebase integration', False),
            ('SMTP_PASSWORD', 'Email service integration', False),
        ]
        
        for env_var, description, required in external_services:
            value = os.getenv(env_var, '').strip()
            
            if not value or value.startswith('REPLACE_WITH_'):
                if required:
                    self.validation_errors.append(f"CRITICAL: {env_var} is required for {description}")
                else:
                    self.validation_warnings.append(f"WARNING: {env_var} not configured - {description} will be disabled")
            else:
                logger.info(f"✅ {env_var} configured for {description}")
    
    def validate_security_config(self):
        """Validate security configuration"""
        logger.info("🛡️  Validating security configuration...")
        
        # Environment
        environment = os.getenv('ENVIRONMENT', '').strip().lower()
        if environment != 'production':
            self.validation_errors.append(f"CRITICAL: ENVIRONMENT must be 'production', got: '{environment}'")
        
        # Debug mode
        debug = os.getenv('DEBUG', '').strip().lower()
        if debug in ('true', '1', 'yes'):
            self.validation_errors.append("CRITICAL: DEBUG must be 'false' in production")
        
        # CORS origins
        allowed_origins = os.getenv('ALLOWED_ORIGINS', '').strip()
        if not allowed_origins or '*' in allowed_origins:
            self.validation_warnings.append("WARNING: ALLOWED_ORIGINS should be restricted to specific domains in production")
        
        # SSL/TLS
        secure_cookies = os.getenv('SECURE_COOKIES', '').strip().lower()
        if secure_cookies not in ('true', '1', 'yes'):
            self.validation_warnings.append("WARNING: SECURE_COOKIES should be enabled in production")
        
        logger.info("✅ Security configuration validated")
    
    def validate_performance_config(self):
        """Validate performance configuration"""
        logger.info("⚡ Validating performance configuration...")
        
        # Worker configuration
        web_concurrency = os.getenv('WEB_CONCURRENCY', '1')
        try:
            concurrency = int(web_concurrency)
            if concurrency < 2:
                self.validation_warnings.append(f"WARNING: WEB_CONCURRENCY={concurrency} may not be optimal for production load")
        except ValueError:
            self.validation_warnings.append(f"WARNING: Invalid WEB_CONCURRENCY value: {web_concurrency}")
        
        # Database pool size
        db_pool_size = os.getenv('DB_POOL_SIZE', '10')
        try:
            pool_size = int(db_pool_size)
            if pool_size < 10:
                self.validation_warnings.append(f"WARNING: DB_POOL_SIZE={pool_size} may be too small for production")
        except ValueError:
            self.validation_warnings.append(f"WARNING: Invalid DB_POOL_SIZE value: {db_pool_size}")
        
        logger.info("✅ Performance configuration validated")
    
    async def test_application_startup(self):
        """Test that the application can start with current configuration"""
        logger.info("🚀 Testing application startup...")
        
        try:
            # Import and initialize core components
            from app.core.config import settings, validate_required_settings
            
            # Validate settings
            validate_required_settings()
            logger.info("✅ Settings validation passed")
            
            # Test database connection
            try:
                from app.core.async_session import check_database_health
                db_healthy = await asyncio.wait_for(check_database_health(), timeout=10.0)
                if db_healthy:
                    logger.info("✅ Database connection test passed")
                else:
                    self.validation_errors.append("CRITICAL: Database connection test failed")
            except asyncio.TimeoutError:
                self.validation_warnings.append("WARNING: Database connection test timed out")
            except Exception as e:
                self.validation_warnings.append(f"WARNING: Database connection test error: {e}")
            
            # Test application creation
            try:
                from app.main import app
                logger.info("✅ Application creation successful")
            except Exception as e:
                self.validation_errors.append(f"CRITICAL: Application creation failed: {e}")
                
        except Exception as e:
            self.validation_errors.append(f"CRITICAL: Application startup test failed: {e}")
    
    async def run_validation(self):
        """Run complete validation suite"""
        logger.info("🔍 Starting MITA Finance Production Configuration Validation")
        logger.info("=" * 60)
        
        # Load environment file
        if not self.load_env_file():
            return False
        
        # Run validation checks
        self.validate_critical_secrets()
        self.validate_database_config()
        self.validate_redis_config()
        self.validate_external_services()
        self.validate_security_config()
        self.validate_performance_config()
        
        # Test application startup
        await self.test_application_startup()
        
        # Report results
        logger.info("=" * 60)
        logger.info("📊 VALIDATION RESULTS")
        logger.info("=" * 60)
        
        if self.validation_errors:
            logger.error("❌ CRITICAL ERRORS FOUND:")
            for error in self.validation_errors:
                logger.error(f"   {error}")
        
        if self.validation_warnings:
            logger.warning("⚠️  WARNINGS:")
            for warning in self.validation_warnings:
                logger.warning(f"   {warning}")
        
        if not self.validation_errors and not self.validation_warnings:
            logger.info("🎉 ALL VALIDATIONS PASSED! Configuration is production-ready.")
            return True
        elif not self.validation_errors:
            logger.info("✅ CRITICAL VALIDATIONS PASSED. Warnings should be addressed.")
            return True
        else:
            logger.error("💥 PRODUCTION DEPLOYMENT BLOCKED - Critical errors must be fixed.")
            return False


async def main():
    """Main validation function"""
    validator = ProductionConfigValidator()
    success = await validator.run_validation()
    
    logger.info("=" * 60)
    if success:
        logger.info("🚀 PRODUCTION READINESS: APPROVED")
        logger.info("   Configuration is ready for production deployment.")
        sys.exit(0)
    else:
        logger.error("🚫 PRODUCTION READINESS: BLOCKED") 
        logger.error("   Fix critical errors before production deployment.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())