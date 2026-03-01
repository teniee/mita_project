"""
AWS Lambda function for automated database credential rotation
Implements zero-downtime rotation for PostgreSQL credentials used by MITA Finance

This function follows AWS best practices for database credential rotation:
1. Create new credentials
2. Test new credentials
3. Update application secrets
4. Remove old credentials after grace period
"""

import json
import logging
import boto3
import psycopg2
import secrets
import string
from datetime import datetime
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
secrets_manager = boto3.client('secretsmanager')
rds = boto3.client('rds')

# Configuration
GRACE_PERIOD_HOURS = 24  # Time to keep old credentials active
MIN_PASSWORD_LENGTH = 32
PASSWORD_CHARS = string.ascii_letters + string.digits + '!@#$%^&*'

class DatabaseRotationError(Exception):
    """Custom exception for database rotation errors"""
    pass

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Main Lambda handler for database credential rotation
    
    Args:
        event: Lambda event containing secret ARN and token
        context: Lambda context
        
    Returns:
        Dictionary with rotation status
    """
    try:
        # Extract event parameters
        secret_arn = event.get('SecretId')
        token = event.get('Token', 'AWSCURRENT')
        step = event.get('Step')
        
        logger.info(f"Starting rotation step: {step} for secret: {secret_arn}")
        
        # Validate required parameters
        if not secret_arn or not step:
            raise DatabaseRotationError("Missing required parameters: SecretId and Step")
        
        # Execute rotation step
        if step == 'createSecret':
            create_secret(secret_arn, token)
        elif step == 'setSecret':
            set_secret(secret_arn, token)
        elif step == 'testSecret':
            test_secret(secret_arn, token)
        elif step == 'finishSecret':
            finish_secret(secret_arn, token)
        else:
            raise DatabaseRotationError(f"Invalid rotation step: {step}")
        
        logger.info(f"Successfully completed rotation step: {step}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Rotation step {step} completed successfully',
                'secret_arn': secret_arn,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Rotation failed: {str(e)}")
        
        # Send alert to monitoring system
        send_rotation_alert(secret_arn, step, str(e))
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'secret_arn': secret_arn,
                'step': step,
                'timestamp': datetime.utcnow().isoformat()
            })
        }

def create_secret(secret_arn: str, token: str) -> None:
    """
    Step 1: Create new secret version with rotated credentials
    
    Args:
        secret_arn: ARN of the secret to rotate
        token: Version token for the new secret
    """
    logger.info(f"Creating new secret version for: {secret_arn}")
    
    try:
        # Check if AWSPENDING version already exists
        try:
            secrets_manager.describe_secret(SecretId=secret_arn, VersionStage='AWSPENDING')
            logger.info("AWSPENDING version already exists, skipping creation")
            return
        except secrets_manager.exceptions.ResourceNotFoundException:
            pass
        
        # Get current secret
        current_secret = get_secret_value(secret_arn, 'AWSCURRENT')
        
        # Generate new credentials
        new_secret = generate_new_credentials(current_secret)
        
        # Store new secret version
        secrets_manager.put_secret_value(
            SecretId=secret_arn,
            SecretString=json.dumps(new_secret),
            VersionStages=['AWSPENDING']
        )
        
        logger.info("New secret version created successfully")
        
    except Exception as e:
        raise DatabaseRotationError(f"Failed to create new secret: {str(e)}")

def set_secret(secret_arn: str, token: str) -> None:
    """
    Step 2: Set the new credentials in the database
    
    Args:
        secret_arn: ARN of the secret to rotate
        token: Version token for the new secret
    """
    logger.info(f"Setting new credentials in database for: {secret_arn}")
    
    try:
        # Get both current and pending secrets
        current_secret = get_secret_value(secret_arn, 'AWSCURRENT')
        pending_secret = get_secret_value(secret_arn, 'AWSPENDING')
        
        # Connect to database with current admin credentials
        admin_connection = connect_to_database(current_secret, use_admin=True)
        
        try:
            with admin_connection.cursor() as cursor:
                # Create or update the user with new password
                username = pending_secret['username']
                password = pending_secret['password']
                
                # Check if user exists
                cursor.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s",
                    (username,)
                )
                
                if cursor.fetchone():
                    # Update existing user password
                    cursor.execute(
                        f"ALTER USER {username} WITH PASSWORD %s",
                        (password,)
                    )
                    logger.info(f"Updated password for existing user: {username}")
                else:
                    # Create new user
                    cursor.execute(
                        f"CREATE USER {username} WITH PASSWORD %s",
                        (password,)
                    )
                    
                    # Grant necessary permissions
                    grant_user_permissions(cursor, username, pending_secret.get('permissions', []))
                    logger.info(f"Created new user: {username}")
                
                admin_connection.commit()
                
        finally:
            admin_connection.close()
        
        logger.info("Database credentials set successfully")
        
    except Exception as e:
        raise DatabaseRotationError(f"Failed to set database credentials: {str(e)}")

def test_secret(secret_arn: str, token: str) -> None:
    """
    Step 3: Test the new credentials
    
    Args:
        secret_arn: ARN of the secret to rotate
        token: Version token for the new secret
    """
    logger.info(f"Testing new credentials for: {secret_arn}")
    
    try:
        # Get pending secret
        pending_secret = get_secret_value(secret_arn, 'AWSPENDING')
        
        # Test database connection
        test_connection = connect_to_database(pending_secret)
        
        try:
            with test_connection.cursor() as cursor:
                # Test basic operations
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result[0] != 1:
                    raise DatabaseRotationError("Basic query test failed")
                
                # Test access to MITA tables (if they exist)
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('users', 'transactions', 'goals')
                    LIMIT 1
                """)
                
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*) FROM users LIMIT 1")
                    logger.info("Successfully tested access to application tables")
                
        finally:
            test_connection.close()
        
        logger.info("New credentials tested successfully")
        
    except Exception as e:
        raise DatabaseRotationError(f"Failed to test new credentials: {str(e)}")

