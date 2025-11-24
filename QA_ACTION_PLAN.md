# MITA Project - QA Action Plan & Testing Roadmap

**Date:** 2025-11-17
**Status:** 🔴 CRITICAL GAPS IDENTIFIED
**Quality Score:** 7.2/10
**Production Readiness:** ❌ NOT READY

---

## EXECUTIVE SUMMARY

**CRITICAL FINDING:** The MITA backend has excellent security and performance testing infrastructure, but **CRITICAL GAPS** in core business logic testing make it **not production-ready** for a financial application.

### RED FLAGS:
1. ❌ **OCR Processing: 0% test coverage** (PRIMARY USER FEATURE)
2. ❌ **Payment Processing: 40% coverage** (FINANCIAL RISK)
3. ❌ **No mobile integration tests** (CROSS-PLATFORM COMPATIBILITY RISK)
4. ⚠️ **Critical path coverage: 60%** (Target: 95%)

### IMMEDIATE ACTIONS REQUIRED:
- [ ] Halt production deployment until OCR and payment testing complete
- [ ] Implement Priority 1 tests (96 hours / 2 weeks)
- [ ] Raise merge coverage gate from 65% to 70%

---

## CRITICAL TEST IMPLEMENTATION PLAN

### SPRINT 1: OCR Processing Test Suite (40 hours)

**Objective:** Implement comprehensive OCR testing to cover PRIMARY user feature

#### File: `app/tests/test_ocr_comprehensive.py`

