"""
Base Repository Pattern Implementation for MITA
Provides abstract base for all repository implementations
"""

from abc import ABC
from typing import Any, Dict, List, Optional, TypeVar, Generic, Type
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import DeclarativeBase

from app.core.async_session import get_async_db_context

# Generic type for model
T = TypeVar('T', bound=DeclarativeBase)


class BaseRepository(Generic[T], ABC):
    """
    Abstract base repository providing common database operations
    All repositories should inherit from this class
    """
    
    def __init__(self, model: Type[T]):
        self.model = model
    
    async def create(self, obj_data: Dict[str, Any]) -> T:
        """Create a new record"""
        async with get_async_db_context() as db:
            db_obj = self.model(**obj_data)
            db.add(db_obj)
            await db.flush()
            await db.refresh(db_obj)
            return db_obj
    
    async def get_by_id(self, obj_id: Any) -> Optional[T]:
        """Get a record by ID"""
        async with get_async_db_context() as db:
            result = await db.execute(select(self.model).where(self.model.id == obj_id))
            return result.scalar_one_or_none()
    
    async def get_by_field(self, field_name: str, value: Any) -> Optional[T]:
        """Get a record by any field"""
        async with get_async_db_context() as db:
            field = getattr(self.model, field_name)
            result = await db.execute(select(self.model).where(field == value))
            return result.scalar_one_or_none()
    
    async def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[T]:
        """Get multiple records with pagination and filters"""
        async with get_async_db_context() as db:
            query = select(self.model)
            
            # Apply filters
            if filters:
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        query = query.where(field == value)
            
            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def update(self, obj_id: Any, obj_data: Dict[str, Any]) -> Optional[T]:
        """Update a record by ID"""
        async with get_async_db_context() as db:
            # First check if record exists
            result = await db.execute(select(self.model).where(self.model.id == obj_id))
            db_obj = result.scalar_one_or_none()
            
            if not db_obj:
                return None
            
            # Update fields
            for field, value in obj_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            await db.flush()
            await db.refresh(db_obj)
            return db_obj
    
    async def delete(self, obj_id: Any) -> bool:
        """Delete a record by ID"""
        async with get_async_db_context() as db:
            result = await db.execute(delete(self.model).where(self.model.id == obj_id))
            return result.rowcount > 0
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters"""
        async with get_async_db_context() as db:
            query = select(func.count(self.model.id))
            
            # Apply filters
            if filters:
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        query = query.where(field == value)
            
            result = await db.execute(query)
            return result.scalar() or 0
    
    async def exists(self, obj_id: Any) -> bool:
        """Check if a record exists by ID"""
        async with get_async_db_context() as db:
            result = await db.execute(
                select(func.count(self.model.id)).where(self.model.id == obj_id)
            )
            return (result.scalar() or 0) > 0
    
    async def bulk_create(self, obj_data_list: List[Dict[str, Any]]) -> List[T]:
        """Create multiple records in bulk"""
        async with get_async_db_context() as db:
            db_objs = [self.model(**obj_data) for obj_data in obj_data_list]
            db.add_all(db_objs)
            await db.flush()
            
            # Refresh all objects to get generated IDs
            for db_obj in db_objs:
                await db.refresh(db_obj)
            
            return db_objs
    
    async def bulk_update(self, updates: List[Dict[str, Any]]) -> int:
        """
        Bulk update records
        Each update dict should contain 'id' and the fields to update
        """
        async with get_async_db_context() as db:
            updated_count = 0
            
            for update_data in updates:
                obj_id = update_data.pop('id')
                if obj_id:
                    result = await db.execute(
                        update(self.model)
                        .where(self.model.id == obj_id)
                        .values(**update_data)
                    )
                    updated_count += result.rowcount
            
            return updated_count
    
    async def get_or_create(
        self, 
        defaults: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> tuple[T, bool]:
        """
        Get an existing record or create a new one
        Returns (object, created) tuple
        """
        async with get_async_db_context() as db:
            # Try to get existing record
            query = select(self.model)
            for field_name, value in kwargs.items():
                if hasattr(self.model, field_name):
                    field = getattr(self.model, field_name)
                    query = query.where(field == value)
            
            result = await db.execute(query)
            existing_obj = result.scalar_one_or_none()
            
            if existing_obj:
                return existing_obj, False
            
            # Create new record
            create_data = {**kwargs}
            if defaults:
                create_data.update(defaults)
            
            new_obj = self.model(**create_data)
            db.add(new_obj)
            await db.flush()
            await db.refresh(new_obj)
            
            return new_obj, True