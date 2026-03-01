"""
GoogleVisionOCRService: Real integration with Google Cloud Vision API.
"""

import io
import os

from google.cloud import vision


class GoogleVisionOCRService:
    def __init__(self, credentials_json_path: str):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_json_path
        self.client = vision.ImageAnnotatorClient()

    def process_image(self, image_path: str) -> dict:
        """
        Process receipt image using Google Cloud Vision API.

        Args:
            image_path: Path to the receipt image.

        Returns:
            dict: Parsed receipt data with merchant, items, amount, date, category.
        """
        from app.ocr.ocr_parser import parse_receipt_details

        with io.open(image_path, "rb") as image_file:
            content = image_file.read()

        image = vision.Image(content=content)
        response = self.client.text_detection(image=image)

        if response.error.message:
            msg = f"Google Vision API error: {response.error.message}"
            raise Exception(msg)

        annotations = response.text_annotations
        if not annotations:
            raise ValueError("No text detected in image")

        full_text = annotations[0].description.strip()

        parsed = parse_receipt_details(full_text)

        # Map to expected format
        return {
            "store": parsed.get("merchant", "Unknown Store"),
            "amount": parsed.get("total", 0.0),
            "category_hint": parsed.get("category", "other"),
            "date": parsed.get("date", ""),
            "items": parsed.get("items", []),
            "raw_text": full_text,
        }
