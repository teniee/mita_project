#!/usr/bin/env python3
"""
Alertmanager Testing Script
Tests notification channels and automated rollback integration

Copyright © 2025 YAKOVLEV LTD - All Rights Reserved
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()


class AlertmanagerTester:
    """Test Alertmanager configuration and integrations"""

    def __init__(
        self,
        alertmanager_url: str = "http://localhost:9093",
        api_url: str = "http://localhost:8000"
    ):
        self.alertmanager_url = alertmanager_url.rstrip('/')
        self.api_url = api_url.rstrip('/')
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def test_alertmanager_status(self) -> bool:
        """Test if Alertmanager is running"""
        logger.info("Testing Alertmanager status...")

        try:
            response = await self.http_client.get(f"{self.alertmanager_url}/api/v1/status")

            if response.status_code == 200:
                data = response.json()
                logger.info("Alertmanager is running",
                           version=data.get("data", {}).get("versionInfo", {}).get("version"),
                           uptime=data.get("data", {}).get("uptime"))
                return True
            else:
                logger.error("Alertmanager returned non-200 status",
                           status_code=response.status_code)
                return False

        except Exception as e:
            logger.error("Failed to connect to Alertmanager", error=str(e))
            return False

    async def test_rollback_webhook(self, alert_name: str = "CriticalErrorRate") -> bool:
        """Test rollback webhook endpoint"""
        logger.info("Testing rollback webhook...", alert_name=alert_name)

        # Create test webhook payload
        webhook_payload = {
            "version": "4",
            "groupKey": f"test-{datetime.now().isoformat()}",
            "truncatedAlerts": 0,
            "status": "firing",
            "receiver": "rollback-trigger",
            "groupLabels": {
                "alertname": alert_name
            },
            "commonLabels": {
                "alertname": alert_name,
                "service": "mita-backend",
                "severity": "critical",
                "component": "api"
            },
            "commonAnnotations": {
                "summary": f"Test alert: {alert_name}",
                "description": "This is a test alert for rollback system validation",
                "value": "0.25"
            },
            "externalURL": self.alertmanager_url,
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": alert_name,
                        "service": "mita-backend",
                        "severity": "critical"
                    },
                    "annotations": {
                        "summary": f"Test alert: {alert_name}",
                        "description": "Test alert for validation"
                    },
                    "startsAt": datetime.utcnow().isoformat() + "Z",
                    "endsAt": None,
                    "generatorURL": f"{self.alertmanager_url}/graph",
                    "fingerprint": "test-fingerprint-123"
                }
            ]
        }

        try:
            # Get webhook secret
            webhook_secret = os.getenv("ROLLBACK_WEBHOOK_SECRET", "change-me-in-production")

            # Test endpoint
            response = await self.http_client.post(
                f"{self.api_url}/api/admin/rollback/test",
                params={"alert_name": alert_name},
                headers={
                    "Authorization": f"Basic {webhook_secret}"
                }
            )

            if response.status_code == 200:
                result = response.json()
                logger.info("Rollback webhook test successful",
                           alert_name=alert_name,
                           would_trigger_rollback=result.get("would_trigger_rollback"),
                           trigger=result.get("trigger"))
                return True
            else:
                logger.error("Rollback webhook test failed",
                           status_code=response.status_code,
                           response=response.text)
                return False

        except Exception as e:
            logger.error("Failed to test rollback webhook", error=str(e))
            return False

    async def send_test_alert(
        self,
        alert_name: str,
        severity: str = "warning",
        service: str = "mita-backend"
    ) -> bool:
        """Send test alert directly to Alertmanager"""
        logger.info("Sending test alert to Alertmanager",
                   alert_name=alert_name,
                   severity=severity)

        alerts = [{
            "labels": {
                "alertname": alert_name,
                "service": service,
                "severity": severity,
                "component": "test"
            },
            "annotations": {
                "summary": f"Test alert: {alert_name}",
                "description": f"This is a test {severity} alert",
                "value": "test_value"
            },
            "startsAt": datetime.utcnow().isoformat() + "Z",
            "generatorURL": f"{self.alertmanager_url}/test"
        }]

        try:
            response = await self.http_client.post(
                f"{self.alertmanager_url}/api/v1/alerts",
                json=alerts
            )

            if response.status_code == 200:
                logger.info("Test alert sent successfully", alert_name=alert_name)
                return True
            else:
                logger.error("Failed to send test alert",
                           status_code=response.status_code,
                           response=response.text)
                return False

        except Exception as e:
            logger.error("Exception sending test alert", error=str(e))
            return False

    async def test_notification_channels(self) -> dict:
        """Test all notification channels"""
        logger.info("Testing notification channels...")

        results = {
            "slack": False,
            "email": False,
            "pagerduty": False,
            "webhook": False
        }

        # Test Slack webhook (if configured)
        slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        if slack_webhook:
            results["slack"] = await self._test_slack_webhook(slack_webhook)
        else:
            logger.warning("SLACK_WEBHOOK_URL not configured, skipping Slack test")

        # Test email (SendGrid)
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        if sendgrid_key:
            results["email"] = await self._test_sendgrid(sendgrid_key)
        else:
            logger.warning("SENDGRID_API_KEY not configured, skipping email test")

        # Test PagerDuty
        pagerduty_key = os.getenv("PAGERDUTY_CRITICAL_KEY")
        if pagerduty_key:
            results["pagerduty"] = await self._test_pagerduty(pagerduty_key)
        else:
            logger.warning("PAGERDUTY_CRITICAL_KEY not configured, skipping PagerDuty test")

        # Test rollback webhook
        results["webhook"] = await self.test_rollback_webhook()

        return results

    async def _test_slack_webhook(self, webhook_url: str) -> bool:
        """Test Slack webhook"""
        logger.info("Testing Slack webhook...")

        payload = {
            "text": "🧪 Alertmanager Test",
            "attachments": [
                {
                    "color": "good",
                    "title": "Slack Integration Test",
                    "text": "This is a test message from MITA Alertmanager",
                    "footer": "MITA Alertmanager",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }

        try:
            response = await self.http_client.post(webhook_url, json=payload)

            if response.status_code == 200:
                logger.info("Slack webhook test successful")
                return True
            else:
                logger.error("Slack webhook test failed",
                           status_code=response.status_code)
                return False

        except Exception as e:
            logger.error("Slack webhook test exception", error=str(e))
            return False

    async def _test_sendgrid(self, api_key: str) -> bool:
        """Test SendGrid email"""
        logger.info("Testing SendGrid email...")

        # Test SendGrid API connectivity
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            response = await self.http_client.get(
                "https://api.sendgrid.com/v3/scopes",
                headers=headers
            )

            if response.status_code == 200:
                logger.info("SendGrid API test successful")
                return True
            else:
                logger.error("SendGrid API test failed",
                           status_code=response.status_code)
                return False

        except Exception as e:
            logger.error("SendGrid test exception", error=str(e))
            return False

    async def _test_pagerduty(self, integration_key: str) -> bool:
        """Test PagerDuty integration"""
        logger.info("Testing PagerDuty integration...")

        payload = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": "MITA Alertmanager Integration Test",
                "source": "mita-alertmanager",
                "severity": "info",
                "custom_details": {
                    "message": "This is a test event from MITA Alertmanager"
                }
            }
        }

        try:
            response = await self.http_client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload
            )

            if response.status_code == 202:
                logger.info("PagerDuty test successful")
                return True
            else:
                logger.error("PagerDuty test failed",
                           status_code=response.status_code,
                           response=response.text)
                return False

        except Exception as e:
            logger.error("PagerDuty test exception", error=str(e))
            return False

    async def run_all_tests(self) -> bool:
        """Run all tests"""
        logger.info("=" * 80)
        logger.info("Starting Alertmanager Integration Tests")
        logger.info("=" * 80)

        all_passed = True

        # Test 1: Alertmanager status
        status_ok = await self.test_alertmanager_status()
        all_passed = all_passed and status_ok

        print()

        # Test 2: Notification channels
        channel_results = await self.test_notification_channels()

        print()
        logger.info("=" * 80)
        logger.info("Test Results Summary")
        logger.info("=" * 80)

        results = {
            "Alertmanager Status": status_ok,
            **channel_results
        }

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name:30} {status}")

        print()

        if all(results.values()):
            logger.info("✅ All tests passed!")
            return True
        else:
            logger.error("❌ Some tests failed. Check configuration.")
            return False

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


async def main():
    """Main test entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Alertmanager configuration")
    parser.add_argument("--alertmanager-url",
                       default="http://localhost:9093",
                       help="Alertmanager URL")
    parser.add_argument("--api-url",
                       default="http://localhost:8000",
                       help="MITA API URL")
    parser.add_argument("--test-alert",
                       help="Send test alert with this name")
    parser.add_argument("--severity",
                       default="warning",
                       choices=["warning", "error", "critical"],
                       help="Test alert severity")

    args = parser.parse_args()

    tester = AlertmanagerTester(
        alertmanager_url=args.alertmanager_url,
        api_url=args.api_url
    )

    try:
        if args.test_alert:
            # Send specific test alert
            success = await tester.send_test_alert(
                alert_name=args.test_alert,
                severity=args.severity
            )
            sys.exit(0 if success else 1)
        else:
            # Run all tests
            success = await tester.run_all_tests()
            sys.exit(0 if success else 1)

    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
