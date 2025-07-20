"""
ReceiptTransactionService: Service for creating transactions based on OCR receipt data.
"""

from datetime import datetime


class ReceiptTransactionService:
    """
    Service to create financial transactions from processed receipt data.
    """

    def __init__(self, transaction_store, budget_tracker, calendar_engine):
        """
        Initialize with references to system services.

        Args:
            transaction_store: The store/service managing user transactions.
            budget_tracker: The budget management component.
            calendar_engine: The engine managing expense calendars.
        """
        self.transaction_store = transaction_store
        self.budget_tracker = budget_tracker
        self.calendar_engine = calendar_engine

    def create_transaction_from_receipt(self, user_id: str, receipt_data: dict):
        """
        Creates a financial transaction based on receipt data.

        Args:
            user_id (str): ID of the user.
            receipt_data (dict): Must contain 'store', 'amount', 'category', 'date'.
        """
        if not all(k in receipt_data for k in ("store", "amount", "category", "date")):
            raise ValueError(
                "Incomplete receipt data. Required fields: store, amount, category, date."
            )

        transaction = {
            "user_id": user_id,
            "store": receipt_data["store"],
            "amount": receipt_data["amount"],
            "category": receipt_data["category"],
            "date": datetime.strptime(receipt_data["date"], "%Y-%m-%d"),
            "source": "receipt_ocr",
        }

        # Step 1: Save the transaction
        self.transaction_store.add_transaction(transaction)

        # Step 2: Update the budget
        self.budget_tracker.record_expense(
            user_id=user_id,
            category=transaction["category"],
            amount=transaction["amount"],
        )

        # Step 3: Update the expense calendar
        self.calendar_engine.update_calendar_for_new_transaction(
            user_id=user_id, transaction=transaction
        )
