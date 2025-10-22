from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, EmailStr, Field


class UserProfileOut(BaseModel):
    """User profile response schema - flexible to accept any additional fields"""
    class Config:
        extra = "allow"  # Allow extra fields not explicitly defined


class UserUpdateIn(BaseModel):
    """User profile update schema - accepts all user and preference fields"""
    # Basic user fields
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    country: Optional[str] = None
    region: Optional[str] = None  # Alias for country
    timezone: Optional[str] = None
    income: Optional[float] = Field(None, ge=0)
    monthly_income: Optional[float] = Field(None, ge=0)  # Alias for income

    # Preference fields
    currency: Optional[str] = None
    language: Optional[str] = None
    dark_mode: Optional[bool] = None
    notifications: Optional[bool] = None
    biometric_auth: Optional[bool] = None
    auto_sync: Optional[bool] = None
    offline_mode: Optional[bool] = None
    date_format: Optional[str] = None
    budget_alert_threshold: Optional[float] = Field(None, ge=0, le=100)
    savings_goal: Optional[float] = Field(None, ge=0)
    budget_method: Optional[str] = None

    class Config:
        extra = "allow"  # Allow additional fields for future compatibility
