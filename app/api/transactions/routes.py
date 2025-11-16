from datetime import datetime
from typing import List, Optional
import logging

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Request
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload, joinedload

from app.api.dependencies import get_current_user
from app.api.transactions.schemas import TxnIn, TxnOut, TxnUpdate
from app.ocr.ocr_receipt_service import OCRReceiptService

# Import standardized error handling system
from app.core.standardized_error_handler import (
    ValidationError,
    BusinessLogicError,
    ResourceNotFoundError,
    InternalServerError,
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
    get_transaction_by_id,
    update_transaction,
    delete_transaction,
)

# isort: on
from app.core.async_session import get_async_db
from app.utils.response_wrapper import success_response
from app.services.task_manager import task_manager

logger = logging.getLogger(__name__)

current_user_dep = Depends(get_current_user)  # noqa: B008
db_dep = Depends(get_async_db)  # noqa: B008
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
    db: AsyncSession = db_dep,
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
    db: AsyncSession = db_dep,
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
    db: AsyncSession = db_dep,
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
    db: AsyncSession = db_dep,
):
    """Get transactions filtered by date range"""
    from datetime import datetime

    # Parse dates
    start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
    end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None

    # Query transactions with date filter using REAL database query
    from app.db.models.transaction import Transaction

    query_stmt = select(Transaction).options(
        joinedload(Transaction.user),
        joinedload(Transaction.goal)
    ).where(Transaction.user_id == user.id)

    if start:
        query_stmt = query_stmt.where(Transaction.spent_at >= start)
    if end:
        query_stmt = query_stmt.where(Transaction.spent_at <= end)

    result = await db.execute(query_stmt.order_by(Transaction.spent_at.desc()))
    txns = result.unique().scalars().all()

    transactions = [
        {
            "id": txn.id,
            "amount": float(txn.amount) if txn.amount else 0.0,
            "category": txn.category,
            "description": txn.description,
            "spent_at": txn.spent_at.isoformat() if txn.spent_at else None,
            "created_at": txn.created_at.isoformat() if txn.created_at else None
        }
        for txn in txns
    ]

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
    db: AsyncSession = db_dep,
):
    """Get merchant name suggestions based on user's history"""
    from app.db.models.transaction import Transaction

    # Query user's transaction history for merchant autocomplete
    query_stmt = select(
        Transaction.description,
        Transaction.category,
        func.count(Transaction.id).label('frequency')
    ).where(Transaction.user_id == user.id)

    if query:
        query_stmt = query_stmt.where(Transaction.description.ilike(f'%{query}%'))

    query_stmt = query_stmt.group_by(
        Transaction.description,
        Transaction.category
    ).order_by(func.count(Transaction.id).desc()).limit(10)

    result = await db.execute(query_stmt)
    merchants = result.all()

    suggestions = [
        {
            "name": merchant.description,
            "category": merchant.category,
            "frequency": merchant.frequency
        }
        for merchant in merchants
    ]

    return success_response({
        "suggestions": suggestions,
        "query": query
    })


# REMOVED DUPLICATE: /receipt endpoint already defined at line 228
# This was causing FastAPI routing conflict


