#!/usr/bin/env python3
"""
Production System 8001 Test Script
Tests the registration endpoint directly with the fixes applied
"""

import asyncio
import json
import requests
import time
from datetime import datetime

def test_registration_endpoint(base_url="https://your-production-url.com", test_local=True):
    """Test the registration endpoint directly"""
    
    if test_local:
        base_url = "http://localhost:8000"
    
    print(f"🧪 Testing Registration Endpoint: {base_url}")
    print("=" * 50)
    
    # Test data
    test_email = f"test_{int(time.time())}@example.com"
    test_data = {
        "email": test_email,
        "password": "TestPassword123!",
        "country": "US",
        "annual_income": 50000,
        "timezone": "UTC"
    }
    
    # Test endpoints to try
    endpoints_to_test = [
        "/api/auth/register",           # Main endpoint with the fix
        "/api/auth/register-fast",      # Fast endpoint (backup)
        "/api/auth/emergency-register", # Emergency endpoint
    ]
    
    results = {}
    
    for endpoint in endpoints_to_test:
        print(f"\n🔍 Testing: {endpoint}")
        
        try:
            start_time = time.time()
            
            response = requests.post(
                f"{base_url}{endpoint}",
                json=test_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            response_time = time.time() - start_time
            
            print(f"   Status Code: {response.status_code}")
            print(f"   Response Time: {response_time:.2f}s")
            
            try:
                response_json = response.json()
                
                # Check for SYSTEM_8001 error
                if response.status_code >= 500:
                    error_info = response_json.get('error', {})
                    error_code = error_info.get('code', 'UNKNOWN')
                    print(f"   ❌ Server Error: {error_code}")
                    
                    if error_code == "SYSTEM_8001":
                        print(f"   ❌ SYSTEM_8001 ERROR DETECTED!")
                        print(f"   Message: {error_info.get('message', 'Unknown')}")
                        results[endpoint] = {
                            "status": "SYSTEM_8001_ERROR",
                            "response_time": response_time,
                            "error": error_info
                        }
                    else:
                        results[endpoint] = {
                            "status": "OTHER_SERVER_ERROR",
                            "response_time": response_time,
                            "status_code": response.status_code,
                            "error": error_info
                        }
                elif response.status_code >= 400:
                    print(f"   ⚠️ Client Error: {response.status_code}")
                    results[endpoint] = {
                        "status": "CLIENT_ERROR",
                        "response_time": response_time,
                        "status_code": response.status_code,
                        "error": response_json
                    }
                else:
                    print(f"   ✅ Success!")
                    
                    # Check if we got tokens
                    has_access_token = bool(response_json.get('access_token'))
                    has_refresh_token = bool(response_json.get('refresh_token'))
                    
                    print(f"   Access Token: {'✅' if has_access_token else '❌'}")
                    print(f"   Refresh Token: {'✅' if has_refresh_token else '❌'}")
                    
                    results[endpoint] = {
                        "status": "SUCCESS",
                        "response_time": response_time,
                        "has_access_token": has_access_token,
                        "has_refresh_token": has_refresh_token,
                        "user_id": response_json.get('user_id', 'N/A')
                    }
                    
            except json.JSONDecodeError:
                print(f"   ❌ Invalid JSON Response")
                print(f"   Raw Response: {response.text[:200]}")
                results[endpoint] = {
                    "status": "INVALID_JSON",
                    "response_time": response_time,
                    "raw_response": response.text[:200]
                }
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection Error (Server may be down)")
            results[endpoint] = {"status": "CONNECTION_ERROR"}
            
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout (>30s)")
            results[endpoint] = {"status": "TIMEOUT"}
            
        except Exception as e:
            print(f"   ❌ Unexpected Error: {e}")
            results[endpoint] = {"status": "UNEXPECTED_ERROR", "error": str(e)}
    
    # Summary
    print(f"\n📊 Test Results Summary:")
    print("=" * 30)
    
    system_8001_found = False
    working_endpoints = []
    
    for endpoint, result in results.items():
        status = result['status']
        print(f"{endpoint:<25}: {status}")
        
        if status == "SYSTEM_8001_ERROR":
            system_8001_found = True
        elif status == "SUCCESS":
            working_endpoints.append(endpoint)
    
    print(f"\n🎯 Conclusion:")
    if system_8001_found:
        print("❌ SYSTEM_8001 ERROR STILL PRESENT!")
        print("   The client_ip fix may not have been deployed yet.")
        print("   Check if the server has been restarted with the fix.")
    elif working_endpoints:
        print(f"✅ SUCCESS! {len(working_endpoints)} endpoint(s) working:")
        for ep in working_endpoints:
            print(f"   - {ep}")
        print("   The SYSTEM_8001 error appears to be resolved!")
    else:
        print("⚠️ No endpoints are working, but no SYSTEM_8001 errors detected.")
        print("   This may indicate other issues (database, network, etc.)")
    
    # Save detailed report
    report = {
        "timestamp": datetime.now().isoformat(),
        "test_results": results,
        "system_8001_detected": system_8001_found,
        "working_endpoints": working_endpoints,
        "conclusion": "SYSTEM_8001 resolved" if not system_8001_found and working_endpoints else "Issues remain"
    }
    
    report_filename = f"production_test_report_{int(time.time())}.json"
    with open(report_filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📝 Detailed report saved to: {report_filename}")
    
    return results

def test_health_endpoint(base_url="https://your-production-url.com", test_local=True):
    """Test the health endpoint to verify server status"""
    
    if test_local:
        base_url = "http://localhost:8000"
    
    print(f"\n🏥 Testing Health Endpoint: {base_url}/api/health")
    
    try:
        response = requests.get(f"{base_url}/api/health", timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            health_data = response.json()
            print("   ✅ Server is healthy")
            
            # Check database status
            db_status = health_data.get('database', 'unknown')
            print(f"   Database: {db_status}")
            
            return True
        else:
            print("   ❌ Health check failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 MITA Finance Production SYSTEM_8001 Test")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Instructions
    print("\n📋 Instructions:")
    print("1. Update the base_url below to your production server URL")
    print("2. Run this script to test the registration endpoints")
    print("3. Check for SYSTEM_8001 errors")
    print()
    
    # Configuration
    PRODUCTION_URL = "https://your-production-server.com"  # UPDATE THIS
    TEST_PRODUCTION = False  # Set to True to test production
    
    if TEST_PRODUCTION:
        print(f"🌐 Testing Production Server: {PRODUCTION_URL}")
        health_ok = test_health_endpoint(PRODUCTION_URL, test_local=False)
        if health_ok:
            test_registration_endpoint(PRODUCTION_URL, test_local=False)
        else:
            print("❌ Production server health check failed, skipping registration test")
    else:
        print("🔧 Local Testing Mode")
        print("   To test production, update PRODUCTION_URL and set TEST_PRODUCTION = True")
        print("   Attempting local server test...")
        
        health_ok = test_health_endpoint(test_local=True)
        if health_ok:
            test_registration_endpoint(test_local=True)
        else:
            print("ℹ️  Local server not running, showing test configuration only")
    
    print(f"\n✨ Test completed at {datetime.now().isoformat()}")