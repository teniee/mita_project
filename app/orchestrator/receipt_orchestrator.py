from datetime import datetime

from app.ocr.ocr_parser import parse_receipt_text
from app.services.expense_tracker import record_expense


def process_receipt_from_text(user_id: int, text: str, db) -> dict:
    parsed = parse_receipt_text(text)
    amount = parsed["amount"]
    category = parsed["category"]
    date_str = parsed["date"]

    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
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