```python
"""
OCR Processing Comprehensive Test Suite
Tests receipt image upload, OCR text extraction, transaction creation from receipts
"""

import pytest
import base64
from io import BytesIO
from PIL import Image
from unittest.mock import patch, Mock, AsyncMock

from app.api.ocr.services import OCRService, ReceiptParser
from app.schemas.ocr import ReceiptUploadSchema, OCRResultSchema


class TestReceiptImageUpload:
    """Test receipt image upload and validation"""

    @pytest.fixture
    def mock_receipt_image(self):
        """Create mock receipt image for testing"""
        img = Image.new('RGB', (800, 1200), color='white')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        return buffer.getvalue()

    @pytest.mark.asyncio
    async def test_valid_receipt_upload(self, mock_receipt_image, test_user):
        """Test successful receipt image upload"""
        # Test valid JPEG upload
        result = await upload_receipt(
            user_id=test_user.id,
            image_data=mock_receipt_image,
            image_format='jpeg'
        )

        assert result.status == 'uploaded'
        assert result.receipt_id is not None
        assert result.file_size > 0

    @pytest.mark.asyncio
    async def test_invalid_image_format(self, test_user):
        """Test rejection of invalid image formats"""
        invalid_formats = ['bmp', 'gif', 'tiff', 'webp']

        for format in invalid_formats:
            with pytest.raises(ValidationError) as exc:
                await upload_receipt(
                    user_id=test_user.id,
                    image_data=b'invalid',
                    image_format=format
                )
            assert 'Unsupported image format' in str(exc.value)

    @pytest.mark.asyncio
    async def test_oversized_image_rejection(self, test_user):
        """Test rejection of images exceeding size limit"""
        # Create 20MB image (exceeds 10MB limit)
        large_image = b'0' * (20 * 1024 * 1024)

        with pytest.raises(ValidationError) as exc:
            await upload_receipt(
                user_id=test_user.id,
                image_data=large_image,
                image_format='jpeg'
            )
        assert 'Image too large' in str(exc.value)

    @pytest.mark.asyncio
    async def test_corrupted_image_handling(self, test_user):
        """Test handling of corrupted image data"""
        corrupted_data = b'NOT_AN_IMAGE_FILE'

        with pytest.raises(OCRProcessingError) as exc:
            await upload_receipt(
                user_id=test_user.id,
                image_data=corrupted_data,
                image_format='jpeg'
            )
        assert 'Invalid image data' in str(exc.value)

    @pytest.mark.asyncio
    async def test_concurrent_receipt_uploads(self, test_user, mock_receipt_image):
        """Test concurrent receipt uploads from same user"""
        import asyncio

        # Upload 10 receipts concurrently
        tasks = [
            upload_receipt(
                user_id=test_user.id,
                image_data=mock_receipt_image,
                image_format='jpeg'
            )
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed with unique IDs
        assert len(results) == 10
        receipt_ids = [r.receipt_id for r in results]
        assert len(set(receipt_ids)) == 10  # All unique


class TestOCRTextExtraction:
    """Test OCR text extraction accuracy and performance"""

    @pytest.fixture
    def mock_ocr_response(self):
        """Mock OCR service response"""
        return {
            'text': 'WALMART\\nSubtotal: $45.67\\nTax: $3.65\\nTotal: $49.32\\nDate: 2025-11-15',
            'confidence': 0.92,
            'bounding_boxes': [...]
        }

    @pytest.mark.asyncio
    async def test_ocr_text_extraction_success(self, mock_receipt_image, mock_ocr_response):
        """Test successful OCR text extraction"""
        with patch('app.services.google_vision.detect_text') as mock_ocr:
            mock_ocr.return_value = mock_ocr_response

            result = await extract_text_from_receipt(mock_receipt_image)

            assert result.text is not None
            assert result.confidence >= 0.8
            assert 'WALMART' in result.text

    @pytest.mark.asyncio
    async def test_ocr_low_confidence_handling(self, mock_receipt_image):
        """Test handling of low confidence OCR results"""
        with patch('app.services.google_vision.detect_text') as mock_ocr:
            mock_ocr.return_value = {'text': 'unclear text', 'confidence': 0.45}

            with pytest.raises(OCRConfidenceError) as exc:
                await extract_text_from_receipt(
                    mock_receipt_image,
                    min_confidence=0.75
                )
            assert 'OCR confidence too low' in str(exc.value)

    @pytest.mark.asyncio
    async def test_ocr_performance_benchmark(self, mock_receipt_image):
        """Test OCR processing meets performance requirements"""
        import time

        start_time = time.time()
        result = await extract_text_from_receipt(mock_receipt_image)
        processing_time = time.time() - start_time

        # OCR should complete within 5 seconds
        assert processing_time < 5.0, f"OCR took {processing_time}s, expected <5s"

    @pytest.mark.asyncio
    async def test_ocr_batch_processing(self, mock_receipt_image):
        """Test batch OCR processing for multiple receipts"""
        images = [mock_receipt_image for _ in range(5)]

        results = await batch_extract_text(images)

        assert len(results) == 5
        for result in results:
            assert result.text is not None
            assert result.confidence > 0


class TestReceiptDataParsing:
    """Test parsing structured data from OCR text"""

    @pytest.fixture
    def sample_receipt_text(self):
        """Sample receipt text for parsing tests"""
        return """
        WALMART SUPERCENTER
        123 Main St, Anytown USA

        Subtotal:    $45.67
        Tax:          $3.65
        Total:       $49.32

        Date: 11/15/2025
        Time: 14:32:15
        """

    def test_parse_receipt_amount(self, sample_receipt_text):
        """Test parsing total amount from receipt"""
        parser = ReceiptParser()
        result = parser.parse(sample_receipt_text)

        assert result.total_amount == 49.32
        assert result.subtotal == 45.67
        assert result.tax == 3.65

    def test_parse_receipt_date(self, sample_receipt_text):
        """Test parsing date from receipt"""
        parser = ReceiptParser()
        result = parser.parse(sample_receipt_text)

        assert result.date.year == 2025
        assert result.date.month == 11
        assert result.date.day == 15

    def test_parse_receipt_merchant(self, sample_receipt_text):
        """Test parsing merchant name from receipt"""
        parser = ReceiptParser()
        result = parser.parse(sample_receipt_text)

        assert 'WALMART' in result.merchant_name

    def test_parse_ambiguous_amount(self):
        """Test handling of receipts with multiple total-like amounts"""
        ambiguous_text = """
        Subtotal: $50.00
        Discount: $10.00
        New Total: $40.00
        Grand Total: $40.00
        """

        parser = ReceiptParser()
        result = parser.parse(ambiguous_text)

        # Should pick the last/largest "total"
        assert result.total_amount == 40.00

    def test_parse_missing_required_fields(self):
        """Test error handling when required fields missing"""
        incomplete_text = "Just some random text"

        parser = ReceiptParser()

        with pytest.raises(ReceiptParsingError) as exc:
            parser.parse(incomplete_text)
        assert 'Missing required fields' in str(exc.value)

    def test_parse_multiple_date_formats(self):
        """Test parsing various date formats"""
        date_formats = [
            ("11/15/2025", (2025, 11, 15)),
            ("15-11-2025", (2025, 11, 15)),
            ("2025-11-15", (2025, 11, 15)),
            ("Nov 15, 2025", (2025, 11, 15)),
        ]

        parser = ReceiptParser()

        for date_str, expected_date in date_formats:
            receipt_text = f"Total: $50.00\nDate: {date_str}"
            result = parser.parse(receipt_text)

            assert result.date.year == expected_date[0]
            assert result.date.month == expected_date[1]
            assert result.date.day == expected_date[2]


class TestTransactionCreationFromOCR:
    """Test creating transactions from OCR results"""

    @pytest.fixture
    def parsed_receipt(self):
        """Mock parsed receipt data"""
        return ParsedReceipt(
            merchant_name='WALMART',
            total_amount=49.32,
            subtotal=45.67,
            tax=3.65,
            date=date(2025, 11, 15),
            confidence=0.92
        )

    @pytest.mark.asyncio
    async def test_create_transaction_from_receipt(self, test_user, parsed_receipt):
        """Test automatic transaction creation from receipt"""
        transaction = await create_transaction_from_receipt(
            user_id=test_user.id,
            receipt_data=parsed_receipt
        )

        assert transaction.amount == 49.32
        assert transaction.description == 'WALMART'
        assert transaction.date == date(2025, 11, 15)
        assert transaction.category is not None  # Auto-categorized
        assert transaction.source == 'ocr'

    @pytest.mark.asyncio
    async def test_duplicate_receipt_prevention(self, test_user, parsed_receipt):
        """Test prevention of duplicate transaction from same receipt"""
        # Create first transaction
        tx1 = await create_transaction_from_receipt(
            user_id=test_user.id,
            receipt_data=parsed_receipt
        )

        # Attempt to create duplicate
        with pytest.raises(DuplicateReceiptError) as exc:
            await create_transaction_from_receipt(
                user_id=test_user.id,
                receipt_data=parsed_receipt
            )
        assert 'Receipt already processed' in str(exc.value)

    @pytest.mark.asyncio
    async def test_transaction_categorization_from_merchant(self, test_user, parsed_receipt):
        """Test automatic categorization based on merchant"""
        # Test grocery store categorization
        parsed_receipt.merchant_name = 'WALMART'
        tx = await create_transaction_from_receipt(test_user.id, parsed_receipt)
        assert tx.category == 'groceries'

        # Test restaurant categorization
        parsed_receipt.merchant_name = "McDonald's"
        tx = await create_transaction_from_receipt(test_user.id, parsed_receipt)
        assert tx.category in ['food', 'dining']

    @pytest.mark.asyncio
    async def test_user_confirmation_workflow(self, test_user, parsed_receipt):
        """Test user confirmation before finalizing transaction"""
        # Create pending transaction
        pending_tx = await create_pending_transaction_from_receipt(
            user_id=test_user.id,
            receipt_data=parsed_receipt
        )

        assert pending_tx.status == 'pending_confirmation'
        assert pending_tx.requires_user_confirmation is True

        # User confirms
        confirmed_tx = await confirm_transaction(
            user_id=test_user.id,
            transaction_id=pending_tx.id,
            confirmed=True
        )

        assert confirmed_tx.status == 'confirmed'
        assert confirmed_tx.id == pending_tx.id

    @pytest.mark.asyncio
    async def test_user_edit_before_confirmation(self, test_user, parsed_receipt):
        """Test user editing OCR results before confirmation"""
        pending_tx = await create_pending_transaction_from_receipt(
            user_id=test_user.id,
            receipt_data=parsed_receipt
        )

        # User edits amount and category
        edited_tx = await update_pending_transaction(
            user_id=test_user.id,
            transaction_id=pending_tx.id,
            updates={
                'amount': 50.00,  # User corrects OCR error
                'category': 'household'  # User changes category
            }
        )

        assert edited_tx.amount == 50.00
        assert edited_tx.category == 'household'
        assert edited_tx.status == 'pending_confirmation'


class TestOCRErrorHandling:
    """Test OCR error scenarios and recovery"""

    @pytest.mark.asyncio
    async def test_google_vision_api_failure(self, mock_receipt_image):
        """Test handling of Google Vision API failures"""
        with patch('app.services.google_vision.detect_text') as mock_ocr:
            mock_ocr.side_effect = Exception("API quota exceeded")

            with pytest.raises(OCRServiceError) as exc:
                await extract_text_from_receipt(mock_receipt_image)
            assert 'OCR service unavailable' in str(exc.value)

    @pytest.mark.asyncio
    async def test_ocr_retry_mechanism(self, mock_receipt_image):
        """Test automatic retry on transient OCR failures"""
        with patch('app.services.google_vision.detect_text') as mock_ocr:
            # Fail twice, succeed on third attempt
            mock_ocr.side_effect = [
                Exception("Temporary error"),
                Exception("Temporary error"),
                {'text': 'Success', 'confidence': 0.9}
            ]

            result = await extract_text_from_receipt(
                mock_receipt_image,
                max_retries=3
            )

            assert result.text == 'Success'
            assert mock_ocr.call_count == 3

    @pytest.mark.asyncio
    async def test_fallback_to_manual_entry(self, test_user, mock_receipt_image):
        """Test fallback to manual transaction entry on OCR failure"""
        with patch('app.services.google_vision.detect_text') as mock_ocr:
            mock_ocr.side_effect = Exception("Permanent failure")

            # OCR fails, but user can still create transaction manually
            manual_tx = await create_transaction_manual_fallback(
                user_id=test_user.id,
                receipt_id='failed_ocr_123',
                manual_data={
                    'amount': 50.00,
                    'merchant': 'Unknown Store',
                    'date': date.today()
                }
            )

            assert manual_tx.source == 'manual_from_failed_ocr'
            assert manual_tx.amount == 50.00


class TestOCRPerformanceUnderLoad:
    """Test OCR system performance under concurrent load"""

    @pytest.mark.asyncio
    async def test_concurrent_ocr_processing(self, mock_receipt_image):
        """Test OCR system handles concurrent requests"""
        import asyncio

        # Simulate 20 users uploading receipts simultaneously
        tasks = [
            extract_text_from_receipt(mock_receipt_image)
            for _ in range(20)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete without errors
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) >= 18  # Allow for 10% failure rate under load

    @pytest.mark.asyncio
    async def test_ocr_queue_management(self, mock_receipt_image):
        """Test OCR job queue prevents system overload"""
        # Submit 100 OCR jobs rapidly
        for i in range(100):
            await queue_ocr_job(
                receipt_id=f'receipt_{i}',
                image_data=mock_receipt_image
            )

        # Check queue size is limited
        queue_size = await get_ocr_queue_size()
        assert queue_size <= 50  # Max queue size enforced

    @pytest.mark.asyncio
    async def test_ocr_timeout_handling(self, mock_receipt_image):
        """Test OCR processing timeout after max duration"""
        with patch('app.services.google_vision.detect_text') as mock_ocr:
            # Simulate slow OCR processing
            async def slow_ocr(*args, **kwargs):
                await asyncio.sleep(10)  # Exceeds 5s timeout
                return {'text': 'too slow', 'confidence': 0.9}

            mock_ocr.side_effect = slow_ocr

            with pytest.raises(OCRTimeoutError) as exc:
                await extract_text_from_receipt(
                    mock_receipt_image,
                    timeout=5
                )
            assert 'OCR processing timeout' in str(exc.value)


# Estimated test count: ~35 test functions
# Estimated LOC: ~800 lines
# Coverage target: 90%+ for OCR module
```

