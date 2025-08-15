#!/usr/bin/env python3
"""
🚨 EMERGENCY REGISTRATION TEST SCRIPT
Test the ultra-simple registration endpoint to ensure it works without timeouts.
"""
import requests
import json
import time
import os
import sys

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_EMAIL = f"emergency_test_{int(time.time())}@example.com"
TEST_PASSWORD = "TestPassword123!"

def test_server_connectivity():
    """Test basic server connectivity"""
    print("🔍 Testing server connectivity...")
    
    try:
        response = requests.get(f"{BASE_URL}/emergency-test", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is LIVE: {data.get('message')}")
            print(f"📊 Server timestamp: {data.get('timestamp')}")
            return True
        else:
            print(f"❌ Server responded with status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Server connectivity test failed: {e}")
        return False

def test_emergency_registration():
    """Test the emergency registration endpoint"""
    print(f"\n🚨 Testing emergency registration with email: {TEST_EMAIL}")
    
    start_time = time.time()
    
    try:
        payload = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        response = requests.post(
            f"{BASE_URL}/emergency-register",
            json=payload,
            timeout=20,  # Allow up to 20 seconds (generous timeout)
            headers={"Content-Type": "application/json"}
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code == 201:
            data = response.json()
            print(f"✅ EMERGENCY REGISTRATION SUCCESS in {elapsed_time:.2f}s")
            print(f"📝 Response: {json.dumps(data, indent=2)}")
            
            # Check if we got all required fields
            required_fields = ["access_token", "token_type", "user_id"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                print(f"⚠️ Warning: Missing fields in response: {missing_fields}")
            else:
                print(f"✅ All required fields present in response")
            
            return True, elapsed_time, data
        else:
            print(f"❌ EMERGENCY REGISTRATION FAILED with status {response.status_code}")
            print(f"📝 Error response: {response.text}")
            return False, elapsed_time, response.text
            
    except requests.exceptions.Timeout:
        elapsed_time = time.time() - start_time
        print(f"❌ EMERGENCY REGISTRATION TIMEOUT after {elapsed_time:.2f}s")
        return False, elapsed_time, "TIMEOUT"
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"❌ EMERGENCY REGISTRATION ERROR after {elapsed_time:.2f}s: {e}")
        return False, elapsed_time, str(e)

def test_duplicate_email():
    """Test registration with duplicate email (should fail gracefully)"""
    print(f"\n🔄 Testing duplicate email registration...")
    
    try:
        payload = {
            "email": TEST_EMAIL,  # Same email as before
            "password": TEST_PASSWORD
        }
        
        response = requests.post(
            f"{BASE_URL}/emergency-register",
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 400:
            data = response.json()
            print(f"✅ Duplicate email correctly rejected: {data.get('error')}")
            return True
        else:
            print(f"⚠️ Unexpected response for duplicate email: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Duplicate email test error: {e}")
        return False

def main():
    """Run all emergency registration tests"""
    print("🚨 EMERGENCY REGISTRATION TEST SUITE")
    print("=" * 50)
    
    results = {
        "connectivity": False,
        "registration": False,
        "duplicate_check": False,
        "total_time": 0
    }
    
    # Test 1: Server connectivity
    results["connectivity"] = test_server_connectivity()
    
    if not results["connectivity"]:
        print("\n❌ CRITICAL: Server is not responding. Cannot proceed with registration tests.")
        sys.exit(1)
    
    # Test 2: Emergency registration
    success, elapsed_time, response = test_emergency_registration()
    results["registration"] = success
    results["total_time"] = elapsed_time
    
    if success:
        # Test 3: Duplicate email check (only if registration succeeded)
        results["duplicate_check"] = test_duplicate_email()
    
    # Summary
    print("\n" + "=" * 50)
    print("🚨 EMERGENCY REGISTRATION TEST RESULTS:")
    print(f"📡 Server Connectivity: {'✅ PASS' if results['connectivity'] else '❌ FAIL'}")
    print(f"🚀 Emergency Registration: {'✅ PASS' if results['registration'] else '❌ FAIL'}")
    print(f"🔒 Duplicate Email Check: {'✅ PASS' if results['duplicate_check'] else '❌ FAIL'}")
    print(f"⏱️  Total Registration Time: {results['total_time']:.2f}s")
    
    if results["registration"]:
        if results["total_time"] < 5.0:
            print("🎉 EXCELLENT: Registration completed in under 5 seconds!")
        elif results["total_time"] < 10.0:
            print("✅ GOOD: Registration completed in under 10 seconds")
        else:
            print("⚠️  WARNING: Registration took longer than expected")
            
        print(f"\n📱 Mobile app should now use: POST {BASE_URL}/emergency-register")
        print("📱 This endpoint bypasses ALL middleware and should be much faster!")
    else:
        print("\n❌ CRITICAL: Emergency registration is not working!")
        print("🔧 Check server logs and database connectivity")
        sys.exit(1)

if __name__ == "__main__":
    main()