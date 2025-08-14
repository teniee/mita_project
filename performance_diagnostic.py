#!/usr/bin/env python3
"""
Performance diagnostic tool for MITA Finance API
Helps identify performance bottlenecks and configuration issues
"""

import asyncio
import time
import logging
import os
import psutil
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_database_performance():
    """Test database connection performance"""
    try:
        from app.core.async_session import get_async_db_context
        
        start_time = time.time()
        async with get_async_db_context() as db:
            await db.execute("SELECT 1")
            connection_time = (time.time() - start_time) * 1000
            
        return {
            "status": "connected",
            "connection_time_ms": round(connection_time, 2),
            "performance": "good" if connection_time < 100 else "slow" if connection_time < 500 else "poor"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "performance": "failed"
        }


async def test_auth_performance():
    """Test authentication performance"""
    try:
        from app.services.auth_jwt_service import async_hash_password, create_access_token
        
        # Test password hashing performance
        start_time = time.time()
        await async_hash_password("test_password_123")
        hash_time = (time.time() - start_time) * 1000
        
        # Test token creation performance
        start_time = time.time()
        create_access_token({"sub": "test_user"})
        token_time = (time.time() - start_time) * 1000
        
        return {
            "password_hash_time_ms": round(hash_time, 2),
            "token_creation_time_ms": round(token_time, 2),
            "hash_performance": "good" if hash_time < 200 else "slow" if hash_time < 500 else "poor",
            "token_performance": "good" if token_time < 10 else "slow" if token_time < 50 else "poor"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def check_system_resources():
    """Check system resource usage"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory.percent,
            "memory_available_mb": round(memory.available / 1024 / 1024, 2),
            "disk_usage_percent": disk.percent,
            "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def check_environment_config():
    """Check critical environment variables"""
    config_checks = {
        "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
        "JWT_SECRET": bool(os.getenv("JWT_SECRET")),
        "SECRET_KEY": bool(os.getenv("SECRET_KEY")),
        "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
        "UPSTASH_REDIS_URL": bool(os.getenv("UPSTASH_REDIS_URL")),
        "RENDER": bool(os.getenv("RENDER")),
        "PORT": os.getenv("PORT", "8000")
    }
    
    return config_checks


async def run_performance_diagnostic():
    """Run comprehensive performance diagnostic"""
    logger.info("🔍 Starting MITA Finance API Performance Diagnostic...")
    
    diagnostic_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": "render" if os.getenv("RENDER") else "local",
        "environment_config": check_environment_config(),
        "system_resources": check_system_resources(),
        "database_performance": await test_database_performance(),
        "auth_performance": await test_auth_performance()
    }
    
    # Print diagnostic results
    print("\n" + "="*60)
    print("MITA FINANCE API PERFORMANCE DIAGNOSTIC REPORT")
    print("="*60)
    
    print(f"\n📅 Timestamp: {diagnostic_results['timestamp']}")
    print(f"🔧 Platform: {diagnostic_results['platform']}")
    
    print(f"\n🔧 Environment Configuration:")
    for key, value in diagnostic_results['environment_config'].items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}: {value}")
    
    print(f"\n💻 System Resources:")
    resources = diagnostic_results['system_resources']
    if 'error' not in resources:
        print(f"  🔥 CPU Usage: {resources['cpu_usage_percent']:.1f}%")
        print(f"  🧠 Memory Usage: {resources['memory_usage_percent']:.1f}%")
        print(f"  💾 Memory Available: {resources['memory_available_mb']:.1f} MB")
        print(f"  💿 Disk Usage: {resources['disk_usage_percent']:.1f}%")
        print(f"  🗃️ Disk Free: {resources['disk_free_gb']:.1f} GB")
    else:
        print(f"  ❌ Error: {resources['error']}")
    
    print(f"\n🗄️ Database Performance:")
    db_perf = diagnostic_results['database_performance']
    if db_perf['status'] == 'connected':
        print(f"  ✅ Status: Connected")
        print(f"  ⚡ Connection Time: {db_perf['connection_time_ms']} ms")
        print(f"  📊 Performance: {db_perf['performance']}")
    else:
        print(f"  ❌ Status: {db_perf['status']}")
        if 'error' in db_perf:
            print(f"  🚫 Error: {db_perf['error']}")
    
    print(f"\n🔐 Authentication Performance:")
    auth_perf = diagnostic_results['auth_performance']
    if 'error' not in auth_perf:
        print(f"  🔑 Password Hashing: {auth_perf['password_hash_time_ms']} ms ({auth_perf['hash_performance']})")
        print(f"  🎫 Token Creation: {auth_perf['token_creation_time_ms']} ms ({auth_perf['token_performance']})")
    else:
        print(f"  ❌ Error: {auth_perf['error']}")
    
    # Performance recommendations
    print(f"\n💡 Performance Recommendations:")
    
    if db_perf.get('connection_time_ms', 0) > 500:
        print("  ⚠️ Database connection is slow - check network latency and connection pool settings")
    
    if auth_perf.get('password_hash_time_ms', 0) > 500:
        print("  ⚠️ Password hashing is slow - consider reducing bcrypt rounds")
    
    if resources.get('memory_usage_percent', 0) > 80:
        print("  ⚠️ High memory usage - consider reducing cache sizes and connection pools")
    
    if resources.get('cpu_usage_percent', 0) > 80:
        print("  ⚠️ High CPU usage - consider optimizing crypto operations and middleware")
    
    if not diagnostic_results['environment_config'].get('UPSTASH_REDIS_URL'):
        print("  ⚠️ Redis URL not configured - rate limiting may not work properly")
    
    print(f"\n✅ Diagnostic complete!")
    print("="*60)
    
    return diagnostic_results


if __name__ == "__main__":
    asyncio.run(run_performance_diagnostic())