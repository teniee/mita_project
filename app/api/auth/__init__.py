"""
Authentication module initialization.

Exports the main authentication router for inclusion in the FastAPI application.
"""

from app.api.auth.routes import router

__all__ = ["router"]
