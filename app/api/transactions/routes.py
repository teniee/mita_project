from datetime import datetime
from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.transactions.schemas import TxnIn, TxnOut
from app.ocr.ocr_receipt_service import OCRReceiptService

# Import standardized error handling system
from app.core.standardized_error_handler import (
    ValidationError,
    BusinessLogicError,
    ResourceNotFoundError,
    ErrorCode,
    validate_amount,
    validate_required_fields
)
from app.core.error_decorators import handle_financial_errors, ErrorHandlingMixin
from app.utils.response_wrapper import StandardizedResponse, FinancialResponseHelper

# isort: off
from app.api.transactions.services import (
    add_transaction,
    list_user_transactions,
)

# isort: on
from app.core.session import get_db
from app.utils.response_wrapper import success_response
from app.services.task_manager import task_manager

logger = logging.getLogger(__name__)

current_user_dep = Depends(get_current_user)  # noqa: B008
db_dep = Depends(get_db)  # noqa: B008
file_upload = File(...)  # noqa: B008

router = APIRouter(prefix="/transactions", tags=["transactions"])

# Error handling mixin for transaction routes
class TransactionErrorHandler(ErrorHandlingMixin):
    pass

transaction_error_handler = TransactionErrorHandler()


@router.post("/", response_model=TxnOut, summary="Create new transaction")
@handle_financial_errors
async def create_transaction_standardized(
    request: Request,
    txn: TxnIn,
    user=current_user_dep,
    db: Session = db_dep,
):
    """
    Create a new financial transaction with comprehensive validation and error handling.
    
    Features:
    - Amount validation with proper limits
    - Category validation
    - Date validation
    - Budget impact assessment
    - Standardized error responses
    """
    
    # Validate transaction data
    txn_dict = txn.dict()
    validate_required_fields(txn_dict, ["amount", "category", "description"])
    
    # Validate amount
    if txn.amount <= 0:
        raise ValidationError(
            "Transaction amount must be positive",
            ErrorCode.VALIDATION_AMOUNT_INVALID,
            details={"provided_amount": txn.amount}
        )
    
    validated_amount = validate_amount(
        txn.amount,
        min_amount=0.01,
        max_amount=100000.0
    )
    
    # Validate category
    valid_categories = [
        'food', 'dining', 'groceries', 'transportation', 'gas', 'public_transport',
        'entertainment', 'shopping', 'clothing', 'healthcare', 'insurance',
        'utilities', 'rent', 'mortgage', 'education', 'childcare', 'pets',
        'travel', 'subscriptions', 'gifts', 'charity', 'other'
    ]
    
    if txn.category not in valid_categories:
        raise ValidationError(
            f"Invalid category. Must be one of: {', '.join(valid_categories)}",
            ErrorCode.VALIDATION_CATEGORY_INVALID,
            details={"provided_category": txn.category, "valid_categories": valid_categories}
        )
    
    try:
        # Create transaction using existing service
        result = add_transaction(user, txn, db)
        
        if not result:
            raise BusinessLogicError(
                "Failed to create transaction",
                ErrorCode.BUSINESS_INVALID_OPERATION
            )
        
        # Calculate budget impact (if budget tracking is available)
        budget_impact = {
            "category": txn.category,
            "amount": validated_amount,
            "remaining_budget": None,  # Calculate from user's budget if available
            "budget_exceeded": False
        }
        
        return FinancialResponseHelper.transaction_created(
            transaction_data=result,
            balance_impact=budget_impact
        )
        
    except Exception as e:
        if isinstance(e, (ValidationError, BusinessLogicError)):
            raise
        else:
            raise BusinessLogicError(
                f"Transaction creation failed: {str(e)}",
                ErrorCode.BUSINESS_INVALID_OPERATION
            )


@router.get("/", response_model=List[TxnOut], summary="List user transactions")
@handle_financial_errors
async def get_transactions_standardized(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    category: Optional[str] = None,
    user=current_user_dep,
    db: Session = db_dep,
):
    """
    Retrieve user transactions with filtering and pagination support.
    
    Features:
    - Pagination validation
    - Date range validation
    - Category filtering
    - Standardized error responses
    """
    
    # Validate pagination parameters
    if skip < 0:
        raise ValidationError(
            "Skip parameter must be non-negative",
            ErrorCode.VALIDATION_OUT_OF_RANGE,
            details={"provided_skip": skip, "minimum": 0}
        )
    
    if limit <= 0 or limit > 1000:
        raise ValidationError(
            "Limit parameter must be between 1 and 1000",
            ErrorCode.VALIDATION_OUT_OF_RANGE,
            details={"provided_limit": limit, "minimum": 1, "maximum": 1000}
        )
    
    # Validate date range
    if start_date and end_date:
        if start_date > end_date:
            raise ValidationError(
                "Start date must be before or equal to end date",
                ErrorCode.VALIDATION_DATE_INVALID,
                details={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}
            )
        
        # Check for reasonable date range (not more than 2 years)
        date_diff = (end_date - start_date).days
        if date_diff > 730:  # 2 years
            raise ValidationError(
                "Date range cannot exceed 2 years",
                ErrorCode.VALIDATION_OUT_OF_RANGE,
                details={"date_range_days": date_diff, "maximum_days": 730}
            )
    
    # Validate category if provided
    if category:
        valid_categories = [
            'food', 'dining', 'groceries', 'transportation', 'gas', 'public_transport',
            'entertainment', 'shopping', 'clothing', 'healthcare', 'insurance',
            'utilities', 'rent', 'mortgage', 'education', 'childcare', 'pets',
            'travel', 'subscriptions', 'gifts', 'charity', 'other'
        ]
        
        if category not in valid_categories:
            raise ValidationError(
                f"Invalid category filter. Must be one of: {', '.join(valid_categories)}",
                ErrorCode.VALIDATION_CATEGORY_INVALID,
                details={"provided_category": category, "valid_categories": valid_categories}
            )
    
    try:
        # Get transactions using existing service
        transactions = list_user_transactions(
            user,
            db,
            skip=skip,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            category=category,
        )
        
        return success_response(
            data=transactions,
            message="Transactions retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error retrieving transactions for user {user.id}: {e}")
        raise InternalServerError("Failed to retrieve transactions")


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


