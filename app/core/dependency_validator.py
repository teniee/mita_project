"""
Dependency Validation System for MITA Finance
Validates that all required dependencies are properly configured and available
"""

import logging
import sys
import importlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from packaging import version
import pkg_resources

logger = logging.getLogger(__name__)


@dataclass
class DependencyRequirement:
    """Dependency requirement specification"""
    name: str
    min_version: Optional[str] = None
    max_version: Optional[str] = None
    required: bool = True
    description: str = ""
    critical: bool = False  # Critical dependencies prevent startup if missing


class DependencyValidator:
    """Validates application dependencies and their versions"""
    
    def __init__(self):
        self.critical_dependencies = self._get_critical_dependencies()
        self.optional_dependencies = self._get_optional_dependencies()
        self.validation_results: Dict[str, Dict] = {}
    
    def _get_critical_dependencies(self) -> List[DependencyRequirement]:
        """Define critical dependencies that must be present for application to start"""
        return [
            DependencyRequirement(
                name="fastapi", 
                min_version="0.115.0", 
                critical=True,
                description="Core FastAPI framework"
            ),
            DependencyRequirement(
                name="uvicorn", 
                min_version="0.32.0", 
                critical=True,
                description="ASGI server"
            ),
            DependencyRequirement(
                name="pydantic", 
                min_version="2.9.0", 
                critical=True,
                description="Data validation and serialization"
            ),
            DependencyRequirement(
                name="sqlalchemy", 
                min_version="2.0.30", 
                critical=True,
                description="Database ORM"
            ),
            DependencyRequirement(
                name="asyncpg", 
                min_version="0.30.0", 
                critical=True,
                description="PostgreSQL async driver"
            ),
            DependencyRequirement(
                name="alembic", 
                min_version="1.14.0", 
                critical=True,
                description="Database migrations"
            ),
            DependencyRequirement(
                name="pyjwt", 
                min_version="2.9.0", 
                critical=True,
                description="JWT token handling"
            ),
            DependencyRequirement(
                name="cryptography", 
                min_version="43.0.0", 
                critical=True,
                description="Security and encryption"
            ),
            DependencyRequirement(
                name="redis", 
                min_version="5.2.0", 
                critical=True,
                description="Redis client for caching"
            ),
            DependencyRequirement(
                name="starlette", 
                min_version="0.41.0", 
                critical=True,
                description="ASGI framework foundation"
            )
        ]
    
    def _get_optional_dependencies(self) -> List[DependencyRequirement]:
        """Define optional dependencies that enhance functionality"""
        return [
            DependencyRequirement(
                name="sentry-sdk", 
                min_version="2.17.0", 
                required=False,
                description="Error monitoring and performance tracking"
            ),
            DependencyRequirement(
                name="prometheus-client", 
                min_version="0.21.0", 
                required=False,
                description="Metrics collection"
            ),
            DependencyRequirement(
                name="openai", 
                min_version="1.54.0", 
                required=False,
                description="AI/ML functionality"
            ),
            DependencyRequirement(
                name="firebase-admin", 
                min_version="6.5.0", 
                required=False,
                description="Firebase integration"
            ),
            DependencyRequirement(
                name="boto3", 
                min_version="1.35.0", 
                required=False,
                description="AWS services integration"
            )
        ]
    
    def validate_dependency(self, requirement: DependencyRequirement) -> Dict:
        """Validate a single dependency"""
        result = {
            "name": requirement.name,
            "required": requirement.required,
            "critical": requirement.critical,
            "description": requirement.description,
            "status": "unknown",
            "installed_version": None,
            "meets_requirements": False,
            "issues": []
        }
        
        try:
            # Try to import the module
            try:
                module = importlib.import_module(requirement.name.replace("-", "_"))
                result["status"] = "imported"
            except ImportError:
                # If direct import fails, try to get version from pkg_resources
                try:
                    installed = pkg_resources.get_distribution(requirement.name)
                    result["status"] = "available"
                    result["installed_version"] = installed.version
                except pkg_resources.DistributionNotFound:
                    result["status"] = "missing"
                    result["issues"].append(f"Package {requirement.name} is not installed")
                    return result
            
            # Get version information if we have the module
            if result["status"] == "imported":
                try:
                    # Try common version attributes
                    for attr in ["__version__", "version", "VERSION"]:
                        if hasattr(module, attr):
                            result["installed_version"] = getattr(module, attr)
                            break
                    
                    # If no version found in module, try pkg_resources
                    if not result["installed_version"]:
                        try:
                            installed = pkg_resources.get_distribution(requirement.name)
                            result["installed_version"] = installed.version
                        except pkg_resources.DistributionNotFound:
                            result["issues"].append(f"Could not determine version for {requirement.name}")
                            
                except Exception as e:
                    result["issues"].append(f"Error getting version for {requirement.name}: {str(e)}")
            
            # Validate version requirements
            if result["installed_version"]:
                try:
                    installed_ver = version.parse(result["installed_version"])
                    meets_min = True
                    meets_max = True
                    
                    if requirement.min_version:
                        min_ver = version.parse(requirement.min_version)
                        meets_min = installed_ver >= min_ver
                        if not meets_min:
                            result["issues"].append(
                                f"Version {result['installed_version']} is below minimum {requirement.min_version}"
                            )
                    
                    if requirement.max_version:
                        max_ver = version.parse(requirement.max_version)
                        meets_max = installed_ver <= max_ver
                        if not meets_max:
                            result["issues"].append(
                                f"Version {result['installed_version']} is above maximum {requirement.max_version}"
                            )
                    
                    result["meets_requirements"] = meets_min and meets_max
                    
                except Exception as e:
                    result["issues"].append(f"Error parsing version: {str(e)}")
            else:
                result["meets_requirements"] = False
                result["issues"].append("Could not determine installed version")
        
        except Exception as e:
            result["status"] = "error"
            result["issues"].append(f"Unexpected error: {str(e)}")
        
        return result
    
    def validate_all_dependencies(self) -> Dict[str, List[Dict]]:
        """Validate all dependencies"""
        logger.info("Starting dependency validation...")
        
        results = {
            "critical": [],
            "optional": [],
            "summary": {
                "total_critical": len(self.critical_dependencies),
                "critical_passing": 0,
                "total_optional": len(self.optional_dependencies),
                "optional_passing": 0,
                "overall_status": "unknown"
            }
        }
        
        # Validate critical dependencies
        for requirement in self.critical_dependencies:
            result = self.validate_dependency(requirement)
            results["critical"].append(result)
            
            if result["meets_requirements"] and result["status"] in ["imported", "available"]:
                results["summary"]["critical_passing"] += 1
        
        # Validate optional dependencies
        for requirement in self.optional_dependencies:
            result = self.validate_dependency(requirement)
            results["optional"].append(result)
            
            if result["meets_requirements"] and result["status"] in ["imported", "available"]:
                results["summary"]["optional_passing"] += 1
        
        # Determine overall status
        critical_failing = results["summary"]["total_critical"] - results["summary"]["critical_passing"]
        
        if critical_failing == 0:
            if results["summary"]["optional_passing"] == results["summary"]["total_optional"]:
                results["summary"]["overall_status"] = "excellent"
            elif results["summary"]["optional_passing"] >= results["summary"]["total_optional"] * 0.8:
                results["summary"]["overall_status"] = "good"
            else:
                results["summary"]["overall_status"] = "acceptable"
        else:
            results["summary"]["overall_status"] = "critical_failures"
        
        self.validation_results = results
        logger.info(f"Dependency validation complete. Status: {results['summary']['overall_status']}")
        
        return results
    
    def get_failed_critical_dependencies(self) -> List[Dict]:
        """Get list of failed critical dependencies"""
        if not self.validation_results:
            self.validate_all_dependencies()
        
        failed = []
        for dep in self.validation_results.get("critical", []):
            if not dep["meets_requirements"] or dep["status"] not in ["imported", "available"]:
                failed.append(dep)
        
        return failed
    
    def check_security_vulnerabilities(self) -> Dict[str, List[str]]:
        """Check for known security vulnerabilities in dependencies"""
        vulnerabilities = {
            "high_risk": [],
            "medium_risk": [],
            "low_risk": [],
            "recommendations": []
        }
        
        # Known vulnerable versions (this should be integrated with security databases)
        known_vulnerabilities = {
            "cryptography": {
                "versions": ["41.0.7", "42.0.0", "42.0.1", "42.0.2"],
                "risk": "high",
                "description": "Known cryptographic vulnerabilities"
            },
            "pillow": {
                "versions": ["10.0.1", "10.1.0", "10.2.0"],
                "risk": "medium", 
                "description": "Image processing vulnerabilities"
            },
            "starlette": {
                "versions": ["0.27.0", "0.28.0", "0.37.0"],
                "risk": "high",
                "description": "Web framework security issues"
            },
            "fastapi": {
                "versions": ["0.104.1", "0.105.0", "0.108.0"],
                "risk": "high",
                "description": "API framework vulnerabilities"
            }
        }
        
        if not self.validation_results:
            self.validate_all_dependencies()
        
        # Check all dependencies against known vulnerabilities
        all_deps = self.validation_results.get("critical", []) + self.validation_results.get("optional", [])
        
        for dep in all_deps:
            if dep["installed_version"] and dep["name"] in known_vulnerabilities:
                vuln_info = known_vulnerabilities[dep["name"]]
                if dep["installed_version"] in vuln_info["versions"]:
                    risk_level = f"{vuln_info['risk']}_risk"
                    vulnerabilities[risk_level].append(
                        f"{dep['name']} {dep['installed_version']}: {vuln_info['description']}"
                    )
        
        # Generate recommendations
        if vulnerabilities["high_risk"]:
            vulnerabilities["recommendations"].append("URGENT: Update high-risk dependencies immediately")
        if vulnerabilities["medium_risk"]:
            vulnerabilities["recommendations"].append("Schedule updates for medium-risk dependencies")
        if not any(vulnerabilities[key] for key in ["high_risk", "medium_risk", "low_risk"]):
            vulnerabilities["recommendations"].append("No known vulnerabilities detected in current versions")
        
        return vulnerabilities
    
    def generate_report(self) -> str:
        """Generate a comprehensive dependency validation report"""
        if not self.validation_results:
            self.validate_all_dependencies()
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("MITA Finance - Dependency Validation Report")
        report_lines.append("=" * 80)
        
        # Summary
        summary = self.validation_results["summary"]
        report_lines.append(f"\nOVERALL STATUS: {summary['overall_status'].upper()}")
        report_lines.append(f"Critical Dependencies: {summary['critical_passing']}/{summary['total_critical']} passing")
        report_lines.append(f"Optional Dependencies: {summary['optional_passing']}/{summary['total_optional']} passing")
        
        # Critical Dependencies
        report_lines.append("\n" + "-" * 40)
        report_lines.append("CRITICAL DEPENDENCIES")
        report_lines.append("-" * 40)
        
        for dep in self.validation_results["critical"]:
            status_symbol = "✓" if dep["meets_requirements"] else "✗"
            version_info = f" ({dep['installed_version']})" if dep['installed_version'] else " (version unknown)"
            report_lines.append(f"{status_symbol} {dep['name']}{version_info}")
            
            if dep["issues"]:
                for issue in dep["issues"]:
                    report_lines.append(f"    - {issue}")
        
        # Optional Dependencies
        report_lines.append("\n" + "-" * 40)
        report_lines.append("OPTIONAL DEPENDENCIES")
        report_lines.append("-" * 40)
        
        for dep in self.validation_results["optional"]:
            status_symbol = "✓" if dep["meets_requirements"] else "⚠"
            version_info = f" ({dep['installed_version']})" if dep['installed_version'] else " (not installed)"
            report_lines.append(f"{status_symbol} {dep['name']}{version_info}")
        
        # Security vulnerabilities
        vulnerabilities = self.check_security_vulnerabilities()
        if any(vulnerabilities[key] for key in ["high_risk", "medium_risk", "low_risk"]):
            report_lines.append("\n" + "-" * 40)
            report_lines.append("SECURITY VULNERABILITIES")
            report_lines.append("-" * 40)
            
            for risk_level in ["high_risk", "medium_risk", "low_risk"]:
                if vulnerabilities[risk_level]:
                    report_lines.append(f"\n{risk_level.replace('_', ' ').title()}:")
                    for vuln in vulnerabilities[risk_level]:
                        report_lines.append(f"  - {vuln}")
        
        # Recommendations
        if vulnerabilities["recommendations"]:
            report_lines.append("\n" + "-" * 40)
            report_lines.append("RECOMMENDATIONS")
            report_lines.append("-" * 40)
            for rec in vulnerabilities["recommendations"]:
                report_lines.append(f"• {rec}")
        
        report_lines.append("\n" + "=" * 80)
        
        return "\n".join(report_lines)
    
    def validate_startup_requirements(self) -> Tuple[bool, List[str]]:
        """Validate that all requirements for application startup are met"""
        failed_critical = self.get_failed_critical_dependencies()
        
        if not failed_critical:
            return True, []
        
        error_messages = []
        for dep in failed_critical:
            error_msg = f"Critical dependency '{dep['name']}' failed validation"
            if dep["issues"]:
                error_msg += f": {'; '.join(dep['issues'])}"
            error_messages.append(error_msg)
        
        return False, error_messages


