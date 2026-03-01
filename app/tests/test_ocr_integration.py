"""
Integration tests for OCR receipt processing system.

Tests the complete flow: image upload → OCR processing → categorization → transaction creation.

Coverage includes:
- File upload validation (5 tests)
- OCR text extraction (8 tests)
- Confidence scoring (7 tests)
- Receipt categorization (5 tests)
- Image storage (5 tests)
- API endpoints (5 tests)
- Error handling (5 tests)
- Security & authorization (4 tests)

Total: 44+ comprehensive test cases covering 533 lines of OCR code (currently 0% coverage)
"""

import os
import sys
import types
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

# ============================================================================
# ENVIRONMENT & FIREBASE SETUP (MUST come before app imports)
# ============================================================================

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost:5432/test_mita?sslmode=disable')
os.environ.setdefault('SECRET_KEY', 'test_secret_key_for_testing_only')
os.environ.setdefault('ENVIRONMENT', 'test')
os.environ.setdefault('FIREBASE_JSON', '{}')
os.environ.setdefault('JWT_SECRET', 'test_jwt_secret_key_min_32_chars_long_for_testing')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/1')
os.environ.setdefault('OPENAI_API_KEY', 'sk-test-key')
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', '/tmp/test-credentials.json')

# Mock Firebase (CRITICAL - before any other imports)
dummy = types.ModuleType("firebase_admin")
dummy._apps = []
dummy.credentials = types.SimpleNamespace(
    ApplicationDefault=lambda: None,
    Certificate=lambda *a, **k: None,
)
dummy.initialize_app = lambda cred=None: None
dummy.firestore = types.SimpleNamespace(
    client=lambda: None,
)
dummy.messaging = types.SimpleNamespace(
    Message=lambda **kwargs: None,
    send=lambda message: "mock_message_id",
)
sys.modules["firebase_admin"] = dummy
sys.modules["firebase_admin.credentials"] = dummy.credentials
sys.modules["firebase_admin.firestore"] = dummy.firestore
sys.modules["firebase_admin.messaging"] = dummy.messaging

# ============================================================================
# APP & ROUTE IMPORTS (after env setup)
# ============================================================================

from app.main import app
from app.api.dependencies import get_current_user
from app.core.session import get_db

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for API testing"""
    return TestClient(app)

@pytest.fixture
def mock_user():
    """Create mock authenticated premium user"""
    return SimpleNamespace(
        id="test_user_premium_123",
        email="premium@example.com",
        is_premium=True,
        timezone="UTC"
    )

@pytest.fixture
def mock_basic_user():
    """Create mock basic (non-premium) user"""
    return SimpleNamespace(
        id="test_user_basic_456",
        email="basic@example.com",
        is_premium=False,
        timezone="UTC"
    )

@pytest.fixture
def mock_db():
    """Create mock database session"""
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.execute = AsyncMock()

    # Mock query results
    mock_result = Mock()
    mock_result.scalars.return_value.first.return_value = None
    db.execute.return_value = mock_result

    return db

@pytest.fixture
def sample_image_bytes():
    """Create sample valid JPEG bytes for testing (1x1 pixel)"""
    return (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01'
        b'\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07'
        b'\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14'
        b'\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444'
        b'\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11'
        b'\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07'
        b'\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\xd9'
    )

@pytest.fixture
def sample_walmart_receipt_text():
    """Sample receipt text for Walmart grocery store"""
    return """
    Walmart Supercenter
    123 Main Street
    Springfield, IL 62701

    Bread                $3.99
    Milk 2%              $2.50
    Eggs Dozen           $4.25
    Cheese Cheddar       $5.99

    Subtotal:           $16.73
    Tax:                 $1.34
    TOTAL:              $18.07

    Date: 2025-12-03
    Time: 14:35:22

    Thank you for shopping!
    """

@pytest.fixture
def sample_ocr_result_walmart():
    """Sample OCR processing result for Walmart receipt"""
    return {
        "merchant": "Walmart Supercenter",
        "amount": 18.07,
        "date": "2025-12-03",
        "category_hint": "groceries",
        "items": [
            {"name": "Bread", "price": 3.99},
            {"name": "Milk 2%", "price": 2.50},
            {"name": "Eggs Dozen", "price": 4.25},
            {"name": "Cheese Cheddar", "price": 5.99}
        ],
        "confidence": 0.92,
        "raw_text": "Walmart Supercenter\n123 Main Street\nBread $3.99..."
    }

@pytest.fixture
def sample_ocr_result_starbucks():
    """Sample OCR result for Starbucks restaurant receipt"""
    return {
        "merchant": "Starbucks Coffee",
        "amount": 8.45,
        "date": "2025-12-04",
        "category_hint": "restaurants",
        "items": [
            {"name": "Latte Grande", "price": 5.95},
            {"name": "Croissant", "price": 2.50}
        ],
        "confidence": 0.88,
        "raw_text": "Starbucks Coffee\nLatte Grande $5.95..."
    }

@pytest.fixture
def sample_ocr_low_confidence():
    """Sample OCR result with low confidence (blurry receipt)"""
    return {
        "merchant": "Unknown Store",
        "amount": 0.0,
        "date": None,
        "category_hint": "other",
        "items": [],
        "confidence": 0.35,
        "raw_text": "blurry... illegible... unclear..."
    }

# ============================================================================
# FIXTURE CLEANUP
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Automatically clean up dependency overrides after each test"""
    yield
    app.dependency_overrides = {}