@router.get("/receipt/{receipt_id}/image")
async def get_receipt_image(
    receipt_id: str,
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """Get receipt image URL"""
    from app.db.models import OCRJob

    # Query OCR job to get image path
    result = await db.execute(
        select(OCRJob).where(
            and_(
                OCRJob.job_id == receipt_id,
                OCRJob.user_id == user.id
            )
        )
    )
    ocr_job = result.scalar_one_or_none()

    if not ocr_job or not ocr_job.image_url:
        return success_response({
            "receipt_id": receipt_id,
            "image_url": None,
            "thumbnail_url": None,
            "error": "Receipt image not found"
        })

    return success_response({
        "receipt_id": receipt_id,
        "image_url": ocr_job.image_url or f"file://{ocr_job.image_path}",
        "thumbnail_url": ocr_job.image_url or f"file://{ocr_job.image_path}"
    })


@router.post("/receipt/advanced")
async def process_receipt_advanced(
    file: UploadFile = File(...),
    options: dict = {},
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """Advanced receipt processing with OCR and categorization"""
    import tempfile
    import os
    from app.db.models import OCRJob

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
        content = await file.read()
        temp.write(content)
        temp_path = temp.name

    try:
        # Process receipt with REAL OCR service
        ocr_service = OCRReceiptService()
        result = ocr_service.process_image(temp_path)

        job_id = f"rcpt_{datetime.now().timestamp()}"

        # Store in database
        ocr_job = OCRJob(
            job_id=job_id,
            user_id=user.id,
            status="completed",
            progress=100.0,
            image_path=temp_path,
            store_name=result.get("store", ""),
            amount=result.get("amount", 0.0),
            date=result.get("date", ""),
            category_hint=result.get("category_hint", ""),
            confidence=result.get("confidence", 0.0),
            raw_result=result,
            completed_at=datetime.utcnow()
        )
        db.add(ocr_job)
        await db.commit()

        return success_response({
            "receipt_id": job_id,
            "status": "completed",
            "items": result.get("items", []),
            "total": result.get("amount", 0.0),
            "merchant": result.get("store", ""),
            "date": result.get("date", ""),
            "confidence": result.get("confidence", 0.0)
        })
    except Exception as e:
        logger.error(f"Advanced receipt processing failed: {e}")
        return success_response({
            "receipt_id": f"rcpt_{datetime.now().timestamp()}",
            "status": "failed",
            "items": [],
            "total": 0.0,
            "merchant": "",
            "date": "",
            "confidence": 0.0,
            "error": str(e)
        })
    finally:
        # Cleanup
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception:
            pass


@router.post("/receipt/batch")
async def process_receipts_batch(
    files: List[UploadFile] = File(...),
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """Process multiple receipts in batch"""
    import tempfile
    import os
    from app.db.models import OCRJob

    batch_id = f"batch_{datetime.now().timestamp()}"
    receipt_ids = []
    results = []

    for idx, file in enumerate(files):
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
            content = await file.read()
            temp.write(content)
            temp_path = temp.name

        try:
            # Process each receipt with OCR service
            ocr_service = OCRReceiptService()
            result = ocr_service.process_image(temp_path)

            receipt_id = f"rcpt_{datetime.now().timestamp()}_{idx}"
            receipt_ids.append(receipt_id)

            # Store in database
            ocr_job = OCRJob(
                job_id=receipt_id,
                user_id=user.id,
                status="completed",
                progress=100.0,
                image_path=temp_path,
                store_name=result.get("store", ""),
                amount=result.get("amount", 0.0),
                date=result.get("date", ""),
                category_hint=result.get("category_hint", ""),
                confidence=result.get("confidence", 0.0),
                raw_result=result,
                completed_at=datetime.utcnow()
            )
            db.add(ocr_job)

            results.append({
                "receipt_id": receipt_id,
                "status": "completed",
                "store": result.get("store", ""),
                "amount": result.get("amount", 0.0)
            })

        except Exception as e:
            logger.error(f"Batch receipt processing failed for file {idx}: {e}")
            receipt_id = f"rcpt_{datetime.now().timestamp()}_{idx}"
            receipt_ids.append(receipt_id)
            results.append({
                "receipt_id": receipt_id,
                "status": "failed",
                "error": str(e)
            })
        finally:
            # Cleanup
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception:
                pass

    await db.commit()

    return success_response({
        "job_id": batch_id,
        "receipt_count": len(files),
        "receipt_ids": receipt_ids,
        "status": "completed",
        "results": results
    })


@router.get("/receipt/status/{job_id}")
async def get_receipt_processing_status(
    job_id: str,
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """Get status of receipt processing job"""
    from app.db.models import OCRJob

    # Check if it's a batch job
    if job_id.startswith("batch_"):
        # Query all jobs that match the batch
        result = await db.execute(
            select(OCRJob).where(
                OCRJob.user_id == user.id,
                OCRJob.job_id.like(f"rcpt_{job_id.split('_')[1]}_%")
            )
        )
        ocr_jobs = result.scalars().all()

        if not ocr_jobs:
            return success_response({
                "job_id": job_id,
                "status": "not_found",
                "progress": 0,
                "results": [],
                "errors": ["Batch job not found"]
            })

        completed_count = sum(1 for j in ocr_jobs if j.status == "completed")
        progress = int((completed_count / len(ocr_jobs)) * 100) if ocr_jobs else 0

        results = [{
            "receipt_id": j.job_id,
            "status": j.status,
            "store": j.store_name,
            "amount": float(j.amount) if j.amount else 0.0
        } for j in ocr_jobs]

        errors = [j.error_message for j in ocr_jobs if j.error_message]

        return success_response({
            "job_id": job_id,
            "status": "completed" if completed_count == len(ocr_jobs) else "processing",
            "progress": progress,
            "results": results,
            "errors": errors
        })
    else:
        # Single job query
        result = await db.execute(
            select(OCRJob).where(
                and_(
                    OCRJob.job_id == job_id,
                    OCRJob.user_id == user.id
                )
            )
        )
        ocr_job = result.scalar_one_or_none()

        if not ocr_job:
            return success_response({
                "job_id": job_id,
                "status": "not_found",
                "progress": 0,
                "results": [],
                "errors": ["Job not found"]
            })

        return success_response({
            "job_id": job_id,
            "status": ocr_job.status,
            "progress": int(ocr_job.progress),
            "results": [{
                "receipt_id": ocr_job.job_id,
                "store": ocr_job.store_name,
                "amount": float(ocr_job.amount) if ocr_job.amount else 0.0
            }] if ocr_job.status == "completed" else [],
            "errors": [ocr_job.error_message] if ocr_job.error_message else []
        })


@router.post("/receipt/validate")
async def validate_receipt_data(
    data: dict,
    user=current_user_dep,
    db: AsyncSession = db_dep,
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


# CRUD endpoints for individual transactions
@router.get("/{transaction_id}", response_model=TxnOut, summary="Get transaction by ID")
@handle_financial_errors
async def get_transaction(
    request: Request,
    transaction_id: str,
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """Get a specific transaction by ID"""
    from uuid import UUID

    try:
        txn_uuid = UUID(transaction_id)
    except ValueError:
        raise ValidationError(
            "Invalid transaction ID format",
            ErrorCode.VALIDATION_ID_INVALID,
            details={"transaction_id": transaction_id}
        )

    txn = get_transaction_by_id(user, txn_uuid, db)

    if not txn:
        raise ResourceNotFoundError(
            f"Transaction {transaction_id} not found",
            details={"transaction_id": transaction_id}
        )

    return success_response(txn, message="Transaction retrieved successfully")


@router.put("/{transaction_id}", response_model=TxnOut, summary="Update transaction")
@handle_financial_errors
async def update_transaction_endpoint(
    request: Request,
    transaction_id: str,
    txn_update: TxnUpdate,
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """Update an existing transaction"""
    from uuid import UUID

    try:
        txn_uuid = UUID(transaction_id)
    except ValueError:
        raise ValidationError(
            "Invalid transaction ID format",
            ErrorCode.VALIDATION_ID_INVALID,
            details={"transaction_id": transaction_id}
        )

    updated_txn = update_transaction(user, txn_uuid, txn_update, db)

    if not updated_txn:
        raise ResourceNotFoundError(
            f"Transaction {transaction_id} not found",
            details={"transaction_id": transaction_id}
        )

    return FinancialResponseHelper.transaction_updated(updated_txn)


@router.delete("/{transaction_id}", summary="Delete transaction")
@handle_financial_errors
async def delete_transaction_endpoint(
    request: Request,
    transaction_id: str,
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """Delete a transaction"""
    from uuid import UUID

    try:
        txn_uuid = UUID(transaction_id)
    except ValueError:
        raise ValidationError(
            "Invalid transaction ID format",
            ErrorCode.VALIDATION_ID_INVALID,
            details={"transaction_id": transaction_id}
        )

    success = delete_transaction(user, txn_uuid, db)

    if not success:
        raise ResourceNotFoundError(
            f"Transaction {transaction_id} not found",
            details={"transaction_id": transaction_id}
        )

    return success_response(
        data={"deleted": True, "transaction_id": transaction_id},
        message="Transaction deleted successfully"
    )


# ============================================================================
# SPENDING PREVENTION ENDPOINTS
# Real-time budget validation BEFORE transaction creation
# Implements MITA's core differentiator: preventive overspending protection
# ============================================================================

from pydantic import BaseModel, Field
from decimal import Decimal
from app.services.spending_prevention_service import SpendingPreventionService


class AffordabilityCheckRequest(BaseModel):
    """Request to check if user can afford a transaction"""
    category: str = Field(..., description="Transaction category (e.g., 'food', 'transport')")
    amount: Decimal = Field(..., gt=0, description="Transaction amount (must be positive)")
    date: Optional[datetime] = Field(None, description="Transaction date (defaults to today)")

    class Config:
        json_schema_extra = {
            "example": {
                "category": "food",
                "amount": 45.50,
                "date": "2025-11-06T14:30:00"
            }
        }


@router.post(
    "/check-affordability",
    summary="Check if user can afford transaction",
    description="""
    **Real-time spending prevention**: Check if user can afford a transaction BEFORE creating it.
    
    This endpoint provides:
    - Current budget status for category
    - Warning level (safe/caution/danger/blocked)
    - Remaining budget after transaction
    - Alternative categories with available budget
    - Actionable suggestions to stay within budget
    
    **Use this BEFORE calling POST /transactions to prevent overspending!**
    
    **Warning Levels:**
    - `safe` (green): Under 70% of budget used
    - `caution` (yellow): 70-90% of budget used
    - `danger` (orange): 90-100% of budget used
    - `blocked` (red): Over budget limit
    
    **Example Response:**
    ```json
    {
        "can_afford": false,
        "warning_level": "blocked",
        "daily_budget": 50.00,
        "current_spent": 35.00,
        "remaining_budget": -30.50,
        "overage": 30.50,
        "impact_message": "🔴 This will exceed your food budget by $30.50!",
        "alternative_categories": [
            {"category": "entertainment", "available": 75.00}
        ],
        "suggestions": [
            "Use 'entertainment' category instead ($75.00 available)",
            "Reduce amount to $15.00 to stay within budget",
            "Wait until tomorrow when daily budget resets"
        ]
    }
    ```
    """,
    responses={
        200: {
            "description": "Affordability check completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "can_afford": True,
                            "warning_level": "caution",
                            "daily_budget": 50.00,
                            "current_spent": 35.00,
                            "remaining_budget": 5.50,
                            "percentage_used": 80.9,
                            "impact_message": "⚠️ This will use 81% of your food budget. $5.50 remaining.",
                            "suggestions": ["This will leave only $5.50 for food today"]
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid request (negative amount, invalid category)"},
        401: {"description": "Unauthorized - user not authenticated"},
        429: {"description": "Rate limit exceeded"}
    },
    dependencies=[Depends(RateLimiter(times=60, seconds=60))]  # Max 60 checks per minute
)
@handle_financial_errors
async def check_transaction_affordability(
    request: Request,
    check_request: AffordabilityCheckRequest,
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """
    Check if user can afford transaction BEFORE creating it
    Returns budget status, warnings, and suggestions
    """
    # Validate category
    valid_categories = [
        'food', 'dining', 'groceries',
        'transportation', 'gas', 'public_transport',
        'entertainment', 'shopping', 'clothing',
        'healthcare', 'insurance',
        'utilities', 'rent', 'mortgage',
        'education', 'childcare', 'pets',
        'travel', 'subscriptions', 'gifts', 'charity', 'other'
    ]
    
    if check_request.category not in valid_categories:
        raise ValidationError(
            f"Invalid category '{check_request.category}'",
            ErrorCode.VALIDATION_INVALID_VALUE,
            details={
                "category": check_request.category,
                "valid_categories": valid_categories
            }
        )

    # Validate amount
    if check_request.amount <= 0:
        raise ValidationError(
            "Transaction amount must be positive",
            ErrorCode.VALIDATION_INVALID_VALUE,
            details={"amount": float(check_request.amount)}
        )

    # Initialize prevention service
    prevention_service = SpendingPreventionService(db, user.id)

    # Check affordability
    result = prevention_service.check_affordability(
        category=check_request.category,
        amount=check_request.amount,
        transaction_date=check_request.date
    )

    # Return standardized response
    return success_response(
        data=result,
        message=result['impact_message']
    )


@router.get(
    "/budget-status",
    summary="Get current budget status for all categories",
    description="""
    Get real-time budget status for ALL categories for today.
    
    Useful for:
    - Dashboard overview
    - Budget summary widgets
    - Category selection UI (show which categories have budget available)
    
    **Example Response:**
    ```json
    {
        "food": {
            "daily_budget": 50.00,
            "spent": 35.00,
            "remaining": 15.00,
            "percentage_used": 70.0,
            "status": "caution"
        },
        "transportation": {
            "daily_budget": 30.00,
            "spent": 5.00,
            "remaining": 25.00,
            "percentage_used": 16.7,
            "status": "safe"
        }
    }
    ```
    """,
    responses={
        200: {"description": "Budget status retrieved successfully"},
        401: {"description": "Unauthorized"}
    },
    dependencies=[Depends(RateLimiter(times=120, seconds=60))]  # Max 120 requests per minute
)
@handle_financial_errors
async def get_budget_status(
    request: Request,
    date: Optional[str] = None,  # Format: YYYY-MM-DD
    user=current_user_dep,
    db: AsyncSession = db_dep,
):
    """
    Get current budget status for all categories
    Useful for dashboard and category selection screens
    """
    # Parse date if provided
    transaction_date = None
    if date:
        try:
            transaction_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError(
                "Invalid date format. Use YYYY-MM-DD",
                ErrorCode.VALIDATION_INVALID_VALUE,
                details={"date": date, "expected_format": "YYYY-MM-DD"}
            )

    # Initialize prevention service
    prevention_service = SpendingPreventionService(db, user.id)

    # Get all category status
    status = prevention_service.get_all_category_status(transaction_date)

    return success_response(
        data=status,
        message=f"Budget status for {len(status)} categories"
    )
