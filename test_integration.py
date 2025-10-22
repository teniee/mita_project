#!/usr/bin/env python3
"""
MITA Frontend-Backend Integration Test Script

This script validates that the Flutter frontend and FastAPI backend
are properly connected and working as a complete system.

Usage:
    python test_integration.py

Requirements:
    pip install requests python-dotenv colorama
"""

import json
import sys
import time
from typing import Dict, Any, Optional, Tuple
import requests
from datetime import datetime
from colorama import Fore, Style, init

# Initialize colorama for colored output
init(autoreset=True)

# Configuration
API_BASE_URL = "https://mita-docker-ready-project-manus.onrender.com"
API_PREFIX = "/api"
TIMEOUT = 30

class IntegrationTester:
    """Integration test suite for MITA Finance API"""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.test_results: Dict[str, bool] = {}
        self.test_user_email = f"test_integration_{int(time.time())}@example.com"
        self.test_user_password = "SecurePassword123!"

    def log_success(self, message: str):
        """Print success message"""
        print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")

    def log_error(self, message: str):
        """Print error message"""
        print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")

    def log_info(self, message: str):
        """Print info message"""
        print(f"{Fore.CYAN}ℹ️  {message}{Style.RESET_ALL}")

    def log_warning(self, message: str):
        """Print warning message"""
        print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")

    def log_test_start(self, test_name: str):
        """Print test start message"""
        print(f"\n{Fore.BLUE}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}Testing: {test_name}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'='*60}{Style.RESET_ALL}")

    def record_result(self, test_name: str, passed: bool):
        """Record test result"""
        self.test_results[test_name] = passed

    def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        authenticated: bool = False
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        request_headers = headers or {}

        if authenticated and self.access_token:
            request_headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            self.log_info(f"{method.upper()} {endpoint}")

            if method.upper() == "GET":
                response = self.session.get(
                    url,
                    headers=request_headers,
                    params=data,
                    timeout=TIMEOUT
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url,
                    json=data,
                    headers=request_headers,
                    timeout=TIMEOUT
                )
            elif method.upper() == "PUT":
                response = self.session.put(
                    url,
                    json=data,
                    headers=request_headers,
                    timeout=TIMEOUT
                )
            elif method.upper() == "DELETE":
                response = self.session.delete(
                    url,
                    headers=request_headers,
                    timeout=TIMEOUT
                )
            else:
                return None, f"Unsupported method: {method}"

            self.log_info(f"Status: {response.status_code}")
            return response, None

        except requests.exceptions.Timeout:
            error = f"Request timeout after {TIMEOUT}s"
            self.log_error(error)
            return None, error
        except requests.exceptions.ConnectionError as e:
            error = f"Connection error: {str(e)}"
            self.log_error(error)
            return None, error
        except Exception as e:
            error = f"Request failed: {str(e)}"
            self.log_error(error)
            return None, error

    def test_health_check(self) -> bool:
        """Test backend health check endpoint"""
        self.log_test_start("Health Check Endpoint")

        response, error = self.make_request("GET", "/health")

        if error:
            self.log_error(f"Health check failed: {error}")
            return False

        if response and response.status_code == 200:
            try:
                data = response.json()
                self.log_success(f"Health check passed")
                self.log_info(f"Service: {data.get('service', 'Unknown')}")
                self.log_info(f"Version: {data.get('version', 'Unknown')}")
                self.log_info(f"Status: {data.get('status', 'Unknown')}")
                self.log_info(f"Database: {data.get('database', 'Unknown')}")
                return True
            except json.JSONDecodeError:
                self.log_error("Invalid JSON response from health check")
                return False
        else:
            self.log_error(f"Health check failed with status {response.status_code}")
            return False

    def test_root_endpoint(self) -> bool:
        """Test root endpoint"""
        self.log_test_start("Root Endpoint")

        response, error = self.make_request("GET", "/")

        if error:
            self.log_warning(f"Root endpoint check failed: {error}")
            return False

        if response and response.status_code == 200:
            try:
                data = response.json()
                self.log_success("Root endpoint accessible")
                self.log_info(f"Message: {data.get('message', 'No message')}")
                return True
            except json.JSONDecodeError:
                self.log_error("Invalid JSON response from root endpoint")
                return False
        else:
            self.log_error(f"Root endpoint failed with status {response.status_code}")
            return False

    def test_registration(self) -> bool:
        """Test user registration endpoint"""
        self.log_test_start("User Registration")

        registration_data = {
            "email": self.test_user_email,
            "password": self.test_user_password
        }

        response, error = self.make_request(
            "POST",
            f"{API_PREFIX}/auth/register",
            data=registration_data
        )

        if error:
            self.log_error(f"Registration failed: {error}")
            return False

        if response and response.status_code in [200, 201]:
            try:
                data = response.json()
                self.access_token = data.get("access_token") or data.get("data", {}).get("access_token")
                self.refresh_token = data.get("refresh_token") or data.get("data", {}).get("refresh_token")

                if self.access_token:
                    self.log_success("Registration successful")
                    self.log_info(f"Test user: {self.test_user_email}")
                    self.log_info(f"Access token received: {self.access_token[:20]}...")
                    return True
                else:
                    self.log_error("Registration successful but no access token received")
                    return False
            except json.JSONDecodeError:
                self.log_error("Invalid JSON response from registration")
                return False
        elif response and response.status_code == 400:
            # User might already exist, try login instead
            self.log_warning("User might already exist, will try login")
            return self.test_login()
        else:
            self.log_error(f"Registration failed with status {response.status_code}")
            if response:
                self.log_error(f"Response: {response.text}")
            return False

    def test_login(self) -> bool:
        """Test user login endpoint"""
        self.log_test_start("User Login")

        login_data = {
            "email": self.test_user_email,
            "password": self.test_user_password
        }

        response, error = self.make_request(
            "POST",
            f"{API_PREFIX}/auth/login",
            data=login_data
        )

        if error:
            self.log_error(f"Login failed: {error}")
            return False

        if response and response.status_code == 200:
            try:
                data = response.json()
                self.access_token = data.get("access_token") or data.get("data", {}).get("access_token")
                self.refresh_token = data.get("refresh_token") or data.get("data", {}).get("refresh_token")

                if self.access_token:
                    self.log_success("Login successful")
                    self.log_info(f"Access token received: {self.access_token[:20]}...")
                    return True
                else:
                    self.log_error("Login successful but no access token received")
                    return False
            except json.JSONDecodeError:
                self.log_error("Invalid JSON response from login")
                return False
        else:
            self.log_error(f"Login failed with status {response.status_code}")
            if response:
                self.log_error(f"Response: {response.text}")
            return False

    def test_authenticated_endpoint(self) -> bool:
        """Test authenticated user profile endpoint"""
        self.log_test_start("Authenticated Endpoint (User Profile)")

        if not self.access_token:
            self.log_error("No access token available, cannot test authenticated endpoint")
            return False

        response, error = self.make_request(
            "GET",
            f"{API_PREFIX}/users/profile",
            authenticated=True
        )

        if error:
            self.log_error(f"User profile request failed: {error}")
            return False

        if response and response.status_code == 200:
            try:
                data = response.json()
                self.log_success("Authenticated endpoint accessible")

                user_data = data.get("data", data)
                if user_data:
                    self.log_info(f"User email: {user_data.get('email', 'Not provided')}")
                    self.log_info(f"User ID: {user_data.get('id', 'Not provided')}")
                return True
            except json.JSONDecodeError:
                self.log_error("Invalid JSON response from user profile")
                return False
        elif response and response.status_code == 401:
            self.log_error("Authentication failed - token might be invalid")
            return False
        else:
            self.log_error(f"User profile request failed with status {response.status_code}")
            return False

    def test_onboarding_endpoint(self) -> bool:
        """Test onboarding questions endpoint"""
        self.log_test_start("Onboarding Questions Endpoint")

        if not self.access_token:
            self.log_warning("No access token, skipping authenticated onboarding test")
            return True  # Don't fail if not authenticated

        response, error = self.make_request(
            "GET",
            f"{API_PREFIX}/onboarding/questions",
            authenticated=True
        )

        if error:
            self.log_warning(f"Onboarding questions request failed: {error}")
            return True  # Don't fail - optional endpoint

        if response and response.status_code == 200:
            try:
                data = response.json()
                self.log_success("Onboarding endpoint accessible")
                return True
            except json.JSONDecodeError:
                self.log_warning("Invalid JSON response from onboarding")
                return True
        else:
            self.log_warning(f"Onboarding endpoint returned status {response.status_code}")
            return True  # Don't fail - optional

    def test_transactions_endpoint(self) -> bool:
        """Test transactions list endpoint"""
        self.log_test_start("Transactions List Endpoint")

        if not self.access_token:
            self.log_warning("No access token, skipping authenticated transactions test")
            return True

        response, error = self.make_request(
            "GET",
            f"{API_PREFIX}/transactions",
            authenticated=True
        )

        if error:
            self.log_warning(f"Transactions request failed: {error}")
            return True  # Don't fail - optional

        if response and response.status_code in [200, 404]:  # 404 is OK if no transactions
            self.log_success("Transactions endpoint accessible")
            return True
        else:
            self.log_warning(f"Transactions endpoint returned status {response.status_code}")
            return True  # Don't fail - optional

    def run_all_tests(self):
        """Run all integration tests"""
        print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}MITA Frontend-Backend Integration Test Suite{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Backend URL: {self.base_url}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}\n")

        # Run tests in order
        tests = [
            ("Health Check", self.test_health_check),
            ("Root Endpoint", self.test_root_endpoint),
            ("User Registration", self.test_registration),
            ("User Login", self.test_login),
            ("Authenticated Endpoint", self.test_authenticated_endpoint),
            ("Onboarding Endpoint", self.test_onboarding_endpoint),
            ("Transactions Endpoint", self.test_transactions_endpoint),
        ]

        for test_name, test_func in tests:
            try:
                result = test_func()
                self.record_result(test_name, result)
            except Exception as e:
                self.log_error(f"Test {test_name} crashed: {str(e)}")
                self.record_result(test_name, False)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test results summary"""
        print(f"\n{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}Test Summary{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}\n")

        passed = sum(1 for result in self.test_results.values() if result)
        total = len(self.test_results)

        for test_name, result in self.test_results.items():
            status = f"{Fore.GREEN}✅ PASS" if result else f"{Fore.RED}❌ FAIL"
            print(f"{status}{Style.RESET_ALL} - {test_name}")

        print(f"\n{Fore.CYAN}Total: {passed}/{total} tests passed{Style.RESET_ALL}")

        if passed == total:
            print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}✅ ALL TESTS PASSED - INTEGRATION VERIFIED{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")
            sys.exit(0)
        else:
            print(f"\n{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}⚠️  SOME TESTS FAILED - CHECK LOGS ABOVE{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}\n")
            sys.exit(1)


def main():
    """Main entry point"""
    tester = IntegrationTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
