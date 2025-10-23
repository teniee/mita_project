from datetime import datetime
import logging

from app.ocr.ocr_parser import parse_receipt_text, parse_receipt_details
from app.services.expense_tracker import record_expense

logger = logging.getLogger(__name__)


def process_receipt_from_text(user_id: int, text: str, db) -> dict:
    """
    Legacy method: Parse receipt from raw text and create transaction.

    NOTE: This re-parses the text. For already-parsed OCR results,
    use process_receipt_from_ocr_result() instead to avoid duplicate parsing.
    """
    parsed = parse_receipt_text(text)
    amount = parsed["amount"]
    category = parsed["category"]
    date_str = parsed["date"]

    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid date format in receipt '{date_str}': {str(e)}. Using today's date.")
        parsed_date = datetime.today().date()
    except Exception as e:
        logger.error(f"Unexpected error parsing date '{date_str}': {str(e)}. Using today's date.")
        parsed_date = datetime.today().date()

    # Create transaction
    result = record_expense(
        db=db,
        user_id=user_id,
        day=parsed_date,
        category=category,
        amount=amount,
        description="Imported from receipt",
    )

    return {"parsed": parsed, "status": "created", "transaction": result}


def process_receipt_from_ocr_result(user_id: int, ocr_result: dict, db) -> dict:
    """
    Efficient method: Create transaction from already-parsed OCR result.

    Args:
        user_id: User ID
        ocr_result: Already-parsed OCR result with merchant, amount, category, date
        db: Database session

    Returns:
        Dictionary with transaction result and metadata
    """
    # Extract data from OCR result (supports both naming conventions)
    merchant = ocr_result.get("store", ocr_result.get("merchant", "Unknown Store"))
    amount = ocr_result.get("amount", ocr_result.get("total", 0.0))
    category = ocr_result.get("category_hint", ocr_result.get("category", "other"))
    date_str = ocr_result.get("date", "")
    confidence = ocr_result.get("confidence", 0.0)

    # Parse date
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Invalid date format in OCR result '{date_str}': {str(e)}. Using today's date."
        )
        parsed_date = datetime.today().date()
    except Exception as e:
        logger.error(
            f"Unexpected error parsing date '{date_str}': {str(e)}. Using today's date."
        )
        parsed_date = datetime.today().date()

    # Create more detailed description
    description = f"Receipt from {merchant}"
    if confidence > 0:
        description += f" (confidence: {int(confidence * 100)}%)"

    # Create transaction
    result = record_expense(
        db=db,
        user_id=user_id,
        day=parsed_date,
        category=category,
        amount=amount,
        description=description,
    )

    return {
        "parsed": ocr_result,
        "status": "created",
        "transaction": result,
        "confidence": confidence,
        "merchant": merchant
    }
