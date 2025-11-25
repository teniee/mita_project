"""
Pydantic schemas for OCR API endpoints.

Provides comprehensive request/response validation with proper field constraints.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class ReceiptItemData(BaseModel):
    """Schema for individual receipt items"""
    name: Optional[str] = Field(None, description="Item name")
    quantity: Optional[float] = Field(None, ge=0, description="Item quantity")
    price: Optional[float] = Field(None, ge=0, description="Item price")


class CategorizeReceiptRequest(BaseModel):
    """Request schema for receipt categorization endpoint"""
    merchant: Optional[str] = Field(None, description="Merchant/store name")
    store: Optional[str] = Field(None, description="Store name (alternative field)")
    amount: Optional[float] = Field(None, ge=0, description="Receipt total amount")
    total: Optional[float] = Field(None, ge=0, description="Total amount (alternative field)")
    items: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="List of items on receipt")
    category_hint: Optional[str] = Field(None, description="Category hint from OCR")
    category: Optional[str] = Field(None, description="Category (alternative field)")

    @field_validator('items')
    @classmethod
    def validate_items(cls, v: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Validate items list is properly formatted"""
        if v is None:
            return []

        if not isinstance(v, list):
            raise ValueError("items must be an array")

        # Validate each item has reasonable structure
        for idx, item in enumerate(v):
            if not isinstance(item, dict):
                raise ValueError(f"Item at index {idx} must be an object")

        return v

    @field_validator('merchant', 'store', 'category_hint', 'category')
    @classmethod
    def validate_string_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate and sanitize string fields"""
        if v is not None and isinstance(v, str):
            # Strip whitespace
            v = v.strip()
            # Return None if empty after stripping
            if not v:
                return None
            # Limit length to prevent abuse
            if len(v) > 500:
                raise ValueError("Field value too long (max 500 characters)")
        return v

    @field_validator('amount', 'total')
    @classmethod
    def validate_amounts(cls, v: Optional[float]) -> Optional[float]:
        """Validate amount fields are reasonable"""
        if v is not None:
            if v < 0:
                raise ValueError("Amount cannot be negative")
            # Reasonable upper limit to prevent abuse
            if v > 1_000_000:
                raise ValueError("Amount exceeds reasonable limit")
        return v

    def get_merchant(self) -> str:
        """Get merchant name, preferring 'merchant' over 'store'"""
        return self.merchant or self.store or ""

    def get_amount(self) -> float:
        """Get amount, preferring 'amount' over 'total'"""
        return self.amount or self.total or 0.0

    def get_category_hint(self) -> str:
        """Get category hint, preferring 'category_hint' over 'category'"""
        return self.category_hint or self.category or ""


class ConfidenceScores(BaseModel):
    """Schema for OCR confidence scores"""
    merchant: Optional[float] = Field(None, ge=0, le=1, description="Merchant detection confidence")
    amount: Optional[float] = Field(None, ge=0, le=1, description="Amount detection confidence")
    date: Optional[float] = Field(None, ge=0, le=1, description="Date detection confidence")
    items: Optional[float] = Field(None, ge=0, le=1, description="Items detection confidence")


class CategorizeReceiptResponse(BaseModel):
    """Response schema for receipt categorization"""
    category: str = Field(..., description="Detected category")
    confidence: float = Field(..., ge=0, le=1, description="Categorization confidence")
    merchant: str = Field(..., description="Merchant name")
    suggestions: List[str] = Field(..., description="Alternative category suggestions")
    amount: float = Field(..., description="Receipt amount")


class OCRResultData(BaseModel):
    """Schema for OCR processing result"""
    merchant: str = Field(..., description="Detected merchant name")
    amount: float = Field(..., ge=0, description="Total amount")
    date: str = Field(..., description="Receipt date")
    category: str = Field(..., description="Suggested category")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted items")
    confidence: float = Field(..., ge=0, le=1, description="Overall confidence")
    confidence_scores: Optional[Dict[str, float]] = Field(None, description="Field-specific confidence scores")
    fields_needing_review: List[str] = Field(default_factory=list, description="Fields requiring manual review")
    image_url: Optional[str] = Field(None, description="URL to receipt image")


class ProcessReceiptResponse(BaseModel):
    """Response schema for receipt processing"""
    job_id: str = Field(..., description="OCR job identifier")
    status: str = Field(..., description="Processing status")
    result: OCRResultData = Field(..., description="OCR extraction results")
    processed_at: str = Field(..., description="Processing timestamp")


class OCRJobStatusResponse(BaseModel):
    """Response schema for OCR job status check"""
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Job status (pending/processing/completed/failed)")
    progress: float = Field(..., ge=0, le=100, description="Processing progress percentage")
    created_at: Optional[str] = Field(None, description="Job creation timestamp")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp")
    result: Optional[OCRResultData] = Field(None, description="Result data if completed")
    error: Optional[str] = Field(None, description="Error message if failed")


class DeleteReceiptResponse(BaseModel):
    """Response schema for receipt deletion"""
    job_id: str = Field(..., description="Job identifier")
    deleted: bool = Field(..., description="Deletion success flag")
    message: str = Field(..., description="Result message")


class EnhanceImageResponse(BaseModel):
    """Response schema for image enhancement"""
    enhanced: bool = Field(..., description="Enhancement success flag")
    message: str = Field(..., description="Result message")
    enhancements_applied: List[str] = Field(..., description="List of applied enhancements")
    size: int = Field(..., description="Enhanced image size in bytes")
