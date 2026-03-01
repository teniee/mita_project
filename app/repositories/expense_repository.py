"""
Expense Repository Implementation
Provides expense-specific database operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, desc

from app.repositories.base_repository import BaseRepository
from app.db.models import Expense
from app.core.async_session import get_async_db_context


class ExpenseRepository(BaseRepository[Expense]):
    """Repository for Expense entity with specialized operations"""
    
    def __init__(self):
        super().__init__(Expense)
    
    async def get_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Expense]:
        """Get expenses for a specific user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Expense)
                .where(Expense.user_id == user_id)
                .order_by(desc(Expense.date))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())
    
    async def get_by_date_range(
        self, 
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Expense]:
        """Get expenses within a date range for a user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Expense)
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.date >= start_date.date(),
                        Expense.date <= end_date.date()
                    )
                )
                .order_by(desc(Expense.date))
            )
            return list(result.scalars().all())
    
    async def get_daily_expenses(self, user_id: int, date: datetime) -> List[Expense]:
        """Get expenses for a specific date"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Expense)
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.date == date.date()
                    )
                )
                .order_by(desc(Expense.created_at))
            )
            return list(result.scalars().all())
    
    async def get_by_category(
        self, 
        user_id: int, 
        category: str,
        limit: int = 50
    ) -> List[Expense]:
        """Get expenses by category for a user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Expense)
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.category == category
                    )
                )
                .order_by(desc(Expense.date))
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_total_by_period(
        self, 
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Decimal:
        """Get total expenses in a period"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(func.sum(Expense.amount))
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.date >= start_date.date(),
                        Expense.date <= end_date.date()
                    )
                )
            )
            total = result.scalar()
            return total or Decimal('0.00')
    
    async def get_daily_total(self, user_id: int, date: datetime) -> Decimal:
        """Get total expenses for a specific date"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(func.sum(Expense.amount))
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.date == date.date()
                    )
                )
            )
            total = result.scalar()
            return total or Decimal('0.00')
    
    async def get_monthly_total(self, user_id: int, year: int, month: int) -> Decimal:
        """Get total expenses for a specific month"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        return await self.get_total_by_period(user_id, start_date, end_date)
    
    async def get_category_breakdown(
        self, 
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Decimal]:
        """Get expense breakdown by category"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(
                    Expense.category,
                    func.sum(Expense.amount).label('total_amount')
                )
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.date >= start_date.date(),
                        Expense.date <= end_date.date()
                    )
                )
                .group_by(Expense.category)
            )
            
            return {row.category: row.total_amount for row in result}
    
    async def get_largest_expenses(
        self, 
        user_id: int,
        limit: int = 10,
        days: int = 30
    ) -> List[Expense]:
        """Get largest expenses in the last N days"""
        start_date = datetime.now() - timedelta(days=days)
        
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Expense)
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.date >= start_date.date()
                    )
                )
                .order_by(desc(Expense.amount))
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_recurring_expenses(self, user_id: int) -> List[Expense]:
        """Get expenses that appear to be recurring (same description/category pattern)"""
        async with get_async_db_context() as db:
            # Find expenses with similar descriptions that occur multiple times
            result = await db.execute(
                select(Expense)
                .where(Expense.user_id == user_id)
                .order_by(desc(Expense.date))
            )
            
            expenses = list(result.scalars().all())
            
            # Simple heuristic: group by description and category
            description_counts = {}
            for expense in expenses:
                key = (expense.description.lower().strip(), expense.category)
                if key not in description_counts:
                    description_counts[key] = []
                description_counts[key].append(expense)
            
            # Return expenses that appear more than once
            recurring = []
            for expenses_group in description_counts.values():
                if len(expenses_group) > 1:
                    recurring.extend(expenses_group)
            
            return recurring
    
    async def get_expense_trends(
        self, 
        user_id: int, 
        days: int = 30
    ) -> Dict[str, Any]:
        """Get expense trends and patterns"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        async with get_async_db_context() as db:
            # Daily average
            total_amount = await self.get_total_by_period(user_id, start_date, end_date)
            daily_average = total_amount / days if days > 0 else Decimal('0.00')
            
            # Most expensive day
            daily_totals = await db.execute(
                select(
                    Expense.date,
                    func.sum(Expense.amount).label('daily_total')
                )
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.date >= start_date.date(),
                        Expense.date <= end_date.date()
                    )
                )
                .group_by(Expense.date)
                .order_by(desc('daily_total'))
                .limit(1)
            )
            
            most_expensive_day = daily_totals.first()
            
            # Category analysis
            category_breakdown = await self.get_category_breakdown(user_id, start_date, end_date)
            top_category = max(category_breakdown.items(), key=lambda x: x[1]) if category_breakdown else None
            
            return {
                'total_amount': total_amount,
                'daily_average': daily_average,
                'most_expensive_day': {
                    'date': most_expensive_day.date if most_expensive_day else None,
                    'amount': most_expensive_day.daily_total if most_expensive_day else Decimal('0.00')
                },
                'top_category': {
                    'name': top_category[0] if top_category else None,
                    'amount': top_category[1] if top_category else Decimal('0.00')
                },
                'category_breakdown': category_breakdown,
                'period_days': days
            }
    
    async def search_expenses(
        self, 
        user_id: int,
        search_term: str,
        limit: int = 50
    ) -> List[Expense]:
        """Search expenses by description"""
        async with get_async_db_context() as db:
            search_pattern = f"%{search_term.lower()}%"
            result = await db.execute(
                select(Expense)
                .where(
                    and_(
                        Expense.user_id == user_id,
                        Expense.description.ilike(search_pattern)
                    )
                )
                .order_by(desc(Expense.date))
                .limit(limit)
            )
            return list(result.scalars().all())


# Singleton instance
_expense_repository: Optional[ExpenseRepository] = None

def get_expense_repository() -> ExpenseRepository:
    """Get singleton expense repository instance"""
    global _expense_repository
    if _expense_repository is None:
        _expense_repository = ExpenseRepository()
    return _expense_repository