**Implementation Schedule:**
- Day 1-2: Receipt upload validation tests (8 hours)
- Day 3-4: OCR text extraction tests (8 hours)
- Day 5-6: Receipt parsing tests (8 hours)
- Day 7-8: Transaction creation tests (8 hours)
- Day 9-10: Error handling and performance tests (8 hours)

**Success Criteria:**
- [ ] 35+ test functions implemented
- [ ] OCR module coverage >= 90%
- [ ] All critical OCR paths tested
- [ ] Performance benchmarks established
- [ ] Error scenarios validated

---

### SPRINT 2: Payment Processing Test Suite (32 hours)

**Objective:** Eliminate financial risk by comprehensive payment testing

#### File: `app/tests/test_iap_payment_comprehensive.py`

```python
"""
In-App Purchase Payment Processing Comprehensive Test Suite
Tests Apple App Store and Google Play Store payment validation,
webhook security, subscription flows, and refund handling.
"""

import pytest
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock, AsyncMock

from app.api.iap.services import (
    validate_receipt,
    process_webhook,
    handle_subscription_renewal,
    process_refund
)
from app.schemas.iap import (
    AppleReceiptSchema,
    GoogleReceiptSchema,
    WebhookPayloadSchema
)


class TestAppleReceiptValidation:
    """Test Apple App Store receipt validation"""

    @pytest.fixture
    def apple_receipt_response(self):
        """Mock Apple receipt validation response"""
        return {
            'status': 0,
            'receipt': {
                'bundle_id': 'com.mita.finance',
                'application_version': '1.0.0'
            },
            'latest_receipt_info': [{
                'product_id': 'com.mita.premium.yearly',
                'transaction_id': 'APPLE_TX_123456',
                'original_transaction_id': 'APPLE_TX_ORIGINAL_123',
                'purchase_date_ms': '1700000000000',
                'expires_date_ms': '1731536000000',  # Future date
                'is_trial_period': 'false',
                'is_in_intro_offer_period': 'false'
            }],
            'pending_renewal_info': [{
                'auto_renew_status': '1',
                'product_id': 'com.mita.premium.yearly'
            }]
        }

    @pytest.mark.asyncio
    async def test_valid_apple_receipt_validation(
        self,
        test_user,
        apple_receipt_response
    ):
        """Test successful Apple receipt validation"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = apple_receipt_response
            mock_post.return_value = mock_response

            result = await validate_receipt(
                user_id=test_user.id,
                receipt_data='BASE64_ENCODED_RECEIPT',
                platform='ios'
            )

            assert result['status'] == 'valid'
            assert result['platform'] == 'ios'
            assert result['product_id'] == 'com.mita.premium.yearly'
            assert result['subscription_active'] is True
            assert isinstance(result['expires_at'], datetime)

    @pytest.mark.asyncio
    async def test_expired_apple_subscription(self, test_user):
        """Test handling of expired Apple subscriptions"""
        expired_response = {
            'status': 0,
            'latest_receipt_info': [{
                'product_id': 'com.mita.premium.monthly',
                'expires_date_ms': '1600000000000'  # Past date
            }]
        }

        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = expired_response
            mock_post.return_value = mock_response

            result = await validate_receipt(
                user_id=test_user.id,
                receipt_data='EXPIRED_RECEIPT',
                platform='ios'
            )

            assert result['status'] == 'expired'
            assert result['subscription_active'] is False

    @pytest.mark.asyncio
    async def test_apple_receipt_validation_error_codes(self, test_user):
        """Test handling of Apple receipt validation error codes"""
        error_codes = [
            (21000, 'Malformed receipt'),
            (21002, 'Receipt data invalid'),
            (21003, 'Receipt authentication failed'),
            (21005, 'Receipt server unavailable'),
            (21007, 'Sandbox receipt in production'),
            (21008, 'Production receipt in sandbox')
        ]

        for status_code, expected_error in error_codes:
            with patch('httpx.AsyncClient.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {'status': status_code}
                mock_post.return_value = mock_response

                with pytest.raises(ReceiptValidationError) as exc:
                    await validate_receipt(
                        user_id=test_user.id,
                        receipt_data='INVALID_RECEIPT',
                        platform='ios'
                    )
                assert expected_error.lower() in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_apple_trial_period_detection(self, test_user):
        """Test detection of trial period subscriptions"""
        trial_response = {
            'status': 0,
            'latest_receipt_info': [{
                'product_id': 'com.mita.premium.monthly',
                'expires_date_ms': '1731536000000',
                'is_trial_period': 'true'
            }]
        }

        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = trial_response
            mock_post.return_value = mock_response

            result = await validate_receipt(
                user_id=test_user.id,
                receipt_data='TRIAL_RECEIPT',
                platform='ios'
            )

            assert result['is_trial'] is True
            assert result['subscription_active'] is True


class TestGooglePlayReceiptValidation:
    """Test Google Play Store receipt validation"""

    @pytest.fixture
    def google_purchase_response(self):
        """Mock Google Play purchase validation response"""
        return {
            'kind': 'androidpublisher#subscriptionPurchase',
            'startTimeMillis': '1700000000000',
            'expiryTimeMillis': '1731536000000',
            'autoRenewing': True,
            'priceCurrencyCode': 'USD',
            'priceAmountMicros': '49990000',  # $49.99
            'countryCode': 'US',
            'developerPayload': '',
            'paymentState': 1,  # Payment received
            'orderId': 'GPA.1234-5678-9012-34567'
        }

    @pytest.mark.asyncio
    async def test_valid_google_receipt_validation(
        self,
        test_user,
        google_purchase_response
    ):
        """Test successful Google Play receipt validation"""
        with patch('google.oauth2.service_account.Credentials') as mock_creds, \
             patch('googleapiclient.discovery.build') as mock_build:

            # Mock Google API client
            mock_service = Mock()
            mock_purchases = Mock()
            mock_get = Mock()
            mock_get.execute.return_value = google_purchase_response

            mock_purchases.get.return_value = mock_get
            mock_service.purchases.return_value = mock_purchases
            mock_build.return_value = mock_service

            result = await validate_receipt(
                user_id=test_user.id,
                receipt_data='GOOGLE_PURCHASE_TOKEN',
                platform='android',
                product_id='com.mita.premium.yearly'
            )

            assert result['status'] == 'valid'
            assert result['platform'] == 'android'
            assert result['subscription_active'] is True
            assert result['auto_renewing'] is True

    @pytest.mark.asyncio
    async def test_google_payment_pending(self, test_user):
        """Test handling of pending Google payments"""
        pending_response = {
            'paymentState': 0,  # Payment pending
            'expiryTimeMillis': '1731536000000'
        }

        with patch('google.oauth2.service_account.Credentials'), \
             patch('googleapiclient.discovery.build') as mock_build:

            mock_service = Mock()
            mock_purchases = Mock()
            mock_get = Mock()
            mock_get.execute.return_value = pending_response

            mock_purchases.get.return_value = mock_get
            mock_service.purchases.return_value = mock_purchases
            mock_build.return_value = mock_service

            result = await validate_receipt(
                user_id=test_user.id,
                receipt_data='PENDING_TOKEN',
                platform='android',
                product_id='com.mita.premium.monthly'
            )

            assert result['status'] == 'pending'
            assert result['payment_received'] is False

    @pytest.mark.asyncio
    async def test_google_subscription_cancelled(self, test_user):
        """Test handling of cancelled Google subscriptions"""
        cancelled_response = {
            'expiryTimeMillis': '1731536000000',
            'autoRenewing': False,
            'cancelReason': 0,  # User cancelled
            'paymentState': 1
        }

        with patch('google.oauth2.service_account.Credentials'), \
             patch('googleapiclient.discovery.build') as mock_build:

            mock_service = Mock()
            mock_purchases = Mock()
            mock_get = Mock()
            mock_get.execute.return_value = cancelled_response

            mock_purchases.get.return_value = mock_get
            mock_service.purchases.return_value = mock_purchases
            mock_build.return_value = mock_service

            result = await validate_receipt(
                user_id=test_user.id,
                receipt_data='CANCELLED_TOKEN',
                platform='android',
                product_id='com.mita.premium.monthly'
            )

            assert result['auto_renewing'] is False
            assert result['cancel_reason'] == 'user_cancelled'


class TestWebhookSecurity:
    """Test webhook security and signature verification"""

    def test_apple_webhook_signature_verification(self):
        """Test Apple App Store webhook signature verification"""
        # Apple sends JWS (JSON Web Signature) for webhooks
        payload = {
            'signedPayload': 'HEADER.PAYLOAD.SIGNATURE'
        }

        # Mock JWS verification
        with patch('jwt.decode') as mock_decode:
            mock_decode.return_value = {
                'notificationType': 'DID_RENEW',
                'data': {
                    'bundleId': 'com.mita.finance',
                    'productId': 'com.mita.premium.yearly'
                }
            }

            result = verify_apple_webhook(payload)

            assert result.is_valid is True
            assert result.notification_type == 'DID_RENEW'

    def test_apple_webhook_invalid_signature(self):
        """Test rejection of Apple webhooks with invalid signatures"""
        payload = {
            'signedPayload': 'TAMPERED.PAYLOAD.INVALID_SIG'
        }

        with patch('jwt.decode') as mock_decode:
            mock_decode.side_effect = jwt.InvalidSignatureError()

            with pytest.raises(WebhookSecurityError) as exc:
                verify_apple_webhook(payload)
            assert 'Invalid webhook signature' in str(exc.value)

    def test_google_webhook_signature_verification(self):
        """Test Google Play webhook signature verification"""
        # Google sends base64-encoded signature
        message_data = json.dumps({
            'subscriptionNotification': {
                'version': '1.0',
                'notificationType': 2,  # SUBSCRIPTION_RENEWED
                'purchaseToken': 'GOOGLE_TOKEN_123'
            }
        })

        # Create HMAC signature
        secret = 'WEBHOOK_SECRET_KEY'
        signature = hmac.new(
            secret.encode(),
            message_data.encode(),
            hashlib.sha256
        ).hexdigest()

        result = verify_google_webhook(
            message=message_data,
            signature=signature,
            secret=secret
        )

        assert result.is_valid is True
        assert result.notification_type == 'SUBSCRIPTION_RENEWED'

    def test_google_webhook_replay_attack_prevention(self):
        """Test prevention of webhook replay attacks"""
        timestamp = datetime.utcnow() - timedelta(minutes=10)  # Old timestamp

        message_data = json.dumps({
            'timestamp': timestamp.isoformat(),
            'subscriptionNotification': {
                'notificationType': 2
            }
        })

        signature = hmac.new(
            b'SECRET',
            message_data.encode(),
            hashlib.sha256
        ).hexdigest()

        with pytest.raises(WebhookReplayError) as exc:
            verify_google_webhook(
                message=message_data,
                signature=signature,
                secret='SECRET',
                max_age_minutes=5
            )
        assert 'Webhook too old' in str(exc.value)


class TestDuplicateTransactionPrevention:
    """Test prevention of duplicate payment transactions"""

    @pytest.mark.asyncio
    async def test_duplicate_apple_transaction_detection(self, test_user):
        """Test detection of duplicate Apple transactions"""
        transaction_id = 'APPLE_TX_UNIQUE_123'

        # Process transaction first time
        tx1 = await process_apple_purchase(
            user_id=test_user.id,
            transaction_id=transaction_id,
            product_id='com.mita.premium.monthly',
            receipt_data='RECEIPT_DATA'
        )

        assert tx1.id is not None

        # Attempt duplicate processing
        tx2 = await process_apple_purchase(
            user_id=test_user.id,
            transaction_id=transaction_id,  # Same transaction ID
            product_id='com.mita.premium.monthly',
            receipt_data='RECEIPT_DATA'
        )

        # Should return existing transaction, not create duplicate
        assert tx2.id == tx1.id
        assert tx2.is_duplicate is True

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_prevention(self, test_user):
        """Test duplicate prevention under concurrent requests"""
        import asyncio

        transaction_id = 'CONCURRENT_TX_789'

        # Simulate 10 concurrent webhook notifications for same transaction
        tasks = [
            process_apple_purchase(
                user_id=test_user.id,
                transaction_id=transaction_id,
                product_id='com.mita.premium.yearly',
                receipt_data='CONCURRENT_RECEIPT'
            )
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # All should return same transaction ID (no duplicates created)
        transaction_ids = [r.id for r in results]
        assert len(set(transaction_ids)) == 1


class TestSubscriptionRenewalFlow:
    """Test subscription renewal handling"""

    @pytest.mark.asyncio
    async def test_successful_subscription_renewal(self, test_user):
        """Test successful automatic subscription renewal"""
        # User has existing subscription expiring soon
        existing_sub = await create_subscription(
            user_id=test_user.id,
            product_id='com.mita.premium.monthly',
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )

        # Simulate renewal webhook
        renewal_result = await handle_subscription_renewal(
            user_id=test_user.id,
            subscription_id=existing_sub.id,
            new_expiry=datetime.utcnow() + timedelta(days=30)
        )

        assert renewal_result.renewed is True
        assert renewal_result.new_expiry_date > existing_sub.expires_at
        assert renewal_result.subscription_id == existing_sub.id

    @pytest.mark.asyncio
    async def test_renewal_failure_grace_period(self, test_user):
        """Test grace period handling on renewal failure"""
        existing_sub = await create_subscription(
            user_id=test_user.id,
            product_id='com.mita.premium.yearly',
            expires_at=datetime.utcnow()
        )

        # Renewal fails (payment declined)
        result = await handle_subscription_renewal_failure(
            user_id=test_user.id,
            subscription_id=existing_sub.id,
            failure_reason='payment_declined'
        )

        # Should enter grace period (e.g., 7 days)
        assert result.status == 'grace_period'
        assert result.grace_period_end > datetime.utcnow()
        assert result.features_available is True  # Still has access during grace

    @pytest.mark.asyncio
    async def test_subscription_expiry_after_grace_period(self, test_user):
        """Test subscription expiry after grace period ends"""
        expired_sub = await create_subscription(
            user_id=test_user.id,
            product_id='com.mita.premium.monthly',
            expires_at=datetime.utcnow() - timedelta(days=8),  # Past grace period
            grace_period_end=datetime.utcnow() - timedelta(days=1)
        )

        # Check subscription status
        status = await get_subscription_status(
            user_id=test_user.id,
            subscription_id=expired_sub.id
        )

        assert status.is_active is False
        assert status.features_available is False
        assert status.status == 'expired'


class TestRefundHandling:
    """Test refund processing and user account updates"""

    @pytest.mark.asyncio
    async def test_full_refund_processing(self, test_user):
        """Test processing of full subscription refund"""
        # User has active subscription
        subscription = await create_subscription(
            user_id=test_user.id,
            product_id='com.mita.premium.yearly',
            amount_paid=Decimal('49.99'),
            expires_at=datetime.utcnow() + timedelta(days=300)
        )

        # Process refund
        refund_result = await process_refund(
            user_id=test_user.id,
            subscription_id=subscription.id,
            refund_amount=Decimal('49.99'),
            refund_type='full',
            reason='user_requested'
        )

        assert refund_result.refunded is True
        assert refund_result.refund_amount == Decimal('49.99')

        # Subscription should be immediately cancelled
        updated_sub = await get_subscription(subscription.id)
        assert updated_sub.is_active is False
        assert updated_sub.refunded is True

    @pytest.mark.asyncio
    async def test_partial_refund_processing(self, test_user):
        """Test processing of partial subscription refund"""
        subscription = await create_subscription(
            user_id=test_user.id,
            product_id='com.mita.premium.yearly',
            amount_paid=Decimal('49.99'),
            expires_at=datetime.utcnow() + timedelta(days=300)
        )

        # Partial refund (pro-rated for unused time)
        refund_result = await process_refund(
            user_id=test_user.id,
            subscription_id=subscription.id,
            refund_amount=Decimal('25.00'),
            refund_type='partial',
            reason='pro_rated'
        )

        assert refund_result.refunded is True
        assert refund_result.refund_amount == Decimal('25.00')

        # Subscription should still be active until original expiry
        updated_sub = await get_subscription(subscription.id)
        assert updated_sub.is_active is True  # Still active
        assert updated_sub.partially_refunded is True

    @pytest.mark.asyncio
    async def test_refund_duplicate_prevention(self, test_user):
        """Test prevention of duplicate refund processing"""
        subscription = await create_subscription(
            user_id=test_user.id,
            product_id='com.mita.premium.monthly',
            amount_paid=Decimal('9.99')
        )

        # Process refund first time
        refund1 = await process_refund(
            user_id=test_user.id,
            subscription_id=subscription.id,
            refund_amount=Decimal('9.99'),
            refund_type='full'
        )

        # Attempt duplicate refund
        with pytest.raises(RefundAlreadyProcessedError) as exc:
            await process_refund(
                user_id=test_user.id,
                subscription_id=subscription.id,
                refund_amount=Decimal('9.99'),
                refund_type='full'
            )
        assert 'Refund already processed' in str(exc.value)


class TestPaymentPerformance:
    """Test payment processing performance requirements"""

    @pytest.mark.asyncio
    async def test_receipt_validation_performance(self, test_user):
        """Test receipt validation meets performance SLA"""
        import time

        start_time = time.time()

        await validate_receipt(
            user_id=test_user.id,
            receipt_data='PERFORMANCE_TEST_RECEIPT',
            platform='ios'
        )

        processing_time = time.time() - start_time

        # Receipt validation should complete within 3 seconds
        assert processing_time < 3.0, f"Validation took {processing_time}s, expected <3s"

    @pytest.mark.asyncio
    async def test_webhook_processing_performance(self):
        """Test webhook processing meets performance SLA"""
        import time

        webhook_payload = {
            'signedPayload': 'MOCK_SIGNED_PAYLOAD'
        }

        start_time = time.time()

        await process_webhook(
            platform='ios',
            payload=webhook_payload
        )

        processing_time = time.time() - start_time

        # Webhook processing should complete within 2 seconds
        assert processing_time < 2.0, f"Webhook took {processing_time}s, expected <2s"


# Estimated test count: 40+ test functions
# Estimated LOC: ~1000 lines
# Coverage target: 90%+ for IAP module
```

