#!/usr/bin/env python3
"""
Check the actual production database schema to see if it has the updated_at column
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Database URL - same as in alembic.ini but with async driver
DATABASE_URL = "postgresql+asyncpg://postgres.atdcxppfflmiwjwjuqyl:33SatinSatin11Satin@aws-0-us-east-2.pooler.supabase.com:5432/postgres?ssl=require"

async def check_production_schema():
    """Check the production database schema"""
    engine = create_async_engine(DATABASE_URL)
    
    try:
        async with engine.begin() as conn:
            # Check if updated_at column exists
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """))
            
            columns = result.fetchall()
            
            print("Current users table schema:")
            print("=" * 50)
            print(f"{'Column Name':<30} {'Data Type':<20} {'Nullable'}")
            print("-" * 60)
            
            has_updated_at = False
            has_token_version = False
            
            for col in columns:
                print(f"{col[0]:<30} {col[1]:<20} {col[2]}")
                if col[0] == 'updated_at':
                    has_updated_at = True
                if col[0] == 'token_version':
                    has_token_version = True
            
            print("\n" + "=" * 50)
            if has_updated_at and has_token_version:
                print("✅ SUCCESS: Both updated_at and token_version columns exist!")
                
                # Check if there are any users and their data
                user_count = await conn.execute(text("SELECT COUNT(*) FROM users"))
                count = user_count.fetchone()[0]
                print(f"✅ Database has {count} users")
                
                if count > 0:
                    # Check a sample user to see the columns
                    sample = await conn.execute(text("""
                        SELECT email, created_at, updated_at, token_version 
                        FROM users 
                        LIMIT 1
                    """))
                    user = sample.fetchone()
                    if user:
                        print(f"✅ Sample user data:")
                        print(f"   Email: {user[0]}")
                        print(f"   Created at: {user[1]}")
                        print(f"   Updated at: {user[2]}")
                        print(f"   Token version: {user[3]}")
                
                return True
            else:
                print("❌ MISSING COLUMNS:")
                if not has_updated_at:
                    print("   - updated_at column is missing")
                if not has_token_version:
                    print("   - token_version column is missing")
                return False
                
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return False
        
    finally:
        await engine.dispose()

async def main():
    """Main function"""
    print("Checking production database schema...")
    success = await check_production_schema()
    
    if success:
        print("\n🎉 Production database schema is correct!")
        print("The issue might be with the application code or deployment.")
    else:
        print("\n❌ Production database schema needs to be fixed.")
        print("The migration may not have been applied to production.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)