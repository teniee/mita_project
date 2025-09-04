"""
MITA Finance - Clean Secret Management System
Provides secure secret loading with environment separation
"""
import json
import os
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SecretConfig:
    """Configuration for a specific secret"""
    name: str
    category: str  # critical, high, medium, low
    env_var: str
    required_in_production: bool = True
    default_value: Optional[str] = None
    min_length: Optional[int] = None
    description: str = ""


class SecretValidationError(Exception):
    """Raised when secret validation fails"""
    pass


class SecretManager:
    """Secure secret management with environment separation"""
    
    # Secret categories and their requirements
    SECRET_CONFIGS = {
        'database_url': SecretConfig(
            name='database_url',
            category='critical',
            env_var='DATABASE_URL',
            required_in_production=True,
            min_length=20,
            description='PostgreSQL database connection string'
        ),
        'jwt_secret': SecretConfig(
            name='jwt_secret',
            category='critical',
            env_var='JWT_SECRET',
            required_in_production=True,
            min_length=32,
            description='JWT token signing secret'
        ),
        'jwt_previous_secret': SecretConfig(
            name='jwt_previous_secret',
            category='critical',
            env_var='JWT_PREVIOUS_SECRET',
            required_in_production=True,
            min_length=32,
            description='Previous JWT secret for token migration'
        ),
        'secret_key': SecretConfig(
            name='secret_key',
            category='critical',
            env_var='SECRET_KEY',
            required_in_production=True,
            min_length=32,
            description='Application secret key for encryption'
        ),
        'openai_api_key': SecretConfig(
            name='openai_api_key',
            category='high',
            env_var='OPENAI_API_KEY',
            required_in_production=True,
            min_length=10,
            description='OpenAI API key for AI features'
        ),
        'redis_password': SecretConfig(
            name='redis_password',
            category='high',
            env_var='REDIS_PASSWORD',
            required_in_production=False,
            description='Redis authentication password'
        ),
        'sentry_dsn': SecretConfig(
            name='sentry_dsn',
            category='medium',
            env_var='SENTRY_DSN',
            required_in_production=False,
            description='Sentry DSN for error monitoring'
        ),
    }
    
    def __init__(self, environment: str = 'development'):
        self.environment = environment.lower()
        self.logger = logging.getLogger(__name__)
        self._secrets_cache: Dict[str, Any] = {}
        self._validation_results: Dict[str, Any] = {}
        
    def load_secret(self, secret_name: str) -> Optional[str]:
        """Load a secret value with validation"""
        if secret_name not in self.SECRET_CONFIGS:
            raise ValueError(f"Unknown secret: {secret_name}")
        
        config = self.SECRET_CONFIGS[secret_name]
        
        # Check cache first
        if secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]
        
        # Load from environment
        value = os.getenv(config.env_var)
        
        # Handle missing secrets
        if not value:
            if self.environment == 'production' and config.required_in_production:
                raise SecretValidationError(
                    f"Required secret '{secret_name}' not found in production environment"
                )
            elif self.environment == 'development' and config.default_value:
                value = config.default_value
            elif self.environment == 'development':
                # Generate secure default for development
                value = self._generate_development_secret(secret_name)
        
        # Validate secret
        if value:
            self._validate_secret(secret_name, value)
            self._secrets_cache[secret_name] = value
        
        return value
    
    def _validate_secret(self, secret_name: str, value: str) -> None:
        """Validate a secret value"""
        config = self.SECRET_CONFIGS[secret_name]
        errors = []
        
        # Check minimum length
        if config.min_length and len(value) < config.min_length:
            errors.append(f"Secret '{secret_name}' must be at least {config.min_length} characters")
        
        # Check for placeholder values
        placeholder_indicators = [
            'REPLACE_WITH',
            'your_',
            'test_',
            'example_',
            'placeholder'
        ]
        
        if self.environment == 'production':
            for indicator in placeholder_indicators:
                if indicator in value:
                    errors.append(f"Secret '{secret_name}' contains placeholder value: {indicator}")
        
        # JWT-specific validation
        if 'jwt' in secret_name.lower():
            if len(value) < 32:
                errors.append(f"JWT secret '{secret_name}' must be at least 32 characters for security")
        
        # Database URL validation
        if secret_name == 'database_url':
            if not any(protocol in value for protocol in ['postgresql://', 'postgres://', 'sqlite://']):
                errors.append(f"Database URL '{secret_name}' must contain valid protocol")
        
        # OpenAI API key validation
        if secret_name == 'openai_api_key':
            if not value.startswith('sk-'):
                if self.environment == 'production':
                    errors.append(f"OpenAI API key '{secret_name}' must start with 'sk-' in production")
        
        if errors:
            raise SecretValidationError(f"Secret validation failed: {'; '.join(errors)}")
    
    def _generate_development_secret(self, secret_name: str) -> str:
        """Generate a secure secret for development use"""
        import secrets
        import string
        
        # Generate base secret
        alphabet = string.ascii_letters + string.digits
        base_secret = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        # Add prefix based on secret type
        prefixes = {
            'jwt_secret': 'dev_jwt_',
            'jwt_previous_secret': 'dev_jwt_prev_',
            'secret_key': 'dev_secret_',
            'database_url': 'sqlite:///dev_mita.db',
            'openai_api_key': 'sk-dev-key-',
        }
        
        prefix = prefixes.get(secret_name, 'dev_')
        
        if secret_name == 'database_url':
            return prefixes[secret_name]
        else:
            return f"{prefix}{base_secret}"
    
    def validate_all_secrets(self) -> Dict[str, Any]:
        """Validate all secrets for current environment"""
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'missing_secrets': [],
            'environment': self.environment,
            'validation_time': datetime.now().isoformat()
        }
        
        for secret_name, config in self.SECRET_CONFIGS.items():
            try:
                value = self.load_secret(secret_name)
                if not value and config.required_in_production and self.environment == 'production':
                    results['missing_secrets'].append(secret_name)
                    results['errors'].append(f"Required secret '{secret_name}' is missing")
                    results['valid'] = False
                elif not value and self.environment != 'production':
                    results['warnings'].append(f"Optional secret '{secret_name}' is missing (ok in {self.environment})")
                
            except SecretValidationError as e:
                results['errors'].append(str(e))
                results['valid'] = False
            except Exception as e:
                results['errors'].append(f"Error validating secret '{secret_name}': {str(e)}")
                results['valid'] = False
        
        self._validation_results = results
        return results
    
    def get_secret_health_check(self) -> Dict[str, Any]:
        """Get secret health check information (without exposing values)"""
        validation_results = self.validate_all_secrets()
        
        secret_status = {}
        for secret_name, config in self.SECRET_CONFIGS.items():
            value = self.load_secret(secret_name)
            secret_status[secret_name] = {
                'configured': bool(value),
                'category': config.category,
                'required_in_production': config.required_in_production,
                'length': len(value) if value else 0,
                'description': config.description
            }
        
        return {
            'environment': self.environment,
            'overall_health': validation_results['valid'],
            'secrets': secret_status,
            'error_count': len(validation_results['errors']),
            'warning_count': len(validation_results['warnings']),
            'last_validation': validation_results['validation_time']
        }
    
    def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        """Rotate a secret (for future implementation with external secret managers)"""
        if self.environment == 'production':
            self.logger.warning(f"Secret rotation for '{secret_name}' should be handled by external secret manager")
            return False
        
        # For development/staging, update environment variable
        config = self.SECRET_CONFIGS[secret_name]
        os.environ[config.env_var] = new_value
        
        # Clear cache
        if secret_name in self._secrets_cache:
            del self._secrets_cache[secret_name]
        
        # Validate new secret
        try:
            self._validate_secret(secret_name, new_value)
            self.logger.info(f"Secret '{secret_name}' rotated successfully in {self.environment}")
            return True
        except SecretValidationError as e:
            self.logger.error(f"Failed to rotate secret '{secret_name}': {e}")
            return False
    
    def clear_cache(self):
        """Clear secrets cache"""
        self._secrets_cache.clear()
        self._validation_results.clear()
    
    @classmethod
    def create_for_environment(cls, environment: str) -> 'SecretManager':
        """Create a secret manager for specific environment"""
        return cls(environment=environment)


# Global secret manager instances
_secret_managers: Dict[str, SecretManager] = {}


def get_secret_manager(environment: str = None) -> SecretManager:
    """Get secret manager for environment"""
    if environment is None:
        environment = os.getenv('ENVIRONMENT', 'development')
    
    if environment not in _secret_managers:
        _secret_managers[environment] = SecretManager(environment)
    
    return _secret_managers[environment]


def load_secret(secret_name: str, environment: str = None) -> Optional[str]:
    """Convenience function to load a secret"""
    manager = get_secret_manager(environment)
    return manager.load_secret(secret_name)


def validate_secrets(environment: str = None) -> Dict[str, Any]:
    """Convenience function to validate all secrets"""
    manager = get_secret_manager(environment)
    return manager.validate_all_secrets()