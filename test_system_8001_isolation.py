#!/usr/bin/env python3
"""
🔍 SYSTEM_8001 Error Isolation Test Suite

This script systematically tests the authentication system components to isolate
the source of the SYSTEM_8001 error that has been persisting through multiple fixes.

Usage:
    python test_system_8001_isolation.py [--server-url=http://localhost:8000]

Features:
- Tests each component individually (password hashing, database ops, response generation)
- Full end-to-end registration test with step-by-step logging
- Comprehensive error analysis and recommendations
- Detailed timing information for performance analysis
"""

import asyncio
import json
import time
import uuid
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import aiohttp
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class SYSTEM8001TestSuite:
    """Comprehensive test suite to isolate SYSTEM_8001 errors"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip('/')
        self.api_base = f"{self.server_url}/api/auth"
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_results: Dict[str, Any] = {}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_component(self, endpoint: str, test_data: Dict[str, Any], component_name: str) -> Dict[str, Any]:
        """Test individual component with detailed error handling"""
        
        logger.info(f"🧪 Testing {component_name}...")
        
        start_time = time.time()
        
        try:
            async with self.session.post(
                f"{self.api_base}/{endpoint}",
                json=test_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                elapsed_ms = (time.time() - start_time) * 1000
                response_text = await response.text()
                
                result = {
                    "component": component_name,
                    "endpoint": endpoint,
                    "status_code": response.status,
                    "response_time_ms": elapsed_ms,
                    "success": False,
                    "response_size": len(response_text),
                    "headers": dict(response.headers),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Try to parse JSON response
                try:
                    response_data = json.loads(response_text)
                    result["response_data"] = response_data
                    result["success"] = response_data.get("success", False)
                    
                    # Check for SYSTEM_8001 specifically
                    if isinstance(response_data, dict):
                        error = response_data.get("error", {})
                        if isinstance(error, dict) and error.get("code") == "SYSTEM_8001":
                            result["system_8001_detected"] = True
                            result["error_details"] = error
                            logger.error(f"🚨 SYSTEM_8001 detected in {component_name}")
                        else:
                            result["system_8001_detected"] = False
                    
                except json.JSONDecodeError:
                    result["response_data"] = {"raw_response": response_text}
                    result["json_parse_error"] = True
                    logger.warning(f"⚠️ Non-JSON response from {component_name}")
                
                if response.status == 200:
                    logger.info(f"✅ {component_name} test completed successfully ({elapsed_ms:.1f}ms)")
                else:
                    logger.error(f"❌ {component_name} test failed with status {response.status}")
                
                return result
                
        except asyncio.TimeoutError:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"⏱️ {component_name} test timed out after {elapsed_ms:.1f}ms")
            return {
                "component": component_name,
                "endpoint": endpoint,
                "error": "timeout",
                "response_time_ms": elapsed_ms,
                "success": False,
                "system_8001_detected": False,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"💥 {component_name} test failed with exception: {e}")
            return {
                "component": component_name,
                "endpoint": endpoint,
                "error": str(e),
                "error_type": type(e).__name__,
                "response_time_ms": elapsed_ms,
                "success": False,
                "system_8001_detected": False,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def run_component_tests(self, test_email: str, test_password: str) -> Dict[str, Any]:
        """Run all individual component tests"""
        
        logger.info("🔬 Starting individual component tests...")
        
        component_results = {}
        
        # Test 1: Password Hashing Component
        component_results["password_hashing"] = await self.test_component(
            "test-password-hashing",
            {"password": test_password},
            "Password Hashing"
        )
        
        # Test 2: Database Operations Component 
        component_results["database_operations"] = await self.test_component(
            "test-database-operations",
            {"email": test_email, "country": "US"},
            "Database Operations"
        )
        
        # Test 3: Response Generation Component
        component_results["response_generation"] = await self.test_component(
            "test-response-generation",
            {"test_data": "sample"},
            "Response Generation"
        )
        
        return component_results
    
    async def run_full_registration_test(self, test_email: str, test_password: str) -> Dict[str, Any]:
        """Run the full end-to-end registration test with step-by-step logging"""
        
        logger.info("🎯 Starting full end-to-end registration test...")
        
        test_data = {
            "email": test_email,
            "password": test_password,
            "country": "US",
            "annual_income": 50000,
            "timezone": "UTC"
        }
        
        return await self.test_component(
            "test-registration",
            test_data,
            "Full Registration Flow"
        )
    
    async def analyze_results(self) -> Dict[str, Any]:
        """Analyze test results and provide recommendations"""
        
        logger.info("📊 Analyzing test results...")
        
        analysis = {
            "summary": {},
            "system_8001_occurrences": [],
            "failed_components": [],
            "performance_analysis": {},
            "recommendations": []
        }
        
        # Count results
        total_tests = len(self.test_results.get("component_tests", {})) + (1 if "full_registration" in self.test_results else 0)
        successful_tests = 0
        system_8001_count = 0
        
        # Analyze component tests
        for component_name, result in self.test_results.get("component_tests", {}).items():
            if result.get("success", False):
                successful_tests += 1
            else:
                analysis["failed_components"].append({
                    "component": component_name,
                    "error": result.get("error", "Unknown error"),
                    "status_code": result.get("status_code"),
                    "response_time_ms": result.get("response_time_ms", 0)
                })
            
            # Check for SYSTEM_8001
            if result.get("system_8001_detected", False):
                system_8001_count += 1
                analysis["system_8001_occurrences"].append({
                    "component": component_name,
                    "error_details": result.get("error_details", {}),
                    "timestamp": result.get("timestamp")
                })
        
        # Analyze full registration test
        full_reg_result = self.test_results.get("full_registration", {})
        if full_reg_result.get("success", False):
            successful_tests += 1
        elif full_reg_result.get("system_8001_detected", False):
            system_8001_count += 1
            analysis["system_8001_occurrences"].append({
                "component": "full_registration",
                "error_details": full_reg_result.get("error_details", {}),
                "timestamp": full_reg_result.get("timestamp")
            })
        
        analysis["summary"] = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": total_tests - successful_tests,
            "success_rate": f"{(successful_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%",
            "system_8001_count": system_8001_count,
            "system_8001_affected": system_8001_count > 0
        }
        
        # Performance analysis
        response_times = []
        for result in [*self.test_results.get("component_tests", {}).values(), self.test_results.get("full_registration", {})]:
            if "response_time_ms" in result:
                response_times.append(result["response_time_ms"])
        
        if response_times:
            analysis["performance_analysis"] = {
                "avg_response_time_ms": sum(response_times) / len(response_times),
                "max_response_time_ms": max(response_times),
                "min_response_time_ms": min(response_times),
                "total_response_times": len(response_times)
            }
        
        # Generate recommendations
        if system_8001_count > 0:
            analysis["recommendations"].append({
                "priority": "HIGH",
                "issue": "SYSTEM_8001 Error Detected",
                "recommendation": "Focus investigation on components showing SYSTEM_8001 errors",
                "affected_components": [occ["component"] for occ in analysis["system_8001_occurrences"]]
            })
        
        if len(analysis["failed_components"]) > 0:
            analysis["recommendations"].append({
                "priority": "MEDIUM", 
                "issue": "Component Failures Detected",
                "recommendation": "Review failed components for underlying issues",
                "affected_components": [fc["component"] for fc in analysis["failed_components"]]
            })
        
        if analysis["performance_analysis"].get("avg_response_time_ms", 0) > 5000:
            analysis["recommendations"].append({
                "priority": "LOW",
                "issue": "Slow Response Times",
                "recommendation": "Optimize slow-performing components",
                "avg_time": analysis["performance_analysis"]["avg_response_time_ms"]
            })
        
        return analysis
    
    async def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        
        analysis = await self.analyze_results()
        
        report_lines = [
            "🔍 SYSTEM_8001 Error Isolation Test Report",
            "=" * 50,
            f"Generated: {datetime.utcnow().isoformat()}Z",
            f"Server: {self.server_url}",
            "",
            "📊 Test Summary:",
            f"  Total Tests: {analysis['summary']['total_tests']}",
            f"  Successful: {analysis['summary']['successful_tests']}",
            f"  Failed: {analysis['summary']['failed_tests']}",
            f"  Success Rate: {analysis['summary']['success_rate']}",
            f"  SYSTEM_8001 Count: {analysis['summary']['system_8001_count']}",
            ""
        ]
        
        # SYSTEM_8001 Analysis
        if analysis["system_8001_occurrences"]:
            report_lines.extend([
                "🚨 SYSTEM_8001 Error Analysis:",
                "-" * 30
            ])
            for occurrence in analysis["system_8001_occurrences"]:
                report_lines.extend([
                    f"  Component: {occurrence['component']}",
                    f"  Error Code: {occurrence['error_details'].get('code', 'N/A')}",
                    f"  Message: {occurrence['error_details'].get('message', 'N/A')}",
                    f"  Error ID: {occurrence['error_details'].get('error_id', 'N/A')}",
                    f"  Timestamp: {occurrence['error_details'].get('timestamp', 'N/A')}",
                    ""
                ])
        else:
            report_lines.extend([
                "✅ No SYSTEM_8001 errors detected",
                ""
            ])
        
        # Failed Components
        if analysis["failed_components"]:
            report_lines.extend([
                "❌ Failed Components:",
                "-" * 20
            ])
            for failure in analysis["failed_components"]:
                report_lines.extend([
                    f"  {failure['component']}:",
                    f"    Error: {failure['error']}",
                    f"    Status Code: {failure.get('status_code', 'N/A')}",
                    f"    Response Time: {failure['response_time_ms']:.1f}ms",
                    ""
                ])
        
        # Performance Analysis
        if analysis["performance_analysis"]:
            perf = analysis["performance_analysis"]
            report_lines.extend([
                "⚡ Performance Analysis:",
                "-" * 22,
                f"  Average Response Time: {perf['avg_response_time_ms']:.1f}ms",
                f"  Maximum Response Time: {perf['max_response_time_ms']:.1f}ms",
                f"  Minimum Response Time: {perf['min_response_time_ms']:.1f}ms",
                ""
            ])
        
        # Recommendations
        if analysis["recommendations"]:
            report_lines.extend([
                "💡 Recommendations:",
                "-" * 17
            ])
            for rec in analysis["recommendations"]:
                report_lines.extend([
                    f"  [{rec['priority']}] {rec['issue']}:",
                    f"    {rec['recommendation']}",
                    f"    Components: {', '.join(rec.get('affected_components', []))}",
                    ""
                ])
        
        # Detailed Results
        report_lines.extend([
            "📝 Detailed Results:",
            "-" * 18,
            json.dumps(self.test_results, indent=2, default=str),
            ""
        ])
        
        return "\n".join(report_lines)
    
    async def run_complete_test_suite(self) -> str:
        """Run the complete test suite and return a detailed report"""
        
        # Generate unique test identifiers
        test_id = str(uuid.uuid4())[:8]
        test_email = f"test_{test_id}@system8001test.com"
        test_password = "TestPassword123!System8001"
        
        logger.info(f"🚀 Starting SYSTEM_8001 isolation test suite (ID: {test_id})")
        logger.info(f"📧 Test email: {test_email}")
        
        self.test_results = {
            "test_id": test_id,
            "test_email": test_email,
            "start_time": datetime.utcnow().isoformat(),
            "server_url": self.server_url
        }
        
        # Run component tests
        self.test_results["component_tests"] = await self.run_component_tests(test_email, test_password)
        
        # Run full registration test
        self.test_results["full_registration"] = await self.run_full_registration_test(test_email, test_password)
        
        # Complete test results
        self.test_results["end_time"] = datetime.utcnow().isoformat()
        self.test_results["total_duration_seconds"] = (
            datetime.fromisoformat(self.test_results["end_time"].replace('Z', '')) - 
            datetime.fromisoformat(self.test_results["start_time"])
        ).total_seconds()
        
        # Generate and return report
        report = await self.generate_report()
        
        logger.info(f"🏁 Test suite completed (Duration: {self.test_results['total_duration_seconds']:.1f}s)")
        
        return report


async def main():
    """Main function to run the test suite"""
    
    parser = argparse.ArgumentParser(description="SYSTEM_8001 Error Isolation Test Suite")
    parser.add_argument(
        "--server-url", 
        default="http://localhost:8000",
        help="Server URL to test against (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--output-file",
        help="File to save the test report (optional)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        async with SYSTEM8001TestSuite(args.server_url) as test_suite:
            report = await test_suite.run_complete_test_suite()
            
            # Print report to console
            print("\n" + "="*60)
            print(report)
            print("="*60)
            
            # Save to file if specified
            if args.output_file:
                with open(args.output_file, 'w') as f:
                    f.write(report)
                logger.info(f"📄 Report saved to {args.output_file}")
                
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())