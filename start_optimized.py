#!/usr/bin/env python3
"""
Optimized startup script for MITA Finance Backend
Applies platform-specific optimizations and starts the server with optimal settings
"""

import os
import sys
import logging
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from app.core.deployment_optimizations import get_deployment_config, apply_platform_optimizations

def main():
    """Main startup function with optimizations"""
    
    # Apply platform optimizations
    config = get_deployment_config()
    platform = config["platform"]
    
    print(f"🚀 Starting MITA Finance API for platform: {platform}")
    
    # Apply optimizations
    apply_platform_optimizations()
    
    # Get uvicorn configuration
    uvicorn_config = config["uvicorn"]
    
    # Import and configure uvicorn
    import uvicorn
    
    # Override with environment variables if present
    host = os.getenv("HOST", uvicorn_config.get("host", "0.0.0.0"))
    port = int(os.getenv("PORT", uvicorn_config.get("port", 8000)))
    workers = int(os.getenv("WEB_CONCURRENCY", uvicorn_config.get("workers", 1)))
    
    # Configure based on platform
    if platform in ["render", "heroku", "railway"]:
        # These platforms handle process management
        workers = 1
        
    elif platform == "aws_lambda":
        # Lambda-specific configuration
        print("⚠️ Lambda detected - use serverless deployment instead")
        sys.exit(1)
    
    # Start the server with optimized configuration
    print(f"🔧 Platform: {platform}")
    print(f"🌐 Host: {host}:{port}")
    print(f"👥 Workers: {workers}")
    print(f"📊 Database pool size: {config['optimizations'].get('database_pool_size', 10)}")
    print(f"🧠 Memory limit: {config['optimizations'].get('memory_limit', 'Unknown')}")
    
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            workers=workers,
            reload=False,  # Always False in production
            access_log=uvicorn_config.get("access_log", True),
            log_level=uvicorn_config.get("log_level", "info"),
            timeout_keep_alive=uvicorn_config.get("timeout_keep_alive", 2),
            limit_max_requests=uvicorn_config.get("limit_max_requests", 1000),
            backlog=uvicorn_config.get("backlog", 100),
            timeout_graceful_shutdown=uvicorn_config.get("timeout_graceful_shutdown", 10)
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()