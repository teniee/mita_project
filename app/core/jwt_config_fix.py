"""
JWT Configuration Fix and Validator
"""

import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class JWTConfigFix:
    """JWT configuration fixes for production"""
    
    @staticmethod
    def get_jwt_secret() -> str:
        """Get JWT secret with fallbacks"""
        # Priority order
        secrets = [
            os.getenv("JWT_SECRET"),
            os.getenv("SECRET_KEY"),
        ]
        
        for secret in secrets:
            if secret and len(secret) >= 32:
                return secret
        
        # Production check
        if os.getenv("ENVIRONMENT", "").lower() == "production":
            raise ValueError("JWT_SECRET or SECRET_KEY must be set in production")
        
        # Development fallback
        logger.warning("Using development JWT secret - NOT FOR PRODUCTION")
        return "dev-secret-key-not-for-production-use-only-12345"
    
    @staticmethod
    def validate_jwt_config() -> dict:
        """Validate JWT configuration"""
        try:
            secret = JWTConfigFix.get_jwt_secret()
            
            # Test token creation and verification
            test_payload = {
                "sub": "test-user",
                "exp": datetime.utcnow() + timedelta(minutes=30),
                "iat": datetime.utcnow()
            }
            
            # Create token
            token = jwt.encode(test_payload, secret, algorithm="HS256")
            
            # Verify token  
            decoded = jwt.decode(token, secret, algorithms=["HS256"])
            
            return {
                "valid": True,
                "secret_length": len(secret),
                "token_test": "passed",
                "message": "JWT configuration is working correctly"
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "message": "JWT configuration has issues"
            }
    
    @staticmethod
    def fix_token_expiration_issue():
        """Fix token expiration timing issues"""
        # This addresses the "Signature has expired" error in diagnostics
        
        # The issue is likely that tokens are created with very short expiration
        # or there's a clock skew issue
        
        recommended_settings = {
            "ACCESS_TOKEN_EXPIRE_MINUTES": 30,  # 30 minutes  
            "REFRESH_TOKEN_EXPIRE_DAYS": 7,    # 7 days
            "CLOCK_SKEW_SECONDS": 10,          # Allow 10 seconds clock skew
        }
        
        return recommended_settings

# Test JWT config on import
if __name__ == "__main__":
    config_result = JWTConfigFix.validate_jwt_config()
    print(f"JWT Config Status: {config_result}")
