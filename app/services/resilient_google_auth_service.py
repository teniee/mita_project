"""
Resilient Google Authentication Service
Enhanced version with circuit breaker protection and proper error handling
"""

import uuid
import logging
from typing import Optional
import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.auth_jwt_service import hash_password
from app.core.circuit_breaker import get_circuit_breaker_manager, CircuitBreakerConfig
from app.repositories.user_repository import get_user_repository

logger = logging.getLogger(__name__)

ALLOWED_GOOGLE_CLIENT_IDS = [
    # Production Android/iOS client IDs
    "796406677497-kgkd6q7t75bpcsn343baokpuli8p5gad.apps.googleusercontent.com",  # Android
    "796406677497-0a9jg6vkuv2jtibddll5dp2b0394h21h.apps.googleusercontent.com",  # iOS
    # Development/web client ID used by the Flutter app
    "147595998708-0pkq7emouan1rs2lrgjau0ee2lge35pl.apps.googleusercontent.com",
]


class ResilientGoogleAuthService:
    """Enhanced Google authentication service with circuit breaker protection"""
    
    def __init__(self):
        self.circuit_breaker_manager = get_circuit_breaker_manager()
        self.user_repository = get_user_repository()
        
        # Register Google OAuth service with circuit breaker
        self.circuit_breaker_manager.register_service(
            'google_oauth_verify',
            CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout_duration=60,  # 1 minute recovery time
                max_retry_attempts=3,
                retry_backoff_factor=1.5,
                timeout_seconds=10.0,  # 10 second timeout per request
                trigger_exceptions=(
                    httpx.RequestError,
                    httpx.HTTPStatusError,
                    httpx.TimeoutException,
                    ConnectionError,
                    TimeoutError,
                    OSError,
                )
            )
        )
    
    async def authenticate_google_user(self, id_token_str: str) -> User:
        """
        Authenticate user with Google ID token using circuit breaker protection
        
        Args:
            id_token_str: Google ID token to verify
            
        Returns:
            User: Authenticated user object
            
        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Verify token with Google using circuit breaker protection
            payload = await self._verify_google_token(id_token_str)
            
            # Validate client ID
            aud = payload.get("aud")
            if aud not in ALLOWED_GOOGLE_CLIENT_IDS:
                logger.warning(f"Invalid client ID attempted: {aud}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid Client ID: {aud}"
                )
            
            # Extract email
            email = payload.get("email")
            if not email:
                logger.error("Email not found in Google token payload")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email not found in token"
                )
            
            # Get or create user
            user = await self._get_or_create_user(email, payload)
            
            logger.info(f"Successfully authenticated Google user: {email}")
            return user
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Google authentication: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service temporarily unavailable"
            )
    
    async def _verify_google_token(self, id_token: str) -> dict:
        """Verify Google ID token with circuit breaker protection"""
        
        async def _make_verification_request():
            """Internal function to make the verification request"""
            timeout_config = httpx.Timeout(10.0, connect=5.0)
            
            async with httpx.AsyncClient(timeout=timeout_config) as client:
                try:
                    response = await client.get(
                        "https://oauth2.googleapis.com/tokeninfo",
                        params={"id_token": id_token}
                    )
                    
                    if response.status_code == 400:
                        logger.warning(f"Invalid Google token provided")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid ID token"
                        )
                    elif response.status_code == 429:
                        logger.warning("Google OAuth rate limit exceeded")
                        raise HTTPException(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Too many authentication requests. Please try again later."
                        )
                    elif response.status_code != 200:
                        logger.error(f"Google token verification failed with status {response.status_code}")
                        # Raise an exception that will trigger the circuit breaker
                        raise httpx.HTTPStatusError(
                            f"Token verification failed: {response.status_code}",
                            request=response.request,
                            response=response
                        )
                    
                    return response.json()
                    
                except httpx.TimeoutException as e:
                    logger.error(f"Google OAuth timeout: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_408_REQUEST_TIMEOUT,
                        detail="Authentication service is taking too long to respond"
                    )
                except httpx.RequestError as e:
                    logger.error(f"Google OAuth connection error: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Authentication service temporarily unavailable"
                    )
        
        try:
            return await self.circuit_breaker_manager.call_service(
                'google_oauth_verify',
                _make_verification_request
            )
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Circuit breaker error in Google OAuth: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is currently experiencing issues"
            )
    
    async def _get_or_create_user(self, email: str, google_payload: dict) -> User:
        """Get existing user or create new one from Google authentication"""
        try:
            # Try to find existing user
            existing_user = await self.user_repository.get_by_email(email)
            
            if existing_user:
                # Update last login
                await self.user_repository.update_last_login(existing_user.id)
                logger.info(f"Existing Google user logged in: {email}")
                return existing_user
            
            # Create new user
            user_data = {
                'email': email.lower(),
                'password_hash': hash_password(uuid.uuid4().hex),  # Random password for OAuth users
                'is_premium': False,
                'country': self._extract_country_from_payload(google_payload),
            }
            
            # Extract additional profile information if available
            if google_payload.get('name'):
                user_data['name'] = google_payload['name']
            
            new_user = await self.user_repository.create_user(user_data)
            logger.info(f"New Google user created: {email}")
            
            return new_user
            
        except Exception as e:
            logger.error(f"Error creating/retrieving user for Google auth: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User creation failed"
            )
    
    def _extract_country_from_payload(self, payload: dict) -> str:
        """Extract country code from Google payload with fallback"""
        # Try to extract country from locale or other fields
        locale = payload.get('locale', 'en_US')
        if '_' in locale:
            country = locale.split('_')[1].upper()
            if len(country) == 2:
                return country
        
        # Default fallback
        return 'US'
    
    async def get_service_health(self) -> dict:
        """Get health status of the Google authentication service"""
        circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker('google_oauth_verify')
        stats = circuit_breaker.get_stats()
        
        return {
            'service_name': 'google_auth_service',
            'status': 'healthy' if stats['state'] == 'closed' else 'degraded' if stats['state'] == 'half_open' else 'unhealthy',
            'circuit_breaker_state': stats['state'],
            'total_requests': stats['total_requests'],
            'success_rate': stats['success_rate'],
            'consecutive_failures': stats['consecutive_failures'],
            'last_request_time': stats['last_success_time'] or stats['last_failure_time'],
            'allowed_client_ids': len(ALLOWED_GOOGLE_CLIENT_IDS),
        }
    
    async def test_connection(self) -> bool:
        """Test connection to Google OAuth service"""
        try:
            # Make a simple request to Google's OAuth discovery endpoint
            async def _test_request():
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get("https://accounts.google.com/.well-known/openid_configuration")
                    return response.status_code == 200
            
            return await self.circuit_breaker_manager.call_service(
                'google_oauth_verify',
                _test_request
            )
            
        except Exception as e:
            logger.error(f"Google OAuth connection test failed: {str(e)}")
            return False


# Global instance
_google_auth_service: Optional[ResilientGoogleAuthService] = None

def get_google_auth_service() -> ResilientGoogleAuthService:
    """Get singleton Google authentication service"""
    global _google_auth_service
    if _google_auth_service is None:
        _google_auth_service = ResilientGoogleAuthService()
    return _google_auth_service


# Convenience function for backward compatibility
async def authenticate_google_user(id_token_str: str) -> User:
    """Authenticate Google user - convenience function"""
    service = get_google_auth_service()
    return await service.authenticate_google_user(id_token_str)