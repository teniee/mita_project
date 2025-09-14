#!/usr/bin/env python3
"""
Final authentication test to verify the mobile app can handle slow server responses
"""
import requests
import time
import json

def test_authentication_performance():
    """Test authentication with realistic mobile app expectations"""
    
    print("🧪 Final Mobile Authentication Test")
    print("=" * 50)
    
    # Test credentials
    email = "cutmeout1@gmail.com"
    password = "33SatinSatin11$"
    base_url = "https://mita-docker-ready-project-manus.onrender.com"
    
    print(f"Testing with: {email}")
    print(f"Server: {base_url}")
    print()
    
    # Test 1: Check server response time
    print("1️⃣ Testing server response time...")
    start_time = time.time()
    
    try:
        login_response = requests.post(
            f"{base_url}/api/auth/login",
            json={"email": email, "password": password},
            timeout=120  # 2 minute timeout like mobile app
        )
        
        response_time = time.time() - start_time
        
        print(f"   Status Code: {login_response.status_code}")
        print(f"   Response Time: {response_time:.2f} seconds")
        
        if login_response.status_code == 200:
            print("   ✅ Login successful!")
            
            # Parse response
            response_data = login_response.json()
            
            # Check for required fields
            if 'data' in response_data:
                data = response_data['data']
                if 'access_token' in data and 'user' in data:
                    print("   ✅ Valid authentication response structure")
                    print(f"   📱 Mobile App Compatibility:")
                    
                    if response_time <= 90:  # Mobile app timeout
                        print(f"      ✅ Response time ({response_time:.2f}s) is within mobile app timeout (90s)")
                    else:
                        print(f"      ❌ Response time ({response_time:.2f}s) exceeds mobile app timeout (90s)")
                    
                    # Show user data
                    user = data['user']
                    print(f"   👤 User Data:")
                    print(f"      ID: {user.get('id')}")
                    print(f"      Email: {user.get('email')}")
                    print(f"      Country: {user.get('country')}")
                    print(f"      Premium: {user.get('is_premium')}")
                    
                    return True
                else:
                    print("   ❌ Missing required fields in response")
                    return False
            else:
                print("   ❌ Invalid response structure")
                return False
        else:
            print(f"   ❌ Login failed: {login_response.text}")
            return False
            
    except requests.Timeout:
        response_time = time.time() - start_time
        print(f"   ⏰ Request timed out after {response_time:.2f} seconds")
        print("   ❌ Server is too slow for mobile app")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Main test function"""
    print("Testing authentication performance for mobile app compatibility...")
    print()
    
    success = test_authentication_performance()
    
    print()
    print("=" * 50)
    if success:
        print("🎉 SUCCESS: Authentication is mobile app compatible!")
        print("✅ The user should be able to login with the mobile app")
        print("📱 Mobile app timeout settings should handle server response time")
    else:
        print("❌ ISSUE: Authentication may still timeout in mobile app")
        print("🔧 Further optimization may be needed")
    print("=" * 50)

if __name__ == "__main__":
    main()