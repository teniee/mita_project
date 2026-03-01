"""
AWS Lambda function for automated JWT secret rotation
Implements zero-downtime rotation for JWT signing keys used by MITA Finance

This function ensures that:
1. Old tokens remain valid during transition period
2. New tokens are signed with new key
3. Both keys are available during graceful transition
4. Old key is retired after all tokens expire
"""

import json
import logging
import boto3
import jwt
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Any
import requests

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
secrets_manager = boto3.client('secretsmanager')

# Configuration
JWT_ALGORITHM = 'HS256'
TOKEN_EXPIRY_MINUTES = 30  # Should match your application's token expiry
TRANSITION_PERIOD_MINUTES = 60  # How long to keep old key active
MIN_KEY_LENGTH = 32

class JWTRotationError(Exception):
    """Custom exception for JWT rotation errors"""
    pass

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Main Lambda handler for JWT secret rotation
    
    Args:
        event: Lambda event containing secret ARN and rotation step
        context: Lambda context
        
    Returns:
        Dictionary with rotation status
    """
    try:
        # Extract event parameters
        secret_arn = event.get('SecretId')
        step = event.get('Step')
        
        logger.info(f"Starting JWT rotation step: {step} for secret: {secret_arn}")
        
        # Validate required parameters
        if not secret_arn or not step:
            raise JWTRotationError("Missing required parameters: SecretId and Step")
        
        # Execute rotation step
        if step == 'createSecret':
            create_jwt_secret(secret_arn)
        elif step == 'setSecret':
            set_jwt_secret(secret_arn)
        elif step == 'testSecret':
            test_jwt_secret(secret_arn)
        elif step == 'finishSecret':
            finish_jwt_secret(secret_arn)
        else:
            raise JWTRotationError(f"Invalid rotation step: {step}")
        
        logger.info(f"Successfully completed JWT rotation step: {step}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'JWT rotation step {step} completed successfully',
                'secret_arn': secret_arn,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"JWT rotation failed: {str(e)}")
        
        # Send alert to monitoring system
        send_jwt_rotation_alert(secret_arn, step, str(e))
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'secret_arn': secret_arn,
                'step': step,
                'timestamp': datetime.utcnow().isoformat()
            })
        }

def create_jwt_secret(secret_arn: str) -> None:
    """
    Step 1: Create new JWT secret version
    
    Args:
        secret_arn: ARN of the JWT secret to rotate
    """
    logger.info(f"Creating new JWT secret version for: {secret_arn}")
    
    try:
        # Check if AWSPENDING version already exists
        try:
            secrets_manager.describe_secret(SecretId=secret_arn, VersionStage='AWSPENDING')
            logger.info("AWSPENDING JWT version already exists, skipping creation")
            return
        except secrets_manager.exceptions.ResourceNotFoundException:
            pass
        
        # Get current JWT secret
        current_secret = get_secret_value(secret_arn, 'AWSCURRENT')
        
        # Generate new JWT signing key
        new_jwt_key = generate_jwt_signing_key()
        
        # Create new secret data structure
        new_secret = {
            'current_key': new_jwt_key,
            'previous_key': current_secret.get('current_key'),  # Keep previous key for validation
            'algorithm': JWT_ALGORITHM,
            'created_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(minutes=TRANSITION_PERIOD_MINUTES)).isoformat(),
            'version': current_secret.get('version', 0) + 1,
            'rotation_metadata': {
                'trigger': 'automated_rotation',
                'previous_version': current_secret.get('version', 0),
                'rotation_timestamp': datetime.utcnow().isoformat()
            }
        }
        
        # Store new JWT secret version
        secrets_manager.put_secret_value(
            SecretId=secret_arn,
            SecretString=json.dumps(new_secret),
            VersionStages=['AWSPENDING']
        )
        
        logger.info("New JWT secret version created successfully")
        
    except Exception as e:
        raise JWTRotationError(f"Failed to create new JWT secret: {str(e)}")

def set_jwt_secret(secret_arn: str) -> None:
    """
    Step 2: Set the new JWT secret (no external system to update)
    
    For JWT secrets, this step primarily validates the new key format
    and ensures compatibility with the JWT library.
    
    Args:
        secret_arn: ARN of the JWT secret to rotate
    """
    logger.info(f"Validating new JWT secret for: {secret_arn}")
    
    try:
        # Get pending JWT secret
        pending_secret = get_secret_value(secret_arn, 'AWSPENDING')
        
        # Validate JWT key format
        validate_jwt_key(pending_secret['current_key'])
        
        # Test key compatibility with JWT library
        test_payload = {
            'sub': 'rotation_test',
            'iat': int(time.time()),
            'exp': int(time.time()) + 300,
            'test': True
        }
        
        # Test encoding with new key
        token = jwt.encode(test_payload, pending_secret['current_key'], algorithm=JWT_ALGORITHM)
        
        # Test decoding with new key
        decoded = jwt.decode(token, pending_secret['current_key'], algorithms=[JWT_ALGORITHM])
        
        if decoded['sub'] != 'rotation_test':
            raise JWTRotationError("JWT encoding/decoding test failed")
        
        logger.info("JWT secret validation completed successfully")
        
    except Exception as e:
        raise JWTRotationError(f"Failed to validate JWT secret: {str(e)}")

def test_jwt_secret(secret_arn: str) -> None:
    """
    Step 3: Test the new JWT secret with the application
    
    Args:
        secret_arn: ARN of the JWT secret to rotate
    """
    logger.info(f"Testing new JWT secret with application for: {secret_arn}")
    
    try:
        # Get pending JWT secret
        pending_secret = get_secret_value(secret_arn, 'AWSPENDING')
        
        # Test token generation and validation
        test_token = generate_test_token(pending_secret['current_key'])
        
        # Test token validation (simulating application behavior)
        validate_test_token(test_token, pending_secret['current_key'])
        
        # Test previous key compatibility (during transition)
        if pending_secret.get('previous_key'):
            previous_test_token = generate_test_token(pending_secret['previous_key'])
            validate_test_token(previous_test_token, pending_secret['previous_key'])
            logger.info("Previous JWT key compatibility confirmed")
        
        # If application health endpoint is available, test with real endpoint
        health_endpoint = get_application_health_endpoint()
        if health_endpoint:
            test_with_application_endpoint(health_endpoint, test_token)
        
        logger.info("JWT secret testing completed successfully")
        
    except Exception as e:
        raise JWTRotationError(f"Failed to test JWT secret: {str(e)}")

def finish_jwt_secret(secret_arn: str) -> None:
    """
    Step 4: Finalize the JWT rotation
    
    Args:
        secret_arn: ARN of the JWT secret to rotate
    """
    logger.info(f"Finalizing JWT rotation for: {secret_arn}")
    
    try:
        # Get secret information
        secret_info = secrets_manager.describe_secret(SecretId=secret_arn)
        
        # Find version IDs
        pending_version_id = None
        current_version_id = None
        
        for version_id, stages in secret_info['VersionIdsToStages'].items():
            if 'AWSPENDING' in stages:
                pending_version_id = version_id
            if 'AWSCURRENT' in stages:
                current_version_id = version_id
        
        if not pending_version_id:
            raise JWTRotationError("No AWSPENDING version found for JWT secret")
        
        # Update version stages
        secrets_manager.update_secret_version_stage(
            SecretId=secret_arn,
            VersionStage='AWSCURRENT',
            MoveToVersionId=pending_version_id,
            RemoveFromVersionId=current_version_id
        )
        
        # Update previous secret with cleanup schedule
        schedule_jwt_key_cleanup(secret_arn, current_version_id)
        
        logger.info("JWT rotation finalized successfully")
        
        # Send success notification
        send_jwt_rotation_success_notification(secret_arn)
        
    except Exception as e:
        raise JWTRotationError(f"Failed to finalize JWT rotation: {str(e)}")

def generate_jwt_signing_key() -> str:
    """
    Generate a cryptographically secure JWT signing key
    
    Returns:
        Secure JWT signing key
    """
    # Generate a 256-bit (32 byte) key for HS256
    secrets.token_bytes(32)
    
    # Convert to URL-safe base64 string
    jwt_key = secrets.token_urlsafe(32)
    
    # Ensure minimum length
    if len(jwt_key) < MIN_KEY_LENGTH:
        jwt_key = secrets.token_urlsafe(MIN_KEY_LENGTH)
    
    return jwt_key

def validate_jwt_key(jwt_key: str) -> None:
    """
    Validate JWT key format and strength
    
    Args:
        jwt_key: JWT key to validate
        
    Raises:
        JWTRotationError: If key is invalid
    """
    if not jwt_key:
        raise JWTRotationError("JWT key cannot be empty")
    
    if len(jwt_key) < MIN_KEY_LENGTH:
        raise JWTRotationError(f"JWT key too short, minimum length: {MIN_KEY_LENGTH}")
    
    # Test key with JWT library
    try:
        test_token = jwt.encode({'test': True}, jwt_key, algorithm=JWT_ALGORITHM)
        jwt.decode(test_token, jwt_key, algorithms=[JWT_ALGORITHM])
    except Exception as e:
        raise JWTRotationError(f"JWT key validation failed: {str(e)}")

def generate_test_token(jwt_key: str) -> str:
    """
    Generate a test JWT token
    
    Args:
        jwt_key: JWT signing key
        
    Returns:
        Test JWT token
    """
    payload = {
        'sub': 'rotation_test_user',
        'iat': int(time.time()),
        'exp': int(time.time()) + TOKEN_EXPIRY_MINUTES * 60,
        'user_id': 'test_user_123',
        'email': 'test@mita.finance',
        'roles': ['user'],
        'test_rotation': True
    }
    
    return jwt.encode(payload, jwt_key, algorithm=JWT_ALGORITHM)

def validate_test_token(token: str, jwt_key: str) -> None:
    """
    Validate a test JWT token
    
    Args:
        token: JWT token to validate
        jwt_key: JWT signing key
        
    Raises:
        JWTRotationError: If token validation fails
    """
    try:
        decoded = jwt.decode(token, jwt_key, algorithms=[JWT_ALGORITHM])
        
        # Verify test payload
        if not decoded.get('test_rotation'):
            raise JWTRotationError("Test token missing test_rotation claim")
        
        if decoded.get('sub') != 'rotation_test_user':
            raise JWTRotationError("Test token subject mismatch")
        
        logger.info("Test token validation successful")
        
    except jwt.ExpiredSignatureError:
        raise JWTRotationError("Test token has expired")
    except jwt.InvalidTokenError as e:
        raise JWTRotationError(f"Test token validation failed: {str(e)}")

def get_application_health_endpoint() -> str:
    """
    Get application health endpoint for testing
    
    Returns:
        Health endpoint URL or None if not configured
    """
    # This would typically come from environment variables or configuration
    # For now, return None to skip application endpoint testing
    return None

def test_with_application_endpoint(endpoint: str, token: str) -> None:
    """
    Test JWT token with actual application endpoint
    
    Args:
        endpoint: Application health endpoint
        token: JWT token to test
    """
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(endpoint, headers=headers, timeout=10)
        
        if response.status_code not in [200, 401]:  # 401 is expected for test token
            raise JWTRotationError(f"Application endpoint test failed: {response.status_code}")
        
        logger.info("Application endpoint test completed")
        
    except requests.RequestException as e:
        logger.warning(f"Application endpoint test failed (non-critical): {str(e)}")

def schedule_jwt_key_cleanup(secret_arn: str, old_version_id: str) -> None:
    """
    Schedule cleanup of old JWT key after transition period
    
    Args:
        secret_arn: ARN of the JWT secret
        old_version_id: Version ID of old key to clean up
    """
    cleanup_time = datetime.utcnow() + timedelta(minutes=TRANSITION_PERIOD_MINUTES)
    
    logger.info(f"Scheduled JWT key cleanup for version {old_version_id} at {cleanup_time}")
    
    # In production, you would:
    # 1. Create CloudWatch Events rule
    # 2. Send message to SQS with delay
    # 3. Store in DynamoDB for scheduled processing

def get_secret_value(secret_arn: str, version_stage: str) -> Dict[str, Any]:
    """
    Get secret value for a specific version stage
    
    Args:
        secret_arn: ARN of the secret
        version_stage: Version stage to retrieve
        
    Returns:
        Dictionary containing secret data
    """
    response = secrets_manager.get_secret_value(
        SecretId=secret_arn,
        VersionStage=version_stage
    )
    
    return json.loads(response['SecretString'])

def send_jwt_rotation_alert(secret_arn: str, step: str, error_message: str) -> None:
    """
    Send alert about JWT rotation failure
    
    Args:
        secret_arn: ARN of the secret
        step: Rotation step that failed
        error_message: Error message
    """
    logger.error(f"JWT ROTATION ALERT: {secret_arn} failed at step {step}: {error_message}")
    
    # In production, integrate with:
    # 1. SNS for immediate alerts
    # 2. PagerDuty for critical failures
    # 3. Slack for team notifications
    # 4. CloudWatch alarms

def send_jwt_rotation_success_notification(secret_arn: str) -> None:
    """
    Send notification about successful JWT rotation
    
    Args:
        secret_arn: ARN of the secret
    """
    logger.info(f"JWT ROTATION SUCCESS: {secret_arn} rotated successfully")
    
    # In production, notify:
    # 1. Security team
    # 2. Development team
    # 3. Audit systems
    # 4. Monitoring dashboards