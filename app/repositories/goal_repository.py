"""
Goal Repository Implementation
Provides goal-specific database operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base_repository import BaseRepository
from app.db.models import Goal
from app.core.async_session import get_async_db_context


class GoalRepository(BaseRepository[Goal]):
    """Repository for Goal entity with specialized operations"""
    
    def __init__(self):
        super().__init__(Goal)
    
    async def get_by_user(self, user_id: int) -> List[Goal]:
        """Get all goals for a specific user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Goal)
                .where(Goal.user_id == user_id)
                .order_by(desc(Goal.created_at))
            )
            return list(result.scalars().all())
    
    async def get_active_goals(self, user_id: int) -> List[Goal]:
        """Get active goals for a user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Goal)
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.status == 'active'
                    )
                )
                .order_by(desc(Goal.created_at))
            )
            return list(result.scalars().all())
    
    async def get_completed_goals(self, user_id: int) -> List[Goal]:
        """Get completed goals for a user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Goal)
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.status == 'completed'
                    )
                )
                .order_by(desc(Goal.completed_at))
            )
            return list(result.scalars().all())
    
    async def get_by_category(self, user_id: int, category: str) -> List[Goal]:
        """Get goals by category for a user"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Goal)
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.category == category
                    )
                )
                .order_by(desc(Goal.created_at))
            )
            return list(result.scalars().all())
    
    async def get_goals_due_soon(self, user_id: int, days_ahead: int = 7) -> List[Goal]:
        """Get goals with target dates within the next N days"""
        async with get_async_db_context() as db:
            future_date = datetime.now() + timedelta(days=days_ahead)
            result = await db.execute(
                select(Goal)
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.status == 'active',
                        Goal.target_date <= future_date.date(),
                        Goal.target_date >= datetime.now().date()
                    )
                )
                .order_by(Goal.target_date)
            )
            return list(result.scalars().all())
    
    async def get_overdue_goals(self, user_id: int) -> List[Goal]:
        """Get goals that are past their target date but not completed"""
        async with get_async_db_context() as db:
            today = datetime.now().date()
            result = await db.execute(
                select(Goal)
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.status == 'active',
                        Goal.target_date < today
                    )
                )
                .order_by(Goal.target_date)
            )
            return list(result.scalars().all())
    
    async def get_goals_by_progress_range(
        self, 
        user_id: int,
        min_progress: float = 0.0,
        max_progress: float = 100.0
    ) -> List[Goal]:
        """Get goals within a specific progress range"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(Goal)
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.progress >= min_progress,
                        Goal.progress <= max_progress
                    )
                )
                .order_by(desc(Goal.progress))
            )
            return list(result.scalars().all())
    
    async def get_near_completion_goals(self, user_id: int, threshold: float = 80.0) -> List[Goal]:
        """Get goals that are near completion (above threshold progress)"""
        return await self.get_goals_by_progress_range(user_id, threshold, 99.9)
    
    async def update_goal_progress(self, goal_id: int, progress: float) -> bool:
        """Update progress for a specific goal"""
        update_data = {
            'progress': min(max(progress, 0.0), 100.0),  # Clamp between 0-100
            'last_updated': datetime.now()
        }
        
        # If progress reaches 100%, mark as completed
        if progress >= 100.0:
            update_data.update({
                'status': 'completed',
                'completed_at': datetime.now()
            })
        
        return await self.update(goal_id, update_data) is not None
    
    async def mark_goal_completed(self, goal_id: int) -> bool:
        """Mark a goal as completed"""
        update_data = {
            'status': 'completed',
            'completed_at': datetime.now(),
            'progress': 100.0,
            'last_updated': datetime.now()
        }
        return await self.update(goal_id, update_data) is not None
    
    async def pause_goal(self, goal_id: int) -> bool:
        """Pause an active goal"""
        update_data = {
            'status': 'paused',
            'last_updated': datetime.now()
        }
        return await self.update(goal_id, update_data) is not None
    
    async def resume_goal(self, goal_id: int) -> bool:
        """Resume a paused goal"""
        update_data = {
            'status': 'active',
            'last_updated': datetime.now()
        }
        return await self.update(goal_id, update_data) is not None
    
    async def get_goal_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive goal statistics for a user"""
        async with get_async_db_context() as db:
            # Total goals
            total_goals = await db.execute(
                select(func.count(Goal.id)).where(Goal.user_id == user_id)
            )
            
            # Completed goals
            completed_goals = await db.execute(
                select(func.count(Goal.id))
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.status == 'completed'
                    )
                )
            )
            
            # Active goals
            active_goals = await db.execute(
                select(func.count(Goal.id))
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.status == 'active'
                    )
                )
            )
            
            # Average progress
            avg_progress = await db.execute(
                select(func.avg(Goal.progress))
                .where(
                    and_(
                        Goal.user_id == user_id,
                        Goal.status == 'active'
                    )
                )
            )
            
            # Goals by category
            category_counts = await db.execute(
                select(
                    Goal.category,
                    func.count(Goal.id).label('count')
                )
                .where(Goal.user_id == user_id)
                .group_by(Goal.category)
            )
            
            total_count = total_goals.scalar() or 0
            completed_count = completed_goals.scalar() or 0
            completion_rate = (completed_count / total_count * 100) if total_count > 0 else 0.0
            
            return {
                'total_goals': total_count,
                'active_goals': active_goals.scalar() or 0,
                'completed_goals': completed_count,
                'completion_rate': completion_rate,
                'average_progress': avg_progress.scalar() or 0.0,
                'goals_by_category': {row.category: row.count for row in category_counts},
                'overdue_goals': len(await self.get_overdue_goals(user_id)),
                'due_soon': len(await self.get_goals_due_soon(user_id))
            }
    
    async def get_goal_recommendations(self, user_id: int) -> List[Dict[str, Any]]:
        """Get goal recommendations based on user's goal patterns"""
        recommendations = []
        
        # Get user's goal history
        goals = await self.get_by_user(user_id)
        completed_goals = await self.get_completed_goals(user_id)
        
        # Analyze patterns
        category_success = {}
        for goal in completed_goals:
            if goal.category not in category_success:
                category_success[goal.category] = {'completed': 0, 'total': 0}
            category_success[goal.category]['completed'] += 1
        
        for goal in goals:
            if goal.category not in category_success:
                category_success[goal.category] = {'completed': 0, 'total': 0}
            category_success[goal.category]['total'] += 1
        
        # Recommend categories with high success rates
        for category, stats in category_success.items():
            if stats['total'] > 0:
                success_rate = stats['completed'] / stats['total']
                if success_rate > 0.7:  # 70% success rate
                    recommendations.append({
                        'type': 'category_success',
                        'category': category,
                        'message': f"You have a {success_rate:.0%} success rate with {category} goals",
                        'success_rate': success_rate
                    })
        
        # Check for overdue goals
        overdue = await self.get_overdue_goals(user_id)
        if overdue:
            recommendations.append({
                'type': 'overdue_warning',
                'count': len(overdue),
                'message': f"You have {len(overdue)} overdue goals that need attention"
            })
        
        return recommendations
    
    async def search_goals(self, user_id: int, search_term: str) -> List[Goal]:
        """Search goals by title or description"""
        async with get_async_db_context() as db:
            search_pattern = f"%{search_term.lower()}%"
            result = await db.execute(
                select(Goal)
                .where(
                    and_(
                        Goal.user_id == user_id,
                        or_(
                            Goal.title.ilike(search_pattern),
                            Goal.description.ilike(search_pattern)
                        )
                    )
                )
                .order_by(desc(Goal.created_at))
            )
            return list(result.scalars().all())


# Singleton instance
_goal_repository: Optional[GoalRepository] = None

def get_goal_repository() -> GoalRepository:
    """Get singleton goal repository instance"""
    global _goal_repository
    if _goal_repository is None:
        _goal_repository = GoalRepository()
    return _goal_repository