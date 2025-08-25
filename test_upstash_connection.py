#!/usr/bin/env python3
"""
Test Upstash Redis REST API connection
Проверяет подключение к Upstash Redis через REST API
"""

import os
import requests
import json
import base64
from datetime import datetime

def test_upstash_rest_connection():
    """Test Upstash Redis REST API connection"""
    
    # Get environment variables
    rest_url = os.getenv("UPSTASH_REDIS_REST_URL")
    rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    
    if not rest_url or not rest_token:
        print("❌ UPSTASH_REDIS_REST_URL или UPSTASH_REDIS_REST_TOKEN не найдены")
        print("Убедись, что переменные настроены в Render Dashboard")
        return False
    
    print(f"🔧 Testing Upstash Redis REST API...")
    print(f"📡 URL: {rest_url}")
    print(f"🔑 Token: {rest_token[:10]}...")
    
    try:
        # Test 1: PING command
        ping_url = f"{rest_url}/ping"
        headers = {"Authorization": f"Bearer {rest_token}"}
        
        response = requests.get(ping_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ PING successful!")
            print(f"   Response: {response.text}")
        else:
            print(f"❌ PING failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        # Test 2: SET/GET commands  
        test_key = f"mita_test_{int(datetime.now().timestamp())}"
        test_value = "MITA Finance Backend Test"
        
        # SET command
        set_url = f"{rest_url}/set/{test_key}"
        set_response = requests.post(
            set_url, 
            headers=headers,
            json={"value": test_value, "ex": 60},  # Expire in 60 seconds
            timeout=10
        )
        
        if set_response.status_code == 200:
            print(f"✅ SET {test_key} successful!")
        else:
            print(f"❌ SET failed: {set_response.status_code}")
            return False
        
        # GET command
        get_url = f"{rest_url}/get/{test_key}"
        get_response = requests.get(get_url, headers=headers, timeout=10)
        
        if get_response.status_code == 200:
            result = get_response.json()
            if result.get("result") == test_value:
                print(f"✅ GET {test_key} successful!")
                print(f"   Value: {result.get('result')}")
            else:
                print(f"❌ GET value mismatch: {result}")
                return False
        else:
            print(f"❌ GET failed: {get_response.status_code}")
            return False
        
        # Clean up: DELETE command
        del_url = f"{rest_url}/del/{test_key}"
        del_response = requests.post(del_url, headers=headers, timeout=10)
        print(f"🧹 Cleanup: DEL {test_key}")
        
        print("🎉 All Upstash Redis REST tests passed!")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_from_environment():
    """Test using environment variables from .env or system"""
    print("=" * 60)
    print("🚀 MITA Finance - Upstash Redis REST API Test")
    print("=" * 60)
    
    # Load from .env if exists
    env_file = ".env.production"
    if os.path.exists(env_file):
        print(f"📁 Loading environment from {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"\'')
    
    success = test_upstash_rest_connection()
    
    print("=" * 60)
    if success:
        print("✅ РЕЗУЛЬТАТ: Upstash Redis REST API работает корректно!")
    else:
        print("❌ РЕЗУЛЬТАТ: Проблемы с подключением к Upstash Redis")
        print("\n🔧 Проверь:")
        print("1. UPSTASH_REDIS_REST_URL правильный (без кавычек)")  
        print("2. UPSTASH_REDIS_REST_TOKEN правильный (без кавычек)")
        print("3. В Upstash Dashboard включен REST API")
    print("=" * 60)

if __name__ == "__main__":
    test_from_environment()