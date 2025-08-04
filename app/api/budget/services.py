import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.core.engine.budget_tracker import BudgetTracker
from app.core.error_handler import MITAException

logger = logging.getLogger(__name__)


def fetch_spent_by_category(db: Session, user_id: int, year: int, month: int) -> Dict[str, Any]:
    """Fetch spending by category with proper error handling"""
    try:
        # Validate input parameters
        if not user_id or user_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )
        
        if not (1 <= month <= 12):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Month must be between 1 and 12"
            )
        
        if year < 2020 or year > 2030:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Year must be between 2020 and 2030"
            )
        
        tracker = BudgetTracker(db=db, user_id=user_id, year=year, month=month)
        result = tracker.get_spent()
        
        if result is None:
            logger.warning(f"No spending data found for user {user_id} in {year}-{month}")
            return {}
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching spent by category for user {user_id}: {str(e)}")
        raise MITAException(
            message="Failed to fetch spending data",
            details={"user_id": user_id, "year": year, "month": month}
        )


def fetch_remaining_budget(db: Session, user_id: int, year: int, month: int) -> Dict[str, Any]:
    """Fetch remaining budget with proper error handling"""
    try:
        # Validate input parameters
        if not user_id or user_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID"
            )
        
        if not (1 <= month <= 12):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Month must be between 1 and 12"
            )
        
        if year < 2020 or year > 2030:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Year must be between 2020 and 2030"
            )
        
        tracker = BudgetTracker(db=db, user_id=user_id, year=year, month=month)
        result = tracker.get_remaining_per_category()
        
        if result is None:
            logger.warning(f"No budget data found for user {user_id} in {year}-{month}")
            return {}
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching remaining budget for user {user_id}: {str(e)}")
        raise MITAException(
            message="Failed to fetch budget data",
            details={"user_id": user_id, "year": year, "month": month}
        )
