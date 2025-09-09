#!/usr/bin/env python3
"""
Continuously monitor server and test authentication when it's ready
"""
import requests
import time
import json
import uuid

def wait_for_server():
    """Wait for server to come online"""
    url = 'https://mita-docker-ready-project-manus.onrender.com/health'
    
    print("⏳ Waiting for server to come online...")
    while True:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print("✅ Server is online!")
                return True
        except:
            pass
        
        print(".", end="", flush=True)
        time.sleep(5)

def test_authentication():
    """Test authentication once server is ready"""
    base_url = 'https://mita-docker-ready-project-manus.onrender.com'
    
    # Generate unique test email
    unique_id = str(uuid.uuid4())[:8]
    test_email = f"test_{unique_id}@example.com"
    test_password = "TestPassword123!"
    
    test_user = {
        'email': test_email,
        'password': test_password,
        'country': 'US',
        'annual_income': 50000
    }
    
    print(f"\n🧪 Testing authentication with: {test_email}")
    
    # Test registration
    print("1️⃣ Testing registration...")
    try:
        reg_response = requests.post(
            f'{base_url}/api/auth/register',
            json=test_user,
            timeout=15
        )
        
        print(f"   Status: {reg_response.status_code}")
        if reg_response.status_code == 201:
            print("   ✅ Registration successful!")
            reg_data = reg_response.json()
            print(f"   Response: {json.dumps(reg_data, indent=2)}")
        elif reg_response.status_code == 422:
            print(f"   ⚠️ User might already exist: {reg_response.text}")
        else:
            print(f"   ❌ Registration failed: {reg_response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Registration error: {e}")
        return False
    
    # Test login
    print("\n2️⃣ Testing login...")
    try:
        login_data = {
            'email': test_email,
            'password': test_password
        }
        
        login_response = requests.post(
            f'{base_url}/api/auth/login',
            json=login_data,
            timeout=15
        )
        
        print(f"   Status: {login_response.status_code}")
        if login_response.status_code == 200:
            login_result = login_response.json()
            print("   ✅ Login successful!")
            print(f"   User ID: {login_result.get('data', {}).get('user', {}).get('id', 'N/A')}")
            
            # Check if access token is present
            access_token = login_result.get('data', {}).get('access_token')
            if access_token:
                print("   ✅ Access token received")
                return True
            else:
                print("   ⚠️ No access token in response")
                print(f"   Response: {json.dumps(login_result, indent=2)}")
                return False
        else:
            print(f"   ❌ Login failed: {login_response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Login error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 MITA Finance Authentication Test")
    print("=" * 50)
    
    # Wait for server
    if wait_for_server():
        # Test authentication
        success = test_authentication()
        
        print("\n" + "=" * 50)
        if success:
            print("🎉 SUCCESS: Authentication is working!")
            print("✅ Mobile app should now be able to register and login")
        else:
            print("❌ FAILURE: Authentication still has issues")
        print("=" * 50)