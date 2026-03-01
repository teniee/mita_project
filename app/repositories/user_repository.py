"""
User Repository Implementation
Provides user-specific database operations with advanced features
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_

from app.repositories.base_repository import BaseRepository
from app.db.models import User
from app.core.async_session import get_async_db_context


class UserRepository(BaseRepository[User]):
    """Repository for User entity with specialized operations"""
    
    def __init__(self):
        super().__init__(User)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(User).where(User.email == email.lower())
            )
            return result.scalar_one_or_none()
    
    async def create_user(self, user_data: Dict[str, Any]) -> User:
        """Create a new user with email normalization"""
        # Normalize email to lowercase
        if 'email' in user_data:
            user_data['email'] = user_data['email'].lower()
        
        return await self.create(user_data)
    
    async def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp"""
        return await self.update(user_id, {'last_login': datetime.utcnow()}) is not None
    
    async def get_premium_users(self) -> List[User]:
        """Get all premium users"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(User).where(User.is_premium == True)
            )
            return list(result.scalars().all())
    
    async def get_users_by_registration_date(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[User]:
        """Get users registered within a date range"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(User).where(
                    and_(
                        User.created_at >= start_date,
                        User.created_at <= end_date
                    )
                ).order_by(User.created_at.desc())
            )
            return list(result.scalars().all())
    
    async def search_users(self, search_term: str, limit: int = 20) -> List[User]:
        """Search users by name or email"""
        async with get_async_db_context() as db:
            search_pattern = f"%{search_term.lower()}%"
            result = await db.execute(
                select(User).where(
                    or_(
                        User.email.ilike(search_pattern),
                        User.name.ilike(search_pattern)
                    )
                ).limit(limit)
            )
            return list(result.scalars().all())
    
    async def get_user_stats(self) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        async with get_async_db_context() as db:
            # Total users
            total_users = await db.execute(select(func.count(User.id)))
            total_count = total_users.scalar() or 0
            
            # Premium users
            premium_users = await db.execute(
                select(func.count(User.id)).where(User.is_premium == True)
            )
            premium_count = premium_users.scalar() or 0
            
            # Active users (logged in within last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            active_users = await db.execute(
                select(func.count(User.id)).where(User.last_login >= thirty_days_ago)
            )
            active_count = active_users.scalar() or 0
            
            # Users registered in last 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            new_users = await db.execute(
                select(func.count(User.id)).where(User.created_at >= seven_days_ago)
            )
            new_count = new_users.scalar() or 0
            
            return {
                'total_users': total_count,
                'premium_users': premium_count,
                'active_users': active_count,
                'new_users_7d': new_count,
                'premium_rate': (premium_count / max(total_count, 1)) * 100,
                'activity_rate': (active_count / max(total_count, 1)) * 100,
            }
    
    async def get_inactive_users(self, days: int = 30) -> List[User]:
        """Get users who haven't logged in for specified days"""
        async with get_async_db_context() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await db.execute(
                select(User).where(
                    or_(
                        User.last_login < cutoff_date,
                        User.last_login.is_(None)
                    )
                ).order_by(User.last_login.desc())
            )
            return list(result.scalars().all())
    
    async def update_premium_status(self, user_id: int, is_premium: bool, premium_until: Optional[datetime] = None) -> bool:
        """Update user's premium status"""
        update_data = {'is_premium': is_premium}
        if premium_until:
            update_data['premium_until'] = premium_until
        
        return await self.update(user_id, update_data) is not None
    
    async def get_expiring_premium_users(self, days_ahead: int = 7) -> List[User]:
        """Get premium users whose subscription expires within specified days"""
        async with get_async_db_context() as db:
            future_date = datetime.utcnow() + timedelta(days=days_ahead)
            result = await db.execute(
                select(User).where(
                    and_(
                        User.is_premium == True,
                        User.premium_until <= future_date,
                        User.premium_until >= datetime.utcnow()
                    )
                ).order_by(User.premium_until.asc())
            )
            return list(result.scalars().all())
    
    async def bulk_update_premium_status(self, user_ids: List[int], is_premium: bool) -> int:
        """Bulk update premium status for multiple users"""
        updates = [{'id': user_id, 'is_premium': is_premium} for user_id in user_ids]
        return await self.bulk_update(updates)
    
    async def get_user_engagement_metrics(self, user_id: int) -> Dict[str, Any]:
        """Get engagement metrics for a specific user"""
        async with get_async_db_context():
            user = await self.get_by_id(user_id)
            if not user:
                return {}
            
            days_since_registration = (datetime.utcnow() - user.created_at).days
            days_since_last_login = None
            
            if user.last_login:
                days_since_last_login = (datetime.utcnow() - user.last_login).days
            
            return {
                'user_id': user_id,
                'days_since_registration': days_since_registration,
                'days_since_last_login': days_since_last_login,
                'is_premium': user.is_premium,
                'registration_date': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
            }
    
    async def validate_email_unique(self, email: str, exclude_user_id: Optional[int] = None) -> bool:
        """Check if email is unique (optionally excluding a specific user)"""
        async with get_async_db_context() as db:
            query = select(func.count(User.id)).where(User.email == email.lower())
            
            if exclude_user_id:
                query = query.where(User.id != exclude_user_id)
            
            result = await db.execute(query)
            count = result.scalar() or 0
            return count == 0


# Singleton instance
_user_repository: Optional[UserRepository] = None

def get_user_repository() -> UserRepository:
    """Get singleton user repository instance"""
    global _user_repository
    if _user_repository is None:
        _user_repository = UserRepository()
    return _user_repository