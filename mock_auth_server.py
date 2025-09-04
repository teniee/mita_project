#!/usr/bin/env python3
"""
Mock Authentication Server for Load Testing
Simulates MITA auth endpoints for comprehensive load testing
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
import hashlib
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Mock database
mock_users: Dict[str, dict] = {}
mock_sessions: Dict[str, dict] = {}
rate_limit_storage: Dict[str, list] = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mock MITA Auth Server", description="For load testing purposes")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def check_rate_limit(request: Request, limit: int = 5, window: int = 300) -> bool:
    """Simple rate limiting check"""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    if client_ip not in rate_limit_storage:
        rate_limit_storage[client_ip] = []
    
    # Clean old entries
    rate_limit_storage[client_ip] = [
        timestamp for timestamp in rate_limit_storage[client_ip]
        if now - timestamp < window
    ]
    
    # Check limit
    if len(rate_limit_storage[client_ip]) >= limit:
        return False
    
    # Add current request
    rate_limit_storage[client_ip].append(now)
    return True

def create_mock_token(user_id: str, email: str) -> str:
    """Create a mock JWT token"""
    token_data = {
        "sub": user_id,
        "email": email,
        "exp": int((datetime.utcnow() + timedelta(days=30)).timestamp()),
        "iat": int(datetime.utcnow().timestamp())
    }
    # Simple encoding for testing
    return f"mock_token_{user_id}_{int(time.time())}"

# Simulate processing delay randomly
async def simulate_processing_delay():
    """Simulate realistic processing delays"""
    import random
    delay = random.uniform(0.01, 0.3)  # 10ms to 300ms
    await asyncio.sleep(delay)

@app.get("/auth/emergency-diagnostics")
async def emergency_diagnostics():
    """Mock emergency diagnostics endpoint"""
    await simulate_processing_delay()
    
    return {
        "status": "EMERGENCY_DIAGNOSTICS_COMPLETE",
        "message": "Mock diagnostics for load testing",
        "diagnostics": {
            "timestamp": time.time(),
            "server_status": "LIVE",
            "database": {"status": "connected", "connection_time_ms": 15.5},
            "registration_endpoints": {
                "emergency_register": "✅ AVAILABLE - /auth/emergency-register",
                "regular_register": "✅ AVAILABLE - /auth/register"
            }
        }
    }

@app.get("/auth/security/status")
async def security_status():
    """Mock security status endpoint"""
    await simulate_processing_delay()
    
    return {
        "success": True,
        "data": {
            "security_health": {"status": "healthy", "checks_passed": 5},
            "password_security": {"bcrypt_rounds": 12, "security_compliant": True},
            "rate_limit_status": {"requests_remaining": 999, "reset_time": 0}
        }
    }

@app.post("/auth/emergency-register")
async def emergency_register(request: Request):
    """Mock emergency registration endpoint"""
    if not check_rate_limit(request, limit=10, window=300):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    await simulate_processing_delay()
    
    try:
        data = await request.json()
        email = data.get("email", "").lower()
        password = data.get("password", "")
        
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="Invalid email")
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password too short")
        
        if email in mock_users:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create mock user
        user_id = str(uuid.uuid4())
        mock_users[email] = {
            "id": user_id,
            "email": email,
            "password": hashlib.sha256(password.encode()).hexdigest(),
            "country": data.get("country", "US"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Create tokens
        access_token = create_mock_token(user_id, email)
        refresh_token = f"refresh_{access_token}"
        
        mock_sessions[access_token] = {
            "user_id": user_id,
            "email": email,
            "created_at": time.time()
        }
        
        logger.info(f"Mock registration successful: {email[:3]}***")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mock registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/auth/register")
async def register(request: Request):
    """Mock registration endpoint"""
    if not check_rate_limit(request, limit=3, window=3600):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    await simulate_processing_delay()
    
    try:
        data = await request.json()
        email = data.get("email", "").lower()
        password = data.get("password", "")
        
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="Invalid email")
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password too short")
        
        if email in mock_users:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create mock user
        user_id = str(uuid.uuid4())
        mock_users[email] = {
            "id": user_id,
            "email": email,
            "password": hashlib.sha256(password.encode()).hexdigest(),
            "country": data.get("country", "US"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Create tokens
        access_token = create_mock_token(user_id, email)
        refresh_token = f"refresh_{access_token}"
        
        mock_sessions[access_token] = {
            "user_id": user_id,
            "email": email,
            "created_at": time.time()
        }
        
        logger.info(f"Mock registration successful: {email[:3]}***")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mock registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/auth/register-fast")
async def register_fast(request: Request):
    """Mock fast registration endpoint"""
    if not check_rate_limit(request, limit=5, window=1800):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    await simulate_processing_delay()
    return await register(request)

@app.post("/auth/register-full")
async def register_full(request: Request):
    """Mock full registration endpoint"""
    if not check_rate_limit(request, limit=3, window=3600):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    await simulate_processing_delay()
    return await register(request)

@app.post("/auth/login")
async def login(request: Request):
    """Mock login endpoint"""
    if not check_rate_limit(request, limit=5, window=900):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    await simulate_processing_delay()
    
    try:
        data = await request.json()
        email = data.get("email", "").lower()
        password = data.get("password", "")
        
        if email not in mock_users:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        user = mock_users[email]
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if user["password"] != password_hash:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Create new session
        access_token = create_mock_token(user["id"], email)
        refresh_token = f"refresh_{access_token}"
        
        mock_sessions[access_token] = {
            "user_id": user["id"],
            "email": email,
            "created_at": time.time()
        }
        
        logger.info(f"Mock login successful: {email[:3]}***")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mock login error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@app.post("/auth/refresh")
async def refresh_token(request: Request):
    """Mock token refresh endpoint"""
    if not check_rate_limit(request, limit=20, window=300):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    await simulate_processing_delay()
    
    try:
        auth_header = request.headers.get("authorization", "")
        token = auth_header.replace("Bearer ", "")
        
        if not token or not token.startswith("refresh_"):
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Extract original token
        original_token = token.replace("refresh_", "")
        
        if original_token not in mock_sessions:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        session = mock_sessions[original_token]
        
        # Create new tokens
        new_access_token = create_mock_token(session["user_id"], session["email"])
        new_refresh_token = f"refresh_{new_access_token}"
        
        # Update session
        del mock_sessions[original_token]
        mock_sessions[new_access_token] = session
        
        logger.info(f"Mock token refresh successful: {session['email'][:3]}***")
        
        return {
            "success": True,
            "data": {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mock refresh error: {e}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@app.post("/auth/logout")
async def logout(request: Request):
    """Mock logout endpoint"""
    await simulate_processing_delay()
    
    try:
        auth_header = request.headers.get("authorization", "")
        token = auth_header.replace("Bearer ", "")
        
        if token in mock_sessions:
            del mock_sessions[token]
            logger.info("Mock logout successful")
        
        return {"success": True, "data": {"message": "Successfully logged out."}}
        
    except Exception as e:
        logger.error(f"Mock logout error: {e}")
        return {"success": True, "data": {"message": "Logout processed."}}

@app.get("/auth/token/validate")
async def validate_token(request: Request):
    """Mock token validation endpoint"""
    await simulate_processing_delay()
    
    try:
        auth_header = request.headers.get("authorization", "")
        token = auth_header.replace("Bearer ", "")
        
        if token not in mock_sessions:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        session = mock_sessions[token]
        
        return {
            "success": True,
            "data": {
                "user_id": session["user_id"],
                "token_validation": {"valid": True, "expires_in": 3600}
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mock validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/auth/password-reset/request")
async def password_reset_request(request: Request):
    """Mock password reset endpoint"""
    if not check_rate_limit(request, limit=3, window=1800):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    await simulate_processing_delay()
    
    return {
        "success": True,
        "data": {
            "message": "If this email is registered, you will receive password reset instructions."
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "mock_server": True,
        "users_registered": len(mock_users),
        "active_sessions": len(mock_sessions)
    }

if __name__ == "__main__":
    print("🚀 Starting Mock MITA Authentication Server for Load Testing")
    print("📊 This server simulates all authentication endpoints")
    print("🔄 Rate limiting is enabled to test rate limiting scenarios")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )