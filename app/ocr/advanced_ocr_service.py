"""
AdvancedOCRService: Dual OCR Engine (Tesseract for free users, Google Vision API for premium users)
"""

import os

import pytesseract
from PIL import Image

from app.ocr.google_vision_ocr_service import GoogleVisionOCRService


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

        # After processing, delete the image
        try:
            os.remove(image_path)
        except Exception as e:
            print(f"Warning: Could not delete temporary image file: {str(e)}")

        return result

    def _tesseract_ocr(self, image_path: str) -> dict:
        """
        Extract text using Tesseract OCR.

        Args:
            image_path (str): Path to image.

        Returns:
            dict: Simulated parsed receipt data.
        """
        try:
            image = Image.open(image_path)
            raw_text = pytesseract.image_to_string(image)

            if not raw_text.strip():
                raise ValueError("No text detected on the image.")

            return {
                "store": "Detected Store (Tesseract)",
                "amount": 50.0,
                "category_hint": "groceries",
                "date": "2025-04-26",
                "raw_text": raw_text,
            }

        except Exception as e:
            raise RuntimeError(f"Tesseract OCR failed: {str(e)}")
