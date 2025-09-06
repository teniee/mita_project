"""OCR receipt processing using Tesseract OCR."""

import os
from typing import Dict, Union

import pytesseract
from PIL import Image

from app.ocr.ocr_parser import parse_receipt_details
from app.core.logger import get_logger

logger = get_logger(__name__)


class OCRReceiptService:
    """Simple OCR service backed by Tesseract."""

    def __init__(self, temp_dir: str = "/tmp"):
        self.temp_dir = temp_dir

    def process_image(self, image_path: str) -> Dict[str, Union[str, float]]:
        """Extract structured data from a receipt image.

        Args:
            image_path: Path to the uploaded receipt image.

        Returns:
            Dict with keys ``store``, ``amount``, ``category_hint`` and
            ``date``.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError("Image file not found.")

        try:
            image = Image.open(image_path)
            raw_text = pytesseract.image_to_string(image)
        finally:
            try:
                os.remove(image_path)
            except Exception as e:  # pragma: no cover - best effort cleanup
                logger.warning(f"Could not delete temporary image file: {e}")

        parsed = parse_receipt_details(raw_text)

        return parsed
