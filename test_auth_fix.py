#!/usr/bin/env python3
"""
Test script to verify the authentication fix works correctly
This script will test the database schema fix by running a simple query
"""
import asyncio
import sys
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Database URL from alembic.ini (using asyncpg driver)
DATABASE_URL = "postgresql+asyncpg://postgres.atdcxppfflmiwjwjuqyl:33SatinSatin11Satin@aws-0-us-east-2.pooler.supabase.com:5432/postgres?ssl=require"

async def test_user_schema():
    """Test that the users table has all required columns"""
    engine = create_async_engine(DATABASE_URL)
    
    try:
        async with engine.begin() as conn:
            # Test if we can query the users table with all expected columns
            result = await conn.execute(text("""
                SELECT 
                    id, 
                    email, 
                    password_hash, 
                    country, 
                    annual_income, 
                    is_premium, 
                    premium_until, 
                    created_at, 
                    updated_at, 
                    timezone, 
                    token_version,
                    password_reset_token,
                    password_reset_expires,
                    password_reset_attempts,
                    email_verified,
                    email_verification_token,
                    email_verification_expires
                FROM users 
                LIMIT 1
            """))
            
            # If query succeeds, schema is correct
            print("✅ Schema test passed: All required columns exist in users table")
            
            # Test inserting a test user to verify constraints work
            test_email = f"test_{datetime.now().timestamp()}@example.com"
            await conn.execute(text("""
                INSERT INTO users (
                    id,
                    email, 
                    password_hash, 
                    country, 
                    annual_income, 
                    is_premium,
                    timezone,
                    token_version,
                    password_reset_attempts,
                    email_verified
                ) VALUES (
                    gen_random_uuid(),
                    :email,
                    'test_hash',
                    'US',
                    50000,
                    false,
                    'UTC',
                    1,
                    0,
                    false
                )
            """), {"email": test_email})
            
            # Verify the test user was created with updated_at automatically set
            result = await conn.execute(text("""
                SELECT email, created_at, updated_at, token_version 
                FROM users 
                WHERE email = :email
            """), {"email": test_email})
            
            user_data = result.fetchone()
            if user_data:
                print(f"✅ Test user created successfully:")
                print(f"   Email: {user_data[0]}")
                print(f"   Created at: {user_data[1]}")
                print(f"   Updated at: {user_data[2]}")
                print(f"   Token version: {user_data[3]}")
                
                # Clean up test user
                await conn.execute(text("DELETE FROM users WHERE email = :email"), {"email": test_email})
                print("✅ Test user cleaned up")
            else:
                print("❌ Test user was not found after creation")
                return False
                
        print("✅ All tests passed! Authentication schema is fixed.")
        return True
        
    except Exception as e:
        print(f"❌ Schema test failed: {e}")
        return False
        
    finally:
        await engine.dispose()

async def main():
    """Main test function"""
    print("Testing database schema fix for authentication...")
    print("=" * 50)
    
    success = await test_user_schema()
    
    if success:
        print("\n🎉 SUCCESS: Database schema is now compatible with the User model!")
        print("Authentication endpoints should now work correctly.")
        sys.exit(0)
    else:
        print("\n❌ FAILURE: There are still issues with the database schema.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())