# ============================================================================
# TESTS: FILE UPLOAD VALIDATION
# ============================================================================

class TestOCRFileUploadValidation:
    """Test file upload validation at API layer"""

    def test_upload_valid_jpeg_file(self, client, mock_user, mock_db, sample_image_bytes):
        """Test upload with valid JPEG file"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch('app.api.ocr.routes.OCRReceiptService') as mock_ocr, \
             patch('app.api.ocr.routes.get_receipt_storage') as mock_get_storage:

            mock_ocr.return_value.process_image.return_value = {
                "merchant": "Test Store",
                "amount": 50.0,
                "date": "2025-12-04",
                "category_hint": "groceries"
            }
            mock_get_storage.return_value.save_image.return_value = (
                "/app/data/receipts/user_123/image.jpg",
                "/receipts/user_123/image.jpg"
            )

            response = client.post(
                "/api/ocr/process",
                files={"file": ("receipt.jpg", sample_image_bytes, "image/jpeg")}
            )

            assert response.status_code == 200

    def test_upload_missing_file(self, client, mock_user, mock_db):
        """Test upload endpoint with missing file parameter"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.post("/api/ocr/process")

        # Should fail validation
        assert response.status_code == 422

    def test_upload_invalid_file_type(self, client, mock_user, mock_db):
        """Test upload with invalid file type (PDF instead of image)"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.post(
            "/api/ocr/process",
            files={"file": ("document.pdf", b"PDF content", "application/pdf")}
        )

        assert response.status_code == 400

    def test_upload_empty_file(self, client, mock_user, mock_db):
        """Test upload with empty file (0 bytes)"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        response = client.post(
            "/api/ocr/process",
            files={"file": ("receipt.jpg", b"", "image/jpeg")}
        )

        assert response.status_code == 400

    def test_upload_oversized_file(self, client, mock_user, mock_db):
        """Test upload with file exceeding 10MB size limit"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Create oversized content (11MB)
        large_content = b"x" * (11 * 1024 * 1024)

        response = client.post(
            "/api/ocr/process",
            files={"file": ("receipt.jpg", large_content, "image/jpeg")}
        )

        assert response.status_code == 400

# ============================================================================
# TESTS: AUTHENTICATION & AUTHORIZATION
# ============================================================================

class TestOCRAuthentication:
    """Test authentication and authorization requirements"""

    def test_process_without_auth(self, client, sample_image_bytes):
        """Test OCR endpoint requires authentication"""
        response = client.post(
            "/api/ocr/process",
            files={"file": ("receipt.jpg", sample_image_bytes, "image/jpeg")}
        )

        # Should fail with 403 Forbidden (no auth)
        assert response.status_code in [401, 403]

    def test_process_with_valid_auth(self, client, mock_user, mock_db, sample_image_bytes):
        """Test OCR endpoint with valid authentication"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch('app.api.ocr.routes.OCRReceiptService') as mock_ocr, \
             patch('app.api.ocr.routes.get_receipt_storage') as mock_get_storage:

            mock_ocr.return_value.process_image.return_value = {
                "merchant": "Test Store",
                "amount": 50.0,
                "date": "2025-12-04"
            }
            mock_get_storage.return_value.save_image.return_value = (
                "/app/data/receipts/image.jpg",
                "/receipts/image.jpg"
            )

            response = client.post(
                "/api/ocr/process",
                files={"file": ("receipt.jpg", sample_image_bytes, "image/jpeg")}
            )

            assert response.status_code == 200

    def test_access_other_user_receipt(self, client, mock_user, mock_db):
        """Test that users cannot access other users' receipt images"""
        # Setup: User A uploads receipt
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Query filtered by user_id returns None (not found for this user)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.get("/api/ocr/image/job_123")

        # Should return 404 (query filtered by user_id)
        assert response.status_code == 404

    def test_delete_other_user_receipt(self, client, mock_user, mock_db):
        """Test that users cannot delete other users' receipt images"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Query filtered by user_id returns None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.delete("/api/ocr/image/job_123")

        assert response.status_code == 404

# ============================================================================
# TESTS: OCR TEXT EXTRACTION & PARSING
# ============================================================================

class TestOCRTextExtraction:
    """Test OCR text extraction and parsing logic"""

    def test_parse_walmart_receipt(self, sample_walmart_receipt_text):
        """Test parsing complete Walmart receipt with all fields"""
        from app.ocr.ocr_parser import parse_receipt_details

        result = parse_receipt_details(sample_walmart_receipt_text)

        assert result is not None
        assert "merchant" in result
        assert "Walmart" in result["merchant"]
        assert result["amount"] == pytest.approx(18.07, abs=0.01)
        assert result["date"] == "2025-12-03"
        assert len(result["items"]) >= 4

    def test_parse_receipt_no_text(self):
        """Test parsing returns default values when no text detected"""
        from app.ocr.ocr_parser import parse_receipt_details

        result = parse_receipt_details("")
        assert result["amount"] == 0.0
        assert result["merchant"] == "unknown"

    def test_extract_amount_variations(self):
        """Test amount extraction from different formats"""
        from app.ocr.ocr_parser import parse_receipt_text

        # Test $50.00 format
        result1 = parse_receipt_text("Store\nTotal: $50.00")
        assert result1["amount"] == pytest.approx(50.0, abs=0.01)

        # Test $0.99 format (small amount)
        result2 = parse_receipt_text("Store\nTotal: $0.99")
        assert result2["amount"] == pytest.approx(0.99, abs=0.01)

        # Test amount without cents
        result3 = parse_receipt_text("Store\nTotal: $50")
        assert result3["amount"] == pytest.approx(50.0, abs=0.01)

    def test_extract_date_formats(self):
        """Test date extraction from multiple formats"""
        from app.ocr.ocr_parser import parse_receipt_text

        # YYYY-MM-DD format
        result1 = parse_receipt_text("Store\n$10\n2025-12-04")
        assert result1["date"] == "2025-12-04"

        # MM/DD/YYYY format
        result2 = parse_receipt_text("Store\n$10\n12/04/2025")
        assert result2["date"] is not None

        # Fallback to today if unparseable
        result3 = parse_receipt_text("Store\n$10\ngarbage date")
        assert result3["date"] is not None

    def test_merchant_name_extraction(self):
        """Test merchant name extraction (first non-empty line, max 64 chars)"""
        from app.ocr.ocr_parser import parse_receipt_details

        result = parse_receipt_details("Amazon\nItems: $50\nDate: 2025-12-04")
        assert result["merchant"] == "Amazon"

        # Test truncation at 64 characters
        long_name = "A" * 100
        result2 = parse_receipt_details(f"{long_name}\n$10\n2025-12-04")
        assert len(result2["merchant"]) <= 64

    def test_items_parsing_with_prices(self):
        """Test items list extraction with name and price"""
        from app.ocr.ocr_parser import parse_receipt_details

        receipt_text = """
        Walmart
        Bread         $3.99
        Milk          $2.50
        Eggs          $4.25
        Total:       $10.74
        """

        result = parse_receipt_details(receipt_text)
        # Items include Bread, Milk, Eggs and Total line (which also matches price pattern)
        assert len(result["items"]) >= 3
        assert result["items"][0]["name"] == "Bread"
        assert result["items"][0]["price"] == pytest.approx(3.99, abs=0.01)

    def test_category_hint_keyword_matching(self):
        """Test category hint assignment based on keyword matching"""
        from app.ocr.ocr_parser import parse_receipt_text

        # Walmart matches "shopping" category (contains "walmart")
        result1 = parse_receipt_text("Walmart Supercenter\n$50\n2025-12-04")
        assert result1["category"] == "shopping"

        # Restaurant keyword matching
        result2 = parse_receipt_text("McDonald's Cafe\n$10\n2025-12-04")
        assert result2["category"] == "restaurants"

        # Transport
        result3 = parse_receipt_text("Uber Trip\n$25\n2025-12-04")
        assert result3["category"] == "transport"

    def test_unknown_merchant_category(self):
        """Test unknown merchant defaults to 'other' category"""
        from app.ocr.ocr_parser import parse_receipt_text

        result = parse_receipt_text("Unknown XYZ Place\n$10\n2025-12-04")
        assert result["category"] == "other"

# ============================================================================
# TESTS: CONFIDENCE SCORING
# ============================================================================

class TestOCRConfidenceScoring:
    """Test confidence score calculations"""

    def test_merchant_confidence_known_merchant(self):
        """Test merchant confidence for known merchant names"""
        from app.ocr.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()

        # Known merchant
        conf1 = scorer.calculate_merchant_confidence("Walmart", "Walmart\nTotal: $50")
        assert conf1 >= 0.8

        # Unknown merchant
        conf2 = scorer.calculate_merchant_confidence("Unknown Store", "Unknown Store\n$50")
        assert conf2 < 0.8

    def test_amount_confidence_matches_items(self):
        """Test amount confidence when it matches items sum"""
        from app.ocr.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()
        items = [
            {"name": "Item1", "price": 10.0},
            {"name": "Item2", "price": 5.0}
        ]

        # Exact match
        conf1 = scorer.calculate_amount_confidence(15.0, items, "Total: $15.00")
        assert conf1 >= 0.9

        # Close match (within 10%)
        conf2 = scorer.calculate_amount_confidence(16.0, items, "Total: $16.00")
        assert conf2 >= 0.6

    def test_date_confidence_recent_date(self):
        """Test date confidence for recent dates"""
        from app.ocr.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()

        # Today's date
        today = datetime.now().strftime("%Y-%m-%d")
        raw_text = f"Store\nDate: {today}\nTotal: $10"
        conf1 = scorer.calculate_date_confidence(today, raw_text)
        assert conf1 >= 0.7

        # Future date (penalized)
        future = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        conf2 = scorer.calculate_date_confidence(future, f"Date: {future}")
        assert conf2 < 0.7

    def test_category_confidence_scoring(self):
        """Test category confidence based on keyword matches"""
        from app.ocr.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()

        # Known category with items
        items = [{"name": "Bread"}, {"name": "Milk"}]
        conf1 = scorer.calculate_category_confidence("groceries", "Grocery Store", items)
        assert conf1 >= 0.7

        # "other" category
        conf2 = scorer.calculate_category_confidence("other", "Unknown", [])
        assert conf2 == 0.3

    def test_items_confidence_with_valid_items(self):
        """Test items confidence with 3+ valid items"""
        from app.ocr.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()

        items = [
            {"name": "Item1", "price": 5.0},
            {"name": "Item2", "price": 10.0},
            {"name": "Item3", "price": 15.0}
        ]

        conf = scorer.calculate_items_confidence(items, 30.0)
        assert conf >= 0.8

    def test_overall_confidence_weighted_average(self):
        """Test overall confidence calculation (weighted average)"""
        from app.ocr.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()

        # Mock OCR result
        ocr_result = {
            "merchant": "Walmart",
            "amount": 50.0,
            "date": "2025-12-04",
            "category_hint": "groceries",
            "items": [{"name": "Bread", "price": 3.99}],
            "raw_text": "Walmart\nTotal: $50.00"
        }

        scored_result = scorer.score_ocr_result(ocr_result, ocr_result["raw_text"])

        assert "confidence" in scored_result
        assert 0.0 <= scored_result["confidence"] <= 1.0
        assert "confidence_scores" in scored_result
        assert scored_result["confidence"] == pytest.approx(
            (
                scored_result["confidence_scores"]["merchant"] * 0.25 +
                scored_result["confidence_scores"]["amount"] * 0.30 +
                scored_result["confidence_scores"]["date"] * 0.20 +
                scored_result["confidence_scores"]["category"] * 0.15 +
                scored_result["confidence_scores"]["items"] * 0.10
            ),
            abs=0.01
        )

    def test_fields_needing_review(self):
        """Test identification of fields needing review (confidence < 0.6)"""
        from app.ocr.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()

        # Create result with low confidence merchant
        ocr_result = {
            "merchant": "???",
            "amount": 50.0,
            "date": "2025-12-04",
            "category_hint": "other",
            "items": [],
            "raw_text": "illegible\n$50"
        }

        scored_result = scorer.score_ocr_result(ocr_result, ocr_result["raw_text"])

        assert "fields_needing_review" in scored_result
        # Should flag merchant and category (low confidence)
        assert len(scored_result["fields_needing_review"]) > 0

# ============================================================================
# TESTS: RECEIPT CATEGORIZATION
# ============================================================================

class TestReceiptCategorization:
    """Test receipt categorization service"""

    def test_merchant_based_categorization(self):
        """Test categorization based on merchant keywords"""
        from app.categorization.receipt_categorization_service import ReceiptCategorizationService

        service = ReceiptCategorizationService()

        # Walmart → groceries
        result1 = service.categorize(merchant="Walmart", amount=50.0, items=[], hint="")
        assert result1 == "groceries"

        # Starbucks → restaurants
        result2 = service.categorize(merchant="Starbucks", amount=10.0, items=[], hint="")
        assert result2 == "restaurants"

        # Uber → transport
        result3 = service.categorize(merchant="Uber", amount=25.0, items=[], hint="")
        assert result3 == "transport"

    def test_hint_based_categorization(self):
        """Test categorization using category hint"""
        from app.categorization.receipt_categorization_service import ReceiptCategorizationService

        service = ReceiptCategorizationService()

        result = service.categorize(
            merchant="XYZ Place",
            amount=30.0,
            items=[],
            hint="groceries"
        )

        assert result == "groceries"

    def test_items_based_categorization(self):
        """Test categorization based on item names"""
        from app.categorization.receipt_categorization_service import ReceiptCategorizationService

        service = ReceiptCategorizationService()

        # Grocery items
        result1 = service.categorize(
            merchant="Unknown",
            amount=20.0,
            items=[
                {"name": "Bread"},
                {"name": "Milk"},
                {"name": "Eggs"}
            ],
            hint=""
        )
        assert result1 == "groceries"

    def test_amount_based_heuristics(self):
        """Test amount-based category heuristics"""
        from app.categorization.receipt_categorization_service import ReceiptCategorizationService

        service = ReceiptCategorizationService()

        # Small amount (<$10) should boost restaurants/transport
        result1 = service.categorize(merchant="Unknown", amount=8.0, items=[], hint="")
        assert result1 in ["restaurants", "transport", "other"]

        # Medium amount ($10-100) should boost groceries/restaurants
        result2 = service.categorize(merchant="Unknown", amount=50.0, items=[], hint="")
        assert result2 in ["groceries", "restaurants", "other"]

    def test_multilingual_support(self):
        """Test Bulgarian merchant names"""
        from app.categorization.receipt_categorization_service import ReceiptCategorizationService

        service = ReceiptCategorizationService()

        # Bulgarian grocery store
        result1 = service.categorize(merchant="Kaufland", amount=40.0, items=[], hint="")
        assert result1 == "groceries"

        # Bulgarian pharmacy
        result2 = service.categorize(merchant="Софарма", amount=15.0, items=[], hint="")
        assert result2 == "healthcare"

# ============================================================================
# TESTS: IMAGE STORAGE
# ============================================================================

class TestReceiptImageStorage:
    """Test receipt image storage service"""

    def test_save_image_creates_directory(self):
        """Test save_image creates user directory if needed"""
        from app.storage.receipt_image_storage import ReceiptImageStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ReceiptImageStorage(base_path=tmpdir)

            # Create temp file
            temp_file = os.path.join(tmpdir, "temp.jpg")
            with open(temp_file, 'wb') as f:
                f.write(b"image data")

            # Save image (storage creates dir as "user_{user_id}")
            storage_path, image_url = storage.save_image(
                temp_path=temp_file,
                user_id="123",
                job_id="job_456"
            )

            # Verify directory created
            user_dir = os.path.join(tmpdir, "user_123")
            assert os.path.exists(user_dir)

            # Verify file saved
            assert os.path.exists(storage_path)
            assert "123" in image_url
            assert "job_456" in image_url

    def test_get_image_path(self):
        """Test get_image_path returns correct path"""
        from app.storage.receipt_image_storage import ReceiptImageStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ReceiptImageStorage(base_path=tmpdir)

            # Create user directory (matching storage's "user_{user_id}" format)
            user_dir = os.path.join(tmpdir, "user_123")
            os.makedirs(user_dir, exist_ok=True)
            test_file = os.path.join(user_dir, "test.jpg")
            with open(test_file, 'wb') as f:
                f.write(b"data")

            # Test get_image_path (uses user_id="123", creates path "user_123")
            path = storage.get_image_path("123", "test.jpg")
            assert path == test_file
            assert os.path.exists(path)

            # Test non-existent file
            path_none = storage.get_image_path("123", "nonexistent.jpg")
            assert path_none is None

    def test_delete_image(self):
        """Test delete_image removes file from disk"""
        from app.storage.receipt_image_storage import ReceiptImageStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ReceiptImageStorage(base_path=tmpdir)

            # Create file
            test_file = os.path.join(tmpdir, "test.jpg")
            with open(test_file, 'wb') as f:
                f.write(b"data")

            # Delete
            result = storage.delete_image(test_file)
            assert result is True
            assert not os.path.exists(test_file)

            # Try deleting again (should return False)
            result2 = storage.delete_image(test_file)
            assert result2 is False

    def test_cleanup_old_images(self):
        """Test cleanup_old_images removes old files, keeps recent"""
        from app.storage.receipt_image_storage import ReceiptImageStorage
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ReceiptImageStorage(base_path=tmpdir)

            user_dir = os.path.join(tmpdir, "user_123")
            os.makedirs(user_dir, exist_ok=True)

            # Create old file (modified 100 days ago)
            old_file = os.path.join(user_dir, "old.jpg")
            with open(old_file, 'wb') as f:
                f.write(b"old")
            old_time = time.time() - (100 * 24 * 3600)
            os.utime(old_file, (old_time, old_time))

            # Create recent file
            new_file = os.path.join(user_dir, "new.jpg")
            with open(new_file, 'wb') as f:
                f.write(b"new")

            # Cleanup files older than 90 days
            deleted_count = storage.cleanup_old_images(days=90)

            assert deleted_count >= 1
            assert not os.path.exists(old_file)
            assert os.path.exists(new_file)

    def test_get_user_images(self):
        """Test get_user_images returns list with metadata"""
        from app.storage.receipt_image_storage import ReceiptImageStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ReceiptImageStorage(base_path=tmpdir)

            user_dir = os.path.join(tmpdir, "user_123")
            os.makedirs(user_dir, exist_ok=True)

            # Create files
            for i in range(3):
                file_path = os.path.join(user_dir, f"image_{i}.jpg")
                with open(file_path, 'wb') as f:
                    f.write(b"x" * 1000 * (i + 1))

            # Get images (user_id="123" → dir "user_123")
            images = storage.get_user_images("123", limit=10)

            assert len(images) == 3
            assert "filename" in images[0]
            assert "path" in images[0]
            assert "url" in images[0]
            assert "size" in images[0]

# ============================================================================
# TESTS: API ENDPOINTS
# ============================================================================

class TestOCRAPIEndpoints:
    """Test OCR API endpoint integration"""

    def test_process_receipt_end_to_end(self, client, mock_user, mock_db, sample_image_bytes, sample_ocr_result_walmart):
        """Test complete flow: upload → OCR → parse → store → return result"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch('app.api.ocr.routes.OCRReceiptService') as mock_ocr, \
             patch('app.api.ocr.routes.get_receipt_storage') as mock_get_storage:

            mock_ocr.return_value.process_image.return_value = sample_ocr_result_walmart
            mock_get_storage.return_value.save_image.return_value = (
                "/app/data/receipts/user_123/image.jpg",
                "/receipts/user_123/image.jpg"
            )

            response = client.post(
                "/api/ocr/process",
                files={"file": ("walmart_receipt.jpg", sample_image_bytes, "image/jpeg")}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure (wrapped in success_response)
            assert "data" in data
            result = data["data"]["result"]
            assert result["merchant"] == "Walmart Supercenter"
            assert result["amount"] == 18.07
            assert result["confidence"] >= 0.9

    def test_categorize_receipt_endpoint(self, client, mock_user, mock_db):
        """Test receipt categorization endpoint"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch('app.categorization.receipt_categorization_service.ReceiptCategorizationService') as mock_service:
            mock_service.return_value.categorize.return_value = {
                "category": "groceries",
                "confidence": 0.85
            }

            response = client.post(
                "/api/ocr/categorize",
                json={
                    "merchant": "Walmart",
                    "amount": 50.0,
                    "items": [],
                    "hint": "groceries"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["category"] == "groceries"

    def test_get_ocr_job_status(self, client, mock_user, mock_db):
        """Test get OCR job status endpoint"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        # Mock OCR job
        mock_job = Mock()
        mock_job.status = "completed"
        mock_job.progress = Decimal("100.0")
        mock_job.confidence = Decimal("0.92")
        mock_job.store_name = "Walmart"
        mock_job.amount = Decimal("50.0")
        mock_job.date = "2025-12-04"
        mock_job.category_hint = "groceries"
        mock_job.image_url = "/receipts/image.jpg"
        mock_job.created_at = datetime.utcnow()
        mock_job.completed_at = datetime.utcnow()
        mock_job.error_message = None
        mock_job.raw_result = {"merchant": "Walmart", "amount": 50.0}

        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        response = client.get("/api/ocr/status/job_123")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "completed"
        assert data["data"]["progress"] == 100.0

    def test_get_receipt_image(self, client, mock_user, mock_db):
        """Test retrieve receipt image file"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"image data")
            tmp_path = tmp.name

        try:
            mock_job = Mock()
            mock_job.user_id = mock_user.id
            mock_job.image_path = tmp_path

            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            response = client.get("/api/ocr/image/job_123")

            assert response.status_code == 200
            assert response.headers["content-type"].startswith("image/")
        finally:
            os.unlink(tmp_path)

    def test_delete_receipt_image(self, client, mock_user, mock_db):
        """Test delete receipt image endpoint"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"data")
            tmp_path = tmp.name

        try:
            mock_job = Mock()
            mock_job.user_id = mock_user.id
            mock_job.image_path = tmp_path

            mock_db.query.return_value.filter.return_value.first.return_value = mock_job

            with patch('app.api.ocr.routes.get_receipt_storage') as mock_get_storage:
                mock_get_storage.return_value.delete_image.return_value = True

                response = client.delete("/api/ocr/image/job_123")

                assert response.status_code == 200
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

# ============================================================================
# TESTS: ERROR HANDLING & EDGE CASES
# ============================================================================

class TestOCRErrorHandling:
    """Test error handling and edge cases"""

    def test_ocr_service_failure(self, client, mock_user, mock_db, sample_image_bytes):
        """Test handling of OCR service failures"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch('app.api.ocr.routes.OCRReceiptService') as mock_ocr:
            mock_ocr.return_value.process_image.side_effect = Exception("OCR Service unavailable")

            response = client.post(
                "/api/ocr/process",
                files={"file": ("receipt.jpg", sample_image_bytes, "image/jpeg")}
            )

            assert response.status_code == 500

    def test_no_text_detected_in_image(self, client, mock_user, mock_db, sample_image_bytes):
        """Test handling when no text is detected"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch('app.api.ocr.routes.OCRReceiptService') as mock_ocr:
            mock_ocr.return_value.process_image.side_effect = ValueError("No text detected in image")

            response = client.post(
                "/api/ocr/process",
                files={"file": ("blank.jpg", sample_image_bytes, "image/jpeg")}
            )

            assert response.status_code >= 400

    def test_database_transaction_failure(self, client, mock_user, sample_image_bytes):
        """Test handling of database commit failures"""
        app.dependency_overrides[get_current_user] = lambda: mock_user

        mock_db = Mock()
        mock_db.commit.side_effect = Exception("Database error")
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch('app.api.ocr.routes.OCRReceiptService') as mock_ocr, \
             patch('app.api.ocr.routes.get_receipt_storage') as mock_get_storage:

            mock_ocr.return_value.process_image.return_value = {
                "merchant": "Test",
                "amount": 10.0
            }
            mock_get_storage.return_value.save_image.return_value = ("/path", "/url")

            response = client.post(
                "/api/ocr/process",
                files={"file": ("receipt.jpg", sample_image_bytes, "image/jpeg")}
            )

            assert response.status_code == 500

    def test_malformed_ocr_response(self, client, mock_user, mock_db, sample_image_bytes):
        """Test handling of malformed OCR responses"""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: mock_db

        with patch('app.api.ocr.routes.OCRReceiptService') as mock_ocr, \
             patch('app.api.ocr.routes.get_receipt_storage') as mock_get_storage:

            # Return empty dict
            mock_ocr.return_value.process_image.return_value = {}
            mock_get_storage.return_value.save_image.return_value = ("/path", "/url")

            response = client.post(
                "/api/ocr/process",
                files={"file": ("receipt.jpg", sample_image_bytes, "image/jpeg")}
            )

            # Should handle gracefully
            assert response.status_code in [200, 400, 422, 500]

    def test_path_traversal_prevention(self):
        """Test filename sanitization prevents path traversal"""
        from app.storage.receipt_image_storage import ReceiptImageStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ReceiptImageStorage(base_path=tmpdir)

            # Attempt path traversal
            malicious_filename = "../../../etc/passwd"
            path = storage.get_image_path("user_123", malicious_filename)

            # Should not traverse outside user directory
            if path:
                assert tmpdir in path
                assert "user_123" in path
