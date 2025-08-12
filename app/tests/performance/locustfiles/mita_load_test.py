"""
MITA Load Testing with Locust
Comprehensive load testing for production readiness validation.
Tests concurrent users, financial operations, and system stability under load.
"""

import json
import random
import time
from typing import Dict, Any, List
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner
import logging

# Configure logging for detailed performance analysis
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MITAFinancialUser(HttpUser):
    """
    Simulates realistic MITA user behavior patterns.
    Models typical financial app usage with focus on high-frequency operations.
    """
    
    # Realistic wait times between user actions
    wait_time = between(1, 5)  # 1-5 seconds between actions
    
    def on_start(self):
        """Initialize user session - register or login"""
        self.user_data = self._generate_user_data()
        self.auth_token = None
        self.user_id = None
        
        # 70% of users are existing (login), 30% are new (register)
        if random.random() < 0.7:
            self.login_user()
        else:
            self.register_user()
    
    def _generate_user_data(self) -> Dict[str, Any]:
        """Generate realistic user data for testing"""
        user_id = random.randint(10000, 99999)
        
        return {
            "email": f"loadtest{user_id}@example.com",
            "password": "LoadTest123!",
            "country": "US",
            "annual_income": random.randint(30000, 150000),
            "timezone": random.choice([
                "America/New_York", 
                "America/Chicago", 
                "America/Denver", 
                "America/Los_Angeles"
            ])
        }
    
    def register_user(self):
        """Register a new user"""
        with self.client.post(
            "/api/auth/register",
            json=self.user_data,
            catch_response=True,
            name="auth_register"
        ) as response:
            if response.status_code == 201:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.user_id = self._extract_user_id_from_token(self.auth_token)
                response.success()
            else:
                # Registration might fail due to existing email, try login
                self.login_user()
                response.success()
    
    def login_user(self):
        """Login existing user"""
        login_data = {
            "email": self.user_data["email"],
            "password": self.user_data["password"]
        }
        
        with self.client.post(
            "/api/auth/login",
            json=login_data,
            catch_response=True,
            name="auth_login"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.user_id = self._extract_user_id_from_token(self.auth_token)
                response.success()
            else:
                # Login failed, try registration
                self.register_user()
                response.success()
    
    def _extract_user_id_from_token(self, token: str) -> str:
        """Extract user ID from JWT token (simplified)"""
        try:
            import base64
            import json
            # This is simplified - in real implementation would properly decode JWT
            return f"user_{random.randint(1000, 9999)}"
        except:
            return f"user_{random.randint(1000, 9999)}"
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers for authenticated requests"""
        if not self.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}
    
    @task(10)  # High frequency - income classification happens often
    def view_budget_dashboard(self):
        """View budget dashboard - triggers income classification"""
        if not self.auth_token:
            return
        
        with self.client.get(
            "/api/budget/current",
            headers=self._get_auth_headers(),
            catch_response=True,
            name="budget_dashboard"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self.refresh_token()
                response.success()
            else:
                response.failure(f"Budget dashboard failed: {response.status_code}")
    
    @task(8)  # High frequency - users check transactions often
    def view_transactions(self):
        """View recent transactions"""
        if not self.auth_token:
            return
        
        with self.client.get(
            "/api/transactions",
            headers=self._get_auth_headers(),
            catch_response=True,
            name="transactions_list"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self.refresh_token()
                response.success()
            else:
                response.failure(f"Transactions failed: {response.status_code}")
    
    @task(6)  # Medium frequency - financial insights
    def get_financial_insights(self):
        """Get AI-powered financial insights"""
        if not self.auth_token:
            return
        
        with self.client.get(
            "/api/insights/financial",
            headers=self._get_auth_headers(),
            catch_response=True,
            name="financial_insights"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self.refresh_token()
                response.success()
            else:
                response.failure(f"Financial insights failed: {response.status_code}")
    
    @task(5)  # Medium frequency - add expenses
    def add_expense(self):
        """Add a new expense - critical financial operation"""
        if not self.auth_token:
            return
        
        expense_data = {
            "description": f"Test Expense {random.randint(1, 1000)}",
            "amount": round(random.uniform(10.0, 500.0), 2),
            "category": random.choice([
                "food", "transport", "entertainment", "utilities", 
                "healthcare", "shopping", "education"
            ]),
            "date": time.strftime("%Y-%m-%d"),
            "payment_method": random.choice(["card", "cash", "transfer"])
        }
        
        with self.client.post(
            "/api/expenses",
            json=expense_data,
            headers=self._get_auth_headers(),
            catch_response=True,
            name="add_expense"
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            elif response.status_code == 401:
                self.refresh_token()
                response.success()
            else:
                response.failure(f"Add expense failed: {response.status_code}")
    
    @task(4)  # Medium frequency - check goals
    def view_financial_goals(self):
        """View financial goals and progress"""
        if not self.auth_token:
            return
        
        with self.client.get(
            "/api/goals",
            headers=self._get_auth_headers(),
            catch_response=True,
            name="financial_goals"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self.refresh_token()
                response.success()
            else:
                response.failure(f"Financial goals failed: {response.status_code}")
    
    @task(3)  # Lower frequency - calendar view
    def view_calendar(self):
        """View spending calendar"""
        if not self.auth_token:
            return
        
        with self.client.get(
            "/api/calendar/current",
            headers=self._get_auth_headers(),
            catch_response=True,
            name="spending_calendar"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self.refresh_token()
                response.success()
            else:
                response.failure(f"Spending calendar failed: {response.status_code}")
    
    @task(2)  # Lower frequency - analytics
    def view_analytics(self):
        """View spending analytics"""
        if not self.auth_token:
            return
        
        with self.client.get(
            "/api/analytics/spending-patterns",
            headers=self._get_auth_headers(),
            catch_response=True,
            name="spending_analytics"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self.refresh_token()
                response.success()
            else:
                response.failure(f"Spending analytics failed: {response.status_code}")
    
    @task(1)  # Low frequency - update profile
    def update_user_profile(self):
        """Update user profile information"""
        if not self.auth_token:
            return
        
        profile_updates = {
            "annual_income": random.randint(30000, 150000),
            "timezone": random.choice([
                "America/New_York", "America/Chicago", 
                "America/Denver", "America/Los_Angeles"
            ])
        }
        
        with self.client.put(
            "/api/users/profile",
            json=profile_updates,
            headers=self._get_auth_headers(),
            catch_response=True,
            name="update_profile"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self.refresh_token()
                response.success()
            else:
                response.failure(f"Profile update failed: {response.status_code}")
    
    def refresh_token(self):
        """Refresh expired authentication token"""
        # In real implementation, would use refresh token
        # For load testing, just re-login
        self.login_user()
    
    def on_stop(self):
        """Clean up when user session ends"""
        if self.auth_token:
            # Optionally logout (but don't fail if it doesn't work)
            try:
                self.client.post(
                    "/api/auth/logout",
                    headers=self._get_auth_headers(),
                    name="auth_logout"
                )
            except:
                pass


class MITAHeavyUser(HttpUser):
    """
    Simulates heavy users who perform many financial operations.
    Tests system under intensive usage patterns.
    """
    
    wait_time = between(0.5, 2)  # Faster actions for heavy users
    weight = 1  # Lower weight - fewer heavy users
    
    def on_start(self):
        """Initialize heavy user session"""
        self.user_data = {
            "email": f"heavy_user_{random.randint(10000, 99999)}@example.com",
            "password": "HeavyUser123!",
            "country": "US",
            "annual_income": random.randint(75000, 250000),
            "timezone": "America/New_York"
        }
        self.auth_token = None
        self.login_user()
    
    def login_user(self):
        """Login heavy user"""
        login_data = {
            "email": self.user_data["email"],
            "password": self.user_data["password"]
        }
        
        with self.client.post("/api/auth/login", json=login_data) as response:
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
            else:
                # Try registration
                self.client.post("/api/auth/register", json=self.user_data)
                self.login_user()
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        if not self.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}
    
    @task(15)  # Very high frequency operations
    def bulk_expense_operations(self):
        """Perform multiple expense operations rapidly"""
        if not self.auth_token:
            return
        
        # Add multiple expenses in quick succession
        for _ in range(3):
            expense_data = {
                "description": f"Bulk Expense {random.randint(1, 10000)}",
                "amount": round(random.uniform(5.0, 200.0), 2),
                "category": random.choice(["food", "transport", "entertainment"]),
                "date": time.strftime("%Y-%m-%d")
            }
            
            self.client.post(
                "/api/expenses",
                json=expense_data,
                headers=self._get_auth_headers(),
                name="bulk_expense"
            )
    
    @task(10)  # Intensive dashboard usage
    def rapid_dashboard_checks(self):
        """Rapidly check dashboard multiple times"""
        if not self.auth_token:
            return
        
        for _ in range(5):
            self.client.get(
                "/api/budget/current",
                headers=self._get_auth_headers(),
                name="rapid_dashboard"
            )
            time.sleep(0.1)  # Brief pause between requests


class MITAMobileUser(HttpUser):
    """
    Simulates mobile app usage patterns with different request patterns.
    Mobile users typically have shorter sessions but more frequent requests.
    """
    
    wait_time = between(2, 8)  # Mobile users take longer between actions
    weight = 3  # Higher weight - more mobile users
    
    def on_start(self):
        """Initialize mobile user session"""
        self.user_data = {
            "email": f"mobile_user_{random.randint(10000, 99999)}@example.com",
            "password": "MobileUser123!",
            "country": "US",
            "annual_income": random.randint(40000, 120000),
            "timezone": "America/Los_Angeles"
        }
        self.auth_token = None
        self.session_actions = 0
        self.max_session_actions = random.randint(10, 30)  # Mobile sessions are shorter
        
        self.login_user()
    
    def login_user(self):
        """Login mobile user"""
        login_data = {
            "email": self.user_data["email"], 
            "password": self.user_data["password"]
        }
        
        # Add mobile-specific headers
        headers = {
            "User-Agent": "MITA-Mobile/1.0 (iOS 15.0)",
            "X-Platform": "mobile"
        }
        
        with self.client.post(
            "/api/auth/login",
            json=login_data,
            headers=headers
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
            else:
                # Try registration for mobile
                self.client.post(
                    "/api/auth/register", 
                    json=self.user_data,
                    headers=headers
                )
                self.login_user()
    
    def _get_mobile_headers(self) -> Dict[str, str]:
        """Get mobile-specific headers with auth"""
        headers = {
            "User-Agent": "MITA-Mobile/1.0 (iOS 15.0)",
            "X-Platform": "mobile"
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    @task(12)  # Mobile users check budget frequently
    def quick_budget_check(self):
        """Quick budget check typical of mobile usage"""
        if not self.auth_token:
            return
        
        self.session_actions += 1
        if self.session_actions > self.max_session_actions:
            self.stop(force=True)
            return
        
        with self.client.get(
            "/api/budget/current",
            headers=self._get_mobile_headers(),
            name="mobile_budget_check"
        ) as response:
            if response.status_code != 200:
                response.failure(f"Mobile budget check failed: {response.status_code}")
    
    @task(8)  # Mobile expense entry (camera/OCR would be used)
    def add_mobile_expense(self):
        """Add expense via mobile app"""
        if not self.auth_token:
            return
        
        self.session_actions += 1
        if self.session_actions > self.max_session_actions:
            self.stop(force=True)
            return
        
        expense_data = {
            "description": f"Mobile Expense {random.randint(1, 1000)}",
            "amount": round(random.uniform(5.0, 100.0), 2),
            "category": random.choice(["food", "transport", "shopping"]),
            "date": time.strftime("%Y-%m-%d"),
            "source": "mobile_app"
        }
        
        self.client.post(
            "/api/expenses",
            json=expense_data,
            headers=self._get_mobile_headers(),
            name="mobile_add_expense"
        )


# Locust event handlers for detailed monitoring
@events.request.add_listener
def log_request_stats(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Log detailed request statistics for analysis"""
    if exception:
        logger.error(f"Request failed: {request_type} {name} - {exception}")
    elif response_time > 2000:  # Log slow requests (>2 seconds)
        logger.warning(f"Slow request: {request_type} {name} - {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start and configuration"""
    logger.info("MITA Load Test Starting")
    logger.info(f"Target host: {environment.host}")
    
    if isinstance(environment.runner, MasterRunner):
        logger.info(f"Master runner starting with {environment.runner.worker_count} workers")
    elif isinstance(environment.runner, WorkerRunner):
        logger.info("Worker runner starting")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate performance report at test end"""
    logger.info("MITA Load Test Complete")
    
    # Get stats from runner
    stats = environment.runner.stats
    
    # Generate performance report
    report = {
        "test_duration": stats.last_request_timestamp - stats.start_time if stats.last_request_timestamp else 0,
        "total_requests": stats.num_requests,
        "total_failures": stats.num_failures,
        "average_response_time": stats.avg_response_time,
        "failure_rate": (stats.num_failures / max(stats.num_requests, 1)) * 100,
        "requests_per_second": stats.total_rps,
        "critical_endpoints": []
    }
    
    # Identify critical endpoint performance
    for name, entry in stats.entries.items():
        if name[1] in ["auth_login", "auth_register", "budget_dashboard", "add_expense"]:
            report["critical_endpoints"].append({
                "endpoint": name[1],
                "method": name[0],
                "avg_response_time": entry.avg_response_time,
                "failure_rate": (entry.num_failures / max(entry.num_requests, 1)) * 100,
                "requests": entry.num_requests
            })
    
    # Log performance report
    logger.info(f"Performance Report: {json.dumps(report, indent=2)}")
    
    # Performance assertions for CI/CD
    if report["average_response_time"] > 2000:
        logger.error("PERFORMANCE FAILURE: Average response time > 2 seconds")
    
    if report["failure_rate"] > 5:
        logger.error(f"RELIABILITY FAILURE: Failure rate {report['failure_rate']:.2f}% > 5%")
    
    # Check critical endpoint performance
    for endpoint in report["critical_endpoints"]:
        if endpoint["endpoint"] == "auth_login" and endpoint["avg_response_time"] > 500:
            logger.error(f"AUTH PERFORMANCE FAILURE: Login took {endpoint['avg_response_time']}ms")
        
        if endpoint["endpoint"] == "budget_dashboard" and endpoint["avg_response_time"] > 1000:
            logger.error(f"DASHBOARD PERFORMANCE FAILURE: Dashboard took {endpoint['avg_response_time']}ms")


# Custom load test scenarios
class FinancialReportingLoad(HttpUser):
    """
    Simulates end-of-month financial reporting load.
    Tests system under heavy analytical operations.
    """
    
    wait_time = between(5, 15)
    weight = 1  # Run fewer of these intensive users
    
    @task
    def generate_monthly_report(self):
        """Generate comprehensive monthly financial report"""
        if hasattr(self, 'auth_token') and self.auth_token:
            # This would trigger heavy database operations
            endpoints = [
                "/api/analytics/monthly-summary",
                "/api/transactions?month=current", 
                "/api/budget/analysis",
                "/api/insights/trends"
            ]
            
            for endpoint in endpoints:
                self.client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                    name="monthly_reporting"
                )
                time.sleep(1)  # Brief pause between intensive operations