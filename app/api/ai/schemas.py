"""
AI API Schemas - Request/Response models for AI endpoints
Production-ready Pydantic v2 models with comprehensive validation
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.core.validators import InputSanitizer


class AIAssistantRequest(BaseModel):
    """Request schema for AI assistant endpoint with strict validation"""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User's financial question for the AI assistant"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional context for the question (e.g., category, date range)"
    )

    @field_validator('question')
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Sanitize and validate question text"""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty or whitespace")

        # Sanitize the question text
        sanitized = InputSanitizer.sanitize_string(v.strip(), max_length=1000)

        if not sanitized:
            raise ValueError("Question contains only invalid characters")

        return sanitized

    @field_validator('context')
    @classmethod
    def validate_context(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize context dictionary"""
        if not isinstance(v, dict):
            raise ValueError("Context must be a dictionary")

        # Sanitize string values in context
        sanitized_context = {}
        for key, value in v.items():
            if isinstance(value, str):
                sanitized_context[key] = InputSanitizer.sanitize_string(value, max_length=500)
            else:
                sanitized_context[key] = value

        return sanitized_context


class AIAssistantResponse(BaseModel):
    """Response schema for AI assistant endpoint"""

    answer: str = Field(..., description="AI-generated answer to the question")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    related_insights: List[str] = Field(default_factory=list, description="Related insights")
    follow_up_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")


class CategorySuggestionRequest(BaseModel):
    """Request schema for category suggestion endpoint"""

    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Transaction description"
    )
    amount: Optional[float] = Field(
        None,
        gt=0,
        description="Transaction amount"
    )

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize description if provided"""
        if v is None:
            return v

        sanitized = InputSanitizer.sanitize_string(v.strip(), max_length=500)
        return sanitized if sanitized else None


class SnapshotRequest(BaseModel):
    """Request schema for creating AI snapshot"""

    year: int = Field(..., ge=2020, le=2030, description="Snapshot year")
    month: int = Field(..., ge=1, le=12, description="Snapshot month")


class DayStatusRequest(BaseModel):
    """Request schema for day status explanation"""

    date: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Date in YYYY-MM-DD format"
    )


class SpendingPredictionRequest(BaseModel):
    """Request schema for spending prediction"""

    category: Optional[str] = Field(None, max_length=100, description="Category to predict")
    days: int = Field(7, ge=1, le=365, description="Number of days to predict")

    @field_validator('category')
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize category if provided"""
        if v is None:
            return v

        sanitized = InputSanitizer.sanitize_string(v.strip(), max_length=100)
        return sanitized if sanitized else None


class GoalAnalysisRequest(BaseModel):
    """Request schema for goal analysis"""

    goal_id: str = Field(..., min_length=1, max_length=100, description="Goal ID to analyze")

    @field_validator('goal_id')
    @classmethod
    def validate_goal_id(cls, v: str) -> str:
        """Sanitize goal ID"""
        if not v or not v.strip():
            raise ValueError("Goal ID cannot be empty")

        return InputSanitizer.sanitize_string(v.strip(), max_length=100)


class MonthlyReportRequest(BaseModel):
    """Request schema for monthly report"""

    year: Optional[int] = Field(None, ge=2020, le=2030, description="Report year")
    month: Optional[int] = Field(None, ge=1, le=12, description="Report month")