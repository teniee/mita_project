#!/usr/bin/env python3
"""
Test server startup script with minimal dependencies
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Set test environment
os.environ['ENV_FILE'] = '.env.test'
os.environ['ENVIRONMENT'] = 'development'

# Minimal test database URL (SQLite)
test_db_path = Path(__file__).parent / "test_mita.db"
os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{test_db_path}'

# Test JWT secrets
os.environ['JWT_SECRET'] = 'test_jwt_secret_32_chars_minimum_testing'
os.environ['SECRET_KEY'] = 'test_secret_key_32_chars_minimum_testing'

# Disable external services
os.environ['OPENAI_API_KEY'] = 'test-key'
os.environ['SENTRY_DSN'] = ''

# CORS for testing
os.environ['ALLOWED_ORIGINS'] = 'http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000'

# Port configuration
os.environ['PORT'] = '8000'
os.environ['BACKEND_PORT'] = '8000'

print("🚀 Starting MITA test server with minimal configuration...")
print(f"📊 Database: {os.environ['DATABASE_URL']}")
print(f"🔐 JWT Secret: {'Set' if os.environ.get('JWT_SECRET') else 'Missing'}")
print()

# Create test database if it doesn't exist
if not test_db_path.exists():
    print("📂 Creating test database...")
    test_db_path.touch()

# Import and start the app
try:
    import uvicorn
    
    # Run with minimal configuration
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        workers=1
    )
    
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("🔧 Install with: pip install uvicorn")
    sys.exit(1)
except Exception as e:
    print(f"❌ Server startup failed: {e}")
    sys.exit(1)