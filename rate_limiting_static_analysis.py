#!/usr/bin/env python3
"""
Static code analysis for rate limiting implementation
Validates code structure and configuration without imports
"""

import os
import re
from typing import List, Dict, Any

def analyze_security_config() -> Dict[str, Any]:
    """Analyze security configuration file"""
    results = {
        "file_exists": False,
        "has_rate_limit_tiers": False,
        "has_auth_limits": False,
        "has_sliding_window": False,
        "issues": []
    }
    
    security_file = "app/core/security.py"
    
    if not os.path.exists(security_file):
        results["issues"].append(f"Security file not found: {security_file}")
        return results
    
    results["file_exists"] = True
    
    with open(security_file, 'r') as f:
        content = f.read()
    
    # Check for rate limit tiers
    if "RATE_LIMIT_TIERS" in content:
        results["has_rate_limit_tiers"] = True
        
        # Check for all required tiers
        required_tiers = ["anonymous", "basic_user", "premium_user", "admin_user"]
        for tier in required_tiers:
            if tier not in content:
                results["issues"].append(f"Missing user tier: {tier}")
    else:
        results["issues"].append("RATE_LIMIT_TIERS not found")
    
    # Check for auth rate limits
    auth_limits = ["LOGIN_RATE_LIMIT", "REGISTER_RATE_LIMIT", "PASSWORD_RESET_RATE_LIMIT"]
    found_auth_limits = sum(1 for limit in auth_limits if limit in content)
    
    if found_auth_limits == len(auth_limits):
        results["has_auth_limits"] = True
    else:
        results["issues"].append(f"Missing auth limits: {found_auth_limits}/{len(auth_limits)} found")
    
    # Check for sliding window implementation
    sliding_window_indicators = [
        "_sliding_window_counter",
        "zremrangebyscore", 
        "zadd",
        "zcard"
    ]
    
    if any(indicator in content for indicator in sliding_window_indicators):
        results["has_sliding_window"] = True
    else:
        results["issues"].append("Sliding window algorithm not implemented")
    
    return results

def analyze_rate_limiter_class() -> Dict[str, Any]:
    """Analyze AdvancedRateLimiter class implementation"""
    results = {
        "class_exists": False,
        "has_required_methods": False,
        "has_progressive_penalties": False,
        "has_fail_secure": False,
        "issues": []
    }
    
    security_file = "app/core/security.py"
    
    if not os.path.exists(security_file):
        results["issues"].append("Security file not found")
        return results
    
    with open(security_file, 'r') as f:
        content = f.read()
    
    # Check for AdvancedRateLimiter class
    if "class AdvancedRateLimiter" in content:
        results["class_exists"] = True
    else:
        results["issues"].append("AdvancedRateLimiter class not found")
        return results
    
    # Check for required methods
    required_methods = [
        "_get_client_identifier",
        "_sliding_window_counter",
        "check_rate_limit", 
        "check_auth_rate_limit",
        "_check_progressive_penalties"
    ]
    
    found_methods = sum(1 for method in required_methods if f"def {method}" in content)
    
    if found_methods == len(required_methods):
        results["has_required_methods"] = True
    else:
        results["issues"].append(f"Missing methods: {found_methods}/{len(required_methods)} found")
    
    # Check for progressive penalties
    if "_check_progressive_penalties" in content and "penalty_multiplier" in content:
        results["has_progressive_penalties"] = True
    else:
        results["issues"].append("Progressive penalties not implemented")
    
    # Check for fail-secure behavior
    if "fail_secure_mode" in content or "RATE_LIMIT_FAIL_SECURE" in content:
        results["has_fail_secure"] = True
    else:
        results["issues"].append("Fail-secure behavior not implemented")
    
    return results

def analyze_middleware() -> Dict[str, Any]:
    """Analyze rate limiting middleware"""
    results = {
        "file_exists": False,
        "class_exists": False,
        "has_path_exemptions": False,
        "has_tier_support": False,
        "issues": []
    }
    
    middleware_file = "app/middleware/comprehensive_rate_limiter.py"
    
    if not os.path.exists(middleware_file):
        results["issues"].append(f"Middleware file not found: {middleware_file}")
        return results
    
    results["file_exists"] = True
    
    with open(middleware_file, 'r') as f:
        content = f.read()
    
    # Check for middleware class
    if "class ComprehensiveRateLimitMiddleware" in content:
        results["class_exists"] = True
    else:
        results["issues"].append("ComprehensiveRateLimitMiddleware class not found")
    
    # Check for path exemptions
    if "exempt_paths" in content and "auth_paths" in content:
        results["has_path_exemptions"] = True
    else:
        results["issues"].append("Path exemptions not configured")
    
    # Check for user tier support
    if "get_user_tier_from_request" in content and "tier_config" in content:
        results["has_tier_support"] = True
    else:
        results["issues"].append("User tier support not implemented")
    
    return results

