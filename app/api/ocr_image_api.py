from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.services.auth_dependency import get_current_user
from app.core.db import get_db
from app.ocr.tesseract_ocr import extract_text_from_image
from app.orchestrator.receipt_orchestrator import process_receipt_from_text

router = APIRouter(prefix="/transactions", tags=["ocr"])

@router.post("/ocr/image")
def create_transaction_from_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_bytes = file.file.read()
    text = extract_text_from_image(file_bytes)
    return process_receipt_from_text(user_id=user.id, text=text, db=db)
