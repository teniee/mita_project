"""
Transaction Repository Implementation
Provides transaction-specific database operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base_repository import BaseRepository
from app.db.models import Transaction
from app.core.async_session import get_async_db_context


class TransactionRepository(BaseRepository[Transaction]):
    """Repository for Transaction entity with specialized operations"""
    
    def __init__(self):
        super().__init__(Transaction)
    
    async def get_by_user(self, user_id: int, limit: int = 50, offset: int = 0) -> List[Transaction]:
        """Get transactions for a specific user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Transaction)
                .where(Transaction.user_id == user_id)
                .order_by(desc(Transaction.created_at))
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())
    
    async def get_by_date_range(
        self, 
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Transaction]:
        """Get transactions within a date range for a user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Transaction)
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.created_at >= start_date,
                        Transaction.created_at <= end_date
                    )
                )
                .order_by(desc(Transaction.created_at))
            )
            return list(result.scalars().all())
    
    async def get_monthly_transactions(
        self, 
        user_id: int,
        year: int,
        month: int
    ) -> List[Transaction]:
        """Get transactions for a specific month"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        return await self.get_by_date_range(user_id, start_date, end_date)
    
    async def get_by_category(
        self, 
        user_id: int, 
        category: str,
        limit: int = 50
    ) -> List[Transaction]:
        """Get transactions by category for a user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Transaction)
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.category == category
                    )
                )
                .order_by(desc(Transaction.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_total_spent_by_period(
        self, 
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Decimal:
        """Get total amount spent in a period"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(func.sum(Transaction.amount))
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == 'expense',
                        Transaction.created_at >= start_date,
                        Transaction.created_at <= end_date
                    )
                )
            )
            total = result.scalar()
            return total or Decimal('0.00')
    
    async def get_spending_by_category(
        self, 
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Decimal]:
        """Get spending breakdown by category"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(
                    Transaction.category,
                    func.sum(Transaction.amount).label('total_amount')
                )
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == 'expense',
                        Transaction.created_at >= start_date,
                        Transaction.created_at <= end_date
                    )
                )
                .group_by(Transaction.category)
            )
            
            return {row.category: row.total_amount for row in result}
    
    async def get_recent_transactions(
        self, 
        user_id: int, 
        days: int = 7,
        limit: int = 20
    ) -> List[Transaction]:
        """Get recent transactions within the last N days"""
        start_date = datetime.now() - timedelta(days=days)
        
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Transaction)
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.created_at >= start_date
                    )
                )
                .order_by(desc(Transaction.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_largest_transactions(
        self, 
        user_id: int,
        limit: int = 10,
        days: int = 30
    ) -> List[Transaction]:
        """Get largest transactions in the last N days"""
        start_date = datetime.now() - timedelta(days=days)
        
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Transaction)
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.created_at >= start_date
                    )
                )
                .order_by(desc(Transaction.amount))
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def search_transactions(
        self, 
        user_id: int,
        search_term: str,
        limit: int = 50
    ) -> List[Transaction]:
        """Search transactions by description or merchant"""
        async with get_async_db_context() as db:
            search_pattern = f"%{search_term.lower()}%"
            result = await db.execute(
                select(Transaction)
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        or_(
                            Transaction.description.ilike(search_pattern),
                            Transaction.merchant_name.ilike(search_pattern)
                        )
                    )
                )
                .order_by(desc(Transaction.created_at))
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_transaction_statistics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive transaction statistics for a user"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        async with get_async_db_context() as db:
            # Total transactions
            total_count = await db.execute(
                select(func.count(Transaction.id))
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.created_at >= start_date
                    )
                )
            )
            
            # Total spent
            total_spent = await db.execute(
                select(func.sum(Transaction.amount))
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == 'expense',
                        Transaction.created_at >= start_date
                    )
                )
            )
            
            # Average transaction amount
            avg_amount = await db.execute(
                select(func.avg(Transaction.amount))
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == 'expense',
                        Transaction.created_at >= start_date
                    )
                )
            )
            
            # Most frequent category
            most_frequent_category = await db.execute(
                select(
                    Transaction.category,
                    func.count(Transaction.id).label('count')
                )
                .where(
                    and_(
                        Transaction.user_id == user_id,
                        Transaction.created_at >= start_date
                    )
                )
                .group_by(Transaction.category)
                .order_by(desc('count'))
                .limit(1)
            )
            
            category_result = most_frequent_category.first()
            
            return {
                'total_transactions': total_count.scalar() or 0,
                'total_spent': total_spent.scalar() or Decimal('0.00'),
                'average_amount': avg_amount.scalar() or Decimal('0.00'),
                'most_frequent_category': category_result.category if category_result else None,
                'period_days': days,
            }


# Singleton instance
_transaction_repository: Optional[TransactionRepository] = None

def get_transaction_repository() -> TransactionRepository:
    """Get singleton transaction repository instance"""
    global _transaction_repository
    if _transaction_repository is None:
        _transaction_repository = TransactionRepository()
    return _transaction_repository