**Implementation Schedule:**
- Day 1-2: Apple receipt validation tests (8 hours)
- Day 3-4: Google Play validation tests (8 hours)
- Day 5: Webhook security tests (4 hours)
- Day 6: Duplicate prevention tests (4 hours)
- Day 7: Subscription renewal tests (4 hours)
- Day 8: Refund handling tests (4 hours)

**Success Criteria:**
- [ ] 40+ test functions implemented
- [ ] IAP module coverage >= 90%
- [ ] Payment security validated
- [ ] Webhook replay attacks prevented
- [ ] Duplicate transactions prevented
- [ ] Refund flows tested

---

### SPRINT 3: Transaction Integrity Tests (24 hours)

**Objective:** Prevent data corruption and ensure transaction consistency

#### File: `app/tests/test_transaction_integrity.py`

```python
"""
Transaction Integrity and Consistency Tests
Tests concurrent operations, deduplication, rollback, and data integrity
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, date
from uuid import uuid4
from unittest.mock import patch, AsyncMock

from app.api.transactions.services import (
    create_transaction,
    bulk_create_transactions,
    rollback_transaction
)
from app.db.models import Transaction, Budget


class TestConcurrentTransactionCreation:
    """Test transaction creation under concurrent load"""

    @pytest.mark.asyncio
    async def test_concurrent_transaction_creation_different_users(self):
        """Test concurrent transactions from different users"""
        # Create 10 test users
        users = [await create_test_user(email=f'user{i}@test.com') for i in range(10)]

        # Create transactions concurrently
        tasks = [
            create_transaction(
                user_id=user.id,
                amount=Decimal('50.00'),
                description=f'Transaction for user {i}',
                category='food',
                date=date.today()
            )
            for i, user in enumerate(users)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed with unique IDs
        assert len(results) == 10
        transaction_ids = [r.id for r in results]
        assert len(set(transaction_ids)) == 10

    @pytest.mark.asyncio
    async def test_concurrent_transaction_creation_same_user(self, test_user):
        """Test concurrent transactions from same user"""
        # Create 20 transactions concurrently for same user
        tasks = [
            create_transaction(
                user_id=test_user.id,
                amount=Decimal(f'{10 + i}.99'),
                description=f'Concurrent transaction {i}',
                category='shopping',
                date=date.today()
            )
            for i in range(20)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (transactions are independent)
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 20

        # Budget should be updated correctly (sum of all)
        budget = await get_user_budget(test_user.id)
        expected_total = sum(Decimal(f'{10 + i}.99') for i in range(20))
        assert budget.total_spent == expected_total

    @pytest.mark.asyncio
    async def test_race_condition_budget_update(self, test_user):
        """Test race condition in budget updates"""
        # Initial budget
        budget = await get_user_budget(test_user.id)
        initial_spent = budget.total_spent

        # Create 50 transactions rapidly
        tasks = [
            create_transaction(
                user_id=test_user.id,
                amount=Decimal('1.00'),
                description=f'Race test {i}',
                category='test',
                date=date.today()
            )
            for i in range(50)
        ]

        await asyncio.gather(*tasks)

        # Budget should reflect all 50 transactions
        updated_budget = await get_user_budget(test_user.id)
        assert updated_budget.total_spent == initial_spent + Decimal('50.00')


class TestDuplicateTransactionPrevention:
    """Test prevention of duplicate transaction entries"""

    @pytest.mark.asyncio
    async def test_idempotency_key_duplicate_prevention(self, test_user):
        """Test duplicate prevention using idempotency keys"""
        idempotency_key = str(uuid4())

        transaction_data = {
            'user_id': test_user.id,
            'amount': Decimal('99.99'),
            'description': 'Idempotency test',
            'category': 'test',
            'date': date.today()
        }

        # Create transaction with idempotency key
        tx1 = await create_transaction(
            **transaction_data,
            idempotency_key=idempotency_key
        )

        # Attempt duplicate with same idempotency key
        tx2 = await create_transaction(
            **transaction_data,
            idempotency_key=idempotency_key
        )

        # Should return same transaction
        assert tx1.id == tx2.id

        # Verify only one transaction in database
        user_transactions = await get_user_transactions(test_user.id)
        matching = [t for t in user_transactions if t.description == 'Idempotency test']
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_exact_duplicate_detection(self, test_user):
        """Test detection of exact duplicate transactions"""
        transaction_data = {
            'user_id': test_user.id,
            'amount': Decimal('45.67'),
            'description': 'Duplicate test transaction',
            'merchant': 'Test Merchant',
            'category': 'shopping',
            'date': date.today()
        }

        # Create first transaction
        tx1 = await create_transaction(**transaction_data)

        # Attempt exact duplicate (within 1 minute)
        with pytest.raises(DuplicateTransactionError) as exc:
            await create_transaction(**transaction_data)

        assert 'Possible duplicate transaction' in str(exc.value)
        assert 'same amount, merchant, and time' in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_similar_transaction_warning(self, test_user):
        """Test warning for similar (but not exact duplicate) transactions"""
        # Create first transaction
        tx1 = await create_transaction(
            user_id=test_user.id,
            amount=Decimal('50.00'),
            description='Coffee shop',
            date=date.today()
        )

        # Create similar transaction (same amount, slightly different description)
        tx2 = await create_transaction(
            user_id=test_user.id,
            amount=Decimal('50.00'),
            description='Coffee shop - different location',
            date=date.today(),
            allow_similar=True  # Explicitly allow similar transactions
        )

        # Should succeed but flag as potentially similar
        assert tx2.id != tx1.id
        assert tx2.similarity_warning is True


class TestTransactionRollback:
    """Test transaction rollback scenarios"""

    @pytest.mark.asyncio
    async def test_transaction_rollback_reverses_budget(self, test_user):
        """Test that rolling back transaction reverses budget update"""
        # Get initial budget
        initial_budget = await get_user_budget(test_user.id)
        initial_spent = initial_budget.total_spent

        # Create transaction
        transaction = await create_transaction(
            user_id=test_user.id,
            amount=Decimal('100.00'),
            description='Rollback test',
            category='test',
            date=date.today()
        )

        # Verify budget updated
        updated_budget = await get_user_budget(test_user.id)
        assert updated_budget.total_spent == initial_spent + Decimal('100.00')

        # Rollback transaction
        await rollback_transaction(
            transaction_id=transaction.id,
            reason='Test rollback'
        )

        # Budget should be reverted
        final_budget = await get_user_budget(test_user.id)
        assert final_budget.total_spent == initial_spent

    @pytest.mark.asyncio
    async def test_rollback_reverses_goal_progress(self, test_user):
        """Test rollback reverses goal progress updates"""
        # Create savings goal
        goal = await create_goal(
            user_id=test_user.id,
            title='Emergency Fund',
            target_amount=Decimal('5000.00'),
            saved_amount=Decimal('1000.00')
        )

        # Create transaction linked to goal
        transaction = await create_transaction(
            user_id=test_user.id,
            amount=Decimal('500.00'),
            description='Savings deposit',
            category='savings',
            goal_id=goal.id,
            date=date.today()
        )

        # Goal progress should update
        updated_goal = await get_goal(goal.id)
        assert updated_goal.saved_amount == Decimal('1500.00')

        # Rollback transaction
        await rollback_transaction(transaction.id)

        # Goal progress should revert
        reverted_goal = await get_goal(goal.id)
        assert reverted_goal.saved_amount == Decimal('1000.00')

    @pytest.mark.asyncio
    async def test_rollback_cascade_to_related_entities(self, test_user):
        """Test rollback cascades to all related entities"""
        transaction = await create_transaction(
            user_id=test_user.id,
            amount=Decimal('75.00'),
            description='Cascade test',
            category='food',
            date=date.today()
        )

        # Create related entities (tags, notes, attachments)
        await add_transaction_tag(transaction.id, 'business_expense')
        await add_transaction_note(transaction.id, 'Client lunch')

        # Rollback transaction
        await rollback_transaction(transaction.id)

        # All related entities should be removed
        tags = await get_transaction_tags(transaction.id)
        notes = await get_transaction_notes(transaction.id)

        assert len(tags) == 0
        assert len(notes) == 0


class TestBulkTransactionImport:
    """Test bulk transaction import scenarios"""

    @pytest.mark.asyncio
    async def test_bulk_import_csv_transactions(self, test_user):
        """Test importing transactions from CSV"""
        csv_data = [
            {
                'date': '2025-11-01',
                'amount': '45.67',
                'description': 'Grocery Store',
                'category': 'groceries'
            },
            {
                'date': '2025-11-02',
                'amount': '12.99',
                'description': 'Coffee Shop',
                'category': 'food'
            },
            {
                'date': '2025-11-03',
                'amount': '89.50',
                'description': 'Gas Station',
                'category': 'transport'
            }
        ]

        result = await bulk_create_transactions(
            user_id=test_user.id,
            transactions=csv_data,
            source='csv_import'
        )

        assert result.created_count == 3
        assert result.failed_count == 0
        assert len(result.created_transaction_ids) == 3

    @pytest.mark.asyncio
    async def test_bulk_import_with_validation_errors(self, test_user):
        """Test bulk import handles validation errors gracefully"""
        csv_data = [
            {'date': '2025-11-01', 'amount': '50.00', 'category': 'valid'},
            {'date': 'INVALID_DATE', 'amount': '25.00', 'category': 'invalid'},
            {'date': '2025-11-03', 'amount': '-100.00', 'category': 'negative'},  # Invalid
            {'date': '2025-11-04', 'amount': '30.00', 'category': 'valid'}
        ]

        result = await bulk_create_transactions(
            user_id=test_user.id,
            transactions=csv_data,
            skip_invalid=True
        )

        # Should create 2 valid, skip 2 invalid
        assert result.created_count == 2
        assert result.failed_count == 2
        assert len(result.errors) == 2

    @pytest.mark.asyncio
    async def test_bulk_import_atomic_rollback_on_error(self, test_user):
        """Test bulk import rolls back all if any fail (atomic mode)"""
        initial_tx_count = await count_user_transactions(test_user.id)

        csv_data = [
            {'date': '2025-11-01', 'amount': '50.00', 'category': 'food'},
            {'date': '2025-11-02', 'amount': 'INVALID', 'category': 'food'},  # Will fail
        ]

        with pytest.raises(BulkImportError):
            await bulk_create_transactions(
                user_id=test_user.id,
                transactions=csv_data,
                atomic=True  # All-or-nothing mode
            )

        # No transactions should be created (atomic rollback)
        final_tx_count = await count_user_transactions(test_user.id)
        assert final_tx_count == initial_tx_count


class TestTransactionDataIntegrity:
    """Test transaction data integrity constraints"""

    @pytest.mark.asyncio
    async def test_amount_precision_preservation(self, test_user):
        """Test that transaction amounts preserve decimal precision"""
        amounts = [
            Decimal('0.01'),  # Minimum
            Decimal('123.45'),
            Decimal('9999.99'),
            Decimal('10000.00')
        ]

        for amount in amounts:
            transaction = await create_transaction(
                user_id=test_user.id,
                amount=amount,
                description=f'Precision test {amount}',
                category='test',
                date=date.today()
            )

            # Retrieve and verify precision
            retrieved = await get_transaction(transaction.id)
            assert retrieved.amount == amount
            assert type(retrieved.amount) is Decimal

    @pytest.mark.asyncio
    async def test_category_consistency_validation(self, test_user):
        """Test category validation against allowed categories"""
        valid_categories = ['food', 'transport', 'entertainment', 'shopping']

        for category in valid_categories:
            transaction = await create_transaction(
                user_id=test_user.id,
                amount=Decimal('50.00'),
                category=category,
                date=date.today()
            )
            assert transaction.category == category

        # Invalid category should be rejected or auto-corrected
        with pytest.raises(ValidationError):
            await create_transaction(
                user_id=test_user.id,
                amount=Decimal('50.00'),
                category='invalid_category_xyz',
                date=date.today()
            )

    @pytest.mark.asyncio
    async def test_date_range_validation(self, test_user):
        """Test transaction date validation"""
        from datetime import timedelta

        # Future date should be rejected
        future_date = date.today() + timedelta(days=30)

        with pytest.raises(ValidationError) as exc:
            await create_transaction(
                user_id=test_user.id,
                amount=Decimal('50.00'),
                date=future_date
            )
        assert 'future' in str(exc.value).lower()

        # Very old date should warn or reject
        ancient_date = date(year=1900, month=1, day=1)

        with pytest.raises(ValidationError) as exc:
            await create_transaction(
                user_id=test_user.id,
                amount=Decimal('50.00'),
                date=ancient_date
            )
        assert 'date too old' in str(exc.value).lower()


# Estimated test count: 25+ test functions
# Estimated LOC: ~600 lines
# Coverage target: 85%+ for transaction integrity
```

