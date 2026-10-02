"""Classified tool errors.

Every failure a tool can report falls into exactly one category. The category
and a fixed, user-safe message reach ChatGPT; exception text never does
(it can carry SQL, values or internal names).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCategory(str, Enum):
    AUTH = (
        "auth"  # token valid at the edge but no longer authorizes (revoked, user gone)
    )
    FORBIDDEN = "forbidden"  # missing scope
    VALIDATION = "validation"  # arguments well-typed but not acceptable
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"  # database or dependency unreachable
    INTERNAL = "internal"


class McpToolError(Exception):
    """An expected, classified failure. ``message`` is shown to the model."""

    category: ErrorCategory = ErrorCategory.INTERNAL

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthError(McpToolError):
    category = ErrorCategory.AUTH


class ForbiddenError(McpToolError):
    category = ErrorCategory.FORBIDDEN


class ValidationError(McpToolError):
    category = ErrorCategory.VALIDATION


class RateLimitedError(McpToolError):
    category = ErrorCategory.RATE_LIMITED


class UnavailableError(McpToolError):
    category = ErrorCategory.UNAVAILABLE


class InternalError(McpToolError):
    category = ErrorCategory.INTERNAL


INTERNAL_MESSAGE = (
    "MITA could not complete this request because of an internal error. "
    "No data was changed."
)
UNAVAILABLE_MESSAGE = (
    "MITA's data service is temporarily unavailable. No data was changed; "
    "try again shortly."
)
