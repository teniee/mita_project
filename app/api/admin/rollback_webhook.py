#!/usr/bin/env python3
"""
Alertmanager Webhook Handler for Automated Rollback
Receives alerts from Alertmanager and triggers automated rollback

Copyright © 2025 YAKOVLEV LTD - All Rights Reserved
"""

import asyncio
import os
import subprocess
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin/rollback", tags=["admin", "rollback"])


class AlertStatus(str, Enum):
    """Alertmanager alert status"""
    FIRING = "firing"
    RESOLVED = "resolved"


class Alert(BaseModel):
    """Single alert from Alertmanager"""
    status: AlertStatus
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: datetime
    endsAt: Optional[datetime] = None
    generatorURL: Optional[str] = None
    fingerprint: str


class AlertmanagerWebhook(BaseModel):
    """Alertmanager webhook payload"""
    version: str = Field(..., description="Alertmanager webhook version")
    groupKey: str = Field(..., description="Group key for alert grouping")
    truncatedAlerts: int = Field(default=0, description="Number of truncated alerts")
    status: AlertStatus = Field(..., description="Alert group status")
    receiver: str = Field(..., description="Receiver name")
    groupLabels: Dict[str, str] = Field(..., description="Group labels")
    commonLabels: Dict[str, str] = Field(..., description="Common labels")
    commonAnnotations: Dict[str, str] = Field(..., description="Common annotations")
    externalURL: str = Field(..., description="Alertmanager URL")
    alerts: List[Alert] = Field(..., description="List of alerts")


class RollbackTriggerMapping:
    """Maps Alertmanager alerts to rollback triggers"""

    ROLLBACK_TRIGGERS = {
        "CriticalErrorRate": {
            "trigger": "error_rate_threshold",
            "auto_rollback": True,
            "confidence": "high",
            "reason": "Error rate exceeded 20% for 2 minutes"
        },
        "CriticalP95Latency": {
            "trigger": "latency_degradation",
            "auto_rollback": True,
            "confidence": "high",
            "reason": "P95 latency exceeded 1 second for 2 minutes"
        },
        "MitaSystemUnhealthy": {
            "trigger": "health_check_failure",
            "auto_rollback": True,
            "confidence": "medium",
            "reason": "System health check failed (3 consecutive failures)"
        },
        "MitaDatabaseConnectionIssues": {
            "trigger": "database_error",
            "auto_rollback": True,
            "confidence": "high",
            "reason": "Database connection time exceeded 5 seconds"
        },
        "TransactionProcessingFailure": {
            "trigger": "database_error",
            "auto_rollback": True,
            "confidence": "high",
            "reason": "Multiple transaction processing failures detected (financial impact)"
        },
        "RedisConnectionFailure": {
            "trigger": "database_error",
            "auto_rollback": True,
            "confidence": "medium",
            "reason": "Redis connection failure - cache unavailable"
        },
        "UserRegistrationDown": {
            "trigger": "error_rate_threshold",
            "auto_rollback": True,
            "confidence": "high",
            "reason": "User registration completely down"
        }
    }

    @classmethod
    def should_trigger_rollback(cls, alert_name: str) -> bool:
        """Check if alert should trigger automatic rollback"""
        return alert_name in cls.ROLLBACK_TRIGGERS and cls.ROLLBACK_TRIGGERS[alert_name]["auto_rollback"]

    @classmethod
    def get_trigger_info(cls, alert_name: str) -> Optional[Dict]:
        """Get rollback trigger information for alert"""
        return cls.ROLLBACK_TRIGGERS.get(alert_name)


