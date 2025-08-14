#!/usr/bin/env python3
"""
Render-optimized startup script for MITA Finance API
This script applies specific optimizations for Render deployment
"""

import os
import sys
import logging
from app.core.deployment_optimizations import get_deployment_config

# Set up optimized logging for Render
logging.basicConfig(
    level=logging.WARNING,  # Reduce log volume for Render
    format="%(levelname)s - %(message)s",  # Simple format
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def optimize_for_render():
    """Apply Render-specific optimizations"""
    
    # Force Render platform detection
    os.environ["RENDER"] = "true"
    
    # Get deployment configuration
    config = get_deployment_config()
    
    # Apply environment variables for optimal performance
    optimizations = config["optimizations"]
    
    # Uvicorn settings
    os.environ.setdefault("WEB_CONCURRENCY", "1")  # Single worker for Render
    os.environ.setdefault("TIMEOUT", "15")  # Fast timeout
    os.environ.setdefault("KEEPALIVE", "2")
    
    # Database settings
    os.environ.setdefault("DB_POOL_SIZE", "3")
    os.environ.setdefault("DB_MAX_OVERFLOW", "7")
    os.environ.setdefault("DB_POOL_TIMEOUT", "5")
    
    # Memory optimizations
    os.environ.setdefault("PYTHONMAXMEMORY", "256m")
    
    logger.info("Applied Render-specific optimizations")
    return config

def main():
    """Main startup function"""
    try:
        config = optimize_for_render()
        
        # Import and start the application
        import uvicorn
        from app.main import app
        
        # Get optimized uvicorn configuration
        uvicorn_config = config["uvicorn"]
        
        logger.info("Starting MITA Finance API with Render optimizations...")
        
        # Start the server
        uvicorn.run(
            app,
            host=uvicorn_config["host"],
            port=uvicorn_config["port"],
            workers=uvicorn_config["workers"],
            timeout_keep_alive=uvicorn_config["timeout_keep_alive"],
            limit_max_requests=uvicorn_config["limit_max_requests"],
            access_log=False,  # Disable for performance
            log_level="warning"
        )
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()