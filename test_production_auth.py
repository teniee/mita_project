#!/usr/bin/env python3
"""
Comprehensive test of the production authentication endpoints
"""
import requests
import json
import time
import uuid

def test_auth_endpoints():
    """Test authentication endpoints thoroughly"""
    base_url = 'https://mita-docker-ready-project-manus.onrender.com'
    
    print("🧪 Comprehensive Production Authentication Test")
    print("=" * 50)
    
    # Generate unique test email to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    test_email = f"test_fix_{unique_id}@example.com"
    test_password = "TestPassword123!"
    
    test_user = {
        'email': test_email,
        'password': test_password,
        'country': 'US',
        'annual_income': 50000
    }
    
    print(f"Test user: {test_email}")
    print()
    
    # Test 1: Health check
    print("1️⃣ Testing health endpoint...")
    try:
        health_response = requests.get(f'{base_url}/health', timeout=10)
        print(f"   Status: {health_response.status_code}")
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"   Service: {health_data.get('service', 'Unknown')}")
            print(f"   Environment: {health_data.get('environment', 'Unknown')}")
            print("   ✅ Health check passed")
        else:
            print("   ❌ Health check failed")
            return False
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
        return False
    
    print()
    
    # Test 2: Registration
    print("2️⃣ Testing registration endpoint...")
    try:
        reg_response = requests.post(
            f'{base_url}/api/auth/register', 
            json=test_user, 
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"   Status: {reg_response.status_code}")
        print(f"   Headers: {dict(reg_response.headers)}")
        
        if reg_response.status_code == 201:
            try:
                reg_data = reg_response.json()
                print(f"   Response: {json.dumps(reg_data, indent=2)}")
                print("   ✅ Registration successful")
                registration_success = True
            except:
                print(f"   Response (raw): {reg_response.text}")
                print("   ✅ Registration successful (non-JSON response)")
                registration_success = True
        elif reg_response.status_code == 400:
            print(f"   Response: {reg_response.text}")
            if "already exists" in reg_response.text.lower():
                print("   ⚠️  User already exists, will test login")
                registration_success = True
            else:
                print("   ❌ Registration failed with validation error")
                registration_success = False
        else:
            print(f"   Response: {reg_response.text}")
            print("   ❌ Registration failed")
            registration_success = False
            
    except Exception as e:
        print(f"   ❌ Registration error: {e}")
        registration_success = False
    
    print()
    
    # Test 3: Login (whether registration succeeded or user already existed)
    print("3️⃣ Testing login endpoint...")
    try:
        login_data = {
            'email': test_email,
            'password': test_password
        }
        
        login_response = requests.post(
            f'{base_url}/api/auth/login', 
            json=login_data, 
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"   Status: {login_response.status_code}")
        
        if login_response.status_code == 200:
            try:
                login_data = login_response.json()
                print("   ✅ Login successful")
                print(f"   User ID: {login_data.get('user', {}).get('id', 'N/A')}")
                if 'access_token' in login_data:
                    print("   ✅ Access token received")
                return True
            except:
                print(f"   Response (raw): {login_response.text}")
                print("   ✅ Login successful (non-JSON response)")
                return True
        elif login_response.status_code == 404:
            if not registration_success:
                print("   ⚠️  User not found - this is expected since registration failed")
                print("   🔄 Let's try registering again with more details...")
                
                # Retry registration with debug info
                print("\n4️⃣ Retry registration with debug...")
                debug_response = requests.post(
                    f'{base_url}/api/auth/register', 
                    json=test_user, 
                    timeout=30
                )
                print(f"   Debug Status: {debug_response.status_code}")
                print(f"   Debug Response: {debug_response.text}")
            else:
                print("   ❌ User not found despite successful registration")
            return False
        else:
            print(f"   Response: {login_response.text}")
            print("   ❌ Login failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Login error: {e}")
        return False

if __name__ == "__main__":
    success = test_auth_endpoints()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SUCCESS: Authentication endpoints are working correctly!")
        print("✅ The database schema fix has resolved the issue.")
    else:
        print("❌ FAILURE: Authentication endpoints still have issues.")
        print("🔍 Further investigation needed.")
    
    print("=" * 50)