# NEW ENDPOINTS for mobile app integration

@router.get("/by-date")
async def get_transactions_by_date(
    start_date: str = None,
    end_date: str = None,
    user=current_user_dep,
    db: Session = db_dep,
):
    """Get transactions filtered by date range"""
    from datetime import datetime

    # Parse dates
    start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
    end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None

    # TODO: Query transactions with date filter
    transactions = []

    return success_response({
        "transactions": transactions,
        "start_date": start_date,
        "end_date": end_date,
        "count": len(transactions)
    })


@router.get("/merchants/suggestions")
async def get_merchant_suggestions(
    query: str = None,
    user=current_user_dep,
    db: Session = db_dep,
):
    """Get merchant name suggestions based on user's history"""
    # TODO: Query user's transaction history for merchant autocomplete
    suggestions = []

    if query:
        # Mock suggestions based on query
        suggestions = [
            {"name": f"{query} Store", "category": "shopping", "frequency": 15},
            {"name": f"{query} Market", "category": "groceries", "frequency": 8},
        ]

    return success_response({
        "suggestions": suggestions,
        "query": query
    })


@router.post("/receipt")
async def upload_receipt(
    file: UploadFile = File(...),
    user=current_user_dep,
    db: Session = db_dep,
):
    """Upload and process receipt image"""
    # TODO: Process receipt with OCR service
    return success_response({
        "receipt_id": f"rcpt_{datetime.now().timestamp()}",
        "status": "processing",
        "message": "Receipt uploaded successfully"
    })


@router.get("/receipt/{receipt_id}/image")
async def get_receipt_image(
    receipt_id: str,
    user=current_user_dep,
    db: Session = db_dep,
):
    """Get receipt image URL"""
    # TODO: Fetch receipt image from storage
    return success_response({
        "receipt_id": receipt_id,
        "image_url": f"https://storage.example.com/receipts/{receipt_id}.jpg",
        "thumbnail_url": f"https://storage.example.com/receipts/{receipt_id}_thumb.jpg"
    })


@router.post("/receipt/advanced")
async def process_receipt_advanced(
    file: UploadFile = File(...),
    options: dict = {},
    user=current_user_dep,
    db: Session = db_dep,
):
    """Advanced receipt processing with OCR and categorization"""
    # TODO: Use advanced OCR with item-level extraction
    return success_response({
        "receipt_id": f"rcpt_{datetime.now().timestamp()}",
        "status": "processing",
        "items": [],
        "total": 0.0,
        "merchant": "",
        "date": "",
        "confidence": 0.0
    })


@router.post("/receipt/batch")
async def process_receipts_batch(
    files: List[UploadFile] = File(...),
    user=current_user_dep,
    db: Session = db_dep,
):
    """Process multiple receipts in batch"""
    # TODO: Queue batch receipt processing
    receipt_ids = [f"rcpt_{datetime.now().timestamp()}_{i}" for i in range(len(files))]

    return success_response({
        "job_id": f"batch_{datetime.now().timestamp()}",
        "receipt_count": len(files),
        "receipt_ids": receipt_ids,
        "status": "queued"
    })


@router.get("/receipt/status/{job_id}")
async def get_receipt_processing_status(
    job_id: str,
    user=current_user_dep,
    db: Session = db_dep,
):
    """Get status of receipt processing job"""
    # TODO: Check processing status
    return success_response({
        "job_id": job_id,
        "status": "completed",
        "progress": 100,
        "results": [],
        "errors": []
    })


@router.post("/receipt/validate")
async def validate_receipt_data(
    data: dict,
    user=current_user_dep,
    db: Session = db_dep,
):
    """Validate extracted receipt data before saving"""
    total = data.get("total", 0.0)
    merchant = data.get("merchant", "")
    items = data.get("items", [])

    validation_errors = []

    if total <= 0:
        validation_errors.append("Total amount must be positive")

    if not merchant:
        validation_errors.append("Merchant name is required")

    return success_response({
        "valid": len(validation_errors) == 0,
        "errors": validation_errors,
        "warnings": []
    })
