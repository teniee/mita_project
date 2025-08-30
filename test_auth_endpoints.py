#!/usr/bin/env python3
"""
EMERGENCY AUTH ENDPOINT TEST SCRIPT
Tests all authentication endpoints to verify they're working after Redis dependency removal.
"""

import requests
import json
import time
import sys
from typing import Dict, Any

SERVER_URL = "https://mita-docker-ready-project-manus.onrender.com"

def test_endpoint(method: str, endpoint: str, data: Dict[str, Any] = None, headers: Dict[str, str] = None, timeout: int = 30) -> Dict[str, Any]:
    """Test a specific endpoint with timeout and error handling."""
    url = f"{SERVER_URL}{endpoint}"
    test_start = time.time()
    
    try:
        print(f"🧪 Testing {method} {endpoint}...")
        
        if method == "GET":
            response = requests.get(url, headers=headers or {}, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers or {"Content-Type": "application/json"}, timeout=timeout)
        else:
            return {"status": "error", "message": f"Unsupported method: {method}"}
        
        duration = time.time() - test_start
        
        result = {
            "status": "success" if response.status_code < 400 else "error",
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "response_size": len(response.content)
        }
        
        try:
            result["response_json"] = response.json()
        except:
            result["response_text"] = response.text[:200] + "..." if len(response.text) > 200 else response.text
        
        return result
        
    except requests.exceptions.Timeout:
        duration = time.time() - test_start
        return {
            "status": "timeout",
            "duration_ms": round(duration * 1000, 2),
            "message": f"Request timed out after {timeout}s"
        }
    except Exception as e:
        duration = time.time() - test_start
        return {
            "status": "error",
            "duration_ms": round(duration * 1000, 2),
            "message": str(e)
        }

def main():
    """Run comprehensive authentication endpoint tests."""
    print("🚨 EMERGENCY AUTH ENDPOINT TEST")
    print("=" * 50)
    
    # Test cases for all auth endpoints
    test_cases = [
        {
            "name": "Health Check",
            "method": "GET",
            "endpoint": "/health",
            "expected_status": [200],
            "critical": True
        },
        {
            "name": "Emergency Test",
            "method": "GET", 
            "endpoint": "/emergency-test",
            "expected_status": [200],
            "critical": True
        },
        {
            "name": "Emergency Diagnostics",
            "method": "GET",
            "endpoint": "/api/auth/emergency-diagnostics",
            "expected_status": [200],
            "critical": True
        },
        {
            "name": "Login (Invalid User)",
            "method": "POST",
            "endpoint": "/api/auth/login",
            "data": {"email": "test@nonexistent.com", "password": "testpassword123"},
            "expected_status": [401, 400],  # Should return error, not timeout
            "critical": True
        },
        {
            "name": "Emergency Registration",
            "method": "POST",
            "endpoint": "/api/auth/emergency-register",
            "data": {"email": f"test_{int(time.time())}@emergency.com", "password": "emergency123456"},
            "expected_status": [201, 400],  # 201 success or 400 if user exists
            "critical": True
        },
        {
            "name": "Regular Registration",
            "method": "POST",
            "endpoint": "/api/auth/register",
            "data": {
                "email": f"test_{int(time.time())}_reg@example.com",
                "password": "password123",
                "country": "US",
                "annual_income": 50000.0,
                "timezone": "UTC"
            },
            "expected_status": [201, 400],  # Should work or return validation error, not timeout
            "critical": True
        },
        {
            "name": "Google Auth (Invalid Token)",
            "method": "POST",
            "endpoint": "/api/auth/google",
            "data": {"id_token": "invalid_token_test"},
            "expected_status": [401, 400, 422],  # Should return error, not timeout
            "critical": False
        }
    ]
    
    results = []
    critical_failures = 0
    
    print(f"\n🧪 Running {len(test_cases)} test cases...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] {test_case['name']}")
        
        result = test_endpoint(
            method=test_case["method"],
            endpoint=test_case["endpoint"],
            data=test_case.get("data"),
            timeout=30
        )
        
        # Check if result meets expectations
        if result["status"] == "timeout":
            print(f"   ❌ TIMEOUT after {result['duration_ms']}ms")
            if test_case.get("critical", False):
                critical_failures += 1
        elif result["status"] == "error":
            print(f"   ❌ ERROR: {result.get('message', 'Unknown error')}")
            if test_case.get("critical", False):
                critical_failures += 1
        elif result["status_code"] in test_case["expected_status"]:
            print(f"   ✅ SUCCESS: {result['status_code']} in {result['duration_ms']}ms")
        else:
            print(f"   ⚠️  UNEXPECTED: {result['status_code']} (expected {test_case['expected_status']}) in {result['duration_ms']}ms")
            if test_case.get("critical", False):
                critical_failures += 1
        
        results.append({
            "test_case": test_case["name"],
            "result": result
        })
        
        print()  # Empty line for readability
        
        # Small delay between requests
        time.sleep(0.5)
    
    # Summary
    print("=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    successful_tests = sum(1 for r in results if r["result"]["status"] == "success")
    timeout_tests = sum(1 for r in results if r["result"]["status"] == "timeout")
    error_tests = sum(1 for r in results if r["result"]["status"] == "error")
    
    print(f"✅ Successful: {successful_tests}/{len(test_cases)}")
    print(f"⏱️  Timeouts: {timeout_tests}/{len(test_cases)}")
    print(f"❌ Errors: {error_tests}/{len(test_cases)}")
    print(f"🔴 Critical Failures: {critical_failures}")
    
    if timeout_tests == 0:
        print("\n🎉 SUCCESS: No endpoints are hanging/timing out!")
        print("🔧 Auth endpoints are now responding properly.")
    else:
        print(f"\n⚠️  WARNING: {timeout_tests} endpoints still timing out.")
        print("🔧 May need additional fixes.")
    
    if critical_failures == 0:
        print("✅ All critical endpoints are working!")
        return 0
    else:
        print(f"❌ {critical_failures} critical failures need attention.")
        return 1

if __name__ == "__main__":
    sys.exit(main())