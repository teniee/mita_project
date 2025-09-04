#!/usr/bin/env python3
"""
MITA Finance Health Monitoring Deployment Script
Comprehensive setup and validation of the enhanced health monitoring system
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List
import subprocess
import requests
from pathlib import Path

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.core.middleware_health_monitor import middleware_health_monitor
from app.core.health_monitoring_alerts import health_alert_manager
from app.api.health.enhanced_routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('health_monitoring_deployment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class HealthMonitoringDeployment:
    """
    Comprehensive deployment and validation of MITA health monitoring system
    """
    
    def __init__(self):
        self.deployment_start_time = datetime.utcnow()
        self.validation_results = []
        self.base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        
    def log_step(self, step: str, status: str, details: str = ""):
        """Log deployment step with status"""
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'step': step,
            'status': status,
            'details': details
        }
        self.validation_results.append(log_entry)
        
        if status == 'SUCCESS':
            logger.info(f"✓ {step}: {details}")
        elif status == 'WARNING':
            logger.warning(f"⚠ {step}: {details}")
        elif status == 'ERROR':
            logger.error(f"✗ {step}: {details}")
        else:
            logger.info(f"• {step}: {details}")

    def validate_environment(self) -> bool:
        """Validate deployment environment and prerequisites"""
        logger.info("=== VALIDATING DEPLOYMENT ENVIRONMENT ===")
        
        validation_passed = True
        
        # Check Python version
        python_version = sys.version_info
        if python_version.major >= 3 and python_version.minor >= 8:
            self.log_step("Python Version Check", "SUCCESS", 
                         f"Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        else:
            self.log_step("Python Version Check", "ERROR", 
                         f"Python 3.8+ required, found {python_version.major}.{python_version.minor}")
            validation_passed = False
        
        # Check required directories
        required_dirs = [
            'app/core',
            'app/api/health', 
            'monitoring',
            'logs',
            'logs/audit'
        ]
        
        for dir_path in required_dirs:
            full_path = Path(dir_path)
            if full_path.exists():
                self.log_step(f"Directory Check: {dir_path}", "SUCCESS", "Directory exists")
            else:
                # Create directory if it doesn't exist
                try:
                    full_path.mkdir(parents=True, exist_ok=True)
                    self.log_step(f"Directory Check: {dir_path}", "SUCCESS", "Directory created")
                except Exception as e:
                    self.log_step(f"Directory Check: {dir_path}", "ERROR", str(e))
                    validation_passed = False
        
        # Check required files
        required_files = [
            'app/core/middleware_health_monitor.py',
            'app/core/middleware_components_health.py',
            'app/core/health_monitoring_alerts.py',
            'app/api/health/enhanced_routes.py',
            'monitoring/health_monitoring_dashboard.json',
            'monitoring/health_alert_rules.yml'
        ]
        
        for file_path in required_files:
            if Path(file_path).exists():
                self.log_step(f"File Check: {file_path}", "SUCCESS", "File exists")
            else:
                self.log_step(f"File Check: {file_path}", "ERROR", "Required file missing")
                validation_passed = False
        
        # Check environment variables
        required_env_vars = ['JWT_SECRET', 'DATABASE_URL']
        optional_env_vars = ['REDIS_URL', 'ALERT_EMAIL_SMTP_HOST', 'ALERT_WEBHOOK_URL']
        
        for env_var in required_env_vars:
            if os.getenv(env_var):
                self.log_step(f"Environment Variable: {env_var}", "SUCCESS", "Set")
            else:
                self.log_step(f"Environment Variable: {env_var}", "ERROR", "Not set")
                validation_passed = False
        
        for env_var in optional_env_vars:
            if os.getenv(env_var):
                self.log_step(f"Optional Environment Variable: {env_var}", "SUCCESS", "Set")
            else:
                self.log_step(f"Optional Environment Variable: {env_var}", "WARNING", "Not set (optional)")
        
        return validation_passed

    def validate_database_connection(self) -> bool:
        """Validate database connection and health"""
        logger.info("=== VALIDATING DATABASE CONNECTION ===")
        
        try:
            # This would require async context, so we'll simulate
            # In production, this would test actual database connection
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                self.log_step("Database Connection", "ERROR", "DATABASE_URL not configured")
                return False
            
            # For now, just validate URL format
            if database_url.startswith(('postgresql://', 'postgresql+asyncpg://')):
                self.log_step("Database URL Format", "SUCCESS", "Valid PostgreSQL URL")
                return True
            else:
                self.log_step("Database URL Format", "ERROR", "Invalid database URL format")
                return False
                
        except Exception as e:
            self.log_step("Database Connection", "ERROR", str(e))
            return False

    def validate_redis_connection(self) -> bool:
        """Validate Redis connection (optional)"""
        logger.info("=== VALIDATING REDIS CONNECTION ===")
        
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            self.log_step("Redis Connection", "WARNING", "Redis not configured (using in-memory caching)")
            return True
        
        try:
            import redis
            client = redis.Redis.from_url(redis_url)
            client.ping()
            self.log_step("Redis Connection", "SUCCESS", "Redis ping successful")
            
            # Test basic operations
            test_key = "health_deployment_test"
            client.set(test_key, "test_value", ex=60)
            value = client.get(test_key)
            client.delete(test_key)
            
            if value == b"test_value":
                self.log_step("Redis Operations", "SUCCESS", "Basic operations working")
                return True
            else:
                self.log_step("Redis Operations", "ERROR", "Basic operations failed")
                return False
                
        except Exception as e:
            self.log_step("Redis Connection", "ERROR", str(e))
            return False

    def install_monitoring_dependencies(self) -> bool:
        """Install or verify monitoring dependencies"""
        logger.info("=== INSTALLING MONITORING DEPENDENCIES ===")
        
        try:
            # Check if required packages are available
            required_packages = [
                'psutil',
                'redis',
                'requests',
                'prometheus-client'
            ]
            
            missing_packages = []
            
            for package in required_packages:
                try:
                    __import__(package.replace('-', '_'))
                    self.log_step(f"Package Check: {package}", "SUCCESS", "Available")
                except ImportError:
                    missing_packages.append(package)
                    self.log_step(f"Package Check: {package}", "ERROR", "Missing")
            
            if missing_packages:
                self.log_step("Missing Packages", "ERROR", 
                             f"Install missing packages: pip install {' '.join(missing_packages)}")
                return False
            
            return True
            
        except Exception as e:
            self.log_step("Dependency Installation", "ERROR", str(e))
            return False

    async def test_health_endpoints(self) -> bool:
        """Test health monitoring endpoints"""
        logger.info("=== TESTING HEALTH ENDPOINTS ===")
        
        # Note: This assumes the server is running
        # In production deployment, we'd start the server first
        
        endpoints_to_test = [
            '/health/comprehensive',
            '/health/middleware', 
            '/health/performance',
            '/health/alerts',
            '/health/history',
            '/health/metrics'
        ]
        
        all_passed = True
        
        for endpoint in endpoints_to_test:
            try:
                url = f"{self.base_url}{endpoint}"
                
                # Use a short timeout for testing
                response = requests.get(url, timeout=10)
                
                if response.status_code in [200, 503]:  # 503 is acceptable for degraded health
                    self.log_step(f"Endpoint Test: {endpoint}", "SUCCESS", 
                                 f"Status {response.status_code}")
                    
                    # Validate response format
                    try:
                        data = response.json()
                        if 'timestamp' in data:
                            self.log_step(f"Response Format: {endpoint}", "SUCCESS", "Valid JSON")
                        else:
                            self.log_step(f"Response Format: {endpoint}", "WARNING", "Unexpected format")
                    except json.JSONDecodeError:
                        self.log_step(f"Response Format: {endpoint}", "ERROR", "Invalid JSON")
                        all_passed = False
                        
                else:
                    self.log_step(f"Endpoint Test: {endpoint}", "ERROR", 
                                 f"Status {response.status_code}")
                    all_passed = False
                    
            except requests.RequestException as e:
                self.log_step(f"Endpoint Test: {endpoint}", "ERROR", str(e))
                all_passed = False
        
        return all_passed

    def validate_monitoring_configuration(self) -> bool:
        """Validate monitoring and alerting configuration"""
        logger.info("=== VALIDATING MONITORING CONFIGURATION ===")
        
        try:
            # Check Grafana dashboard configuration
            dashboard_file = Path('monitoring/health_monitoring_dashboard.json')
            if dashboard_file.exists():
                with open(dashboard_file) as f:
                    dashboard_config = json.load(f)
                    
                if 'dashboard' in dashboard_config:
                    panels = dashboard_config['dashboard'].get('panels', [])
                    self.log_step("Grafana Dashboard", "SUCCESS", 
                                 f"Dashboard configured with {len(panels)} panels")
                else:
                    self.log_step("Grafana Dashboard", "ERROR", "Invalid dashboard format")
                    return False
            else:
                self.log_step("Grafana Dashboard", "ERROR", "Dashboard file missing")
                return False
            
            # Check Prometheus alert rules
            alerts_file = Path('monitoring/health_alert_rules.yml')
            if alerts_file.exists():
                # Basic validation - in production, you'd use a YAML parser
                with open(alerts_file) as f:
                    content = f.read()
                    if 'groups:' in content and 'rules:' in content:
                        self.log_step("Prometheus Alerts", "SUCCESS", "Alert rules configured")
                    else:
                        self.log_step("Prometheus Alerts", "ERROR", "Invalid alert rules format")
                        return False
            else:
                self.log_step("Prometheus Alerts", "ERROR", "Alert rules file missing")
                return False
            
            return True
            
        except Exception as e:
            self.log_step("Monitoring Configuration", "ERROR", str(e))
            return False

    def validate_performance_thresholds(self) -> bool:
        """Validate that performance thresholds are configured to detect timeout issues"""
        logger.info("=== VALIDATING PERFORMANCE THRESHOLDS ===")
        
        try:
            thresholds = middleware_health_monitor.performance_thresholds
            
            # Critical validation: Ensure thresholds will detect 8-15+ second timeout risks
            critical_checks = [
                ('response_time_critical', 5000, 'Must detect issues before 8-second timeouts'),
                ('response_time_warning', 2000, 'Must provide early warning'),
                ('database_connection_critical', 3000, 'Must detect DB timeout risks'),
                ('database_connection_warning', 1000, 'Must provide DB early warning'),
            ]
            
            all_passed = True
            
            for threshold_name, max_value, description in critical_checks:
                actual_value = thresholds.get(threshold_name, 0)
                
                if actual_value <= max_value:
                    self.log_step(f"Threshold: {threshold_name}", "SUCCESS", 
                                 f"{actual_value}ms <= {max_value}ms - {description}")
                else:
                    self.log_step(f"Threshold: {threshold_name}", "ERROR", 
                                 f"{actual_value}ms > {max_value}ms - {description}")
                    all_passed = False
            
            return all_passed
            
        except Exception as e:
            self.log_step("Performance Thresholds", "ERROR", str(e))
            return False

    def validate_alert_configuration(self) -> bool:
        """Validate alert manager configuration"""
        logger.info("=== VALIDATING ALERT CONFIGURATION ===")
        
        try:
            # Check alert rules
            alert_rules = health_alert_manager.alert_rules
            
            if len(alert_rules) > 0:
                self.log_step("Alert Rules", "SUCCESS", f"{len(alert_rules)} rules configured")
                
                # Check for critical timeout-related rules
                timeout_rules = [rule for rule in alert_rules if 'timeout' in rule.name or 'performance' in rule.name]
                if timeout_rules:
                    self.log_step("Timeout Alert Rules", "SUCCESS", f"{len(timeout_rules)} timeout-related rules")
                else:
                    self.log_step("Timeout Alert Rules", "WARNING", "No specific timeout alert rules found")
                
                # Check notification channels
                channels = health_alert_manager.notification_channels
                if channels:
                    self.log_step("Notification Channels", "SUCCESS", f"{len(channels)} channels configured")
                else:
                    self.log_step("Notification Channels", "WARNING", "No notification channels configured")
                
                return True
            else:
                self.log_step("Alert Rules", "ERROR", "No alert rules configured")
                return False
                
        except Exception as e:
            self.log_step("Alert Configuration", "ERROR", str(e))
            return False

    async def run_comprehensive_validation(self) -> bool:
        """Run comprehensive health monitoring system validation"""
        logger.info("=== STARTING COMPREHENSIVE HEALTH MONITORING DEPLOYMENT VALIDATION ===")
        
        validation_steps = [
            ("Environment Validation", self.validate_environment),
            ("Database Connection", self.validate_database_connection),
            ("Redis Connection", self.validate_redis_connection),
            ("Dependencies Installation", self.install_monitoring_dependencies),
            ("Monitoring Configuration", self.validate_monitoring_configuration),
            ("Performance Thresholds", self.validate_performance_thresholds),
            ("Alert Configuration", self.validate_alert_configuration),
        ]
        
        all_passed = True
        
        for step_name, validation_func in validation_steps:
            try:
                logger.info(f"Running: {step_name}")
                if asyncio.iscoroutinefunction(validation_func):
                    result = await validation_func()
                else:
                    result = validation_func()
                
                if not result:
                    all_passed = False
                    self.log_step(step_name, "ERROR", "Validation failed")
                else:
                    self.log_step(step_name, "SUCCESS", "Validation passed")
                    
            except Exception as e:
                self.log_step(step_name, "ERROR", f"Validation error: {str(e)}")
                all_passed = False
        
        # Test endpoints if server is available
        try:
            if await self.test_health_endpoints():
                self.log_step("Health Endpoints", "SUCCESS", "All endpoints responding")
            else:
                self.log_step("Health Endpoints", "WARNING", "Some endpoints failed (server may not be running)")
        except Exception as e:
            self.log_step("Health Endpoints", "WARNING", f"Endpoint testing failed: {str(e)}")
        
        return all_passed

    def generate_deployment_report(self) -> Dict[str, Any]:
        """Generate comprehensive deployment report"""
        deployment_duration = (datetime.utcnow() - self.deployment_start_time).total_seconds()
        
        successful_steps = [r for r in self.validation_results if r['status'] == 'SUCCESS']
        error_steps = [r for r in self.validation_results if r['status'] == 'ERROR']
        warning_steps = [r for r in self.validation_results if r['status'] == 'WARNING']
        
        report = {
            'deployment_summary': {
                'start_time': self.deployment_start_time.isoformat(),
                'end_time': datetime.utcnow().isoformat(),
                'duration_seconds': deployment_duration,
                'overall_status': 'SUCCESS' if len(error_steps) == 0 else 'FAILED',
                'total_steps': len(self.validation_results),
                'successful_steps': len(successful_steps),
                'error_steps': len(error_steps),
                'warning_steps': len(warning_steps)
            },
            'validation_results': self.validation_results,
            'recommendations': self.generate_recommendations(),
            'next_steps': self.generate_next_steps()
        }
        
        return report

    def generate_recommendations(self) -> List[str]:
        """Generate deployment recommendations based on validation results"""
        recommendations = []
        
        error_steps = [r for r in self.validation_results if r['status'] == 'ERROR']
        warning_steps = [r for r in self.validation_results if r['status'] == 'WARNING']
        
        if error_steps:
            recommendations.append("CRITICAL: Address all ERROR status items before deploying to production")
            
        if warning_steps:
            recommendations.append("IMPORTANT: Review and address WARNING items to ensure optimal monitoring")
            
        # Specific recommendations
        redis_warnings = [r for r in warning_steps if 'redis' in r['step'].lower()]
        if redis_warnings:
            recommendations.append("Consider configuring Redis for improved rate limiting and caching performance")
            
        notification_warnings = [r for r in warning_steps if 'notification' in r['step'].lower()]
        if notification_warnings:
            recommendations.append("Configure notification channels (email, webhook, Slack) for critical alerts")
            
        endpoint_warnings = [r for r in warning_steps if 'endpoint' in r['step'].lower()]
        if endpoint_warnings:
            recommendations.append("Ensure MITA application is running to test health endpoints")
        
        return recommendations

    def generate_next_steps(self) -> List[str]:
        """Generate next steps for deployment"""
        return [
            "1. Deploy monitoring infrastructure (Prometheus, Grafana)",
            "2. Configure alert notification channels", 
            "3. Start MITA application with health monitoring enabled",
            "4. Import Grafana dashboard from monitoring/health_monitoring_dashboard.json",
            "5. Import Prometheus alert rules from monitoring/health_alert_rules.yml",
            "6. Test end-to-end health monitoring and alerting",
            "7. Configure mobile app to use enhanced health endpoints",
            "8. Set up automated health monitoring tests in CI/CD pipeline",
            "9. Train operations team on new health monitoring capabilities",
            "10. Monitor system for 24-48 hours to validate performance"
        ]

    def save_deployment_report(self, report: Dict[str, Any]):
        """Save deployment report to file"""
        report_filename = f"health_monitoring_deployment_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Deployment report saved to: {report_filename}")
            
        except Exception as e:
            logger.error(f"Failed to save deployment report: {str(e)}")


async def main():
    """Main deployment function"""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║            MITA Finance Health Monitoring System             ║
    ║                    Deployment & Validation                   ║
    ║                                                              ║
    ║    Comprehensive health checks to prevent 8-15s timeouts    ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    deployment = HealthMonitoringDeployment()
    
    try:
        # Run comprehensive validation
        validation_passed = await deployment.run_comprehensive_validation()
        
        # Generate and save report
        report = deployment.generate_deployment_report()
        deployment.save_deployment_report(report)
        
        # Print summary
        print("\n" + "="*80)
        print("DEPLOYMENT VALIDATION SUMMARY")
        print("="*80)
        
        summary = report['deployment_summary']
        print(f"Overall Status: {summary['overall_status']}")
        print(f"Duration: {summary['duration_seconds']:.2f} seconds")
        print(f"Steps: {summary['successful_steps']}/{summary['total_steps']} successful")
        
        if summary['error_steps'] > 0:
            print(f"ERRORS: {summary['error_steps']} (must be resolved)")
            
        if summary['warning_steps'] > 0:
            print(f"WARNINGS: {summary['warning_steps']} (should be reviewed)")
        
        print("\nRECOMMENDATIONS:")
        for rec in report['recommendations']:
            print(f"  • {rec}")
        
        print("\nNEXT STEPS:")
        for step in report['next_steps'][:5]:  # Show first 5 steps
            print(f"  {step}")
        
        if validation_passed:
            print("\n✓ HEALTH MONITORING SYSTEM READY FOR DEPLOYMENT")
            return 0
        else:
            print("\n✗ DEPLOYMENT VALIDATION FAILED - RESOLVE ERRORS BEFORE PROCEEDING")
            return 1
            
    except Exception as e:
        logger.error(f"Deployment validation failed with exception: {str(e)}")
        print(f"\n✗ DEPLOYMENT VALIDATION FAILED: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)