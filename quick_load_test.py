#!/usr/bin/env python3
"""
Quick Authentication Load Testing for MITA Finance
Focused, fast tests to validate key scenarios
"""

import asyncio
import aiohttp
import time
import json
import logging
from typing import Dict, List
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuickLoadTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
    
    async def create_session(self):
        timeout = aiohttp.ClientTimeout(total=30)
        return aiohttp.ClientSession(timeout=timeout)
    
    async def test_scenario(self, name: str, requests: int, endpoint: str, data: dict = None):
        """Test a specific scenario with concurrent requests"""
        logger.info(f"Testing {name}: {requests} concurrent requests")
        
        async with await self.create_session() as session:
            start_time = time.time()
            tasks = []
            
            for i in range(requests):
                if data:
                    # Unique data for each request
                    request_data = data.copy()
                    if "email" in request_data:
                        request_data["email"] = f"test_{i}_{int(time.time())}@example.com"
                    task = session.post(f"{self.base_url}{endpoint}", json=request_data)
                else:
                    task = session.get(f"{self.base_url}{endpoint}")
                tasks.append(task)
            
            # Execute all requests concurrently
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            # Analyze results
            successful = 0
            failed = 0
            rate_limited = 0
            response_times = []
            status_codes = []
            
            for response in responses:
                if isinstance(response, Exception):
                    failed += 1
                else:
                    status_codes.append(response.status)
                    if response.status == 200 or response.status == 201:
                        successful += 1
                    elif response.status == 429:
                        rate_limited += 1
                    else:
                        failed += 1
                    response.close()
            
            success_rate = (successful / requests) * 100
            avg_response_time = (total_time / requests) * 1000  # ms
            
            result = {
                "scenario": name,
                "endpoint": endpoint,
                "total_requests": requests,
                "successful": successful,
                "failed": failed,
                "rate_limited": rate_limited,
                "success_rate_percent": success_rate,
                "total_time_seconds": total_time,
                "avg_response_time_ms": avg_response_time,
                "requests_per_second": requests / total_time,
                "status_codes": status_codes
            }
            
            self.results.append(result)
            
            logger.info(f"  ✓ {successful}/{requests} successful ({success_rate:.1f}%)")
            logger.info(f"  ✓ {rate_limited} rate limited (expected)")
            logger.info(f"  ✓ {avg_response_time:.1f}ms avg response time")
            logger.info(f"  ✓ {requests/total_time:.1f} requests/second")
            
            return result

