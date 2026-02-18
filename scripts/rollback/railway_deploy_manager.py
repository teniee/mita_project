#!/usr/bin/env python3
"""
Railway Deployment Manager for MITA Production
Handles Railway CLI interactions for deployment and rollback operations

Copyright © 2025 YAKOVLEV LTD - All Rights Reserved
"""

import asyncio
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger()


class DeploymentStatus(Enum):
    """Railway deployment status"""
    BUILDING = "BUILDING"
    DEPLOYING = "DEPLOYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CRASHED = "CRASHED"
    REMOVED = "REMOVED"


@dataclass
class Deployment:
    """Railway deployment metadata"""
    id: str
    status: DeploymentStatus
    created_at: datetime
    git_sha: str
    git_branch: str
    alembic_revision: Optional[str] = None
    image_tag: Optional[str] = None
    health_check_passed: bool = False


class RailwayDeploymentManager:
    """
    Manages Railway deployment operations for MITA production

    Features:
    - List deployments with metadata
    - Rollback to previous deployment
    - Track deployment history
    - Verify deployment status
    """

    def __init__(self, service_id: Optional[str] = None, project_id: Optional[str] = None):
        self.service_id = service_id or self._get_service_id()
        self.project_id = project_id or self._get_project_id()
        self.history_file = Path(__file__).parent / "deployment_history.json"

    def _get_service_id(self) -> str:
        """Get Railway service ID from environment or config"""
        result = subprocess.run(
            ["railway", "service"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.error("Failed to get Railway service ID", stderr=result.stderr)
            raise RuntimeError("Railway service ID not found")

        # Parse service ID from Railway CLI output
        return result.stdout.strip()

    def _get_project_id(self) -> str:
        """Get Railway project ID from environment or config"""
        result = subprocess.run(
            ["railway", "environment"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.error("Failed to get Railway project ID", stderr=result.stderr)
            raise RuntimeError("Railway project ID not found")

        return result.stdout.strip()

    async def list_deployments(self, limit: int = 30) -> List[Deployment]:
        """
        List recent Railway deployments

        Args:
            limit: Maximum number of deployments to retrieve

        Returns:
            List of Deployment objects sorted by creation time (newest first)
        """
        logger.info("Fetching deployment list", limit=limit)

        try:
            process = await asyncio.create_subprocess_exec(
                "railway", "deployment", "list",
                "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0
            )

            if process.returncode != 0:
                logger.error("Failed to list deployments", stderr=stderr.decode())
                raise RuntimeError(f"Railway deployment list failed: {stderr.decode()}")

            # Parse JSON response
            deployments_data = json.loads(stdout.decode())

            # Convert to Deployment objects
            deployments = []
            for data in deployments_data[:limit]:
                deployment = Deployment(
                    id=data["id"],
                    status=DeploymentStatus(data["status"]),
                    created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
                    git_sha=data.get("meta", {}).get("commitSha", "unknown"),
                    git_branch=data.get("meta", {}).get("branch", "unknown"),
                    image_tag=data.get("meta", {}).get("imageTag")
                )
                deployments.append(deployment)

            logger.info("Fetched deployments", count=len(deployments))
            return deployments

        except asyncio.TimeoutError:
            logger.error("Timeout fetching deployment list")
            raise RuntimeError("Railway CLI timeout after 30 seconds")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse deployment JSON", error=str(e))
            raise RuntimeError(f"Invalid JSON from Railway CLI: {e}")

    async def get_deployment_status(self, deployment_id: str) -> DeploymentStatus:
        """
        Get current status of a specific deployment

        Args:
            deployment_id: Railway deployment ID

        Returns:
            Current DeploymentStatus
        """
        logger.info("Checking deployment status", deployment_id=deployment_id)

        try:
            process = await asyncio.create_subprocess_exec(
                "railway", "deployment", "get", deployment_id,
                "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10.0
            )

            if process.returncode != 0:
                logger.error("Failed to get deployment status",
                           deployment_id=deployment_id,
                           stderr=stderr.decode())
                raise RuntimeError(f"Railway deployment get failed: {stderr.decode()}")

            data = json.loads(stdout.decode())
            status = DeploymentStatus(data["status"])

            logger.info("Deployment status retrieved",
                       deployment_id=deployment_id,
                       status=status.value)
            return status

        except asyncio.TimeoutError:
            logger.error("Timeout getting deployment status")
            raise RuntimeError("Railway CLI timeout")

    async def rollback_to_deployment(self, deployment_id: str) -> bool:
        """
        Rollback to a specific deployment using Railway CLI

        Args:
            deployment_id: Target deployment ID to rollback to

        Returns:
            True if rollback initiated successfully, False otherwise
        """
        logger.info("Initiating rollback", deployment_id=deployment_id)

        try:
            # Verify target deployment exists and is valid
            deployments = await self.list_deployments()
            target_deployment = next(
                (d for d in deployments if d.id == deployment_id),
                None
            )

            if not target_deployment:
                logger.error("Target deployment not found", deployment_id=deployment_id)
                return False

            if target_deployment.status not in [DeploymentStatus.SUCCESS]:
                logger.error("Target deployment was not successful",
                           deployment_id=deployment_id,
                           status=target_deployment.status.value)
                return False

            # Execute Railway rollback (redeploy previous deployment)
            logger.info("Executing Railway rollback",
                       deployment_id=deployment_id,
                       git_sha=target_deployment.git_sha)

            process = await asyncio.create_subprocess_exec(
                "railway", "redeploy",
                "--service", self.service_id,
                "--deployment", deployment_id,
                "--yes",  # Skip confirmation
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120.0  # 2 minutes timeout
            )

            if process.returncode != 0:
                logger.error("Railway rollback failed",
                           stderr=stderr.decode(),
                           stdout=stdout.decode())
                return False

            logger.info("Railway rollback initiated successfully",
                       deployment_id=deployment_id)

            # Save rollback event to history
            await self._save_rollback_event(deployment_id, target_deployment)

            return True

        except asyncio.TimeoutError:
            logger.error("Railway rollback timed out after 2 minutes")
            return False
        except Exception as e:
            logger.error("Unexpected error during rollback", error=str(e))
            return False

    async def wait_for_deployment_success(
        self,
        deployment_id: str,
        timeout: int = 300
    ) -> bool:
        """
        Wait for deployment to reach SUCCESS status

        Args:
            deployment_id: Deployment to monitor
            timeout: Maximum seconds to wait (default: 5 minutes)

        Returns:
            True if deployment succeeded, False if failed or timed out
        """
        logger.info("Waiting for deployment success",
                   deployment_id=deployment_id,
                   timeout=timeout)

        start_time = datetime.now()
        check_interval = 5  # Check every 5 seconds

        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                status = await self.get_deployment_status(deployment_id)

                if status == DeploymentStatus.SUCCESS:
                    logger.info("Deployment succeeded", deployment_id=deployment_id)
                    return True
                elif status in [DeploymentStatus.FAILED, DeploymentStatus.CRASHED]:
                    logger.error("Deployment failed",
                               deployment_id=deployment_id,
                               status=status.value)
                    return False

                # Still building/deploying, wait and retry
                logger.debug("Deployment in progress",
                           deployment_id=deployment_id,
                           status=status.value)
                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.warning("Error checking deployment status", error=str(e))
                await asyncio.sleep(check_interval)

        logger.error("Deployment timed out",
                    deployment_id=deployment_id,
                    timeout=timeout)
        return False

    async def get_previous_successful_deployment(self) -> Optional[Deployment]:
        """
        Get the most recent successful deployment before current

        Returns:
            Previous successful Deployment or None if not found
        """
        deployments = await self.list_deployments()

        # Skip the most recent deployment (current), find previous successful
        for i, deployment in enumerate(deployments):
            if i == 0:
                continue  # Skip current deployment

            if deployment.status == DeploymentStatus.SUCCESS:
                logger.info("Found previous successful deployment",
                          deployment_id=deployment.id,
                          git_sha=deployment.git_sha,
                          created_at=deployment.created_at)
                return deployment

        logger.warning("No previous successful deployment found")
        return None

    async def _save_rollback_event(
        self,
        deployment_id: str,
        deployment: Deployment
    ):
        """Save rollback event to deployment history"""
        try:
            history = self._load_history()

            event = {
                "type": "rollback",
                "timestamp": datetime.utcnow().isoformat(),
                "target_deployment_id": deployment_id,
                "git_sha": deployment.git_sha,
                "git_branch": deployment.git_branch,
                "alembic_revision": deployment.alembic_revision
            }

            history["events"].append(event)

            # Keep only last 100 events
            history["events"] = history["events"][-100:]

            self._save_history(history)

        except Exception as e:
            logger.warning("Failed to save rollback event", error=str(e))

    def _load_history(self) -> Dict:
        """Load deployment history from JSON file"""
        if not self.history_file.exists():
            return {"events": [], "last_known_good": None}

        with open(self.history_file, 'r') as f:
            return json.load(f)

    def _save_history(self, history: Dict):
        """Save deployment history to JSON file"""
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)

    async def mark_deployment_as_good(self, deployment_id: str):
        """Mark deployment as last known good"""
        history = self._load_history()
        history["last_known_good"] = {
            "deployment_id": deployment_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        self._save_history(history)
        logger.info("Marked deployment as last known good", deployment_id=deployment_id)


async def main():
    """CLI interface for Railway deployment management"""
    import argparse

    parser = argparse.ArgumentParser(description="Railway Deployment Manager")
    parser.add_argument("command", choices=["list", "rollback", "status", "previous"])
    parser.add_argument("--deployment-id", help="Deployment ID for rollback/status")
    parser.add_argument("--limit", type=int, default=10, help="Limit for list command")

    args = parser.parse_args()

    manager = RailwayDeploymentManager()

    try:
        if args.command == "list":
            deployments = await manager.list_deployments(limit=args.limit)
            print("\nRecent Deployments:")
            print("-" * 100)
            for d in deployments:
                print(f"{d.id[:8]} | {d.status.value:10} | {d.git_sha[:7]} | "
                      f"{d.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print("-" * 100)

        elif args.command == "rollback":
            if not args.deployment_id:
                print("ERROR: --deployment-id required for rollback")
                sys.exit(1)

            success = await manager.rollback_to_deployment(args.deployment_id)
            if success:
                print(f"✅ Rollback initiated to deployment {args.deployment_id}")

                # Wait for rollback to complete
                new_deployment_id = args.deployment_id  # Railway creates new deployment ID
                success = await manager.wait_for_deployment_success(new_deployment_id)

                if success:
                    print(f"✅ Rollback completed successfully")
                    sys.exit(0)
                else:
                    print(f"❌ Rollback failed")
                    sys.exit(1)
            else:
                print(f"❌ Failed to initiate rollback")
                sys.exit(1)

        elif args.command == "status":
            if not args.deployment_id:
                print("ERROR: --deployment-id required for status")
                sys.exit(1)

            status = await manager.get_deployment_status(args.deployment_id)
            print(f"Deployment {args.deployment_id}: {status.value}")

        elif args.command == "previous":
            deployment = await manager.get_previous_successful_deployment()
            if deployment:
                print(f"\nPrevious Successful Deployment:")
                print(f"  ID: {deployment.id}")
                print(f"  Status: {deployment.status.value}")
                print(f"  Git SHA: {deployment.git_sha}")
                print(f"  Branch: {deployment.git_branch}")
                print(f"  Created: {deployment.created_at}")
            else:
                print("No previous successful deployment found")
                sys.exit(1)

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
