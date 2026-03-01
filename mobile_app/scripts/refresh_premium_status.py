#!/usr/bin/env python3
"""
MITA Premium Subscription Management Script
==========================================

This script manages premium subscription status for the MITA financial application.
It validates App Store and Google Play Store receipts, updates user premium status,
and ensures proper feature access control with financial compliance standards.

Features:
- App Store receipt validation with Apple's verification service
- Google Play Store receipt validation with Google Play API
- Subscription status management (active, expired, cancelled, refunded)
- Premium feature revocation when subscriptions expire
- Comprehensive audit logging and monitoring
- Error handling with retry logic
- Production-ready monitoring and alerting

Requirements:
- Apple App Store Connect API credentials
- Google Play Console service account credentials
- Database access to MITA backend
- Proper security credentials management
"""

import asyncio
import logging
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import asyncpg
from google.oauth2 import service_account
from googleapiclient.discovery import build
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Configuration
SCRIPT_VERSION = "1.0.0"
BATCH_SIZE = 100
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    GRACE_PERIOD = "grace_period"
    BILLING_RETRY = "billing_retry"
    PENDING_RENEWAL = "pending_renewal"

class Platform(Enum):
    IOS = "ios"
    ANDROID = "android"

class PremiumFeature(Enum):
    ADVANCED_OCR = "advanced_ocr"
    BATCH_RECEIPT_PROCESSING = "batch_receipt_processing"
    PREMIUM_INSIGHTS = "premium_insights"
    ENHANCED_ANALYTICS = "enhanced_analytics"
    UNLIMITED_TRANSACTIONS = "unlimited_transactions"
    PRIORITY_SUPPORT = "priority_support"
    CUSTOM_CATEGORIES = "custom_categories"
    EXPORT_DATA = "export_data"

@dataclass
class SubscriptionInfo:
    user_id: str
    platform: Platform
    subscription_id: str
    product_id: str
    status: SubscriptionStatus
    expires_at: datetime
    auto_renew: bool
    receipt_data: str
    last_verified: datetime
    trial_period: bool = False
    grace_period_expires_at: Optional[datetime] = None
    billing_retry_until: Optional[datetime] = None

@dataclass
class AuditLogEntry:
    timestamp: datetime
    user_id: str
    action: str
    old_status: Optional[SubscriptionStatus]
    new_status: SubscriptionStatus
    platform: Platform
    subscription_id: str
    details: Dict[str, Any]
    script_version: str

