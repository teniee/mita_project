#!/usr/bin/env python3
"""
MITA Production Startup Script
Optimized startup sequence for Render deployment
"""
import os
import subprocess
import sys

def main():
    """Main startup sequence"""
    print("🚀 MITA Production Startup")
    print("=" * 50)

    # Set environment defaults
    port = os.getenv('PORT', '8000')

    print(f"Starting on port: {port}")
    print(f"Environment: {os.getenv('ENVIRONMENT', 'production')}")

    # Run database migrations
    print("\n🔄 Running database migrations...")
    try:
        migration_result = subprocess.run(
            ['alembic', 'upgrade', 'head'],
            check=True,
            capture_output=True,
            text=True
        )
        print("✅ Migrations completed successfully")
        if migration_result.stdout:
            print(migration_result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        print("⚠️  Continuing anyway - application may not work correctly")
    except FileNotFoundError:
        print("⚠️  Alembic not found - skipping migrations")

    print("\n🔄 Starting application...")

    # Start uvicorn with production settings
    cmd = [
        'uvicorn',
        'app.main:app',
        '--host', '0.0.0.0',
        '--port', port,
        '--workers', '1',
        '--proxy-headers',  # Trust X-Forwarded-* headers from Railway/Render proxy
        '--forwarded-allow-ips', '*'  # Allow all proxy IPs (Railway/Render internal network)
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("👋 Shutting down gracefully")
        sys.exit(0)

if __name__ == "__main__":
    main()