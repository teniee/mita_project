#!/usr/bin/env python3
"""
MITA Finance - Configuration Cleanup Validation Script
Tests the new clean configuration system across all environments
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add app to Python path
sys.path.append(str(Path(__file__).parent))

# Import our clean configuration modules
try:
    from app.core.config_clean import get_settings, EnvironmentConfig
    from app.core.secret_manager_clean import get_secret_manager, validate_secrets
except ImportError as e:
    print(f"Error importing clean configuration modules: {e}")
    print("Make sure the clean configuration files are in place")
    sys.exit(1)


class ConfigurationValidator:
    """Validates the clean configuration system"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'environments': {},
            'overall_status': 'unknown',
            'critical_issues': [],
            'warnings': [],
            'recommendations': []
        }
    
    def validate_environment(self, env_name: str) -> Dict[str, Any]:
        """Validate configuration for a specific environment"""
        print(f"\n🔍 Validating {env_name.upper()} environment configuration...")
        
        env_results = {
            'environment': env_name,
            'env_file_exists': False,
            'settings_loaded': False,
            'secrets_valid': False,
            'configuration_issues': [],
            'security_issues': [],
            'warnings': [],
            'status': 'failed'
        }
        
        try:
            # Check if environment file exists
            env_file = f".env.{env_name}.clean" if env_name != 'development' else f".env.{env_name}"
            env_file_path = Path(env_file)
            env_results['env_file_exists'] = env_file_path.exists()
            
            if not env_results['env_file_exists']:
                env_results['configuration_issues'].append(f"Environment file {env_file} not found")
                print(f"  ❌ Environment file {env_file} not found")
            else:
                print(f"  ✅ Environment file {env_file} found")
            
            # Set environment for testing
            original_env = os.getenv('ENVIRONMENT')
            os.environ['ENVIRONMENT'] = env_name
            
            try:
                # Test settings loading
                settings = get_settings()
                env_results['settings_loaded'] = True
                print(f"  ✅ Settings loaded successfully")
                
                # Validate environment-specific settings
                if settings.ENVIRONMENT != env_name:
                    env_results['configuration_issues'].append(
                        f"Environment mismatch: expected {env_name}, got {settings.ENVIRONMENT}"
                    )
                
                # Check debug settings
                if env_name == 'production' and settings.DEBUG:
                    env_results['security_issues'].append("DEBUG is enabled in production")
                
                if env_name == 'development' and not settings.DEBUG:
                    env_results['warnings'].append("DEBUG is disabled in development")
                
                # Test secret manager
                secret_manager = get_secret_manager(env_name)
                secret_validation = secret_manager.validate_all_secrets()
                
                env_results['secrets_valid'] = secret_validation['valid']
                env_results['secret_details'] = {
                    'errors': secret_validation['errors'],
                    'warnings': secret_validation['warnings'],
                    'missing_secrets': secret_validation.get('missing_secrets', [])
                }
                
                if secret_validation['valid']:
                    print(f"  ✅ Secret validation passed")
                else:
                    print(f"  ❌ Secret validation failed: {len(secret_validation['errors'])} errors")
                    for error in secret_validation['errors'][:3]:  # Show first 3 errors
                        print(f"    • {error}")
                
                # Check for emergency configurations
                self._check_emergency_configs(env_name, settings, env_results)
                
                # Environment-specific validations
                if env_name == 'production':
                    self._validate_production_security(settings, env_results)
                elif env_name == 'staging':
                    self._validate_staging_config(settings, env_results)
                elif env_name == 'development':
                    self._validate_development_config(settings, env_results)
                
                # Determine overall status for this environment
                if (env_results['settings_loaded'] and 
                    env_results['secrets_valid'] and 
                    not env_results['security_issues'] and
                    not env_results['configuration_issues']):
                    env_results['status'] = 'passed'
                    print(f"  ✅ {env_name.upper()} configuration validation PASSED")
                elif not env_results['security_issues']:
                    env_results['status'] = 'warning'
                    print(f"  ⚠️  {env_name.upper()} configuration validation PASSED with warnings")
                else:
                    env_results['status'] = 'failed'
                    print(f"  ❌ {env_name.upper()} configuration validation FAILED")
                
            finally:
                # Restore original environment
                if original_env:
                    os.environ['ENVIRONMENT'] = original_env
                elif 'ENVIRONMENT' in os.environ:
                    del os.environ['ENVIRONMENT']
                    
        except Exception as e:
            env_results['configuration_issues'].append(f"Exception during validation: {str(e)}")
            print(f"  ❌ Error validating {env_name}: {e}")
        
        return env_results
    
    def _check_emergency_configs(self, env_name: str, settings: Any, results: Dict[str, Any]) -> None:
        """Check for emergency configuration remnants"""
        emergency_indicators = [
            'emergency',
            'EMERGENCY',
            'render',
            'mita-docker-ready-project-manus',
            'localhost:8001',
            'REPLACE_WITH',
            'staging_password_123',
            'test_key'
        ]
        
        # Check critical settings for emergency indicators
        critical_settings = ['DATABASE_URL', 'JWT_SECRET', 'SECRET_KEY', 'OPENAI_API_KEY']
        
        for setting_name in critical_settings:
            value = getattr(settings, setting_name, '')
            if value:
                for indicator in emergency_indicators:
                    if indicator in str(value):
                        if env_name == 'production':
                            results['security_issues'].append(
                                f"Production config contains emergency/placeholder value in {setting_name}: {indicator}"
                            )
                        else:
                            results['warnings'].append(
                                f"Config contains emergency/placeholder value in {setting_name}: {indicator}"
                            )
    
    def _validate_production_security(self, settings: Any, results: Dict[str, Any]) -> None:
        """Validate production-specific security requirements"""
        # Debug must be disabled
        if getattr(settings, 'DEBUG', False):
            results['security_issues'].append("DEBUG is enabled in production")
        
        # Log level should be INFO or higher
        if getattr(settings, 'LOG_LEVEL', 'INFO') == 'DEBUG':
            results['security_issues'].append("LOG_LEVEL is DEBUG in production")
        
        # Feature flags check
        if getattr(settings, 'FEATURE_FLAGS_DEBUG_LOGGING', False):
            results['security_issues'].append("Debug logging feature flag is enabled in production")
        
        # CORS should be restrictive
        allowed_origins = getattr(settings, 'ALLOWED_ORIGINS', [])
        if '*' in str(allowed_origins) or 'localhost' in str(allowed_origins):
            results['security_issues'].append("CORS allows development origins in production")
        
        # APNs should use production
        if getattr(settings, 'APNS_USE_SANDBOX', True):
            results['warnings'].append("APNs is using sandbox in production")
    
    def _validate_staging_config(self, settings: Any, results: Dict[str, Any]) -> None:
        """Validate staging-specific configuration"""
        # Should be production-like but allow some staging features
        if getattr(settings, 'DEBUG', False):
            results['warnings'].append("DEBUG is enabled in staging")
        
        # APNs should use sandbox
        if not getattr(settings, 'APNS_USE_SANDBOX', True):
            results['warnings'].append("APNs is not using sandbox in staging")
    
    def _validate_development_config(self, settings: Any, results: Dict[str, Any]) -> None:
        """Validate development-specific configuration"""
        # Debug should be enabled
        if not getattr(settings, 'DEBUG', True):
            results['warnings'].append("DEBUG is disabled in development")
        
        # Should have permissive CORS
        allowed_origins = getattr(settings, 'ALLOWED_ORIGINS', [])
        if not any('localhost' in origin for origin in allowed_origins):
            results['warnings'].append("CORS doesn't include localhost in development")
    
    def run_validation(self) -> Dict[str, Any]:
        """Run complete configuration validation"""
        print("🧹 MITA Finance - Configuration Cleanup Validation")
        print("=" * 60)
        
        environments = ['development', 'staging', 'production']
        
        for env in environments:
            self.results['environments'][env] = self.validate_environment(env)
        
        # Generate overall assessment
        self._generate_overall_assessment()
        
        return self.results
    
    def _generate_overall_assessment(self) -> None:
        """Generate overall assessment and recommendations"""
        passed_envs = []
        warning_envs = []
        failed_envs = []
        
        for env_name, env_result in self.results['environments'].items():
            if env_result['status'] == 'passed':
                passed_envs.append(env_name)
            elif env_result['status'] == 'warning':
                warning_envs.append(env_name)
            else:
                failed_envs.append(env_name)
        
        # Collect all critical issues
        for env_name, env_result in self.results['environments'].items():
            self.results['critical_issues'].extend([
                f"{env_name}: {issue}" for issue in env_result.get('security_issues', [])
            ])
            if env_name == 'production':
                self.results['critical_issues'].extend([
                    f"{env_name}: {issue}" for issue in env_result.get('configuration_issues', [])
                ])
        
        # Collect warnings
        for env_name, env_result in self.results['environments'].items():
            self.results['warnings'].extend([
                f"{env_name}: {warning}" for warning in env_result.get('warnings', [])
            ])
        
        # Generate recommendations
        self._generate_recommendations(passed_envs, warning_envs, failed_envs)
        
        # Determine overall status
        if failed_envs:
            self.results['overall_status'] = 'failed'
        elif warning_envs or self.results['critical_issues']:
            self.results['overall_status'] = 'warning'
        else:
            self.results['overall_status'] = 'passed'
    
    def _generate_recommendations(self, passed_envs: List[str], warning_envs: List[str], failed_envs: List[str]) -> None:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        if failed_envs:
            recommendations.append(f"❌ Fix configuration issues in: {', '.join(failed_envs)}")
        
        if warning_envs:
            recommendations.append(f"⚠️  Review warnings in: {', '.join(warning_envs)}")
        
        if 'production' in failed_envs:
            recommendations.append("🚨 CRITICAL: Production configuration must be fixed before deployment")
        
        # Check for missing clean files
        missing_clean_files = []
        for env in ['staging', 'production']:
            clean_file = f".env.{env}.clean"
            if not Path(clean_file).exists():
                missing_clean_files.append(clean_file)
        
        if missing_clean_files:
            recommendations.append(f"📁 Replace original files with clean versions: {', '.join(missing_clean_files)}")
        
        # Deployment recommendations
        if self.results['overall_status'] == 'passed':
            recommendations.append("✅ Configuration cleanup is complete and ready for deployment")
        elif self.results['overall_status'] == 'warning':
            recommendations.append("⚠️  Configuration cleanup mostly complete - review warnings before deployment")
        
        self.results['recommendations'] = recommendations
    
    def print_summary(self) -> None:
        """Print validation summary"""
        print(f"\n" + "=" * 60)
        print("📋 CONFIGURATION CLEANUP VALIDATION SUMMARY")
        print("=" * 60)
        
        # Overall status
        status_emoji = {
            'passed': '✅',
            'warning': '⚠️ ',
            'failed': '❌'
        }
        
        print(f"Overall Status: {status_emoji[self.results['overall_status']]} {self.results['overall_status'].upper()}")
        
        # Environment summary
        print(f"\nEnvironment Status:")
        for env_name, env_result in self.results['environments'].items():
            status = env_result['status']
            emoji = status_emoji[status]
            print(f"  {emoji} {env_name.capitalize()}: {status.upper()}")
        
        # Critical issues
        if self.results['critical_issues']:
            print(f"\n🚨 CRITICAL ISSUES ({len(self.results['critical_issues'])}):")
            for issue in self.results['critical_issues']:
                print(f"  • {issue}")
        
        # Warnings
        if self.results['warnings']:
            print(f"\n⚠️  WARNINGS ({len(self.results['warnings'])}):")
            for warning in self.results['warnings'][:5]:  # Show first 5
                print(f"  • {warning}")
            if len(self.results['warnings']) > 5:
                print(f"  ... and {len(self.results['warnings']) - 5} more")
        
        # Recommendations
        if self.results['recommendations']:
            print(f"\n💡 RECOMMENDATIONS:")
            for rec in self.results['recommendations']:
                print(f"  {rec}")
        
        print(f"\n" + "=" * 60)


def main():
    """Main validation function"""
    validator = ConfigurationValidator()
    results = validator.run_validation()
    validator.print_summary()
    
    # Save results to file
    results_file = f"configuration_cleanup_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    # Exit with appropriate code
    if results['overall_status'] == 'failed':
        print("\n❌ Configuration validation FAILED")
        sys.exit(1)
    elif results['overall_status'] == 'warning':
        print("\n⚠️  Configuration validation PASSED with warnings")
        sys.exit(0)
    else:
        print("\n✅ Configuration validation PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()