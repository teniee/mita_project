"""
Base CRUD Helper for Sync Routes

Provides common CRUD operations to reduce code duplication in API routes.
Use these helpers instead of repeating the same patterns in every route.

Usage:
    from app.api.base_crud import CRUDHelper

    # In route:
    habit = CRUDHelper.get_user_resource_or_404(db, Habit, habit_id, user.id)
    new_habit = CRUDHelper.create_user_resource(db, Habit, {"title": "..."}, user.id)
"""

from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

T = TypeVar('T')


class CRUDHelper:
    """
    Static helper class for common CRUD operations in sync routes.
    Reduces code duplication across API endpoints.
    """

    @staticmethod
    def get_or_404(
        db: Session,
        model: Type[T],
        resource_id: UUID,
        detail: str = "Resource not found"
    ) -> T:
        """
        Get a resource by ID or raise 404.

        Args:
            db: Database session
            model: SQLAlchemy model class
            resource_id: UUID of the resource
            detail: Error message if not found

        Returns:
            The resource instance

        Raises:
            HTTPException: 404 if not found
        """
        resource = db.query(model).filter(model.id == resource_id).first()
        if not resource:
            raise HTTPException(status_code=404, detail=detail)
        return resource

    @staticmethod
    def get_user_resource_or_404(
        db: Session,
        model: Type[T],
        resource_id: UUID,
        user_id: UUID,
        detail: str = "Resource not found"
    ) -> T:
        """
        Get a user-owned resource by ID or raise 404.

        Args:
            db: Database session
            model: SQLAlchemy model class (must have user_id field)
            resource_id: UUID of the resource
            user_id: UUID of the owner
            detail: Error message if not found

        Returns:
            The resource instance

        Raises:
            HTTPException: 404 if not found or not owned by user
        """
        resource = db.query(model).filter(
            model.id == resource_id,
            model.user_id == user_id
        ).first()
        if not resource:
            raise HTTPException(status_code=404, detail=detail)
        return resource

    @staticmethod
    def get_user_resources(
        db: Session,
        model: Type[T],
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[Any] = None
    ) -> List[T]:
        """
        Get all resources owned by a user with pagination.

        Args:
            db: Database session
            model: SQLAlchemy model class
            user_id: UUID of the owner
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Optional column to order by

        Returns:
            List of resources
        """
        query = db.query(model).filter(model.user_id == user_id)

        if order_by is not None:
            query = query.order_by(order_by)

        return query.offset(skip).limit(limit).all()

    @staticmethod
    def create_resource(
        db: Session,
        model: Type[T],
        data: Dict[str, Any]
    ) -> T:
        """
        Create a new resource.

        Args:
            db: Database session
            model: SQLAlchemy model class
            data: Dictionary of field values

        Returns:
            The created resource
        """
        resource = model(**data)
        db.add(resource)
        db.commit()
        db.refresh(resource)
        return resource

    @staticmethod
    def create_user_resource(
        db: Session,
        model: Type[T],
        data: Dict[str, Any],
        user_id: UUID
    ) -> T:
        """
        Create a new user-owned resource.

        Args:
            db: Database session
            model: SQLAlchemy model class
            data: Dictionary of field values (without user_id)
            user_id: UUID of the owner

        Returns:
            The created resource
        """
        resource = model(user_id=user_id, **data)
        db.add(resource)
        db.commit()
        db.refresh(resource)
        return resource

    @staticmethod
    def update_resource(
        db: Session,
        resource: T,
        data: Dict[str, Any],
        exclude_none: bool = True
    ) -> T:
        """
        Update a resource with given data.

        Args:
            db: Database session
            resource: The resource to update
            data: Dictionary of field values
            exclude_none: If True, skip None values

        Returns:
            The updated resource
        """
        for field, value in data.items():
            if exclude_none and value is None:
                continue
            if hasattr(resource, field):
                setattr(resource, field, value)

        db.commit()
        db.refresh(resource)
        return resource

    @staticmethod
    def delete_resource(db: Session, resource: T) -> bool:
        """
        Delete a resource.

        Args:
            db: Database session
            resource: The resource to delete

        Returns:
            True if deleted successfully
        """
        db.delete(resource)
        db.commit()
        return True

    @staticmethod
    def delete_user_resource_or_404(
        db: Session,
        model: Type[T],
        resource_id: UUID,
        user_id: UUID,
        detail: str = "Resource not found"
    ) -> bool:
        """
        Delete a user-owned resource by ID or raise 404.

        Args:
            db: Database session
            model: SQLAlchemy model class
            resource_id: UUID of the resource
            user_id: UUID of the owner
            detail: Error message if not found

        Returns:
            True if deleted successfully

        Raises:
            HTTPException: 404 if not found
        """
        resource = CRUDHelper.get_user_resource_or_404(
            db, model, resource_id, user_id, detail
        )
        db.delete(resource)
        db.commit()
        return True

    @staticmethod
    def count_user_resources(
        db: Session,
        model: Type[T],
        user_id: UUID,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Count resources owned by a user.

        Args:
            db: Database session
            model: SQLAlchemy model class
            user_id: UUID of the owner
            filters: Optional additional filters

        Returns:
            Number of resources
        """
        query = db.query(model).filter(model.user_id == user_id)

        if filters:
            for field, value in filters.items():
                if hasattr(model, field):
                    query = query.filter(getattr(model, field) == value)

        return query.count()

    @staticmethod
    def exists(
        db: Session,
        model: Type[T],
        resource_id: UUID
    ) -> bool:
        """
        Check if a resource exists.

        Args:
            db: Database session
            model: SQLAlchemy model class
            resource_id: UUID of the resource

        Returns:
            True if exists
        """
        return db.query(model).filter(model.id == resource_id).first() is not None
