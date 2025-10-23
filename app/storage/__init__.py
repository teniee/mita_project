"""Storage services for MITA application."""

from app.storage.receipt_image_storage import ReceiptImageStorage, get_receipt_storage

__all__ = ["ReceiptImageStorage", "get_receipt_storage"]
