"""
ReceiptProcessingOrchestrator: Orchestrates receipt OCR, categorization, and transaction creation.
"""

from app.categorization.receipt_categorization_service import ReceiptCategorizationService
from app.ocr.ocr_receipt_service import OCRReceiptService
from app.transactions.receipt_transaction_service import ReceiptTransactionService


class ReceiptProcessingOrchestrator:
    """
    Orchestrates the complete receipt processing pipeline:
    1. OCR scanning
    2. Categorization
    3. Transaction creation
    """

    def __init__(
        self, transaction_store, budget_tracker, calendar_engine, temp_dir="/tmp"
    ):
        self.ocr_service = OCRReceiptService(temp_dir=temp_dir)
        self.categorization_service = ReceiptCategorizationService()
        self.transaction_service = ReceiptTransactionService(
            transaction_store, budget_tracker, calendar_engine
        )

    def process_receipt(self, user_id: str, image_path: str) -> dict:
        """
        Full processing of a receipt from image to transaction creation.

        Args:
            user_id (str): ID of the user.
            image_path (str): Path to the uploaded receipt image.

        Returns:
            dict: Result containing status and created transaction information or error.
        """
        try:
            receipt_data = self.ocr_service.process_image(image_path)

            if not receipt_data:
                return {"status": "error", "message": "Failed to extract receipt data."}

            # Categorize the receipt
            detected_category = self.categorization_service.categorize(receipt_data)
            receipt_data["category"] = detected_category

            # Create transaction
            self.transaction_service.create_transaction_from_receipt(
                user_id, receipt_data
            )

            return {
                "status": "success",
                "transaction": {
                    "store": receipt_data["store"],
                    "amount": receipt_data["amount"],
                    "category": receipt_data["category"],
                    "date": receipt_data["date"],
                },
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
