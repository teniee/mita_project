
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.services.auth_dependency import get_current_user
from app.db.models import User
from app.ocr.google_ocr import extract_text_from_image_google
from app.orchestrator.receipt_orchestrator import process_receipt_from_text

router = APIRouter(prefix="/transactions", tags=["ocr-google"])

@router.post("/ocr/google")
def create_transaction_google_ocr(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user.is_premium:
        raise HTTPException(status_code=403, detail="Google OCR доступен только для премиум-пользователей")

    file_bytes = file.file.read()
    text = extract_text_from_image_google(file_bytes)
    return process_receipt_from_text(user_id=user.id, text=text, db=db)
