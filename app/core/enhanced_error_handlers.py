"""
Production Error Handler Enhancements
"""

import logging
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from app.core.standardized_error_handler import ErrorCode, ErrorResponse, StandardizedErrorHandler

logger = logging.getLogger(__name__)

async def enhanced_system_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Enhanced system error handler for production"""
    
    # Map common production errors to proper codes
    if "database" in str(exc).lower():
        # Database connection issues -> SYSTEM_8001
        error = {
            "success": False,
            "error": {
                "code": ErrorCode.SYSTEM_INTERNAL_ERROR,  # SYSTEM_8001
                "message": "An unexpected error occurred",
                "details": {}
            }
        }
    elif "token" in str(exc).lower() or "jwt" in str(exc).lower():
        # JWT issues -> AUTH_1001
        error = {
            "success": False, 
            "error": {
                "code": ErrorCode.AUTH_INVALID_CREDENTIALS,  # AUTH_1001
                "message": "Invalid email or password",
                "details": {}
            }
        }
    else:
        # Generic system error
        error = {
            "success": False,
            "error": {
                "code": ErrorCode.SYSTEM_INTERNAL_ERROR,  # SYSTEM_8001
                "message": "An unexpected error occurred",
                "details": {}
            }
        }
    
    # Log the actual error for debugging
    logger.error(f"System error: {exc}", exc_info=True)
    
    return JSONResponse(status_code=500, content=error)

def register_enhanced_error_handlers(app):
    """Register enhanced error handlers"""
    
    # Handle uncaught exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return await enhanced_system_error_handler(request, exc)
    
    # Handle HTTP exceptions with proper error codes
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        
        # Map HTTP status codes to our error codes
        if exc.status_code == 401:
            error_code = ErrorCode.AUTH_INVALID_CREDENTIALS  # AUTH_1001
        elif exc.status_code == 500:
            error_code = ErrorCode.SYSTEM_INTERNAL_ERROR     # SYSTEM_8001
        else:
            error_code = ErrorCode.SYSTEM_INTERNAL_ERROR
            
        error = {
            "success": False,
            "error": {
                "code": error_code,
                "message": exc.detail if isinstance(exc.detail, str) else "An error occurred",
                "details": {}
            }
        }
        
        return JSONResponse(status_code=exc.status_code, content=error)