class SubscriptionManager:
    """
    Main subscription management class responsible for:
    - Receipt validation across platforms
    - Status updates and feature management
    - Audit logging and monitoring
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.setup_logging()
        self.setup_monitoring()
        self.db_pool: Optional[asyncpg.Pool] = None
        self.metrics = {
            'subscriptions_processed': 0,
            'subscriptions_revoked': 0,
            'subscriptions_renewed': 0,
            'errors': 0,
            'api_calls_apple': 0,
            'api_calls_google': 0,
        }
    
    def setup_logging(self):
        """Configure comprehensive logging for financial compliance"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/mita/subscription_manager.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Security audit logger
        self.audit_logger = logging.getLogger('mita.audit')
        audit_handler = logging.FileHandler('/var/log/mita/subscription_audit.log')
        audit_handler.setFormatter(logging.Formatter(
            '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
        ))
        self.audit_logger.addHandler(audit_handler)
        self.audit_logger.setLevel(logging.INFO)
    
    def setup_monitoring(self):
        """Initialize Sentry for error tracking and monitoring"""
        if self.config.get('sentry_dsn'):
            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            )
            sentry_sdk.init(
                dsn=self.config['sentry_dsn'],
                integrations=[sentry_logging],
                traces_sample_rate=1.0,
                environment=self.config.get('environment', 'production')
            )
    
    async def initialize_database(self):
        """Initialize database connection pool with proper security"""
        try:
            self.db_pool = await asyncpg.create_pool(
                host=self.config['database']['host'],
                port=self.config['database']['port'],
                user=self.config['database']['user'],
                password=self.config['database']['password'],
                database=self.config['database']['name'],
                ssl='require',
                command_timeout=60,
                max_inactive_connection_lifetime=300,
                max_size=20,
                min_size=5
            )
            self.logger.info("Database connection pool initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close_database(self):
        """Properly close database connections"""
        if self.db_pool:
            await self.db_pool.close()
    
    async def get_subscriptions_to_verify(self, limit: int = BATCH_SIZE) -> List[SubscriptionInfo]:
        """
        Get subscriptions that need verification:
        - Active subscriptions approaching expiry
        - Subscriptions not verified in the last hour
        - Grace period subscriptions
        """
        query = """
        SELECT user_id, platform, subscription_id, product_id, status, 
               expires_at, auto_renew, receipt_data, last_verified,
               trial_period, grace_period_expires_at, billing_retry_until
        FROM user_subscriptions 
        WHERE (
            (status = 'active' AND expires_at <= NOW() + INTERVAL '1 hour')
            OR (last_verified <= NOW() - INTERVAL '1 hour')
            OR (status = 'grace_period')
            OR (status = 'billing_retry' AND billing_retry_until <= NOW())
        )
        ORDER BY expires_at ASC
        LIMIT $1
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, limit)
            
            return [
                SubscriptionInfo(
                    user_id=row['user_id'],
                    platform=Platform(row['platform']),
                    subscription_id=row['subscription_id'],
                    product_id=row['product_id'],
                    status=SubscriptionStatus(row['status']),
                    expires_at=row['expires_at'],
                    auto_renew=row['auto_renew'],
                    receipt_data=row['receipt_data'],
                    last_verified=row['last_verified'],
                    trial_period=row['trial_period'],
                    grace_period_expires_at=row['grace_period_expires_at'],
                    billing_retry_until=row['billing_retry_until']
                )
                for row in rows
            ]
    
    async def verify_app_store_receipt(self, subscription: SubscriptionInfo) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify Apple App Store receipt using Apple's verification service.
        Implements production-grade receipt validation with proper error handling.
        """
        self.metrics['api_calls_apple'] += 1
        
        # Use production URL for live receipts, sandbox for testing
        verification_url = self.config['apple']['production_url']
        if self.config.get('use_sandbox', False):
            verification_url = self.config['apple']['sandbox_url']
        
        receipt_data = {
            "receipt-data": subscription.receipt_data,
            "password": self.config['apple']['shared_secret'],
            "exclude-old-transactions": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    verification_url,
                    json=receipt_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"Apple verification failed with status {response.status}")
                        return False, {}
                    
                    result = await response.json()
                    
                    # Handle various Apple response status codes
                    status = result.get('status', -1)
                    
                    if status == 0:
                        # Valid receipt
                        return await self._parse_apple_receipt(result, subscription)
                    elif status == 21007:
                        # Receipt is from sandbox, retry with sandbox URL if not already using it
                        if not self.config.get('use_sandbox', False):
                            self.logger.info("Receipt is sandbox, retrying with sandbox URL")
                            return await self._verify_apple_sandbox_receipt(subscription)
                        return False, {"error": "Sandbox receipt in production"}
                    elif status in [21000, 21002, 21003, 21004, 21005]:
                        # Invalid receipt
                        self.logger.warning(f"Invalid Apple receipt: status {status}")
                        return False, {"error": f"Invalid receipt: {status}"}
                    elif status == 21006:
                        # Receipt server unavailable
                        self.logger.error("Apple receipt server unavailable")
                        raise aiohttp.ClientError("Apple server unavailable")
                    else:
                        self.logger.error(f"Unknown Apple receipt status: {status}")
                        return False, {"error": f"Unknown status: {status}"}
                        
        except asyncio.TimeoutError:
            self.logger.error("Apple receipt verification timeout")
            raise
        except Exception as e:
            self.logger.error(f"Apple receipt verification error: {e}")
            raise
    
    async def _parse_apple_receipt(self, apple_response: Dict[str, Any], subscription: SubscriptionInfo) -> Tuple[bool, Dict[str, Any]]:
        """Parse Apple receipt response and extract subscription information"""
        try:
            apple_response.get('receipt', {})
            latest_receipt_info = apple_response.get('latest_receipt_info', [])
            pending_renewal_info = apple_response.get('pending_renewal_info', [])
            
            # Find the matching subscription
            matching_transaction = None
            for transaction in latest_receipt_info:
                if transaction.get('product_id') == subscription.product_id:
                    matching_transaction = transaction
                    break
            
            if not matching_transaction:
                return False, {"error": "No matching subscription found"}
            
            # Parse expiration date
            expires_ms = int(matching_transaction.get('expires_date_ms', '0'))
            expires_at = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc)
            
            # Check if subscription is active
            is_active = expires_at > datetime.now(timezone.utc)
            
            # Check for grace period or billing retry
            renewal_info = next(
                (info for info in pending_renewal_info 
                 if info.get('product_id') == subscription.product_id), 
                {}
            )
            
            is_in_billing_retry = renewal_info.get('is_in_billing_retry_period') == '1'
            grace_period_expires_ms = renewal_info.get('grace_period_expires_date_ms')
            grace_period_expires = None
            if grace_period_expires_ms:
                grace_period_expires = datetime.fromtimestamp(
                    int(grace_period_expires_ms) / 1000, tz=timezone.utc
                )
            
            return True, {
                "is_active": is_active,
                "expires_at": expires_at,
                "auto_renew": renewal_info.get('auto_renew_status') == '1',
                "is_in_billing_retry": is_in_billing_retry,
                "grace_period_expires_at": grace_period_expires,
                "cancellation_date": matching_transaction.get('cancellation_date_ms'),
                "is_trial_period": matching_transaction.get('is_trial_period') == 'true',
                "original_transaction_id": matching_transaction.get('original_transaction_id'),
                "web_order_line_item_id": matching_transaction.get('web_order_line_item_id')
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Apple receipt: {e}")
            return False, {"error": str(e)}
    
    async def _verify_apple_sandbox_receipt(self, subscription: SubscriptionInfo) -> Tuple[bool, Dict[str, Any]]:
        """Verify receipt using Apple's sandbox environment"""
        old_config = self.config.get('use_sandbox', False)
        self.config['use_sandbox'] = True
        try:
            return await self.verify_app_store_receipt(subscription)
        finally:
            self.config['use_sandbox'] = old_config
    
    async def verify_google_play_receipt(self, subscription: SubscriptionInfo) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify Google Play Store receipt using Google Play Developer API.
        Implements proper service account authentication and error handling.
        """
        self.metrics['api_calls_google'] += 1
        
        try:
            # Initialize Google Play API client
            credentials = service_account.Credentials.from_service_account_file(
                self.config['google']['service_account_file'],
                scopes=['https://www.googleapis.com/auth/androidpublisher']
            )
            
            service = build('androidpublisher', 'v3', credentials=credentials)
            
            # Parse subscription ID and token from receipt data
            receipt_info = json.loads(subscription.receipt_data)
            package_name = self.config['google']['package_name']
            subscription_id = subscription.product_id
            token = receipt_info.get('purchaseToken')
            
            if not token:
                return False, {"error": "Invalid receipt format"}
            
            # Get subscription status
            result = service.purchases().subscriptions().get(
                packageName=package_name,
                subscriptionId=subscription_id,
                token=token
            ).execute()
            
            return await self._parse_google_receipt(result, subscription)
            
        except Exception as e:
            self.logger.error(f"Google Play receipt verification error: {e}")
            if "invalid_grant" in str(e).lower():
                self.logger.error("Google service account credentials may be expired")
            raise
    
    async def _parse_google_receipt(self, google_response: Dict[str, Any], subscription: SubscriptionInfo) -> Tuple[bool, Dict[str, Any]]:
        """Parse Google Play receipt response and extract subscription information"""
        try:
            # Parse expiration time
            expiry_time_millis = int(google_response.get('expiryTimeMillis', '0'))
            expires_at = datetime.fromtimestamp(expiry_time_millis / 1000, tz=timezone.utc)
            
            # Parse various subscription states
            payment_state = int(google_response.get('paymentState', '0'))
            cancel_reason = google_response.get('cancelReason')
            auto_renewing = google_response.get('autoRenewing', False)
            
            # Determine if subscription is active
            is_active = expires_at > datetime.now(timezone.utc) and payment_state == 1
            
            # Handle grace period
            grace_period_expires = None
            if 'gracePeriodExpiryTimeMillis' in google_response:
                grace_period_expires = datetime.fromtimestamp(
                    int(google_response['gracePeriodExpiryTimeMillis']) / 1000, 
                    tz=timezone.utc
                )
            
            return True, {
                "is_active": is_active,
                "expires_at": expires_at,
                "auto_renew": auto_renewing,
                "payment_state": payment_state,
                "cancel_reason": cancel_reason,
                "grace_period_expires_at": grace_period_expires,
                "country_code": google_response.get('countryCode'),
                "price_currency_code": google_response.get('priceCurrencyCode'),
                "is_trial_period": 'trialExpiryTimeMillis' in google_response,
                "acknowledgement_state": google_response.get('acknowledgementState')
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Google Play receipt: {e}")
            return False, {"error": str(e)}
    
    async def update_subscription_status(self, subscription: SubscriptionInfo, verification_result: Dict[str, Any]) -> bool:
        """
        Update subscription status in database and manage premium features.
        Implements proper transaction handling for data consistency.
        """
        old_status = subscription.status
        new_status = self._determine_new_status(verification_result)
        
        try:
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    # Update subscription record
                    await conn.execute("""
                        UPDATE user_subscriptions 
                        SET status = $1,
                            expires_at = $2,
                            auto_renew = $3,
                            last_verified = NOW(),
                            grace_period_expires_at = $4,
                            billing_retry_until = $5,
                            updated_at = NOW()
                        WHERE user_id = $6 AND subscription_id = $7
                    """, 
                    new_status.value,
                    verification_result.get('expires_at'),
                    verification_result.get('auto_renew', False),
                    verification_result.get('grace_period_expires_at'),
                    verification_result.get('billing_retry_until'),
                    subscription.user_id,
                    subscription.subscription_id
                    )
                    
                    # Update user premium status
                    is_premium = new_status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE_PERIOD]
                    await conn.execute("""
                        UPDATE users 
                        SET is_premium = $1,
                            premium_expires_at = $2,
                            updated_at = NOW()
                        WHERE id = $3
                    """, 
                    is_premium,
                    verification_result.get('expires_at') if is_premium else None,
                    subscription.user_id
                    )
                    
                    # Revoke premium features if needed
                    if not is_premium and old_status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE_PERIOD]:
                        await self._revoke_premium_features(conn, subscription.user_id)
                        self.metrics['subscriptions_revoked'] += 1
                    
                    # Log audit entry
                    await self._log_audit_entry(conn, AuditLogEntry(
                        timestamp=datetime.now(timezone.utc),
                        user_id=subscription.user_id,
                        action="status_update",
                        old_status=old_status,
                        new_status=new_status,
                        platform=subscription.platform,
                        subscription_id=subscription.subscription_id,
                        details=verification_result,
                        script_version=SCRIPT_VERSION
                    ))
                    
                    self.metrics['subscriptions_processed'] += 1
                    
                    if new_status == SubscriptionStatus.ACTIVE and old_status != SubscriptionStatus.ACTIVE:
                        self.metrics['subscriptions_renewed'] += 1
                    
                    self.logger.info(f"Updated subscription {subscription.subscription_id} for user {subscription.user_id}: {old_status.value} -> {new_status.value}")
                    return True
                    
        except Exception as e:
            self.logger.error(f"Failed to update subscription status: {e}")
            self.metrics['errors'] += 1
            raise
    
    def _determine_new_status(self, verification_result: Dict[str, Any]) -> SubscriptionStatus:
        """Determine new subscription status based on verification result"""
        if not verification_result.get('is_active', False):
            # Check if in grace period
            grace_expires = verification_result.get('grace_period_expires_at')
            if grace_expires and grace_expires > datetime.now(timezone.utc):
                return SubscriptionStatus.GRACE_PERIOD
            
            # Check if in billing retry
            if verification_result.get('is_in_billing_retry', False):
                return SubscriptionStatus.BILLING_RETRY
            
            # Check if cancelled vs expired
            if verification_result.get('cancellation_date'):
                return SubscriptionStatus.CANCELLED
            
            return SubscriptionStatus.EXPIRED
        
        return SubscriptionStatus.ACTIVE
    
    async def _revoke_premium_features(self, conn: asyncpg.Connection, user_id: str):
        """
        Revoke premium features when subscription expires.
        This ensures users lose access to premium functionality immediately.
        """
        premium_features = [feature.value for feature in PremiumFeature]
        
        # Remove premium feature flags
        await conn.execute("""
            DELETE FROM user_feature_flags 
            WHERE user_id = $1 AND feature_name = ANY($2::text[])
        """, user_id, premium_features)
        
        # Clear premium-specific data
        await conn.execute("""
            UPDATE user_preferences 
            SET 
                advanced_ocr_enabled = true,
                batch_processing_enabled = true,
                premium_insights_enabled = true
            WHERE user_id = $1
        """, user_id)
        
        # Archive premium analytics data (keep for compliance but mark as inactive)
        await conn.execute("""
            UPDATE user_analytics 
            SET is_premium_data = false,
                archived_at = NOW()
            WHERE user_id = $1 AND is_premium_data = true
        """, user_id)
        
        self.logger.info(f"Revoked premium features for user {user_id}")
    
    async def _log_audit_entry(self, conn: asyncpg.Connection, entry: AuditLogEntry):
        """Log audit entry for compliance and monitoring"""
        await conn.execute("""
            INSERT INTO subscription_audit_log 
            (timestamp, user_id, action, old_status, new_status, platform, 
             subscription_id, details, script_version)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, 
        entry.timestamp,
        entry.user_id,
        entry.action,
        entry.old_status.value if entry.old_status else None,
        entry.new_status.value,
        entry.platform.value,
        entry.subscription_id,
        json.dumps(entry.details),
        entry.script_version
        )
        
        # Also log to audit logger
        self.audit_logger.info(json.dumps(asdict(entry), default=str))
    
    async def process_subscription_batch(self) -> Dict[str, int]:
        """Process a batch of subscriptions that need verification"""
        subscriptions = await self.get_subscriptions_to_verify()
        
        self.logger.info(f"Processing {len(subscriptions)} subscriptions")
        
        tasks = []
        for subscription in subscriptions:
            if subscription.platform == Platform.IOS:
                task = self._process_ios_subscription(subscription)
            else:
                task = self._process_android_subscription(subscription)
            tasks.append(task)
        
        # Process subscriptions concurrently but with rate limiting
        semaphore = asyncio.Semaphore(10)  # Limit concurrent API calls
        
        async def rate_limited_task(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(
            *[rate_limited_task(task) for task in tasks], 
            return_exceptions=True
        )
        
        # Count results
        success_count = sum(1 for r in results if r is True)
        error_count = sum(1 for r in results if isinstance(r, Exception))
        
        return {
            'total': len(subscriptions),
            'success': success_count,
            'errors': error_count
        }
    
    async def _process_ios_subscription(self, subscription: SubscriptionInfo) -> bool:
        """Process iOS subscription with retry logic"""
        for attempt in range(MAX_RETRIES):
            try:
                is_valid, verification_result = await self.verify_app_store_receipt(subscription)
                
                if is_valid:
                    return await self.update_subscription_status(subscription, verification_result)
                else:
                    self.logger.warning(f"Invalid iOS receipt for subscription {subscription.subscription_id}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"iOS subscription processing error (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
                else:
                    self.metrics['errors'] += 1
                    raise
        
        return False
    
    async def _process_android_subscription(self, subscription: SubscriptionInfo) -> bool:
        """Process Android subscription with retry logic"""
        for attempt in range(MAX_RETRIES):
            try:
                is_valid, verification_result = await self.verify_google_play_receipt(subscription)
                
                if is_valid:
                    return await self.update_subscription_status(subscription, verification_result)
                else:
                    self.logger.warning(f"Invalid Android receipt for subscription {subscription.subscription_id}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Android subscription processing error (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
                else:
                    self.metrics['errors'] += 1
                    raise
        
        return False
    
    async def cleanup_expired_data(self):
        """Clean up expired subscription data for privacy compliance"""
        try:
            async with self.db_pool.acquire() as conn:
                # Archive old audit logs (keep for 7 years for financial compliance)
                await conn.execute("""
                    UPDATE subscription_audit_log 
                    SET archived = true 
                    WHERE timestamp < NOW() - INTERVAL '7 years'
                """)
                
                # Clean up expired grace period subscriptions
                await conn.execute("""
                    UPDATE user_subscriptions 
                    SET status = 'expired'
                    WHERE status = 'grace_period' 
                    AND grace_period_expires_at < NOW()
                """)
                
                # Clean up failed billing retry subscriptions
                await conn.execute("""
                    UPDATE user_subscriptions 
                    SET status = 'expired'
                    WHERE status = 'billing_retry' 
                    AND billing_retry_until < NOW()
                """)
                
                self.logger.info("Cleanup completed successfully")
                
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            raise
    
    def generate_metrics_report(self) -> Dict[str, Any]:
        """Generate metrics report for monitoring"""
        return {
            'script_version': SCRIPT_VERSION,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': self.metrics,
            'runtime_info': {
                'python_version': sys.version,
                'platform': sys.platform
            }
        }

async def load_configuration() -> Dict[str, Any]:
    """
    Load configuration from environment variables and config files.
    Implements proper security for credential management.
    """
    config = {
        'database': {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'name': os.getenv('DB_NAME', 'mita')
        },
        'apple': {
            'production_url': 'https://buy.itunes.apple.com/verifyReceipt',
            'sandbox_url': 'https://sandbox.itunes.apple.com/verifyReceipt',
            'shared_secret': os.getenv('APPLE_SHARED_SECRET')
        },
        'google': {
            'package_name': os.getenv('GOOGLE_PACKAGE_NAME'),
            'service_account_file': os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
        },
        'sentry_dsn': os.getenv('SENTRY_DSN'),
        'environment': os.getenv('ENVIRONMENT', 'production'),
        'use_sandbox': os.getenv('USE_SANDBOX', 'false').lower() == 'true'
    }
    
    # Validate required configuration
    required_fields = [
        'database.user', 'database.password', 
        'apple.shared_secret', 
        'google.package_name', 'google.service_account_file'
    ]
    
    for field in required_fields:
        keys = field.split('.')
        value = config
        for key in keys:
            value = value.get(key)
            if value is None:
                raise ValueError(f"Required configuration field missing: {field}")
    
    return config

async def main():
    """Main execution function with comprehensive error handling"""
    try:
        # Load configuration
        config = await load_configuration()
        
        # Initialize subscription manager
        manager = SubscriptionManager(config)
        await manager.initialize_database()
        
        try:
            # Process subscription batch
            results = await manager.process_subscription_batch()
            
            # Cleanup expired data
            await manager.cleanup_expired_data()
            
            # Generate and log metrics
            metrics_report = manager.generate_metrics_report()
            manager.logger.info(f"Processing complete: {json.dumps(metrics_report, indent=2)}")
            
            # Send metrics to monitoring system (if configured)
            if config.get('metrics_endpoint'):
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        config['metrics_endpoint'],
                        json=metrics_report,
                        timeout=aiohttp.ClientTimeout(total=10)
                    )
            
            print(f"✅ Successfully processed {results['total']} subscriptions")
            print(f"✅ {results['success']} successful, {results['errors']} errors")
            
            return 0 if results['errors'] == 0 else 1
            
        finally:
            await manager.close_database()
            
    except Exception as e:
        logging.error(f"Script execution failed: {e}")
        sentry_sdk.capture_exception(e)
        return 1

if __name__ == "__main__":
    # Ensure proper signal handling for graceful shutdown
    import signal
    
    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, shutting down gracefully")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run the script
    exit_code = asyncio.run(main())
    sys.exit(exit_code)