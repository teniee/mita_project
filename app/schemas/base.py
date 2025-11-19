"""
Base Pydantic schemas for MITA application.

This module provides base classes to reduce code duplication across schemas.
All response schemas should inherit from appropriate base classes.

Usage:
    from app.schemas.base import (
        BaseSchema,
        BaseResponseSchema,
        UserOwnedResponseSchema,
        DecimalResponseSchema,
        TimestampMixin,
    )

    class MyResponse(UserOwnedResponseSchema):
        name: str
        amount: Decimal

    class MyDecimalResponse(DecimalResponseSchema):
        price: Decimal
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """
    Base schema for all Pydantic models.

    Provides common configuration:
    - from_attributes = True for ORM compatibility
    """
    model_config = ConfigDict(from_attributes=True)


class TimestampMixin(BaseModel):
    """
    Mixin for models with timestamp fields.

    Provides:
    - created_at: datetime
    - updated_at: Optional[datetime]
    """
    created_at: datetime
    updated_at: Optional[datetime] = None


class BaseResponseSchema(BaseSchema):
    """
    Base schema for API responses with common fields.

    Provides:
    - id: UUID
    - created_at: datetime
    - updated_at: Optional[datetime]

    Example:
        class GoalResponse(BaseResponseSchema):
            title: str
            target_amount: Decimal
    """
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserOwnedResponseSchema(BaseResponseSchema):
    """
    Base schema for user-owned resources.

    Extends BaseResponseSchema with:
    - user_id: UUID

    Example:
        class TransactionResponse(UserOwnedResponseSchema):
            amount: Decimal
            category: str
    """
    user_id: UUID


class DecimalResponseSchema(BaseSchema):
    """
    Base schema for responses containing Decimal fields.

    Provides JSON encoder for Decimal -> str conversion.

    Example:
        class PriceResponse(DecimalResponseSchema):
            price: Decimal
            tax: Decimal
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: str(v)
        }
    )


class UserOwnedDecimalResponseSchema(UserOwnedResponseSchema):
    """
    Base schema for user-owned resources with Decimal fields.

    Combines:
    - id, user_id, created_at, updated_at
    - Decimal JSON encoding

    Example:
        class InstallmentResponse(UserOwnedDecimalResponseSchema):
            amount: Decimal
            interest_rate: Decimal
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: str(v)
        }
    )


class PaginatedResponseSchema(BaseSchema):
    """
    Base schema for paginated list responses.

    Provides:
    - total: int
    - has_more: bool

    Example:
        class TransactionListResponse(PaginatedResponseSchema):
            transactions: list[TransactionResponse]
    """
    total: int
    has_more: bool = False


class SuccessResponseSchema(BaseSchema):
    """
    Base schema for simple success responses.

    Provides:
    - status: str
    - message: Optional[str]

    Example:
        return SuccessResponseSchema(status="deleted", message="Goal deleted successfully")
    """
    status: str
    message: Optional[str] = None


class ErrorResponseSchema(BaseSchema):
    """
    Base schema for error responses.

    Provides:
    - detail: str
    - code: Optional[str]
    """
    detail: str
    code: Optional[str] = None


# Type aliases for common field types
UserID = UUID
ResourceID = UUID
