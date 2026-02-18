#!/usr/bin/env python3
"""
Rollback Validation for MITA Production
Comprehensive health check validation after rollback operations

Copyright © 2025 YAKOVLEV LTD - All Rights Reserved
"""

import asyncio
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import httpx
import structlog

logger = structlog.get_logger()


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    endpoint: str
    status: HealthStatus
    response_time_ms: float
    details: Dict
    timestamp: datetime


class RollbackValidator:
    """
    Validates deployment health after rollback

    Implements 4-phase health verification:
    1. Quick verification (<5s) - Basic connectivity
    2. Core functionality (5-10s) - Database, Redis, system
    3. Performance validation (5-10s) - Timeout risk detection
    4. External dependencies (5-10s) - OpenAI, SendGrid, etc.

    Total target: 25-35 seconds
    """

    def __init__(self, base_url: str, timeout: int = 10):
        """
        Initialize rollback validator

        Args:
            base_url: Application base URL (e.g., https://api.mita.finance)
            timeout: Default HTTP timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.http_client = httpx.AsyncClient(timeout=timeout)
        self.results: List[HealthCheckResult] = []

    async def validate_rollback(self) -> bool:
        """
        Execute complete rollback validation

        Returns:
            True if all critical health checks pass, False otherwise
        """
        logger.info("Starting rollback validation", base_url=self.base_url)

        try:
            # Phase 1: Quick Verification (0-5 seconds)
            logger.info("Phase 1: Quick verification")
            if not await self._phase1_quick_verification():
                logger.error("Phase 1 failed - quick verification")
                return False

            # Phase 2: Core Functionality (5-15 seconds)
            logger.info("Phase 2: Core functionality")
            if not await self._phase2_core_functionality():
                logger.error("Phase 2 failed - core functionality")
                return False

            # Phase 3: Performance Validation (15-25 seconds)
            logger.info("Phase 3: Performance validation")
            if not await self._phase3_performance_validation():
                logger.error("Phase 3 failed - performance validation")
                return False

            # Phase 4: External Dependencies (25-35 seconds)
            logger.info("Phase 4: External dependencies")
            external_ok = await self._phase4_external_dependencies()
            if not external_ok:
                logger.warning("Phase 4 degraded - external dependencies (non-critical)")
                # External dependencies can be degraded, don't fail rollback

            # All critical checks passed
            logger.info("Rollback validation successful",
                       total_checks=len(self.results))
            await self._print_summary()
            return True

        except Exception as e:
            logger.error("Rollback validation exception", error=str(e))
            return False
        finally:
            await self.http_client.aclose()

    async def _phase1_quick_verification(self) -> bool:
        """
        Phase 1: Quick Verification (<5 seconds)

        Checks:
        - Basic health endpoint (/)
        - Simple health check (/health)
        """
        # Check 1: Root health endpoint
        result = await self._check_endpoint(
            endpoint="/",
            expected_status=200,
            timeout=2.0
        )
        self.results.append(result)

        if result.status not in [HealthStatus.HEALTHY]:
            logger.error("Root health check failed")
            return False

        # Check 2: Simple health endpoint
        result = await self._check_endpoint(
            endpoint="/health",
            expected_status=200,
            timeout=3.0
        )
        self.results.append(result)

        if result.status not in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
            logger.error("Simple health check failed")
            return False

        logger.info("Phase 1 passed", duration_ms=sum(r.response_time_ms for r in self.results[-2:]))
        return True

    async def _phase2_core_functionality(self) -> bool:
        """
        Phase 2: Core Functionality (3-5 seconds)

        Checks:
        - Production health check (/health/production)
        - Critical services (/health/critical-services)
        """
        # Check 1: Production health check
        result = await self._check_endpoint(
            endpoint="/health/production",
            expected_status=200,
            timeout=5.0
        )
        self.results.append(result)

        if result.status == HealthStatus.UNHEALTHY:
            logger.error("Production health check failed", details=result.details)
            return False

        # Validate critical services within response
        if result.details.get("overall_status") == "unhealthy":
            logger.error("Production health reports unhealthy status")
            return False

        # Check 2: Critical services (if endpoint exists)
        try:
            result = await self._check_endpoint(
                endpoint="/health/critical-services",
                expected_status=200,
                timeout=3.0
            )
            self.results.append(result)

            if result.status == HealthStatus.UNHEALTHY:
                logger.warning("Critical services check failed (non-fatal)")
        except Exception as e:
            logger.debug("Critical services endpoint not available", error=str(e))

        logger.info("Phase 2 passed")
        return True

    async def _phase3_performance_validation(self) -> bool:
        """
        Phase 3: Performance Validation (5-8 seconds)

        CRITICAL: Detects timeout risks that cause 8-15+ second issues

        Checks:
        - Performance health (/health/performance)
        - Comprehensive middleware health (/health/comprehensive)
        """
        # Check 1: Performance health (timeout risk detection)
        result = await self._check_endpoint(
            endpoint="/health/performance",
            expected_status=200,
            timeout=8.0
        )
        self.results.append(result)

        if result.status == HealthStatus.TIMEOUT:
            logger.error("Performance check timed out - CRITICAL")
            return False

        # Validate performance summary
        perf_summary = result.details.get("performance_summary", {})
        components_over_5s = perf_summary.get("components_over_5s", 0)

        if components_over_5s > 0:
            logger.error("CRITICAL: Components exceed 5-second response time",
                        count=components_over_5s,
                        timeout_risks=perf_summary.get("timeout_risks", []))
            return False

        # Check for components approaching timeout (>2s)
        components_over_2s = perf_summary.get("components_over_2s", 0)
        if components_over_2s > 0:
            logger.warning("WARNING: Components exceed 2-second response time",
                          count=components_over_2s)
            # Continue - warning only, not critical yet

        # Check 2: Comprehensive middleware health
        result = await self._check_endpoint(
            endpoint="/health/comprehensive",
            expected_status=200,
            timeout=8.0
        )
        self.results.append(result)

        if result.status == HealthStatus.TIMEOUT:
            logger.error("Comprehensive health check timed out")
            return False

        if result.status == HealthStatus.UNHEALTHY:
            logger.error("Comprehensive health check failed")
            return False

        logger.info("Phase 3 passed - no timeout risks detected")
        return True

    async def _phase4_external_dependencies(self) -> bool:
        """
        Phase 4: External Dependencies (2-4 seconds)

        Checks:
        - External services (/health/external-services)
        - Circuit breakers (/health/circuit-breakers)

        Note: External services can be degraded without failing rollback
        """
        # Check 1: External services
        result = await self._check_endpoint(
            endpoint="/health/external-services",
            expected_status=200,
            timeout=5.0
        )
        self.results.append(result)

        external_healthy = True

        if result.status == HealthStatus.UNHEALTHY:
            logger.warning("External services unhealthy")
            external_healthy = False
        elif result.status == HealthStatus.DEGRADED:
            logger.info("External services degraded (acceptable)")

        # Check service health percentage
        summary = result.details.get("summary", {})
        healthy_services = summary.get("healthy_services", 0)
        enabled_services = summary.get("enabled_services", 1)

        if enabled_services > 0:
            health_percentage = (healthy_services / enabled_services) * 100

            if health_percentage < 50:
                logger.warning("Less than 50% of external services healthy",
                             percentage=health_percentage)
                external_healthy = False

        # Check 2: Circuit breakers
        try:
            result = await self._check_endpoint(
                endpoint="/health/circuit-breakers",
                expected_status=200,
                timeout=3.0
            )
            self.results.append(result)

            # Check for open circuit breakers
            circuit_breakers = result.details.get("circuit_breakers", {})
            open_breakers = [
                name for name, data in circuit_breakers.items()
                if data.get("state") == "open"
            ]

            if open_breakers:
                logger.warning("Open circuit breakers detected", breakers=open_breakers)
                # Don't fail - circuit breakers can be open temporarily

        except Exception as e:
            logger.debug("Circuit breakers endpoint not available", error=str(e))

        logger.info("Phase 4 completed", external_healthy=external_healthy)
        return external_healthy

    async def _check_endpoint(
        self,
        endpoint: str,
        expected_status: int = 200,
        timeout: float = 5.0
    ) -> HealthCheckResult:
        """
        Check a single health endpoint

        Args:
            endpoint: API endpoint path
            expected_status: Expected HTTP status code
            timeout: Request timeout in seconds

        Returns:
            HealthCheckResult with status and details
        """
        url = f"{self.base_url}{endpoint}"
        start_time = datetime.now()

        logger.debug("Checking endpoint", url=url, timeout=timeout)

        try:
            response = await self.http_client.get(url, timeout=timeout)
            duration = (datetime.now() - start_time).total_seconds() * 1000

            # Parse JSON response
            try:
                details = response.json()
            except Exception:
                details = {"body": response.text[:500]}

            # Determine health status
            if response.status_code == expected_status:
                # Check if response indicates degraded/unhealthy
                response_status = details.get("status", "healthy")

                if response_status == "unhealthy":
                    status = HealthStatus.UNHEALTHY
                elif response_status == "degraded":
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.HEALTHY
            else:
                status = HealthStatus.UNHEALTHY
                details["http_status"] = response.status_code

            result = HealthCheckResult(
                endpoint=endpoint,
                status=status,
                response_time_ms=duration,
                details=details,
                timestamp=datetime.now()
            )

            logger.debug("Endpoint check complete",
                        endpoint=endpoint,
                        status=status.value,
                        response_time_ms=duration)

            return result

        except httpx.TimeoutException:
            duration = (datetime.now() - start_time).total_seconds() * 1000

            logger.error("Endpoint timeout", url=url, timeout=timeout)

            return HealthCheckResult(
                endpoint=endpoint,
                status=HealthStatus.TIMEOUT,
                response_time_ms=duration,
                details={"error": "timeout", "timeout_seconds": timeout},
                timestamp=datetime.now()
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000

            logger.error("Endpoint check error", url=url, error=str(e))

            return HealthCheckResult(
                endpoint=endpoint,
                status=HealthStatus.ERROR,
                response_time_ms=duration,
                details={"error": str(e)},
                timestamp=datetime.now()
            )

    async def _print_summary(self):
        """Print validation summary"""
        total_duration = sum(r.response_time_ms for r in self.results)

        print("\n" + "=" * 80)
        print("ROLLBACK VALIDATION SUMMARY")
        print("=" * 80)

        print(f"\nTotal Checks: {len(self.results)}")
        print(f"Total Duration: {total_duration:.0f}ms ({total_duration/1000:.1f}s)")

        # Group by phase
        phase1 = self.results[0:2]
        phase2 = self.results[2:4] if len(self.results) > 2 else []
        phase3 = self.results[4:6] if len(self.results) > 4 else []
        phase4 = self.results[6:] if len(self.results) > 6 else []

        print("\nPhase 1: Quick Verification")
        for r in phase1:
            status_icon = "✅" if r.status == HealthStatus.HEALTHY else "❌"
            print(f"  {status_icon} {r.endpoint:30} {r.response_time_ms:6.0f}ms  {r.status.value}")

        if phase2:
            print("\nPhase 2: Core Functionality")
            for r in phase2:
                status_icon = "✅" if r.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] else "❌"
                print(f"  {status_icon} {r.endpoint:30} {r.response_time_ms:6.0f}ms  {r.status.value}")

        if phase3:
            print("\nPhase 3: Performance Validation")
            for r in phase3:
                status_icon = "✅" if r.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] else "❌"
                print(f"  {status_icon} {r.endpoint:30} {r.response_time_ms:6.0f}ms  {r.status.value}")

        if phase4:
            print("\nPhase 4: External Dependencies")
            for r in phase4:
                status_icon = "✅" if r.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] else "⚠️"
                print(f"  {status_icon} {r.endpoint:30} {r.response_time_ms:6.0f}ms  {r.status.value}")

        print("\n" + "=" * 80)

        # Check for timeout risks
        timeout_risks = [
            r for r in self.results
            if r.response_time_ms > 5000
        ]

        if timeout_risks:
            print("\n⚠️  WARNING: Timeout risks detected:")
            for r in timeout_risks:
                print(f"    {r.endpoint}: {r.response_time_ms:.0f}ms (>5000ms threshold)")

        print()


async def main():
    """CLI interface for rollback validation"""
    import argparse

    parser = argparse.ArgumentParser(description="Rollback Validation")
    parser.add_argument("--base-url",
                       default="http://localhost:8000",
                       help="Application base URL")
    parser.add_argument("--timeout",
                       type=int,
                       default=10,
                       help="HTTP timeout in seconds")
    parser.add_argument("--wait",
                       type=int,
                       default=10,
                       help="Wait N seconds before starting validation")

    args = parser.parse_args()

    # Wait for app to stabilize after deployment
    if args.wait > 0:
        print(f"Waiting {args.wait} seconds for application to stabilize...")
        await asyncio.sleep(args.wait)

    validator = RollbackValidator(
        base_url=args.base_url,
        timeout=args.timeout
    )

    success = await validator.validate_rollback()

    if success:
        print("✅ Rollback validation PASSED")
        sys.exit(0)
    else:
        print("❌ Rollback validation FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
