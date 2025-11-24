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
from fastapi.responses import FileResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models.user import User
from app.utils.response_wrapper import success_response
from app.ocr.ocr_receipt_service import OCRReceiptService
from app.categorization.receipt_categorization_service import ReceiptCategorizationService
from app.storage.receipt_image_storage import get_receipt_storage

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

        # Save image to persistent storage
        storage = get_receipt_storage()
        storage_path, image_url = storage.save_image(temp_path, user.id, job_id)

        # Store result in database for status checking
        from app.db.models import OCRJob
        ocr_job = OCRJob(
            job_id=job_id,
            user_id=user.id,
            status="completed",
            progress=100.0,
            image_path=storage_path,
            image_url=image_url,
            store_name=result.get("store", result.get("merchant", "")),
            amount=result.get("amount", result.get("total", 0.0)),
            date=result.get("date", ""),
            category_hint=result.get("category_hint", result.get("category", "")),
            confidence=result.get("confidence", 0.0),
            raw_result=result,
            completed_at=datetime.utcnow()
        )
        db.add(ocr_job)
        db.commit()

        # Extract confidence scores
        confidence_scores = result.get("confidence_scores", {})
        fields_needing_review = result.get("fields_needing_review", [])

        return success_response({
            "job_id": job_id,
            "status": "completed",
            "result": {
                "merchant": result.get("merchant", result.get("store", "")),
                "amount": result.get("total", result.get("amount", 0.0)),
                "date": result.get("date", ""),
                "category": result.get("category", result.get("category_hint", "")),
                "items": result.get("items", []),
                "confidence": result.get("confidence", 0.0),
                "confidence_scores": confidence_scores,
                "fields_needing_review": fields_needing_review,
                "image_url": image_url
            },
            "processed_at": datetime.utcnow().isoformat()
        })

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"OCR processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {str(e)}"
        )
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
        amount = data.get("amount", data.get("total", 0.0))
        items = data.get("items", [])
        hint = data.get("category_hint", data.get("category", ""))

        # Use enhanced categorization service
        categorization_service = ReceiptCategorizationService()
        category = categorization_service.categorize(
            merchant=merchant,
            amount=amount,
            items=items,
            hint=hint
        )

        # Calculate confidence based on categorization strength
        confidence = 0.85 if category != "other" else 0.3

        return success_response({
            "category": category,
            "confidence": confidence,
            "merchant": merchant,
            "suggestions": [category],
            "amount": amount
        })

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Categorization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Categorization failed: {str(e)}"
        )


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

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
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

        # Extract additional data from raw_result if available
        raw_result = ocr_job.raw_result or {}
        confidence_scores = raw_result.get("confidence_scores", {})
        fields_needing_review = raw_result.get("fields_needing_review", [])
        items = raw_result.get("items", [])

        result_data = {
            "merchant": ocr_job.store_name,
            "amount": float(ocr_job.amount) if ocr_job.amount else 0.0,
            "date": ocr_job.date,
            "category": ocr_job.category_hint,
            "confidence": float(ocr_job.confidence) if ocr_job.confidence else 0.0,
            "confidence_scores": confidence_scores,
            "fields_needing_review": fields_needing_review,
            "items": items,
            "image_url": ocr_job.image_url
        } if ocr_job.status == "completed" else None

        return success_response({
            "job_id": ocr_job_id,
            "status": ocr_job.status,
            "progress": float(ocr_job.progress),
            "created_at": ocr_job.created_at.isoformat() if ocr_job.created_at else None,
            "completed_at": ocr_job.completed_at.isoformat() if ocr_job.completed_at else None,
            "result": result_data,
            "error": ocr_job.error_message if ocr_job.status == "failed" else None
        })

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return success_response({
            "job_id": ocr_job_id,
            "status": "error",
            "progress": 0,
            "error": str(e)
        })


@router.get("/image/{job_id}")
async def get_receipt_image(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get receipt image file by job ID.
    """
    from app.db.models import OCRJob

    try:
        # Query OCRJob from database
        ocr_job = db.query(OCRJob).filter(
            and_(
                OCRJob.job_id == job_id,
                OCRJob.user_id == user.id
            )
        ).first()

        if not ocr_job:
            raise HTTPException(
                status_code=404,
                detail="Receipt image not found or does not belong to user"
            )

        # Check if image path exists
        if not ocr_job.image_path or not os.path.exists(ocr_job.image_path):
            raise HTTPException(
                status_code=404,
                detail="Receipt image file not found"
            )

        # Return image file
        return FileResponse(
            path=ocr_job.image_path,
            media_type="image/jpeg",
            filename=f"receipt_{job_id}.jpg"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve receipt image: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve receipt image: {str(e)}"
        )


@router.delete("/image/{job_id}")
async def delete_receipt_image(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete receipt image by job ID.
    """
    from app.db.models import OCRJob

    try:
        # Query OCRJob from database
        ocr_job = db.query(OCRJob).filter(
            and_(
                OCRJob.job_id == job_id,
                OCRJob.user_id == user.id
            )
        ).first()

        if not ocr_job:
            raise HTTPException(
                status_code=404,
                detail="Receipt not found or does not belong to user"
            )

        # Delete image file if exists
        if ocr_job.image_path:
            storage = get_receipt_storage()
            storage.delete_image(ocr_job.image_path)

            # Update database record
            ocr_job.image_path = None
            ocr_job.image_url = None
            db.commit()

        return success_response({
            "job_id": job_id,
            "deleted": True,
            "message": "Receipt image deleted successfully"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete receipt image: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete receipt image: {str(e)}"
        )