**Implementation Schedule:**
- Day 1-2: Concurrent transaction tests (8 hours)
- Day 2-3: Duplicate prevention tests (8 hours)
- Day 3-4: Rollback scenario tests (8 hours)

**Success Criteria:**
- [ ] 25+ test functions implemented
- [ ] Transaction module integrity >= 85%
- [ ] Concurrent operation safety validated
- [ ] Duplicate prevention working
- [ ] Rollback scenarios tested

---

## MERGE GATE ENHANCEMENTS

### Update `.github/workflows/python-ci.yml`

```yaml
name: Python CI with Enhanced Quality Gates

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  quality-gates:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      # ENHANCED: Database setup
      - name: Start PostgreSQL and Redis
        run: |
          docker run -d --name pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=mita -p 5432:5432 postgres:15
          docker run -d --name redis -p 6379:6379 redis:7-alpine

          # Wait for services
          for i in {1..10}; do
            docker exec pg pg_isready && break
            sleep 2
          done

      # ENHANCED: Migration testing
      - name: Database migration testing
        env:
          DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost:5432/mita
        run: |
          alembic upgrade head
          alembic upgrade head  # Idempotency test
          alembic downgrade 0003_goals
          alembic upgrade head

      # ENHANCED: Code quality
      - name: Code quality checks
        run: |
          black --check .
          isort --check .
          ruff check .
          mypy app/ --ignore-missing-imports

      # NEW: Secret scanning
      - name: Secret scanning
        run: |
          pip install detect-secrets
          detect-secrets scan --all-files --force-use-all-plugins

      # ENHANCED: Tests with critical path coverage
      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql+psycopg2://postgres:postgres@localhost:5432/mita
          REDIS_URL: redis://localhost:6379/0
        run: |
          export PYTHONPATH=.

          # Run all tests with coverage
          pytest \
            --cov=app \
            --cov-report=xml \
            --cov-report=term \
            --cov-report=html \
            --cov-fail-under=70 \
            -v

      # NEW: Critical path coverage validation
      - name: Validate critical path coverage
        run: |
          python scripts/validate_critical_path_coverage.py \
            --coverage-file coverage.xml \
            --min-coverage 95 \
            --critical-paths \
              "app/api/auth" \
              "app/api/iap" \
              "app/api/ocr" \
              "app/api/transactions/services.py"

      # NEW: Security tests must pass
      - name: Security tests (BLOCKING)
        run: |
          pytest app/tests/security/ -v --tb=short

      # NEW: Performance regression check
      - name: Performance benchmark validation
        run: |
          pytest app/tests/performance/ \
            --benchmark-only \
            --benchmark-compare=baseline.json \
            --benchmark-compare-fail=max:10%  # Fail if >10% slower

      # ENHANCED: Security scanning
      - name: Security vulnerability scan (BLOCKING)
        run: |
          pip install safety bandit

          # Check for known vulnerabilities
          safety check --json || exit 1

          # Static security analysis
          bandit -r app/ -ll -f json || exit 1

      - name: Upload coverage reports
        uses: actions/upload-artifact@v4
        with:
          name: coverage-reports
          path: |
            coverage.xml
            htmlcov/

      # NEW: Coverage trend reporting
      - name: Report coverage trend
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: true
```

