"""
OCR API Router
Receipt processing, enhancement, and categorization endpoints
"""
import os
import tempfile
import logging
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models.user import User
from app.utils.response_wrapper import success_response
from app.ocr.ocr_receipt_service import OCRReceiptService
from app.categorization.receipt_categorization_service import ReceiptCategorizationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/process")
async def process_receipt_ocr(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process receipt image with OCR and extract structured data.
    """
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
        content = await file.read()
        temp.write(content)
        temp_path = temp.name

    try:
        # Process with REAL OCR service
        ocr_service = OCRReceiptService()
        result = ocr_service.process_image(temp_path)

        job_id = f"ocr_{user.id}_{int(datetime.now().timestamp())}"

        # Store result in database for status checking
        from app.db.models import OCRJob
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
        db.commit()

        return success_response({
            "job_id": job_id,
            "status": "completed",
            "result": {
                "store": result.get("store", ""),
                "amount": result.get("amount", 0.0),
                "date": result.get("date", ""),
                "category_hint": result.get("category_hint", ""),
                "confidence": result.get("confidence", 0.0)
            },
            "processed_at": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        return success_response({
            "job_id": f"ocr_{user.id}_{int(datetime.now().timestamp())}",
            "status": "failed",
            "error": str(e)
        })
    finally:
        # Cleanup temp file
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception:
            pass


@router.post("/categorize")
async def categorize_receipt_data(
    data: Dict[str, Any],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Categorize receipt based on merchant name and extracted data.
    """
    try:
        merchant = data.get("merchant", data.get("store", ""))
        amount = data.get("amount", 0.0)
        items = data.get("items", [])

        # Use REAL categorization service
        categorization_service = ReceiptCategorizationService()
        category = categorization_service.categorize(merchant, amount, items)

        return success_response({
            "category": category,
            "confidence": 0.85,
            "merchant": merchant,
            "suggestions": [category]
        })

    except Exception as e:
        logger.error(f"Categorization failed: {e}")
        return success_response({
            "category": "other",
            "confidence": 0.0,
            "error": str(e)
        })


@router.post("/enhance")
async def enhance_receipt_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Enhance receipt image quality for better OCR results.
    """
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp:
        content = await file.read()
        temp.write(content)
        temp_path = temp.name

    try:
        # Enhance image using PIL
        from PIL import Image, ImageEnhance

        image = Image.open(temp_path)

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

        # Convert to grayscale for better OCR
        image = image.convert('L')

        # Save enhanced image
        enhanced_path = temp_path.replace('.jpg', '_enhanced.jpg')
        image.save(enhanced_path, 'JPEG', quality=95)

        # Read enhanced file
        with open(enhanced_path, 'rb') as f:
            enhanced_content = f.read()

        # Cleanup
        os.unlink(temp_path)
        os.unlink(enhanced_path)

        return success_response({
            "enhanced": True,
            "message": "Image enhanced successfully",
            "enhancements_applied": ["contrast", "sharpness", "grayscale"],
            "size": len(enhanced_content)
        })

    except Exception as e:
        logger.error(f"Image enhancement failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Image enhancement failed: {str(e)}"
        )
    finally:
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception:
            pass


@router.get("/status/{ocr_job_id}")
async def get_ocr_job_status(
    ocr_job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get status of OCR processing job.
    """
    from app.db.models import OCRJob

    try:
        # Query OCRJob from database
        ocr_job = db.query(OCRJob).filter(
            and_(
                OCRJob.job_id == ocr_job_id,
                OCRJob.user_id == user.id
            )
        ).first()

        if not ocr_job:
            return success_response({
                "job_id": ocr_job_id,
                "status": "not_found",
                "progress": 0,
                "error": "Job not found or does not belong to user"
            })

        return success_response({
            "job_id": ocr_job_id,
            "status": ocr_job.status,
            "progress": float(ocr_job.progress),
            "created_at": ocr_job.created_at.isoformat() if ocr_job.created_at else None,
            "completed_at": ocr_job.completed_at.isoformat() if ocr_job.completed_at else None,
            "result": {
                "store": ocr_job.store_name,
                "amount": float(ocr_job.amount) if ocr_job.amount else 0.0,
                "date": ocr_job.date,
                "category_hint": ocr_job.category_hint,
                "confidence": float(ocr_job.confidence) if ocr_job.confidence else 0.0
            } if ocr_job.status == "completed" else None,
            "error": ocr_job.error_message if ocr_job.status == "failed" else None
        })

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return success_response({
            "job_id": ocr_job_id,
            "status": "error",
            "progress": 0,
            "error": str(e)
        })
