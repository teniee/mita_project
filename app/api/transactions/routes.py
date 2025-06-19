from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.transactions.schemas import TxnIn, TxnOut

# isort: off
from app.api.transactions.services import (
    add_transaction,
    list_user_transactions,
    parse_receipt_image,
)

# isort: on
from app.core.session import get_db
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/", response_model=TxnOut)
async def create_transaction(
    txn: TxnIn,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    return success_response(add_transaction(user, txn, db))


@router.get("/", response_model=List[TxnOut])
async def get_transactions(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    category: Optional[str] = None,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
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
async def upload_receipt(
    receipt: UploadFile = File(...),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
):
    result = parse_receipt_image(
        receipt, is_premium_user=getattr(user, "is_premium", False)
    )
    return success_response(result)
