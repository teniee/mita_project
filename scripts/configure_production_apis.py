#!/usr/bin/env python3
"""
Production API Key Configuration Script for MITA Finance
Validates and configures all external service integrations for production deployment
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import argparse
from pathlib import Path

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.api_key_manager import APIKeyManager, validate_production_keys
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProductionAPIConfigurator:
    """Configure and validate all production API integrations"""
    
    def __init__(self):
        self.api_key_manager = APIKeyManager()
        self.validation_results = {}
        self.missing_keys = []
        self.invalid_keys = []
        
    async def run_full_configuration(self) -> Dict[str, Any]:
        """Run complete API configuration and validation"""
        logger.info("Starting production API configuration...")
        
        # Step 1: Check environment setup
        self._check_environment_setup()
        
        # Step 2: Validate all API keys
        await self._validate_all_apis()
        
        # Step 3: Test external service connections
        await self._test_service_connections()
        
        # Step 4: Generate configuration report
        report = self._generate_configuration_report()
        
        # Step 5: Save configuration state
        self._save_configuration_state(report)
        
        return report
    
    def _check_environment_setup(self):
        """Check that environment is properly configured"""
        logger.info("Checking environment setup...")
        
        required_env_vars = [
            'ENVIRONMENT',
            'SECRET_KEY',
            'JWT_SECRET',
            'DATABASE_URL'
        ]
        
        missing_env_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_env_vars.append(var)
        
        if missing_env_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_env_vars)}")
            raise ValueError(f"Missing environment variables: {missing_env_vars}")
        
        # Check environment type
        env = os.getenv('ENVIRONMENT', 'development')
        if env != 'production':
            logger.warning(f"Environment is set to '{env}', expected 'production'")
        
        logger.info("Environment setup check completed")
    
    async def _validate_all_apis(self):
        """Validate all API keys"""
        logger.info("Validating all API keys...")
        
        self.validation_results = await validate_production_keys()
        
        # Categorize results
        for key_name, result in self.validation_results.items():
            if not result['valid']:
                if result['error'] == 'Key not found':
                    self.missing_keys.append(key_name)
                else:
                    self.invalid_keys.append(key_name)
        
        logger.info(f"API key validation completed. Valid: {len(self.validation_results) - len(self.invalid_keys) - len(self.missing_keys)}, Invalid: {len(self.invalid_keys)}, Missing: {len(self.missing_keys)}")
    
    async def _test_service_connections(self):
        """Test connections to external services"""
        logger.info("Testing external service connections...")
        
        connection_tests = {}
        
        # Test OpenAI connection
        if os.getenv('OPENAI_API_KEY'):
            connection_tests['openai'] = await self._test_openai_connection()
        
        # Test Sentry connection
        if os.getenv('SENTRY_DSN'):
            connection_tests['sentry'] = await self._test_sentry_connection()
        
        # Test Redis/Upstash connection
        if os.getenv('UPSTASH_REDIS_URL'):
            connection_tests['redis'] = await self._test_redis_connection()
        
        # Test SendGrid connection
        if os.getenv('SENDGRID_API_KEY'):
            connection_tests['sendgrid'] = await self._test_sendgrid_connection()
        
        # Test Firebase connection
        if os.getenv('FIREBASE_JSON'):
            connection_tests['firebase'] = await self._test_firebase_connection()
        
        # Test AWS S3 connection
        if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY'):
            connection_tests['aws_s3'] = await self._test_aws_s3_connection()
        
        self.connection_tests = connection_tests
        
        logger.info("Service connection tests completed")
    
    async def _test_openai_connection(self) -> Dict[str, Any]:
        """Test OpenAI API connection"""
        try:
            import openai
            from app.services.resilient_gpt_service import get_gpt_service
            
            api_key = os.getenv('OPENAI_API_KEY')
            gpt_service = get_gpt_service(api_key)
            
            # Test connection
            connected = await gpt_service.test_connection()
            
            return {
                'status': 'connected' if connected else 'failed',
                'service': 'OpenAI GPT',
                'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                'error': None if connected else 'Connection test failed'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'service': 'OpenAI GPT',
                'error': str(e)
            }
    
    async def _test_sentry_connection(self) -> Dict[str, Any]:
        """Test Sentry connection"""
        try:
            import sentry_sdk
            
            dsn = os.getenv('SENTRY_DSN')
            
            # Initialize Sentry
            sentry_sdk.init(
                dsn=dsn,
                environment="production_test",
                traces_sample_rate=0.0
            )
            
            # Capture test event
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("test", "api_configuration")
                event_id = sentry_sdk.capture_message("API configuration test", level="info")
                
                if event_id:
                    return {
                        'status': 'connected',
                        'service': 'Sentry',
                        'event_id': event_id,
                        'error': None
                    }
                else:
                    return {
                        'status': 'failed',
                        'service': 'Sentry',
                        'error': 'Failed to capture test event'
                    }
        
        except Exception as e:
            return {
                'status': 'error',
                'service': 'Sentry',
                'error': str(e)
            }
    
    async def _test_redis_connection(self) -> Dict[str, Any]:
        """Test Redis/Upstash connection"""
        try:
            import redis.asyncio as redis
            
            redis_url = os.getenv('UPSTASH_REDIS_URL')
            r = redis.from_url(redis_url, decode_responses=True)
            
            # Test connection
            await r.ping()
            
            # Test set/get
            test_key = f"test_{datetime.now().timestamp()}"
            await r.set(test_key, "test_value", ex=60)  # Expires in 60 seconds
            value = await r.get(test_key)
            
            await r.aclose()
            
            if value == "test_value":
                return {
                    'status': 'connected',
                    'service': 'Upstash Redis',
                    'error': None
                }
            else:
                return {
                    'status': 'failed',
                    'service': 'Upstash Redis',
                    'error': 'Set/get test failed'
                }
        
        except Exception as e:
            return {
                'status': 'error',
                'service': 'Upstash Redis',
                'error': str(e)
            }
    
    async def _test_sendgrid_connection(self) -> Dict[str, Any]:
        """Test SendGrid API connection"""
        try:
            import httpx
            
            api_key = os.getenv('SENDGRID_API_KEY')
            
            async with httpx.AsyncClient() as client:
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }
                
                # Get user profile
                response = await client.get(
                    'https://api.sendgrid.com/v3/user/profile',
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    profile = response.json()
                    return {
                        'status': 'connected',
                        'service': 'SendGrid',
                        'username': profile.get('username', 'Unknown'),
                        'error': None
                    }
                else:
                    return {
                        'status': 'failed',
                        'service': 'SendGrid',
                        'error': f'HTTP {response.status_code}: {response.text}'
                    }
        
        except Exception as e:
            return {
                'status': 'error',
                'service': 'SendGrid',
                'error': str(e)
            }
    
    async def _test_firebase_connection(self) -> Dict[str, Any]:
        """Test Firebase connection"""
        try:
            import firebase_admin
            from firebase_admin import credentials
            
            # Parse Firebase credentials
            firebase_json = os.getenv('FIREBASE_JSON')
            if not firebase_json:
                return {
                    'status': 'failed',
                    'service': 'Firebase',
                    'error': 'FIREBASE_JSON environment variable not set'
                }
            
            creds_dict = json.loads(firebase_json)
            cred = credentials.Certificate(creds_dict)
            
            # Initialize Firebase (if not already initialized)
            if not firebase_admin._apps:
                app = firebase_admin.initialize_app(cred)
            else:
                app = firebase_admin.get_app()
            
            return {
                'status': 'connected',
                'service': 'Firebase',
                'project_id': creds_dict.get('project_id', 'Unknown'),
                'error': None
            }
        
        except Exception as e:
            return {
                'status': 'error',
                'service': 'Firebase',
                'error': str(e)
            }
    
    async def _test_aws_s3_connection(self) -> Dict[str, Any]:
        """Test AWS S3 connection"""
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            access_key = os.getenv('AWS_ACCESS_KEY_ID')
            secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            
            # Test by listing buckets
            response = s3_client.list_buckets()
            buckets = [bucket['Name'] for bucket in response['Buckets']]
            
            return {
                'status': 'connected',
                'service': 'AWS S3',
                'region': region,
                'bucket_count': len(buckets),
                'error': None
            }
        
        except ClientError as e:
            return {
                'status': 'error',
                'service': 'AWS S3',
                'error': f'AWS Error: {e.response["Error"]["Code"]} - {e.response["Error"]["Message"]}'
            }
        except Exception as e:
            return {
                'status': 'error',
                'service': 'AWS S3',
                'error': str(e)
            }
    
    def _generate_configuration_report(self) -> Dict[str, Any]:
        """Generate comprehensive configuration report"""
        
        # Calculate summary stats
        total_keys = len(self.validation_results)
        valid_keys = len([r for r in self.validation_results.values() if r['valid']])
        
        # Get connection test results
        connection_summary = {}
        if hasattr(self, 'connection_tests'):
            for service, result in self.connection_tests.items():
                connection_summary[service] = result['status']
        
        # Determine overall health
        health_score = 0
        if total_keys > 0:
            health_score = (valid_keys / total_keys) * 100
        
        overall_status = "healthy"
        if health_score < 50:
            overall_status = "critical"
        elif health_score < 80:
            overall_status = "warning"
        elif len(self.missing_keys) > 0:
            overall_status = "incomplete"
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'environment': os.getenv('ENVIRONMENT', 'unknown'),
            'overall_status': overall_status,
            'health_score': health_score,
            'summary': {
                'total_api_keys': total_keys,
                'valid_keys': valid_keys,
                'invalid_keys': len(self.invalid_keys),
                'missing_keys': len(self.missing_keys),
                'services_tested': len(getattr(self, 'connection_tests', {})),
                'services_connected': len([r for r in connection_summary.values() if r == 'connected'])
            },
            'api_key_validation': self.validation_results,
            'missing_keys': self.missing_keys,
            'invalid_keys': self.invalid_keys,
            'service_connections': getattr(self, 'connection_tests', {}),
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on configuration status"""
        recommendations = []
        
        if self.missing_keys:
            recommendations.append(f"Configure missing API keys: {', '.join(self.missing_keys)}")
        
        if self.invalid_keys:
            recommendations.append(f"Fix invalid API keys: {', '.join(self.invalid_keys)}")
        
        # Check for critical services
        critical_services = ['OPENAI_API_KEY', 'SENTRY_DSN', 'UPSTASH_REDIS_URL']
        missing_critical = [key for key in critical_services if key in self.missing_keys or key in self.invalid_keys]
        
        if missing_critical:
            recommendations.append(f"CRITICAL: Fix these essential services immediately: {', '.join(missing_critical)}")
        
        # Service-specific recommendations
        if hasattr(self, 'connection_tests'):
            for service, result in self.connection_tests.items():
                if result['status'] != 'connected':
                    recommendations.append(f"Fix {service} connection: {result.get('error', 'Unknown error')}")
        
        if not recommendations:
            recommendations.append("All API configurations are valid and ready for production!")
        
        return recommendations
    
    def _save_configuration_state(self, report: Dict[str, Any]):
        """Save configuration report to file"""
        try:
            reports_dir = Path("./reports/api_configuration")
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"api_config_report_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            # Also save as latest
            latest_file = reports_dir / "latest_api_config.json"
            with open(latest_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Configuration report saved to: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration report: {str(e)}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Configure MITA Finance Production APIs")
    parser.add_argument('--validate-only', action='store_true', help='Only validate APIs, don\'t test connections')
    parser.add_argument('--output-format', choices=['json', 'yaml', 'text'], default='text', help='Output format')
    parser.add_argument('--save-report', action='store_true', help='Save detailed report to file')
    
    args = parser.parse_args()
    
    try:
        configurator = ProductionAPIConfigurator()
        
        if args.validate_only:
            logger.info("Running API validation only...")
            results = await configurator._validate_all_apis()
            report = configurator._generate_configuration_report()
        else:
            logger.info("Running full API configuration...")
            report = await configurator.run_full_configuration()
        
        # Output results
        if args.output_format == 'json':
            print(json.dumps(report, indent=2))
        elif args.output_format == 'yaml':
            import yaml
            print(yaml.dump(report, default_flow_style=False))
        else:
            # Text output
            print("\n" + "="*60)
            print("MITA FINANCE API CONFIGURATION REPORT")
            print("="*60)
            print(f"Timestamp: {report['timestamp']}")
            print(f"Environment: {report['environment']}")
            print(f"Overall Status: {report['overall_status'].upper()}")
            print(f"Health Score: {report['health_score']:.1f}%")
            print()
            
            print("SUMMARY:")
            for key, value in report['summary'].items():
                print(f"  {key.replace('_', ' ').title()}: {value}")
            print()
            
            if report['missing_keys']:
                print("MISSING API KEYS:")
                for key in report['missing_keys']:
                    print(f"  ❌ {key}")
                print()
            
            if report['invalid_keys']:
                print("INVALID API KEYS:")
                for key in report['invalid_keys']:
                    print(f"  ⚠️  {key}")
                print()
            
            if 'service_connections' in report:
                print("SERVICE CONNECTIONS:")
                for service, result in report['service_connections'].items():
                    status_icon = "✅" if result['status'] == 'connected' else "❌"
                    print(f"  {status_icon} {service}: {result['status']}")
                print()
            
            print("RECOMMENDATIONS:")
            for rec in report['recommendations']:
                print(f"  • {rec}")
            print()
        
        if args.save_report:
            configurator._save_configuration_state(report)
        
        # Exit with appropriate code
        if report['overall_status'] in ['critical', 'warning']:
            sys.exit(1)
        else:
            sys.exit(0)
    
    except Exception as e:
        logger.error(f"Configuration failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())