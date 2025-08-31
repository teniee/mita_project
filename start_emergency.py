#!/usr/bin/env python3
"""
Emergency startup script for MITA authentication service
Use this when the main FastAPI app has middleware issues
"""

import os
import sys

def main():
    """Start emergency authentication service"""
    print("🚨 STARTING EMERGENCY AUTHENTICATION SERVICE")
    print("This service provides working registration/login for Flutter app")
    print()
    
    # Set required environment variables if not set
    if not os.getenv("JWT_SECRET"):
        os.environ["JWT_SECRET"] = "emergency-jwt-secret-32-chars-minimum"
        print("⚠️ Using default JWT_SECRET for emergency")
    
    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL environment variable is required")
        sys.exit(1)
    
    print(f"✅ Database URL configured: {os.getenv('DATABASE_URL')[:50]}...")
    print(f"✅ JWT Secret configured: {'Yes' if os.getenv('JWT_SECRET') else 'No'}")
    print()
    print("🚀 Starting emergency auth service on port 8001...")
    print("📱 Update Flutter app to use: http://localhost:8001/register")
    print()
    
    # Start the emergency service
    from emergency_auth import app
    app.run(host="0.0.0.0", port=8001, debug=False)

if __name__ == "__main__":
    main()