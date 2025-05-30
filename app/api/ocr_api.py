from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.services.auth_dependency import get_current_user
from app.core.db import get_db
from app.orchestrator.receipt_orchestrator import process_receipt_from_text

router = APIRouter(prefix="/transactions", tags=["ocr"])

class ReceiptTextIn(BaseModel):
    text: str

@router.post("/ocr")
def create_transaction_from_receipt(
    input_data: ReceiptTextIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return process_receipt_from_text(user_id=user.id, text=input_data.text, db=db)