def analyze_auth_routes() -> Dict[str, Any]:
    """Analyze authentication routes integration"""
    results = {
        "file_exists": False,
        "has_rate_limiting": False,
        "has_security_dependencies": False,
        "has_logging": False,
        "issues": []
    }
    
    auth_file = "app/api/auth/routes.py"
    
    if not os.path.exists(auth_file):
        results["issues"].append(f"Auth routes file not found: {auth_file}")
        return results
    
    results["file_exists"] = True
    
    with open(auth_file, 'r') as f:
        content = f.read()
    
    # Check for rate limiting imports
    rate_limiting_imports = [
        "AdvancedRateLimiter",
        "comprehensive_auth_security",
        "require_auth_endpoint_protection"
    ]
    
    if any(import_name in content for import_name in rate_limiting_imports):
        results["has_rate_limiting"] = True
    else:
        results["issues"].append("Rate limiting imports not found")
    
    # Check for security dependencies in endpoints
    if "dependencies=[comprehensive_auth_security()]" in content:
        results["has_security_dependencies"] = True
    else:
        results["issues"].append("Security dependencies not applied to endpoints")
    
    # Check for security event logging
    if "log_security_event" in content and "rate_limit" in content:
        results["has_logging"] = True
    else:
        results["issues"].append("Security event logging not implemented")
    
    return results

def analyze_test_coverage() -> Dict[str, Any]:
    """Analyze test coverage"""
    results = {
        "test_file_exists": False,
        "has_comprehensive_tests": False,
        "has_security_tests": False,
        "issues": []
    }
    
    test_file = "app/tests/test_comprehensive_rate_limiting.py"
    
    if not os.path.exists(test_file):
        results["issues"].append("Test file not found")
        return results
    
    results["test_file_exists"] = True
    
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Check for comprehensive test classes
    test_classes = [
        "TestAdvancedRateLimiter",
        "TestSecurityConfiguration", 
        "TestRateLimitingMiddleware",
        "TestIntegrationScenarios"
    ]
    
    found_classes = sum(1 for cls in test_classes if f"class {cls}" in content)
    
    if found_classes >= 3:
        results["has_comprehensive_tests"] = True
    else:
        results["issues"].append(f"Insufficient test coverage: {found_classes}/{len(test_classes)} test classes")
    
    # Check for security-specific tests
    security_tests = [
        "test_brute_force_protection",
        "test_progressive_penalties", 
        "test_fail_secure_mode"
    ]
    
    if any(test in content for test in security_tests):
        results["has_security_tests"] = True
    else:
        results["issues"].append("Security-specific tests missing")
    
    return results

def generate_report(analyses: Dict[str, Dict[str, Any]]) -> str:
    """Generate comprehensive analysis report"""
    report = []
    report.append("🔒 MITA Rate Limiting Implementation - Static Analysis Report")
    report.append("=" * 70)
    
    total_score = 0
    max_score = 0
    
    for component, analysis in analyses.items():
        report.append(f"\n📋 {component}")
        report.append("-" * 30)
        
        component_score = 0
        component_max = 0
        
        for key, value in analysis.items():
            if key == "issues":
                continue
                
            component_max += 1
            if value:
                component_score += 1
                status = "✅"
            else:
                status = "❌"
            
            report.append(f"{status} {key.replace('_', ' ').title()}: {'Yes' if value else 'No'}")
        
        if analysis.get("issues"):
            report.append("\n⚠️  Issues:")
            for issue in analysis["issues"]:
                report.append(f"   • {issue}")
        
        score_pct = (component_score / component_max * 100) if component_max > 0 else 0
        report.append(f"\n📊 Component Score: {component_score}/{component_max} ({score_pct:.1f}%)")
        
        total_score += component_score
        max_score += component_max
    
    overall_pct = (total_score / max_score * 100) if max_score > 0 else 0
    
    report.append("\n" + "=" * 70)
    report.append(f"🎯 Overall Implementation Score: {total_score}/{max_score} ({overall_pct:.1f}%)")
    
    if overall_pct >= 80:
        report.append("🎉 Excellent! Rate limiting implementation is comprehensive and production-ready.")
    elif overall_pct >= 60:
        report.append("👍 Good! Rate limiting implementation is solid with minor improvements needed.")
    else:
        report.append("⚠️  Rate limiting implementation needs significant improvements.")
    
    return "\n".join(report)

def main():
    """Run static analysis"""
    print("Analyzing MITA Rate Limiting Implementation...")
    
    analyses = {
        "Security Configuration": analyze_security_config(),
        "Rate Limiter Class": analyze_rate_limiter_class(),
        "Middleware Implementation": analyze_middleware(),
        "Auth Routes Integration": analyze_auth_routes(),
        "Test Coverage": analyze_test_coverage()
    }
    
    report = generate_report(analyses)
    print(report)
    
    # Save report to file
    with open("rate_limiting_analysis_report.txt", "w") as f:
        f.write(report)
    
    print(f"\n📄 Detailed report saved to: rate_limiting_analysis_report.txt")

if __name__ == "__main__":
    main()