# Global validator instance
_validator: Optional[DependencyValidator] = None

def get_dependency_validator() -> DependencyValidator:
    """Get the global dependency validator instance"""
    global _validator
    if _validator is None:
        _validator = DependencyValidator()
    return _validator


def validate_dependencies_on_startup():
    """Validate dependencies during application startup"""
    validator = get_dependency_validator()
    
    try:
        startup_ok, errors = validator.validate_startup_requirements()
        
        if not startup_ok:
            logger.error("Critical dependency validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            
            print("\n" + "="*60)
            print("CRITICAL DEPENDENCY VALIDATION FAILURE")
            print("="*60)
            for error in errors:
                print(f"ERROR: {error}")
            print("\nPlease install missing dependencies and restart the application.")
            print("="*60)
            
            sys.exit(1)
        
        else:
            logger.info("All critical dependencies validated successfully")
            
            # Log full report at debug level
            report = validator.generate_report()
            logger.debug(f"Dependency validation report:\n{report}")
            
            # Check for security vulnerabilities
            vulnerabilities = validator.check_security_vulnerabilities()
            if vulnerabilities["high_risk"]:
                logger.warning("High-risk security vulnerabilities detected in dependencies!")
                for vuln in vulnerabilities["high_risk"]:
                    logger.warning(f"  - {vuln}")
                logger.warning("Consider updating dependencies immediately.")
    
    except Exception as e:
        logger.error(f"Dependency validation failed with error: {e}")
        # Don't block startup on validation errors, but log them
        logger.warning("Continuing startup despite validation errors...")


if __name__ == "__main__":
    # Command-line interface for dependency validation
    validator = DependencyValidator()
    report = validator.generate_report()
    print(report)
    
    # Exit with non-zero code if critical dependencies are missing
    startup_ok, _ = validator.validate_startup_requirements()
    sys.exit(0 if startup_ok else 1)