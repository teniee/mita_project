"""
Async tasks package for MITA financial platform.

This package contains all long-running and computationally expensive tasks
that are executed asynchronously using the task queue system.
"""

# Import main async tasks to make them available at package level
from .async_tasks import (
    process_ocr_task,
    generate_ai_analysis_task,
    budget_redistribution_task,
    send_email_notification_task,
    send_push_notification_task,
    export_user_data_task,
    daily_ai_advice_batch_task,
    monthly_budget_redistribution_batch_task,
    cleanup_old_tasks_batch_task
)

__all__ = [
    'process_ocr_task',
    'generate_ai_analysis_task',
    'budget_redistribution_task',
    'send_email_notification_task',
    'send_push_notification_task',
    'export_user_data_task',
    'daily_ai_advice_batch_task',
    'monthly_budget_redistribution_batch_task',
    'cleanup_old_tasks_batch_task'
]