"""
AdvancedOCRService: Dual OCR Engine (Tesseract for free users, Google Vision API for premium users)
"""

import os

import pytesseract
from PIL import Image

from app.ocr.google_vision_ocr_service import GoogleVisionOCRService
from app.ocr.confidence_scorer import ConfidenceScorer
from app.core.logger import get_logger

logger = get_logger(__name__)


class AdvancedOCRService:
    """
    OCR service that dynamically switches between Tesseract and Google Vision API based on user type.
    """

    def __init__(
        self,
        temp_dir: str = "/tmp",
        credentials_json_path: str = "/path/to/credentials.json",
    ):
        self.temp_dir = temp_dir
        self.credentials_json_path = credentials_json_path

    def process_image(self, image_path: str, is_premium_user: bool = False) -> dict:
        """
        Process the receipt image.

        Args:
            image_path (str): Path to the receipt image.
            is_premium_user (bool): Determines which OCR engine to use.

        Returns:
            dict: Extracted information (store, amount, date, etc.)
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError("Image file not found.")

        if is_premium_user:
            vision_service = GoogleVisionOCRService(self.credentials_json_path)
            result = vision_service.process_image(image_path)
        else:
            result = self._tesseract_ocr(image_path)

        # Add confidence scores to the result
        raw_text = result.get("raw_text", "")
        result = ConfidenceScorer.score_ocr_result(result, raw_text)

        # Note: File cleanup is handled by the caller (API routes)
        # Do NOT delete the file here to avoid double-deletion issues

        return result

    def _tesseract_ocr(self, image_path: str) -> dict:
        """
        Extract text using Tesseract OCR and parse receipt details.

        Args:
            image_path (str): Path to image.

        Returns:
            dict: Parsed receipt data with merchant, items, amount, date, category.
        """
        from app.ocr.ocr_parser import parse_receipt_details

        try:
            image = Image.open(image_path)
            raw_text = pytesseract.image_to_string(image)

            if not raw_text.strip():
                raise ValueError("No text detected on the image.")

            # Use the real parser instead of hardcoded values
            parsed = parse_receipt_details(raw_text)

            # Map to expected format
            return {
                "store": parsed.get("merchant", "Unknown Store"),
                "amount": parsed.get("total", 0.0),
                "category_hint": parsed.get("category", "other"),
                "date": parsed.get("date", ""),
                "items": parsed.get("items", []),
                "raw_text": raw_text,
            }

        except Exception as e:
            raise RuntimeError(f"Tesseract OCR failed: {str(e)}")
