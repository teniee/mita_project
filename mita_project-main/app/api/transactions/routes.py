from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.transactions.schemas import TxnIn, TxnOut
from app.ocr.ocr_receipt_service import OCRReceiptService

# isort: off
from app.api.transactions.services import (
    add_transaction,
    list_user_transactions,
)

# isort: on
from app.core.session import get_db
from app.utils.response_wrapper import success_response

current_user_dep = Depends(get_current_user)  # noqa: B008
db_dep = Depends(get_db)  # noqa: B008
file_upload = File(...)  # noqa: B008

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/", response_model=TxnOut)
async def create_transaction(
    txn: TxnIn,
    user=current_user_dep,
    db: Session = db_dep,
):
    return success_response(add_transaction(user, txn, db))


@router.get("/", response_model=List[TxnOut])
async def get_transactions(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    category: Optional[str] = None,
    user=current_user_dep,
    db: Session = db_dep,
):
    return success_response(
        list_user_transactions(
            user,
            db,
            skip=skip,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            category=category,
        )
    )


@router.post("/receipt")
async def process_receipt(
    file: UploadFile = file_upload,
    user=current_user_dep,
    db: Session = db_dep,
):
    """Extract and parse receipt data."""
    import os
    import tempfile

    temp = tempfile.NamedTemporaryFile(delete=False)
    try:
        temp.write(await file.read())
        temp.close()
        service = OCRReceiptService()
        data = service.process_image(temp.name)
    finally:
        try:
            os.unlink(temp.name)
        except Exception:
            pass

    return success_response(data)
