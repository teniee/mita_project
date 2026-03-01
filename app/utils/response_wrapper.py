"""
Enhanced Response Wrapper for MITA Finance API

Provides standardized success and error response formats that integrate
with the comprehensive error handling system.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from uuid import uuid4

from app.core.standardized_error_handler import (
    StandardizedErrorHandler, 
    StandardizedAPIException
)


class StandardizedResponse:
    """Standardized response formatter for consistent API responses"""
    
    @staticmethod
    def success(
        data: Optional[Union[Dict[str, Any], List[Dict[str, Any]], Any]] = None,
        message: str = "Request completed successfully",
        meta: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_200_OK
    ) -> JSONResponse:
        """Create standardized success response"""
        
        response_content = {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": f"req_{uuid4().hex[:12]}"
        }
        
        # Add metadata if provided
        if meta:
            response_content["meta"] = meta
        
        return JSONResponse(
            status_code=status_code,
            content=response_content
        )
    
    @staticmethod
    def error(
        error: Union[Exception, StandardizedAPIException],
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Create standardized error response using the centralized error handler"""
        return StandardizedErrorHandler.create_response(error, request, user_id, extra_context)
    
    @staticmethod
    def paginated(
        data: List[Dict[str, Any]],
        page: int,
        page_size: int,
        total_count: int,
        message: str = "Request completed successfully"
    ) -> JSONResponse:
        """Create standardized paginated response"""
        
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_previous = page > 1
        
        meta = {
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
                "next_page": page + 1 if has_next else None,
                "previous_page": page - 1 if has_previous else None
            }
        }
        
        return StandardizedResponse.success(
            data=data,
            message=message,
            meta=meta
        )
    
    @staticmethod
    def created(
        data: Optional[Dict[str, Any]] = None,
        message: str = "Resource created successfully",
        location: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Create standardized response for resource creation"""
        
        response = StandardizedResponse.success(
            data=data,
            message=message,
            meta=meta,
            status_code=status.HTTP_201_CREATED
        )
        
        if location:
            response.headers["Location"] = location
        
        return response
    
    @staticmethod
    def accepted(
        data: Optional[Dict[str, Any]] = None,
        message: str = "Request accepted for processing",
        job_id: Optional[str] = None
    ) -> JSONResponse:
        """Create standardized response for accepted/async operations"""
        
        meta = {}
        if job_id:
            meta["job_id"] = job_id
        
        return StandardizedResponse.success(
            data=data,
            message=message,
            meta=meta if meta else None,
            status_code=status.HTTP_202_ACCEPTED
        )
    
    @staticmethod
    def no_content(message: str = "Operation completed successfully") -> JSONResponse:
        """Create standardized response for operations with no content"""
        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content=None
        )


# Backward compatibility functions (deprecated - use StandardizedResponse instead)
def success_response(
    data: Optional[Union[Dict[str, Any], List[Dict[str, Any]], Any]] = None,
    message: str = "Request successful"
) -> JSONResponse:
    """
    DEPRECATED: Use StandardizedResponse.success() instead
    Legacy success response for backward compatibility
    """
    return StandardizedResponse.success(data=data, message=message)


def error_response(
    error_message: str = "Something went wrong",
    status_code: int = 400
) -> JSONResponse:
    """
    DEPRECATED: Use StandardizedResponse.error() instead
    Legacy error response for backward compatibility
    """
    # Create a simple HTTPException-like object for the error handler
    from fastapi import HTTPException
    error = HTTPException(status_code=status_code, detail=error_message)
    return StandardizedErrorHandler.create_response(error)


# Financial-specific response helpers
class FinancialResponseHelper:
    """Helper class for financial operation responses"""
    
    @staticmethod
    def transaction_created(
        transaction_data: Dict[str, Any],
        balance_impact: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Standardized response for transaction creation"""
        
        meta = {}
        if balance_impact:
            meta["balance_impact"] = balance_impact
        
        return StandardizedResponse.created(
            data=transaction_data,
            message="Transaction recorded successfully",
            meta=meta if meta else None
        )
    
    @staticmethod
    def budget_updated(
        budget_data: Dict[str, Any],
        impact_analysis: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Standardized response for budget updates"""
        
        meta = {}
        if impact_analysis:
            meta["impact_analysis"] = impact_analysis
        
        return StandardizedResponse.success(
            data=budget_data,
            message="Budget updated successfully",
            meta=meta if meta else None
        )
    
    @staticmethod
    def analysis_result(
        analysis_data: Dict[str, Any],
        analysis_type: str,
        confidence_score: Optional[float] = None
    ) -> JSONResponse:
        """Standardized response for financial analysis results"""
        
        meta = {
            "analysis_type": analysis_type,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
        
        if confidence_score is not None:
            meta["confidence_score"] = confidence_score
        
        return StandardizedResponse.success(
            data=analysis_data,
            message="Analysis completed successfully",
            meta=meta
        )


# Authentication-specific response helpers
class AuthResponseHelper:
    """Helper class for authentication operation responses"""
    
    @staticmethod
    def login_success(
        tokens: Dict[str, str],
        user_data: Dict[str, Any],
        login_info: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Standardized response for successful login"""
        
        response_data = {
            **tokens,
            "user": user_data
        }
        
        meta = {}
        if login_info:
            meta["login_info"] = login_info
        
        return StandardizedResponse.success(
            data=response_data,
            message="Login successful",
            meta=meta if meta else None
        )
    
    @staticmethod
    def registration_success(
        tokens: Dict[str, str],
        user_data: Dict[str, Any],
        welcome_info: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Standardized response for successful registration"""
        
        response_data = {
            **tokens,
            "user": user_data
        }
        
        meta = {}
        if welcome_info:
            meta["welcome_info"] = welcome_info
        
        return StandardizedResponse.created(
            data=response_data,
            message="Account created successfully",
            meta=meta if meta else None
        )
    
    @staticmethod
    def token_refreshed(tokens: Dict[str, str]) -> JSONResponse:
        """Standardized response for token refresh"""
        return StandardizedResponse.success(
            data=tokens,
            message="Token refreshed successfully"
        )
