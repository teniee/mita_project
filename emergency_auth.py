#!/usr/bin/env python3
"""
🚀 EMERGENCY AUTHENTICATION SERVICE FOR FLUTTER APP
Independent service to handle registration when main FastAPI app has issues
"""

import os
import json
import uuid
import bcrypt
import psycopg2
import jwt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return {"status": "healthy", "service": "Emergency Auth Service"}

@app.route('/register', methods=['POST'])
def register_user():
    """Working registration endpoint for Flutter app"""
    try:
        data = request.json
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        country = data.get('country', 'US')
        annual_income = data.get('annual_income', 0)
        timezone = data.get('timezone', 'UTC')
        
        # Validation
        if not email or '@' not in email:
            return jsonify({"error": "Invalid email format"}), 400
        if not password or len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        
        # Database connection
        DATABASE_URL = os.getenv("DATABASE_URL", "")
        if "+asyncpg" in DATABASE_URL:
            DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        try:
            # Check if user exists
            cur.execute("SELECT id FROM users WHERE email = %s LIMIT 1", (email,))
            if cur.fetchone():
                return jsonify({"error": "Email already registered"}), 400
            
            # Hash password
            password_bytes = password.encode('utf-8')
            salt = bcrypt.gensalt(rounds=8)
            password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
            
            # Create user
            user_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO users (id, email, password_hash, country, annual_income, timezone, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (user_id, email, password_hash, country, annual_income, timezone))
            
            conn.commit()
            
            # Create JWT token
            payload = {
                'sub': user_id,
                'email': email,
                'exp': datetime.utcnow() + timedelta(days=30),
                'iat': datetime.utcnow(),
                'is_premium': False,
                'country': country
            }
            
            JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or "emergency-jwt-secret"
            access_token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
            
            return jsonify({
                "access_token": access_token,
                "refresh_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user_id,
                    "email": email,
                    "country": country,
                    "is_premium": False
                }
            }), 201
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

@app.route('/login', methods=['POST'])
def login_user():
    """Working login endpoint for Flutter app"""
    try:
        data = request.json
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
        
        # Database connection
        DATABASE_URL = os.getenv("DATABASE_URL", "")
        if "+asyncpg" in DATABASE_URL:
            DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        try:
            # Get user
            cur.execute("SELECT id, password_hash, country FROM users WHERE email = %s", (email,))
            user_data = cur.fetchone()
            
            if not user_data:
                return jsonify({"error": "Invalid email or password"}), 401
            
            user_id, stored_hash, country = user_data
            
            # Verify password
            if not bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                return jsonify({"error": "Invalid email or password"}), 401
            
            # Create JWT token
            payload = {
                'sub': str(user_id),
                'email': email,
                'exp': datetime.utcnow() + timedelta(days=30),
                'iat': datetime.utcnow(),
                'is_premium': False,
                'country': country
            }
            
            JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or "emergency-jwt-secret"
            access_token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
            
            return jsonify({
                "access_token": access_token,
                "refresh_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": str(user_id),
                    "email": email,
                    "country": country,
                    "is_premium": False
                }
            }), 200
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    app.run(host="0.0.0.0", port=port, debug=False)