async def run_quick_tests():
    """Run quick comprehensive authentication tests"""
    
    print("🚀 MITA AUTHENTICATION QUICK LOAD TESTS")
    print("=" * 60)
    print("Testing restored middleware and authentication performance")
    print()
    
    tester = QuickLoadTester()
    
    # Test scenarios
    scenarios = [
        {
            "name": "Health Check Baseline",
            "requests": 10,
            "endpoint": "/health",
            "data": None
        },
        {
            "name": "Emergency Diagnostics",
            "requests": 5,
            "endpoint": "/auth/emergency-diagnostics",
            "data": None
        },
        {
            "name": "Security Status",
            "requests": 5,
            "endpoint": "/auth/security/status",
            "data": None
        },
        {
            "name": "User Registration",
            "requests": 10,
            "endpoint": "/auth/register",
            "data": {
                "email": "test@example.com",
                "password": "password123",
                "country": "US"
            }
        },
        {
            "name": "Emergency Registration",
            "requests": 10,
            "endpoint": "/auth/emergency-register",
            "data": {
                "email": "emergency@example.com",
                "password": "password123",
                "country": "US"
            }
        },
        {
            "name": "Rate Limiting Test (Login)",
            "requests": 20,  # Should trigger rate limiting
            "endpoint": "/auth/login",
            "data": {
                "email": "test@example.com",
                "password": "password123"
            }
        },
        {
            "name": "Password Reset",
            "requests": 5,
            "endpoint": "/auth/password-reset/request",
            "data": {
                "email": "test@example.com"
            }
        }
    ]
    
    all_results = []
    
    for scenario in scenarios:
        try:
            result = await tester.test_scenario(
                scenario["name"],
                scenario["requests"],
                scenario["endpoint"],
                scenario.get("data")
            )
            all_results.append(result)
            
            # Brief pause between tests
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Scenario '{scenario['name']}' failed: {e}")
            all_results.append({
                "scenario": scenario["name"],
                "error": str(e),
                "failed": True
            })
    
    # Generate summary report
    print(f"\n📊 QUICK TEST RESULTS SUMMARY")
    print("=" * 60)
    
    total_requests = sum(r.get("total_requests", 0) for r in all_results if not r.get("failed"))
    total_successful = sum(r.get("successful", 0) for r in all_results if not r.get("failed"))
    total_rate_limited = sum(r.get("rate_limited", 0) for r in all_results if not r.get("failed"))
    
    overall_success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
    
    print(f"Overall Statistics:")
    print(f"  • Total Requests: {total_requests}")
    print(f"  • Successful: {total_successful} ({overall_success_rate:.1f}%)")
    print(f"  • Rate Limited: {total_rate_limited}")
    print(f"  • Failed: {total_requests - total_successful - total_rate_limited}")
    
    print(f"\nScenario Details:")
    for result in all_results:
        if result.get("failed"):
            print(f"  ❌ {result['scenario']}: FAILED - {result.get('error', 'Unknown error')}")
        else:
            scenario = result["scenario"]
            success_rate = result["success_rate_percent"]
            response_time = result["avg_response_time_ms"]
            rate_limited = result["rate_limited"]
            
            status_icon = "✅" if success_rate > 80 else "⚠️" if success_rate > 50 else "❌"
            
            print(f"  {status_icon} {scenario}: {success_rate:.1f}% success, {response_time:.1f}ms avg, {rate_limited} rate limited")
    
    # Key Findings
    print(f"\n🔍 KEY FINDINGS:")
    
    findings = []
    
    # Check if rate limiting is working
    rate_limit_test = next((r for r in all_results if "Rate Limiting" in r.get("scenario", "")), None)
    if rate_limit_test and rate_limit_test.get("rate_limited", 0) > 0:
        findings.append("✅ Rate limiting is working correctly")
    else:
        findings.append("⚠️ Rate limiting may not be properly configured")
    
    # Check emergency endpoints
    emergency_results = [r for r in all_results if "Emergency" in r.get("scenario", "")]
    if emergency_results and all(r.get("success_rate_percent", 0) > 80 for r in emergency_results):
        findings.append("✅ Emergency endpoints are performing well")
    else:
        findings.append("⚠️ Emergency endpoints may have performance issues")
    
    # Check performance
    avg_response_times = [r.get("avg_response_time_ms", 0) for r in all_results if not r.get("failed")]
    if avg_response_times:
        overall_avg_response = sum(avg_response_times) / len(avg_response_times)
        if overall_avg_response < 1000:
            findings.append("✅ Response times are acceptable")
        elif overall_avg_response < 2000:
            findings.append("⚠️ Response times are elevated but acceptable")
        else:
            findings.append("❌ Response times are too high")
    
    # Check overall system health
    if overall_success_rate > 90:
        findings.append("✅ Authentication system is healthy")
    elif overall_success_rate > 70:
        findings.append("⚠️ Authentication system has some issues")
    else:
        findings.append("❌ Authentication system needs immediate attention")
    
    for finding in findings:
        print(f"  • {finding}")
    
    # Final verdict
    print(f"\n🎯 QUICK TEST VERDICT:")
    print("=" * 60)
    
    if overall_success_rate > 85 and total_rate_limited > 0:
        print("✅ AUTHENTICATION LOAD TESTING: PASSED")
        print("🔒 System handles concurrent load appropriately")
        print("⚡ Rate limiting is functional")
        print("🚀 Ready for more comprehensive testing")
        success = True
    elif overall_success_rate > 70:
        print("⚠️ AUTHENTICATION LOAD TESTING: PARTIAL PASS")
        print("🔒 System functions under load with some issues")
        print("🔧 May need minor optimizations")
        success = False
    else:
        print("❌ AUTHENTICATION LOAD TESTING: FAILED")
        print("🔒 System has significant issues under load")
        print("🛠️ Requires immediate investigation")
        success = False
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"quick_auth_load_test_report_{timestamp}.json"
    
    with open(report_file, 'w') as f:
        json.dump({
            "test_summary": {
                "timestamp": timestamp,
                "total_requests": total_requests,
                "successful_requests": total_successful,
                "rate_limited_requests": total_rate_limited,
                "overall_success_rate": overall_success_rate,
                "test_type": "quick_load_test"
            },
            "scenario_results": all_results,
            "findings": findings
        }, f, indent=2, default=str)
    
    print(f"\n📋 Report saved: {report_file}")
    
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(run_quick_tests())
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Quick test failed: {e}")
        exit(1)