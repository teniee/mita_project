#!/usr/bin/env python3
"""
Database Schema Verification and Auto-Fix Script
"""

import asyncio
import sys
import os
sys.path.insert(0, '/Users/mikhail/StudioProjects/mita_project')

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text
import logging

logger = logging.getLogger(__name__)

async def verify_and_fix_schema():
    """Verify and fix database schema"""
    
    try:
        # Get database URL
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print("❌ DATABASE_URL not set - cannot verify schema")
            return False
        
        # Convert to sync URL for migration
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Run pending migrations
        print("🔄 Running database migrations...")
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
        
        try:
            command.upgrade(alembic_cfg, "head")
            print("✅ Database migrations completed successfully")
        except Exception as e:
            print(f"⚠️ Migration warning: {e}")
            print("This may be normal if migrations are already applied")
        
        # Verify critical tables and columns exist
        engine = create_engine(sync_url, pool_pre_ping=True)
        inspector = inspect(engine)
        
        # Check users table
        if 'users' not in inspector.get_table_names():
            print("❌ Users table missing - database not properly initialized")
            return False
        
        # Check required columns
        columns = inspector.get_columns('users')
        column_names = [col['name'] for col in columns]
        
        required_columns = [
            'id', 'email', 'password_hash', 'country', 'annual_income', 
            'is_premium', 'created_at', 'updated_at', 'token_version', 'timezone'
        ]
        
        missing_columns = [col for col in required_columns if col not in column_names]
        
        if missing_columns:
            print(f"❌ Missing required columns: {missing_columns}")
            return False
        
        print("✅ Database schema verification completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Schema verification failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(verify_and_fix_schema())
    sys.exit(0 if result else 1)
