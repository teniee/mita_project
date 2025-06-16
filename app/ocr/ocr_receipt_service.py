"""OCR receipt processing using Tesseract OCR."""

import os
import tempfile
from typing import Dict

import pytesseract
from PIL import Image

from app.ocr.ocr_parser import parse_receipt_text


class OCRReceiptService:
    """Simple OCR service backed by Tesseract."""

    def __init__(self, temp_dir: str | None = None):
        self.temp_dir = temp_dir or tempfile.gettempdir()

    def process_image(self, image_path: str) -> Dict[str, str | float]:
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
                print(f"Warning: Could not delete temporary image file: {e}")

        parsed = parse_receipt_text(raw_text)

        # Use the first non-empty line as a store hint
        store = "unknown"
        for line in raw_text.splitlines():
            stripped = line.strip()
            if stripped:
                store = stripped[:64]
                break

        return {
            "store": store,
            "amount": parsed["amount"],
            "category_hint": parsed["category"],
            "date": parsed["date"],
        }
