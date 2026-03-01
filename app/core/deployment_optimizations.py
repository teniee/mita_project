"""
Deployment-specific optimizations for various platforms
Handles platform-specific configurations for optimal performance
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DeploymentOptimizer:
    """Optimizations for different deployment platforms"""
    
    @staticmethod
    def detect_platform() -> str:
        """Detect the deployment platform"""
        # Render
        if os.getenv("RENDER"):
            return "render"
        
        # Heroku
        if os.getenv("DYNO"):
            return "heroku"
        
        # Railway
        if os.getenv("RAILWAY_ENVIRONMENT"):
            return "railway"
        
        # Vercel
        if os.getenv("VERCEL"):
            return "vercel"
        
        # AWS Lambda
        if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
            return "aws_lambda"
        
        # Google Cloud Run
        if os.getenv("K_SERVICE"):
            return "gcp_cloudrun"
        
        # Azure Container Instances
        if os.getenv("AZURE_CLIENT_ID"):
            return "azure"
        
        # Docker/Generic
        if os.getenv("DOCKER_CONTAINER"):
            return "docker"
        
        return "local"
    
    @staticmethod
    def get_platform_optimizations(platform: str) -> Dict[str, Any]:
        """Get platform-specific optimizations"""
        
        if platform == "render":
            return {
                "worker_processes": 1,  # Render has limited resources
                "worker_connections": 50,   # Reduced for memory conservation
                "keep_alive": 2,
                "timeout": 15,             # Faster timeout for responsive errors
                "max_requests": 500,       # Reduced to prevent memory buildup
                "max_requests_jitter": 25,
                "preload_app": True,
                "database_pool_size": 3,   # Very small pool for Render
                "database_max_overflow": 7, # Reduced overflow
                "memory_limit": "256MB",   # More conservative memory limit
                "log_level": "WARNING",    # Reduce logging overhead
                "enable_gzip": True,
                "static_file_caching": True,
                "render_optimized": True
            }
        
        elif platform == "heroku":
            return {
                "worker_processes": 1,
                "worker_connections": 100,
                "keep_alive": 2,
                "timeout": 30,
                "max_requests": 1200,
                "max_requests_jitter": 100,
                "preload_app": True,
                "database_pool_size": 10,
                "database_max_overflow": 20,
                "memory_limit": "512MB",
                "log_level": "INFO",
                "enable_gzip": True
            }
        
        elif platform == "railway":
            return {
                "worker_processes": 2,
                "worker_connections": 200,
                "keep_alive": 5,
                "timeout": 60,
                "max_requests": 2000,
                "max_requests_jitter": 100,
                "preload_app": True,
                "database_pool_size": 15,
                "database_max_overflow": 25,
                "memory_limit": "1GB",
                "log_level": "INFO"
            }
        
        elif platform == "gcp_cloudrun":
            return {
                "worker_processes": 1,
                "worker_connections": 100,
                "keep_alive": 2,
                "timeout": 60,
                "max_requests": 1000,
                "preload_app": True,
                "database_pool_size": 8,
                "database_max_overflow": 15,
                "memory_limit": "1GB",
                "log_level": "INFO",
                "cold_start_optimization": True
            }
        
        elif platform == "aws_lambda":
            return {
                "worker_processes": 1,
                "database_pool_size": 3,  # Lambda has connection limits
                "database_max_overflow": 5,
                "timeout": 15,  # Lambda timeout limits
                "memory_limit": "512MB",
                "log_level": "WARNING",  # Reduce logging overhead
                "cold_start_optimization": True,
                "lambda_optimized": True
            }
        
        else:  # local or docker
            return {
                "worker_processes": 4,
                "worker_connections": 1000,
                "keep_alive": 5,
                "timeout": 120,
                "max_requests": 5000,
                "max_requests_jitter": 200,
                "preload_app": False,
                "database_pool_size": 20,
                "database_max_overflow": 30,
                "memory_limit": "2GB",
                "log_level": "DEBUG"
            }
    
    @staticmethod
    def get_uvicorn_config(platform: str) -> Dict[str, Any]:
        """Get uvicorn configuration for the platform"""
        opts = DeploymentOptimizer.get_platform_optimizations(platform)
        
        config = {
            "host": "0.0.0.0",
            "port": int(os.getenv("PORT", 8000)),
            "workers": opts.get("worker_processes", 1),
            "backlog": opts.get("worker_connections", 100),
            "keepalive": opts.get("keep_alive", 2),
            "timeout_keep_alive": opts.get("keep_alive", 2),
            "limit_max_requests": opts.get("max_requests", 1000),
            "timeout_graceful_shutdown": 10,
            "access_log": platform != "aws_lambda",  # Disable for Lambda
            "log_level": opts.get("log_level", "info").lower()
        }
        
        # Platform-specific adjustments
        if platform in ["render", "heroku"]:
            # These platforms handle the process management
            config["workers"] = 1
        
        if platform == "aws_lambda":
            # Lambda-specific optimizations
            config.update({
                "timeout_keep_alive": 0,
                "access_log": False,
                "workers": 1
            })
        
        return config
    
    @staticmethod
    def apply_database_optimizations(platform: str, engine_config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply platform-specific database optimizations"""
        opts = DeploymentOptimizer.get_platform_optimizations(platform)
        
        # Update pool settings
        engine_config.update({
            "pool_size": opts.get("database_pool_size", 10),
            "max_overflow": opts.get("database_max_overflow", 20),
        })
        
        # Platform-specific database optimizations
        if platform == "render":
            # Render has strict connection and memory limits
            engine_config.update({
                "pool_timeout": 5,         # Faster timeout for responsiveness
                "pool_recycle": 600,       # 10 minutes - more frequent recycle
                "pool_pre_ping": True,
                "connect_args": {
                    "server_settings": {
                        "application_name": "mita_render",
                        "jit": "off",
                        "log_statement": "none",
                        "tcp_keepalives_idle": "120",  # 2 minutes
                        "tcp_keepalives_interval": "10",
                        "tcp_keepalives_count": "2"
                    },
                    "command_timeout": 3  # Very short query timeout
                }
            })
        
        elif platform == "heroku":
            # Heroku Postgres optimizations
            engine_config.update({
                "pool_timeout": 20,
                "pool_recycle": 3600,  # 1 hour
                "pool_pre_ping": True
            })
        
        elif platform == "aws_lambda":
            # Lambda connection optimizations
            engine_config.update({
                "pool_size": 1,  # Single connection for Lambda
                "max_overflow": 0,
                "pool_timeout": 5,
                "pool_recycle": 300,  # 5 minutes
                "pool_pre_ping": True
            })
        
        return engine_config
    
    @staticmethod
    def get_memory_optimizations(platform: str) -> Dict[str, Any]:
        """Get memory optimization settings"""
        opts = DeploymentOptimizer.get_platform_optimizations(platform)
        
        return {
            "cache_size_limit": {
                "render": 50 * 1024 * 1024,    # 50MB
                "heroku": 100 * 1024 * 1024,   # 100MB
                "railway": 200 * 1024 * 1024,  # 200MB
                "aws_lambda": 25 * 1024 * 1024, # 25MB
                "gcp_cloudrun": 100 * 1024 * 1024, # 100MB
                "local": 500 * 1024 * 1024      # 500MB
            }.get(platform, 100 * 1024 * 1024),
            
            "enable_gc_optimization": platform in ["render", "heroku", "aws_lambda"],
            "max_memory_usage": opts.get("memory_limit", "512MB")
        }
    
    @staticmethod
    def configure_logging(platform: str) -> Dict[str, Any]:
        """Configure logging for the platform"""
        opts = DeploymentOptimizer.get_platform_optimizations(platform)
        
        config = {
            "level": opts.get("log_level", "INFO"),
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "disable_existing_loggers": False
        }
        
        # Platform-specific logging
        if platform in ["render", "heroku", "railway"]:
            # These platforms capture stdout
            config["handlers"] = ["console"]
        
        elif platform == "aws_lambda":
            # Lambda uses CloudWatch
            config.update({
                "level": "WARNING",  # Reduce log volume
                "handlers": ["console"],
                "format": "%(levelname)s - %(message)s"  # Simpler format
            })
        
        return config


