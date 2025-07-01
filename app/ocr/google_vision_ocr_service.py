"""
GoogleVisionOCRService: Real integration with Google Cloud Vision API.
"""

import io
import os
import re

from google.cloud import vision


class GoogleVisionOCRService:
    def __init__(self, credentials_json_path: str):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_json_path
        self.client = vision.ImageAnnotatorClient()

    def process_image(self, image_path: str) -> dict:
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

        amount_match = re.search(r"(\d+[.,]\d{2})", full_text)
        if amount_match:
            amount = float(amount_match.group(1).replace(",", "."))
        else:
            amount = 0.0

        return {
            "store": "Detected Store (Google Vision Real)",
            "amount": amount,
            "category_hint": "shopping",
            "date": "2025-04-26",
            "raw_text": full_text,
        }