### Create `scripts/validate_critical_path_coverage.py`

```python
#!/usr/bin/env python3
"""
Validate that critical paths have required test coverage.
Exits with error code if coverage below threshold.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

def parse_coverage_xml(coverage_file: Path) -> Dict[str, float]:
    """Parse coverage.xml and extract per-file coverage percentages"""
    tree = ET.parse(coverage_file)
    root = tree.getroot()

    coverage_data = {}

    for package in root.findall('.//package'):
        for cls in package.findall('.//class'):
            filename = cls.get('filename')
            lines_covered = int(cls.find('.//lines').get('covered', 0))
            lines_total = int(cls.find('.//lines').get('valid', 1))

            coverage_pct = (lines_covered / lines_total * 100) if lines_total > 0 else 0
            coverage_data[filename] = coverage_pct

    return coverage_data

def validate_critical_paths(
    coverage_data: Dict[str, float],
    critical_paths: List[str],
    min_coverage: float
) -> bool:
    """Validate that critical paths meet coverage threshold"""
    all_passed = True

    print(f"\n{'='*60}")
    print("CRITICAL PATH COVERAGE VALIDATION")
    print(f"{'='*60}\n")
    print(f"Minimum Required Coverage: {min_coverage}%\n")

    for path in critical_paths:
        matching_files = [f for f in coverage_data.keys() if path in f]

        if not matching_files:
            print(f"❌ FAIL: No files found for critical path: {path}")
            all_passed = False
            continue

        # Calculate average coverage for this path
        avg_coverage = sum(coverage_data[f] for f in matching_files) / len(matching_files)

        status = "✅ PASS" if avg_coverage >= min_coverage else "❌ FAIL"
        print(f"{status}: {path}")
        print(f"         Coverage: {avg_coverage:.2f}% ({len(matching_files)} files)")

        if avg_coverage < min_coverage:
            print(f"         Files below threshold:")
            for file in matching_files:
                if coverage_data[file] < min_coverage:
                    print(f"           - {file}: {coverage_data[file]:.2f}%")
            all_passed = False

    print(f"\n{'='*60}")

    return all_passed

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--coverage-file', required=True)
    parser.add_argument('--min-coverage', type=float, default=95.0)
    parser.add_argument('--critical-paths', nargs='+', required=True)

    args = parser.parse_args()

    coverage_data = parse_coverage_xml(Path(args.coverage_file))
    passed = validate_critical_paths(
        coverage_data,
        args.critical_paths,
        args.min_coverage
    )

    sys.exit(0 if passed else 1)
```