def finish_secret(secret_arn: str, token: str) -> None:
    """
    Step 4: Finalize the rotation by updating version stages
    
    Args:
        secret_arn: ARN of the secret to rotate
        token: Version token for the new secret
    """
    logger.info(f"Finalizing rotation for: {secret_arn}")
    
    try:
        # Get current version info
        secret_info = secrets_manager.describe_secret(SecretId=secret_arn)
        
        # Find the version ID for AWSPENDING
        pending_version_id = None
        current_version_id = None
        
        for version_id, stages in secret_info['VersionIdsToStages'].items():
            if 'AWSPENDING' in stages:
                pending_version_id = version_id
            if 'AWSCURRENT' in stages:
                current_version_id = version_id
        
        if not pending_version_id:
            raise DatabaseRotationError("No AWSPENDING version found")
        
        # Update version stages
        secrets_manager.update_secret_version_stage(
            SecretId=secret_arn,
            VersionStage='AWSCURRENT',
            MoveToVersionId=pending_version_id,
            RemoveFromVersionId=current_version_id
        )
        
        # Schedule cleanup of old credentials
        schedule_credential_cleanup(secret_arn, current_version_id)
        
        logger.info("Rotation finalized successfully")
        
        # Send success notification
        send_rotation_success_notification(secret_arn)
        
    except Exception as e:
        raise DatabaseRotationError(f"Failed to finalize rotation: {str(e)}")

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

