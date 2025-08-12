"""
Async task definitions for MITA financial platform heavy operations.
All long-running and computationally expensive tasks are defined here.
"""

import os
import tempfile
from datetime import datetime, date
from typing import Dict, Any, Optional, List
import logging
from sqlalchemy.orm import Session

from app.core.task_queue import task_wrapper, TaskPriority
from app.core.session import get_db
from app.core.logger import get_logger
from app.db.models import User, Transaction, AIAnalysisSnapshot, BudgetAdvice, PushToken
from app.services.advisory_service import AdvisoryService
from app.services.push_service import send_push_notification
from app.services.budget_redistributor import redistribute_budget_for_user
from app.services.core.engine.ai_snapshot_service import save_ai_snapshot
from app.ocr.advanced_ocr_service import AdvancedOCRService
from app.orchestrator.receipt_orchestrator import process_receipt_from_text
from app.utils.email_utils import send_reminder_email

logger = get_logger(__name__)


@task_wrapper(
    priority=TaskPriority.HIGH,
    timeout=300,  # 5 minutes
    retry_count=3,
    retry_delay=60
)
def process_ocr_task(
    user_id: int,
    image_path: str,
    is_premium_user: bool = False,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process receipt image using OCR and extract transaction data.
    
    Args:
        user_id: User ID for the transaction
        image_path: Path to the uploaded image file
        is_premium_user: Whether to use premium OCR service
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing OCR results and created transaction data
    """
    logger.info(f"Starting OCR processing for user {user_id}, image: {image_path}")
    
    try:
        # Initialize OCR service
        ocr_service = AdvancedOCRService()
        
        # Process the image
        ocr_result = ocr_service.process_image(image_path, is_premium_user)
        
        # Get database session
        db: Session = next(get_db())
        
        try:
            # Process the OCR text and create transaction
            transaction_result = process_receipt_from_text(
                user_id=user_id,
                text=ocr_result.get('raw_text', ''),
                db=db
            )
            
            logger.info(
                f"OCR processing completed for user {user_id}: "
                f"Amount: {ocr_result.get('amount')}, "
                f"Store: {ocr_result.get('store')}"
            )
            
            return {
                'status': 'success',
                'ocr_result': ocr_result,
                'transaction': transaction_result,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            f"OCR processing failed for user {user_id}: {str(e)}",
            extra={'user_id': user_id, 'image_path': image_path},
            exc_info=True
        )
        
        # Clean up image file on error
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up image file: {cleanup_error}")
        
        raise


@task_wrapper(
    priority=TaskPriority.HIGH,
    timeout=600,  # 10 minutes
    retry_count=2,
    retry_delay=120
)
def generate_ai_analysis_task(
    user_id: int,
    year: int,
    month: int,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate comprehensive AI financial analysis snapshot for a user.
    
    Args:
        user_id: User ID to analyze
        year: Analysis year
        month: Analysis month
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing the AI analysis results
    """
    logger.info(f"Starting AI analysis for user {user_id}, period: {year}-{month:02d}")
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            # Generate and save AI snapshot
            snapshot_result = save_ai_snapshot(user_id, db, year, month)
            
            logger.info(
                f"AI analysis completed for user {user_id}: "
                f"Rating: {snapshot_result.get('rating')}, "
                f"Risk: {snapshot_result.get('risk')}"
            )
            
            return {
                'status': 'success',
                'snapshot': snapshot_result,
                'user_id': user_id,
                'period': f"{year}-{month:02d}",
                'generated_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            f"AI analysis failed for user {user_id}: {str(e)}",
            extra={'user_id': user_id, 'year': year, 'month': month},
            exc_info=True
        )
        raise


@task_wrapper(
    priority=TaskPriority.NORMAL,
    timeout=180,  # 3 minutes
    retry_count=3,
    retry_delay=60
)
def budget_redistribution_task(
    user_id: int,
    year: int,
    month: int,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Perform budget redistribution for a specific user and period.
    
    Args:
        user_id: User ID to redistribute budget for
        year: Redistribution year
        month: Redistribution month
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing redistribution results
    """
    logger.info(f"Starting budget redistribution for user {user_id}, period: {year}-{month:02d}")
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            # Perform budget redistribution
            result = redistribute_budget_for_user(db, user_id, year, month)
            
            logger.info(
                f"Budget redistribution completed for user {user_id}: {result['status']}"
            )
            
            return {
                'status': 'success',
                'redistribution_result': result,
                'user_id': user_id,
                'period': f"{year}-{month:02d}",
                'processed_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            f"Budget redistribution failed for user {user_id}: {str(e)}",
            extra={'user_id': user_id, 'year': year, 'month': month},
            exc_info=True
        )
        raise


@task_wrapper(
    priority=TaskPriority.NORMAL,
    timeout=60,  # 1 minute
    retry_count=5,
    retry_delay=30
)
def send_email_notification_task(
    user_email: str,
    subject: str,
    body: str,
    user_id: Optional[int] = None,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send email notification to user.
    
    Args:
        user_email: Recipient email address
        subject: Email subject
        body: Email body content
        user_id: Optional user ID for logging
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing send status
    """
    logger.info(f"Sending email notification to {user_email}: {subject}")
    
    try:
        # Get database session for logging
        db: Session = next(get_db()) if user_id else None
        
        try:
            # Send email
            send_reminder_email(
                to_address=user_email,
                subject=subject,
                body=body,
                user_id=user_id,
                db=db
            )
            
            logger.info(f"Email sent successfully to {user_email}")
            
            return {
                'status': 'success',
                'recipient': user_email,
                'subject': subject,
                'sent_at': datetime.utcnow().isoformat()
            }
            
        finally:
            if db:
                db.close()
                
    except Exception as e:
        logger.error(
            f"Email sending failed to {user_email}: {str(e)}",
            extra={'recipient': user_email, 'subject': subject},
            exc_info=True
        )
        raise


@task_wrapper(
    priority=TaskPriority.HIGH,
    timeout=30,  # 30 seconds
    retry_count=3,
    retry_delay=15
)
def send_push_notification_task(
    user_id: int,
    message: str,
    title: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send push notification to user's device.
    
    Args:
        user_id: User ID to send notification to
        message: Notification message
        title: Optional notification title
        data: Optional additional data payload
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing notification status
    """
    logger.info(f"Sending push notification to user {user_id}: {message}")
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            # Get user's push token
            token_record = (
                db.query(PushToken)
                .filter(PushToken.user_id == user_id)
                .order_by(PushToken.created_at.desc())
                .first()
            )
            
            if not token_record:
                raise ValueError(f"No push token found for user {user_id}")
            
            # Send push notification
            send_push_notification(
                user_id=user_id,
                message=message,
                token=token_record.token,
                db=db,
                title=title,
                data=data
            )
            
            logger.info(f"Push notification sent successfully to user {user_id}")
            
            return {
                'status': 'success',
                'user_id': user_id,
                'message': message,
                'sent_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            f"Push notification failed for user {user_id}: {str(e)}",
            extra={'user_id': user_id, 'message': message},
            exc_info=True
        )
        raise


@task_wrapper(
    priority=TaskPriority.LOW,
    timeout=900,  # 15 minutes
    retry_count=2,
    retry_delay=300
)
def export_user_data_task(
    user_id: int,
    export_format: str = 'json',
    include_transactions: bool = True,
    include_analytics: bool = True,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Export comprehensive user data for backup or GDPR compliance.
    
    Args:
        user_id: User ID to export data for
        export_format: Export format ('json' or 'csv')
        include_transactions: Whether to include transaction data
        include_analytics: Whether to include analytics data
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing export results and file path
    """
    logger.info(f"Starting data export for user {user_id}, format: {export_format}")
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            # Get user data
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            export_data = {
                'user_id': user_id,
                'export_generated_at': datetime.utcnow().isoformat(),
                'user_profile': {
                    'email': user.email,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'timezone': getattr(user, 'timezone', None),
                    'is_active': getattr(user, 'is_active', True)
                }
            }
            
            # Include transactions if requested
            if include_transactions:
                transactions = (
                    db.query(Transaction)
                    .filter(Transaction.user_id == user_id)
                    .order_by(Transaction.created_at.desc())
                    .all()
                )
                
                export_data['transactions'] = [
                    {
                        'id': t.id,
                        'amount': float(t.amount),
                        'category': t.category,
                        'description': t.description,
                        'date': t.date.isoformat() if t.date else None,
                        'created_at': t.created_at.isoformat() if t.created_at else None
                    }
                    for t in transactions
                ]
            
            # Include analytics if requested
            if include_analytics:
                snapshots = (
                    db.query(AIAnalysisSnapshot)
                    .filter(AIAnalysisSnapshot.user_id == user_id)
                    .order_by(AIAnalysisSnapshot.created_at.desc())
                    .all()
                )
                
                export_data['ai_analysis'] = [
                    {
                        'id': s.id,
                        'rating': s.rating,
                        'risk': s.risk,
                        'summary': s.summary,
                        'created_at': s.created_at.isoformat() if s.created_at else None
                    }
                    for s in snapshots
                ]
            
            # Create temporary file for export
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix=f'.{export_format}',
                delete=False,
                prefix=f'user_export_{user_id}_'
            ) as temp_file:
                
                if export_format.lower() == 'json':
                    import json
                    json.dump(export_data, temp_file, indent=2, ensure_ascii=False)
                elif export_format.lower() == 'csv':
                    import csv
                    import io
                    
                    # For CSV, we'll create separate sections
                    output = io.StringIO()
                    writer = csv.writer(output)
                    
                    # User profile section
                    writer.writerow(['User Profile'])
                    for key, value in export_data['user_profile'].items():
                        writer.writerow([key, value])
                    writer.writerow([])
                    
                    # Transactions section
                    if 'transactions' in export_data:
                        writer.writerow(['Transactions'])
                        if export_data['transactions']:
                            writer.writerow(export_data['transactions'][0].keys())
                            for transaction in export_data['transactions']:
                                writer.writerow(transaction.values())
                        writer.writerow([])
                    
                    temp_file.write(output.getvalue())
                    output.close()
                
                export_file_path = temp_file.name
            
            logger.info(
                f"Data export completed for user {user_id}: {export_file_path}"
            )
            
            return {
                'status': 'success',
                'user_id': user_id,
                'export_file_path': export_file_path,
                'export_format': export_format,
                'record_counts': {
                    'transactions': len(export_data.get('transactions', [])),
                    'ai_analyses': len(export_data.get('ai_analysis', []))
                },
                'generated_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(
            f"Data export failed for user {user_id}: {str(e)}",
            extra={'user_id': user_id, 'export_format': export_format},
            exc_info=True
        )
        raise


# Batch processing tasks for cron jobs

@task_wrapper(
    priority=TaskPriority.NORMAL,
    timeout=1800,  # 30 minutes
    retry_count=2,
    retry_delay=300
)
def daily_ai_advice_batch_task(task_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate and send daily AI advice to all active users.
    
    Args:
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing batch processing results
    """
    logger.info("Starting daily AI advice batch processing")
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            utc_now = datetime.utcnow()
            today = utc_now.date()
            
            # Get all active users
            users_query = db.query(User)
            if hasattr(User, "is_active"):
                users_query = users_query.filter(User.is_active.is_(True))
            users = users_query.all()
            
            processed_count = 0
            success_count = 0
            error_count = 0
            
            for user in users:
                try:
                    # Check if user already received advice today
                    already_sent = (
                        db.query(BudgetAdvice)
                        .filter(BudgetAdvice.user_id == user.id)
                        .filter(BudgetAdvice.date >= today)
                        .first()
                    )
                    
                    if already_sent:
                        continue
                    
                    # Generate advice using advisory service
                    service = AdvisoryService(db)
                    advice_result = service.evaluate_user_risk(user.id)
                    advice_text = advice_result.get("reason")
                    
                    if not advice_text:
                        continue
                    
                    # Send push notification asynchronously
                    from app.core.task_queue import enqueue_task
                    enqueue_task(
                        send_push_notification_task,
                        user_id=user.id,
                        message=advice_text,
                        title="Daily Financial Advice"
                    )
                    
                    success_count += 1
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process advice for user {user.id}: {str(e)}")
                    error_count += 1
                    processed_count += 1
            
            logger.info(
                f"Daily AI advice batch completed: "
                f"processed={processed_count}, success={success_count}, errors={error_count}"
            )
            
            return {
                'status': 'success',
                'processed_count': processed_count,
                'success_count': success_count,
                'error_count': error_count,
                'batch_date': today.isoformat(),
                'completed_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Daily AI advice batch processing failed: {str(e)}", exc_info=True)
        raise


@task_wrapper(
    priority=TaskPriority.NORMAL,
    timeout=3600,  # 60 minutes
    retry_count=2,
    retry_delay=600
)
def monthly_budget_redistribution_batch_task(task_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Perform monthly budget redistribution for all active users.
    
    Args:
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing batch processing results
    """
    logger.info("Starting monthly budget redistribution batch processing")
    
    try:
        # Get database session
        db: Session = next(get_db())
        
        try:
            now = datetime.utcnow()
            # Redistribute for the previous month
            year = now.year
            month = now.month - 1
            if month == 0:
                month = 12
                year -= 1
            
            # Get all active users
            users = db.query(User).filter(User.is_active.is_(True)).all()
            
            processed_count = 0
            success_count = 0
            error_count = 0
            
            for user in users:
                try:
                    # Enqueue individual redistribution task
                    from app.core.task_queue import enqueue_task
                    enqueue_task(
                        budget_redistribution_task,
                        user_id=user.id,
                        year=year,
                        month=month
                    )
                    
                    success_count += 1
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to enqueue redistribution for user {user.id}: {str(e)}")
                    error_count += 1
                    processed_count += 1
            
            logger.info(
                f"Monthly budget redistribution batch completed: "
                f"processed={processed_count}, success={success_count}, errors={error_count}"
            )
            
            return {
                'status': 'success',
                'processed_count': processed_count,
                'success_count': success_count,
                'error_count': error_count,
                'redistribution_period': f"{year}-{month:02d}",
                'completed_at': datetime.utcnow().isoformat()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Monthly budget redistribution batch failed: {str(e)}", exc_info=True)
        raise


@task_wrapper(
    priority=TaskPriority.LOW,
    timeout=1800,  # 30 minutes
    retry_count=1,
    retry_delay=3600
)
def cleanup_old_tasks_batch_task(
    max_age_hours: int = 48,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Clean up old completed and failed tasks from the queue system.
    
    Args:
        max_age_hours: Maximum age of tasks to keep (in hours)
        task_id: Task ID for progress tracking
    
    Returns:
        Dict containing cleanup results
    """
    logger.info(f"Starting task cleanup for tasks older than {max_age_hours} hours")
    
    try:
        from app.core.task_queue import task_queue
        
        # Clean up old jobs
        cleanup_result = task_queue.clean_old_jobs(max_age_hours)
        
        logger.info(
            f"Task cleanup completed: "
            f"completed={cleanup_result['completed']}, failed={cleanup_result['failed']}"
        )
        
        return {
            'status': 'success',
            'cleanup_result': cleanup_result,
            'max_age_hours': max_age_hours,
            'cleaned_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Task cleanup failed: {str(e)}", exc_info=True)
        raise