---

## SUCCESS METRICS

### Week 1-2 (OCR + Payment Tests):
- [ ] OCR module coverage: 0% → 90%+
- [ ] IAP module coverage: 40% → 90%+
- [ ] Zero critical paths with <80% coverage
- [ ] All payment security tests passing

### Week 3-4 (Integration Tests):
- [ ] Transaction integrity coverage: 60% → 85%+
- [ ] Budget E2E coverage: 55% → 80%+
- [ ] Goal integration coverage: 50% → 75%+
- [ ] Mobile-backend integration test suite created

### Week 5-6 (Performance & Security):
- [ ] Performance regression tests established
- [ ] All hot endpoints have load tests
- [ ] Security compliance score: 9/10 → 9.5/10
- [ ] GDPR compliance tests implemented

### Week 7-8 (Quality Gates):
- [ ] Overall coverage: 65% → 75%+
- [ ] Critical path coverage: 60% → 95%+
- [ ] Merge gate blocking on critical failures
- [ ] Flaky test detection system operational

---

## RISK MITIGATION

### HIGH RISK - Requires Immediate Action:

1. **OCR Processing Untested**
   - **Impact:** PRIMARY user feature could fail in production
   - **Probability:** HIGH (complex ML/image processing)
   - **Mitigation:** Implement OCR test suite ASAP (Sprint 1)