def get_deployment_config() -> Dict[str, Any]:
    """Get complete deployment configuration"""
    platform = DeploymentOptimizer.detect_platform()
    logger.info(f"Detected deployment platform: {platform}")
    
    return {
        "platform": platform,
        "optimizations": DeploymentOptimizer.get_platform_optimizations(platform),
        "uvicorn": DeploymentOptimizer.get_uvicorn_config(platform),
        "memory": DeploymentOptimizer.get_memory_optimizations(platform),
        "logging": DeploymentOptimizer.configure_logging(platform)
    }


def apply_platform_optimizations():
    """Apply optimizations based on detected platform"""
    config = get_deployment_config()
    platform = config["platform"]
    
    logger.info(f"Applying optimizations for platform: {platform}")
    
    # Set environment variables for the platform
    optimizations = config["optimizations"]
    
    if "worker_processes" in optimizations:
        os.environ.setdefault("WEB_CONCURRENCY", str(optimizations["worker_processes"]))
    
    if "timeout" in optimizations:
        os.environ.setdefault("TIMEOUT", str(optimizations["timeout"]))
    
    # Configure garbage collection for memory-constrained environments
    if optimizations.get("enable_gc_optimization"):
        import gc
        gc.set_threshold(700, 10, 10)  # More aggressive GC
        logger.info("Enabled aggressive garbage collection for memory optimization")
    
    return config