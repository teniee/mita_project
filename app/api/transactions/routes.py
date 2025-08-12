from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi_limiter.depends import RateLimiter
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
from app.services.task_manager import task_manager

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


@router.post(
    "/receipt",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def process_receipt(
    file: UploadFile = file_upload,
    user=current_user_dep,
    db: Session = db_dep,
):
    """
    Extract and parse receipt data using async OCR processing.
    Returns task ID for tracking processing status.
    """
    import os
    import tempfile
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400, 
            detail="File must be an image (JPEG, PNG, etc.)"
        )
    
    # Save uploaded file to temporary location
    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    try:
        content = await file.read()
        temp.write(content)
        temp.close()
        
        # Check if user is premium (simplified check)
        is_premium = hasattr(user, 'premium_until') and getattr(user, 'premium_until', None)
        if is_premium and isinstance(is_premium, datetime):
            is_premium = is_premium > datetime.utcnow()
        else:
            is_premium = False
        
        # Submit OCR task for async processing
        task_info = task_manager.submit_ocr_task(
            user_id=user.id,
            image_path=temp.name,
            is_premium_user=is_premium
        )
        
        return success_response({
            'task_id': task_info.task_id,
            'status': task_info.status.value,
            'estimated_completion': task_info.estimated_completion,
            'message': 'Receipt processing started. Use /tasks/{task_id} to check status.'
        })
        
    except Exception as e:
        # Clean up temp file on error
        try:
            if os.path.exists(temp.name):
                os.unlink(temp.name)
        except Exception:
            pass
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process receipt: {str(e)}"
        )