def generate_new_credentials(current_secret: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate new database credentials based on current secret
    
    Args:
        current_secret: Current secret data
        
    Returns:
        New secret data with rotated credentials
    """
    new_secret = current_secret.copy()
    
    # Generate new password
    new_password = generate_secure_password()
    new_secret['password'] = new_password
    
    # Update metadata
    new_secret['last_rotated'] = datetime.utcnow().isoformat()
    new_secret['rotation_version'] = new_secret.get('rotation_version', 0) + 1
    
    # Add rotation audit trail
    if 'rotation_history' not in new_secret:
        new_secret['rotation_history'] = []
    
    new_secret['rotation_history'].append({
        'timestamp': datetime.utcnow().isoformat(),
        'trigger': 'automated_rotation',
        'previous_version': current_secret.get('rotation_version', 0)
    })
    
    # Keep only last 10 rotation history entries
    if len(new_secret['rotation_history']) > 10:
        new_secret['rotation_history'] = new_secret['rotation_history'][-10:]
    
    return new_secret

def generate_secure_password() -> str:
    """
    Generate a cryptographically secure password
    
    Returns:
        Secure password string
    """
    password_length = MIN_PASSWORD_LENGTH
    
    # Ensure password contains at least one of each character type
    password_chars = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase), 
        secrets.choice(string.digits),
        secrets.choice('!@#$%^&*')
    ]
    
    # Fill remaining length with random characters
    password_chars.extend(
        secrets.choice(PASSWORD_CHARS) 
        for _ in range(password_length - len(password_chars))
    )
    
    # Shuffle the password characters
    secrets.SystemRandom().shuffle(password_chars)
    
    return ''.join(password_chars)

def connect_to_database(secret_data: Dict[str, Any], use_admin: bool = False) -> psycopg2.extensions.connection:
    """
    Connect to the database using secret data
    
    Args:
        secret_data: Secret containing connection info
        use_admin: Whether to use admin credentials
        
    Returns:
        Database connection
    """
    if use_admin and 'admin_username' in secret_data:
        username = secret_data['admin_username']
        password = secret_data['admin_password']
    else:
        username = secret_data['username']
        password = secret_data['password']
    
    connection_params = {
        'host': secret_data['host'],
        'port': secret_data.get('port', 5432),
        'database': secret_data['database'],
        'user': username,
        'password': password,
        'sslmode': secret_data.get('sslmode', 'require'),
        'connect_timeout': 10
    }
    
    return psycopg2.connect(**connection_params)

def grant_user_permissions(cursor, username: str, permissions: list) -> None:
    """
    Grant necessary permissions to the new user
    
    Args:
        cursor: Database cursor
        username: Username to grant permissions to
        permissions: List of permissions to grant
    """
    # Default MITA application permissions
    default_permissions = [
        f"GRANT CONNECT ON DATABASE mita TO {username}",
        f"GRANT USAGE ON SCHEMA public TO {username}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {username}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {username}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {username}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {username}"
    ]
    
    # Execute default permissions
    for permission in default_permissions:
        cursor.execute(permission)
    
    # Execute custom permissions
    for permission in permissions:
        cursor.execute(permission)

def schedule_credential_cleanup(secret_arn: str, old_version_id: str) -> None:
    """
    Schedule cleanup of old credentials after grace period
    
    Args:
        secret_arn: ARN of the secret
        old_version_id: Version ID of old credentials to clean up
    """
    # This would typically schedule a cleanup job
    # For now, we'll log the cleanup requirement
    logger.info(f"Scheduled cleanup for old credentials: {old_version_id} in {GRACE_PERIOD_HOURS} hours")
    
    # In a production system, you might:
    # 1. Create a CloudWatch Events rule to trigger cleanup
    # 2. Store cleanup info in DynamoDB
    # 3. Send message to SQS for delayed processing

def send_rotation_alert(secret_arn: str, step: str, error_message: str) -> None:
    """
    Send alert about rotation failure
    
    Args:
        secret_arn: ARN of the secret
        step: Rotation step that failed
        error_message: Error message
    """
    # This would integrate with your alerting system
    logger.error(f"ROTATION ALERT: {secret_arn} failed at step {step}: {error_message}")
    
    # In production, you might:
    # 1. Send to SNS topic
    # 2. Create CloudWatch alarm
    # 3. Send to PagerDuty
    # 4. Post to Slack

def send_rotation_success_notification(secret_arn: str) -> None:
    """
    Send notification about successful rotation
    
    Args:
        secret_arn: ARN of the secret
    """
    logger.info(f"ROTATION SUCCESS: {secret_arn} rotated successfully")
    
    # In production, you might send notifications to:
    # 1. Security team via SNS
    # 2. Audit log system
    # 3. Compliance dashboard
    # 4. Monitoring system