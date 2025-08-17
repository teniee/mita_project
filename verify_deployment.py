#!/usr/bin/env python3
"""
MITA Backend Deployment Verification Script
Verifies that the backend is properly deployed and accessible
"""

import requests
import time
import json
from typing import Dict, Any
import argparse

# Production URLs to test
PRODUCTION_BASE_URL = "https://mita-production.onrender.com"
API_BASE_URL = f"{PRODUCTION_BASE_URL}/api"

def test_endpoint(url: str, method: str = "GET", data: Dict = None, timeout: int = 30) -> Dict[str, Any]:
    """Test a single endpoint and return results"""
    try:
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        return {
            "success": True,
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds(),
            "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Connection Error"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON response"}

def verify_deployment() -> Dict[str, Any]:
    """Comprehensive deployment verification"""
    print("🔍 MITA Backend Deployment Verification")
    print("=" * 50)
    
    results = {
        "timestamp": time.time(),
        "base_url": PRODUCTION_BASE_URL,
        "api_url": API_BASE_URL,
        "tests": {}
    }
    
    # Test cases
    test_cases = [
        {
            "name": "Root Health Check",
            "url": f"{PRODUCTION_BASE_URL}/",
            "method": "GET",
            "expected_status": 200,
            "description": "Basic server response"
        },
        {
            "name": "Detailed Health Check",
            "url": f"{PRODUCTION_BASE_URL}/health",
            "method": "GET", 
            "expected_status": 200,
            "description": "Comprehensive health status"
        },
        {
            "name": "Emergency Test Endpoint",
            "url": f"{PRODUCTION_BASE_URL}/emergency-test",
            "method": "GET",
            "expected_status": 200,
            "description": "Emergency server status"
        },
        {
            "name": "Auth Login Endpoint",
            "url": f"{API_BASE_URL}/auth/login",
            "method": "POST",
            "data": {},  # Empty data to test endpoint availability
            "expected_status": [400, 422],  # Should reject invalid data but be accessible
            "description": "Authentication endpoint accessibility"
        },
        {
            "name": "Auth Register Endpoint",
            "url": f"{API_BASE_URL}/auth/register",
            "method": "POST", 
            "data": {},  # Empty data to test endpoint availability
            "expected_status": [400, 422],  # Should reject invalid data but be accessible
            "description": "Registration endpoint accessibility"
        },
        {
            "name": "Emergency Registration",
            "url": f"{PRODUCTION_BASE_URL}/emergency-register",
            "method": "POST",
            "data": {},  # Empty data to test endpoint availability  
            "expected_status": [400],  # Should reject invalid data but be accessible
            "description": "Emergency registration endpoint"
        }
    ]
    
    overall_success = True
    
    for test_case in test_cases:
        print(f"\n🧪 Testing: {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        
        # Execute test
        result = test_endpoint(
            test_case['url'],
            test_case['method'],
            test_case.get('data'),
            timeout=30
        )
        
        # Evaluate result
        if result['success']:
            expected_status = test_case['expected_status']
            if isinstance(expected_status, list):
                status_ok = result['status_code'] in expected_status
            else:
                status_ok = result['status_code'] == expected_status
                
            if status_ok:
                print(f"   ✅ PASS - Status: {result['status_code']}, Time: {result['response_time']:.2f}s")
                result['test_passed'] = True
            else:
                print(f"   ❌ FAIL - Expected: {expected_status}, Got: {result['status_code']}")
                result['test_passed'] = False
                overall_success = False
        else:
            print(f"   ❌ FAIL - {result['error']}")
            result['test_passed'] = False
            overall_success = False
        
        # Store result
        results['tests'][test_case['name']] = result
    
    # Summary
    print(f"\n📊 SUMMARY")
    print("=" * 50)
    
    passed_tests = sum(1 for test in results['tests'].values() if test.get('test_passed', False))
    total_tests = len(results['tests'])
    
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    print(f"Overall Status: {'✅ HEALTHY' if overall_success else '❌ UNHEALTHY'}")
    
    if overall_success:
        print(f"\n🎉 DEPLOYMENT SUCCESSFUL!")
        print(f"Backend is accessible at: {PRODUCTION_BASE_URL}")
        print(f"API endpoints available at: {API_BASE_URL}")
        print(f"Mobile app can now authenticate users!")
    else:
        print(f"\n🚨 DEPLOYMENT ISSUES DETECTED!")
        print(f"Backend may not be properly deployed or configured.")
        print(f"Check Render dashboard and logs for errors.")
    
    results['overall_success'] = overall_success
    results['passed_tests'] = passed_tests
    results['total_tests'] = total_tests
    
    return results

def monitor_deployment(interval: int = 60, iterations: int = 10):
    """Monitor deployment status over time"""
    print(f"🔄 Monitoring deployment every {interval} seconds for {iterations} iterations...")
    
    for i in range(iterations):
        print(f"\n--- Iteration {i+1}/{iterations} ---")
        result = verify_deployment()
        
        if result['overall_success']:
            print("✅ Deployment healthy!")
            break
        else:
            print(f"❌ Issues detected. Waiting {interval} seconds...")
            if i < iterations - 1:  # Don't sleep on last iteration
                time.sleep(interval)
    
    print("\n🔄 Monitoring complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify MITA backend deployment")
    parser.add_argument("--monitor", action="store_true", help="Monitor deployment continuously")
    parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds")
    parser.add_argument("--iterations", type=int, default=10, help="Number of monitoring iterations")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    
    args = parser.parse_args()
    
    if args.monitor:
        monitor_deployment(args.interval, args.iterations)
    else:
        results = verify_deployment()
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n📄 Results saved to: {args.output}")