2. **Payment Processing Under-tested**
   - **Impact:** Financial loss, compliance violations
   - **Probability:** MEDIUM (payment systems are complex)
   - **Mitigation:** Comprehensive IAP testing (Sprint 1)

3. **No Mobile Integration Tests**
   - **Impact:** Backend-mobile incompatibility in production
   - **Probability:** MEDIUM (different platforms, versions)
   - **Mitigation:** Mobile integration test suite (Sprint 2)

### MEDIUM RISK - Address in Short Term:

4. **Transaction Deduplication**
   - **Impact:** Users charged twice, data integrity issues
   - **Probability:** LOW (but high impact if occurs)
   - **Mitigation:** Transaction integrity tests (Sprint 1)

5. **Budget Calculation Accuracy**
   - **Impact:** Incorrect financial advice to users
   - **Probability:** MEDIUM (complex business logic)
   - **Mitigation:** Budget E2E tests (Sprint 2)

---

## APPENDIX: QUICK START CHECKLIST

### This Week (Immediate):
- [ ] Review this action plan with team
- [ ] Allocate 1-2 QA engineers to testing sprints
- [ ] Set up performance baseline measurements
- [ ] Create GitHub issues for Priority 1 tests
- [ ] Update merge gate coverage threshold: 65% → 70%

### Next Week (Sprint 1 Prep):
- [ ] Set up OCR test environment (mock Google Vision API)
- [ ] Prepare payment test fixtures (Apple/Google receipts)
- [ ] Configure test database with transaction isolation
- [ ] Schedule daily standup for QA progress

### First Sprint Review (Week 2):
- [ ] Demo OCR test suite (35+ tests)
- [ ] Demo payment test suite (40+ tests)
- [ ] Review coverage reports (should show 85%+ for OCR/IAP)
- [ ] Identify any blockers for Sprint 2

---

**Document Owner:** QA Automation Engineer (Claude)
**Last Updated:** 2025-11-17
**Next Review:** After Sprint 1 completion
**Status:** 🔴 CRITICAL - IMPLEMENTATION REQUIRED
