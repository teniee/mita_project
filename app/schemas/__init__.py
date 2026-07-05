"""
Schemas package.

Base schemas for reducing code duplication.
"""

from app.schemas.base import (
    BaseResponseSchema,
    BaseSchema,
    DecimalResponseSchema,
    ErrorResponseSchema,
    PaginatedResponseSchema,
    SuccessResponseSchema,
    TimestampMixin,
    UserOwnedDecimalResponseSchema,
    UserOwnedResponseSchema,
)

__all__ = [
    "BaseSchema",
    "BaseResponseSchema",
    "UserOwnedResponseSchema",
    "DecimalResponseSchema",
    "UserOwnedDecimalResponseSchema",
    "PaginatedResponseSchema",
    "SuccessResponseSchema",
    "ErrorResponseSchema",
    "TimestampMixin",
]
