
"""
OCRReceiptService: Service for handling receipt image processing and text extraction.
"""

import os
import random

class OCRReceiptService:
    """
    A mock OCR service for extracting data from receipt images.
    (In production, replace mock behavior with real OCR, e.g., Tesseract or Google Vision API.)
    """

    def __init__(self, temp_dir: str = "/tmp"):
        self.temp_dir = temp_dir

    def process_image(self, image_path: str) -> dict:
        """
        Process the uploaded receipt image and extract relevant transaction data.

        Args:
            image_path (str): Path to the uploaded receipt image.

        Returns:
            dict: Extracted information with keys 'store', 'amount', 'date', etc.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError("Image file not found.")

        # --- MOCK OCR BEHAVIOR ---
        stores = ['Walmart', 'Costco', 'Starbucks', 'Amazon', 'McDonalds']
        categories = ['groceries', 'transport', 'entertainment', 'restaurants']
        result = {
            "store": random.choice(stores),
            "amount": round(random.uniform(5.0, 100.0), 2),
            "category_hint": random.choice(categories),
            "date": "2025-04-26"
        }

        # After processing, delete the image
        try:
            os.remove(image_path)
        except Exception as e:
            print(f"Warning: Could not delete temporary image file: {str(e)}")

        return result