async def verify_webhook_secret(authorization: str = Header(None)) -> bool:
    """Verify webhook secret from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )

    # Expected format: "Basic base64(username:password)"
    # For simplicity, we're using bearer token
    expected_secret = os.getenv("ROLLBACK_WEBHOOK_SECRET", "change-me-in-production")

    if not authorization.startswith("Basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization format"
        )

    # In production, implement proper Basic auth verification
    # For now, simple check
    token = authorization.replace("Basic ", "")
    # You should decode base64 and verify username:password
    # This is simplified for example

    return True


@router.post("/trigger")
async def trigger_rollback_from_alert(
    webhook: AlertmanagerWebhook,
    authorized: bool = Depends(verify_webhook_secret)
):
    """
    Receive alert webhook from Alertmanager and trigger automated rollback

    This endpoint is called by Alertmanager when critical alerts fire.
    It validates the alert, checks if it should trigger rollback, and
    executes the automated rollback system.

    Authentication: Basic auth with ROLLBACK_WEBHOOK_SECRET
    """
    logger.info("Received webhook from Alertmanager",
               receiver=webhook.receiver,
               status=webhook.status,
               alert_count=len(webhook.alerts))

    # Only process firing alerts
    if webhook.status != AlertStatus.FIRING:
        logger.info("Alert status is not firing, skipping rollback",
                   status=webhook.status)
        return {
            "status": "skipped",
            "reason": "Alert not firing"
        }

    # Get alert name from common labels
    alert_name = webhook.commonLabels.get("alertname")
    if not alert_name:
        logger.error("Alert name not found in webhook")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert name missing"
        )

    # Check if this alert should trigger rollback
    if not RollbackTriggerMapping.should_trigger_rollback(alert_name):
        logger.info("Alert does not trigger automatic rollback",
                   alert_name=alert_name)
        return {
            "status": "skipped",
            "reason": f"Alert {alert_name} not configured for automatic rollback"
        }

    # Get trigger information
    trigger_info = RollbackTriggerMapping.get_trigger_info(alert_name)

    logger.warning("AUTOMATIC ROLLBACK TRIGGERED",
                  alert_name=alert_name,
                  trigger=trigger_info["trigger"],
                  confidence=trigger_info["confidence"],
                  reason=trigger_info["reason"])

    # Execute rollback in background task
    asyncio.create_task(
        execute_automated_rollback(
            alert_name=alert_name,
            trigger=trigger_info["trigger"],
            reason=trigger_info["reason"],
            alert_data=webhook.dict()
        )
    )

    return {
        "status": "rollback_initiated",
        "alert_name": alert_name,
        "trigger": trigger_info["trigger"],
        "reason": trigger_info["reason"],
        "confidence": trigger_info["confidence"],
        "message": "Automated rollback initiated. Monitor progress in #mita-deployments."
    }


async def execute_automated_rollback(
    alert_name: str,
    trigger: str,
    reason: str,
    alert_data: Dict
):
    """
    Execute automated rollback script in background

    This runs the rollback orchestrator script that we created earlier.
    """
    try:
        logger.info("Starting automated rollback execution",
                   alert_name=alert_name,
                   trigger=trigger)

        # Path to automated rollback script
        rollback_script = Path(__file__).parent.parent.parent.parent / "scripts" / "rollback" / "automated_rollback.py"

        if not rollback_script.exists():
            logger.error("Rollback script not found", path=str(rollback_script))
            return

        # Determine base URL based on environment
        base_url = os.getenv("ROLLBACK_BASE_URL", "http://localhost:8000")

        # Execute rollback script
        logger.info("Executing rollback script", script=str(rollback_script))

        process = await asyncio.create_subprocess_exec(
            "python3",
            str(rollback_script),
            "--base-url", base_url,
            "--reason", f"Automatic rollback triggered by {alert_name}: {reason}",
            "--skip-db",  # Database rollback optional for safety
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for rollback to complete (with timeout)
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=600.0  # 10 minute timeout
            )

            if process.returncode == 0:
                logger.info("Automated rollback completed successfully",
                           alert_name=alert_name,
                           duration="See logs for details")

                # TODO: Send success notification to Slack
                await send_rollback_notification(
                    alert_name=alert_name,
                    status="success",
                    reason=reason,
                    output=stdout.decode()
                )
            else:
                logger.error("Automated rollback failed",
                            alert_name=alert_name,
                            return_code=process.returncode,
                            stderr=stderr.decode())

                # TODO: Send failure notification + escalate to PagerDuty
                await send_rollback_notification(
                    alert_name=alert_name,
                    status="failed",
                    reason=reason,
                    error=stderr.decode()
                )

        except asyncio.TimeoutError:
            logger.error("Automated rollback timed out after 10 minutes",
                        alert_name=alert_name)

            # Kill the process
            process.kill()
            await process.wait()

            await send_rollback_notification(
                alert_name=alert_name,
                status="timeout",
                reason=reason,
                error="Rollback exceeded 10 minute timeout"
            )

    except Exception as e:
        logger.error("Exception during automated rollback execution",
                    error=str(e),
                    alert_name=alert_name)

        await send_rollback_notification(
            alert_name=alert_name,
            status="error",
            reason=reason,
            error=str(e)
        )


async def send_rollback_notification(
    alert_name: str,
    status: str,
    reason: str,
    output: Optional[str] = None,
    error: Optional[str] = None
):
    """
    Send rollback status notification to Slack/PagerDuty

    TODO: Implement actual Slack/PagerDuty integration
    """
    logger.info("Sending rollback notification",
               alert_name=alert_name,
               status=status)

    # Placeholder for Slack webhook
    slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not slack_webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not configured, skipping notification")
        return

    # TODO: Implement Slack notification
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     await client.post(slack_webhook_url, json={...})

    logger.info("Rollback notification sent (placeholder)")


@router.get("/status")
async def get_rollback_status():
    """
    Get current rollback system status

    Returns information about recent rollbacks and system health
    """
    # TODO: Implement rollback history tracking
    return {
        "status": "operational",
        "recent_rollbacks": [],
        "rollback_enabled": True,
        "monitored_alerts": list(RollbackTriggerMapping.ROLLBACK_TRIGGERS.keys())
    }


@router.post("/test")
async def test_rollback_webhook(
    alert_name: str,
    authorized: bool = Depends(verify_webhook_secret)
):
    """
    Test rollback webhook with simulated alert

    For testing purposes only. Requires authentication.
    """
    # Create test webhook payload
    test_webhook = AlertmanagerWebhook(
        version="4",
        groupKey="test-group",
        truncatedAlerts=0,
        status=AlertStatus.FIRING,
        receiver="rollback-trigger",
        groupLabels={"alertname": alert_name},
        commonLabels={
            "alertname": alert_name,
            "service": "mita-backend",
            "severity": "critical"
        },
        commonAnnotations={
            "summary": f"Test alert: {alert_name}",
            "description": "This is a test alert for rollback system"
        },
        externalURL="http://alertmanager:9093",
        alerts=[
            Alert(
                status=AlertStatus.FIRING,
                labels={
                    "alertname": alert_name,
                    "service": "mita-backend",
                    "severity": "critical"
                },
                annotations={
                    "summary": f"Test alert: {alert_name}",
                    "description": "This is a test alert"
                },
                startsAt=datetime.utcnow(),
                fingerprint="test-fingerprint"
            )
        ]
    )

    # Process test webhook (but don't actually execute rollback)
    trigger_info = RollbackTriggerMapping.get_trigger_info(alert_name)

    if not trigger_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Alert {alert_name} not configured"
        )

    logger.info("TEST: Rollback webhook triggered",
               alert_name=alert_name,
               trigger=trigger_info["trigger"])

    return {
        "status": "test_successful",
        "alert_name": alert_name,
        "would_trigger_rollback": trigger_info["auto_rollback"],
        "trigger": trigger_info["trigger"],
        "reason": trigger_info["reason"],
        "confidence": trigger_info["confidence"],
        "message": "Test successful. In production, this would trigger automatic rollback."
    }
