#!/usr/bin/env python3
"""
Sentry Release Management for MITA Finance
Handles automated release creation, deployment tracking, and version management
"""

import os
import sys
import json
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
import argparse
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SentryReleaseManager:
    """Manages Sentry releases for MITA Finance application"""
    
    def __init__(
        self,
        org_slug: str,
        project_slug: str,
        auth_token: str,
        environment: str = "production"
    ):
        self.org_slug = org_slug
        self.project_slug = project_slug
        self.auth_token = auth_token
        self.environment = environment
        self.base_url = "https://sentry.io/api/0"
        
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def get_git_info(self) -> Dict[str, str]:
        """Get Git information for release tracking"""
        try:
            # Get current commit SHA
            commit_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], 
                universal_newlines=True
            ).strip()
            
            # Get commit message
            commit_message = subprocess.check_output(
                ["git", "log", "-1", "--pretty=%s"], 
                universal_newlines=True
            ).strip()
            
            # Get author
            commit_author = subprocess.check_output(
                ["git", "log", "-1", "--pretty=%an"], 
                universal_newlines=True
            ).strip()
            
            # Get branch name
            try:
                branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                    universal_newlines=True
                ).strip()
            except subprocess.CalledProcessError:
                branch = "unknown"
            
            # Get repository URL
            try:
                repo_url = subprocess.check_output(
                    ["git", "config", "--get", "remote.origin.url"], 
                    universal_newlines=True
                ).strip()
                
                # Clean up repository URL
                if repo_url.startswith("git@"):
                    repo_url = repo_url.replace("git@", "https://").replace(".com:", ".com/")
                if repo_url.endswith(".git"):
                    repo_url = repo_url[:-4]
                    
            except subprocess.CalledProcessError:
                repo_url = "unknown"
            
            return {
                "commit_sha": commit_sha,
                "commit_message": commit_message,
                "commit_author": commit_author,
                "branch": branch,
                "repository_url": repo_url,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get Git information: {e}")
            return {
                "commit_sha": "unknown",
                "commit_message": "unknown",
                "commit_author": "unknown",
                "branch": "unknown",
                "repository_url": "unknown",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    def create_release(
        self,
        version: str,
        projects: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new Sentry release"""
        
        if projects is None:
            projects = [self.project_slug]
        
        git_info = self.get_git_info()
        
        release_data = {
            "version": version,
            "projects": projects,
            "dateReleased": datetime.utcnow().isoformat() + "Z",
            "refs": [
                {
                    "repository": git_info["repository_url"],
                    "commit": git_info["commit_sha"],
                    "previousCommit": None  # Could be enhanced to get previous release commit
                }
            ]
        }
        
        url = f"{self.base_url}/organizations/{self.org_slug}/releases/"
        
        try:
            response = requests.post(url, headers=self.headers, json=release_data)
            response.raise_for_status()
            
            release_info = response.json()
            logger.info(f"✅ Created Sentry release: {version}")
            logger.info(f"   Release URL: {release_info.get('url', 'N/A')}")
            logger.info(f"   Commit: {git_info['commit_sha'][:8]} - {git_info['commit_message']}")
            
            return release_info
            
        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code == 400:
                error_data = e.response.json()
                if "already exists" in str(error_data):
                    logger.warning(f"⚠️  Release {version} already exists, skipping creation")
                    return self.get_release(version)
                else:
                    logger.error(f"❌ Failed to create release: {error_data}")
                    raise
            else:
                logger.error(f"❌ Failed to create release: {e}")
                raise
    
    def get_release(self, version: str) -> Dict[str, Any]:
        """Get existing release information"""
        url = f"{self.base_url}/organizations/{self.org_slug}/releases/{version}/"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get release {version}: {e}")
            raise
    
    def create_deployment(
        self,
        version: str,
        environment: Optional[str] = None,
        name: Optional[str] = None,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a deployment for a release"""
        
        env = environment or self.environment
        deployment_name = name or f"MITA Finance {env.title()} Deployment"
        
        git_info = self.get_git_info()
        
        deployment_data = {
            "environment": env,
            "name": deployment_name,
            "dateStarted": datetime.utcnow().isoformat() + "Z",
            "dateFinished": datetime.utcnow().isoformat() + "Z",
            "url": url
        }
        
        url_path = f"{self.base_url}/organizations/{self.org_slug}/releases/{version}/deploys/"
        
        try:
            response = requests.post(url_path, headers=self.headers, json=deployment_data)
            response.raise_for_status()
            
            deployment_info = response.json()
            logger.info(f"✅ Created deployment for release {version} in {env} environment")
            logger.info(f"   Deployment ID: {deployment_info.get('id', 'N/A')}")
            
            return deployment_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to create deployment: {e}")
            if e.response:
                logger.error(f"   Response: {e.response.text}")
            raise
    
    def finalize_release(self, version: str) -> Dict[str, Any]:
        """Finalize a release by setting it as deployed"""
        
        url = f"{self.base_url}/organizations/{self.org_slug}/releases/{version}/"
        
        finalize_data = {
            "dateReleased": datetime.utcnow().isoformat() + "Z"
        }
        
        try:
            response = requests.put(url, headers=self.headers, json=finalize_data)
            response.raise_for_status()
            
            release_info = response.json()
            logger.info(f"✅ Finalized release: {version}")
            
            return release_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to finalize release: {e}")
            raise
    
    def set_commits(self, version: str, commits: Optional[List[Dict[str, Any]]] = None) -> None:
        """Set commits for a release"""
        
        if commits is None:
            # Get commits since last release
            commits = self._get_commits_since_last_release()
        
        if not commits:
            logger.warning("No commits found for release")
            return
        
        url = f"{self.base_url}/organizations/{self.org_slug}/releases/{version}/commitfiles/"
        
        try:
            for commit in commits:
                commit_data = {
                    "id": commit["id"],
                    "repository": commit.get("repository", ""),
                    "author_name": commit.get("author_name", ""),
                    "author_email": commit.get("author_email", ""),
                    "message": commit.get("message", ""),
                    "timestamp": commit.get("timestamp", "")
                }
                
                response = requests.post(url, headers=self.headers, json=commit_data)
                # Don't fail on individual commit errors
                if not response.ok:
                    logger.warning(f"Failed to add commit {commit['id']}: {response.text}")
            
            logger.info(f"✅ Added {len(commits)} commits to release {version}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to set commits: {e}")
    
    def _get_commits_since_last_release(self) -> List[Dict[str, Any]]:
        """Get commits since the last release"""
        try:
            # Get the last release tag
            last_tag = subprocess.check_output(
                ["git", "describe", "--tags", "--abbrev=0"], 
                universal_newlines=True,
                stderr=subprocess.DEVNULL
            ).strip()
            
            # Get commits since last tag
            commit_range = f"{last_tag}..HEAD"
            
        except subprocess.CalledProcessError:
            # No previous tags, get all commits from the beginning
            commit_range = "HEAD"
            logger.info("No previous release found, including all commits")
        
        try:
            # Get commit information
            commit_log = subprocess.check_output([
                "git", "log", commit_range,
                "--pretty=format:%H|%an|%ae|%s|%ad",
                "--date=iso"
            ], universal_newlines=True)
            
            commits = []
            for line in commit_log.split('\n'):
                if line.strip():
                    parts = line.split('|', 4)
                    if len(parts) >= 5:
                        commits.append({
                            "id": parts[0],
                            "author_name": parts[1],
                            "author_email": parts[2],
                            "message": parts[3],
                            "timestamp": parts[4]
                        })
            
            return commits
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get commits: {e}")
            return []
    
    def notify_deployment(
        self,
        version: str,
        status: str = "success",
        webhook_url: Optional[str] = None
    ) -> None:
        """Send deployment notification"""
        
        if not webhook_url:
            webhook_url = os.getenv("DEPLOYMENT_WEBHOOK_URL")
        
        if not webhook_url:
            logger.info("No webhook URL configured, skipping notification")
            return
        
        git_info = self.get_git_info()
        
        # Format notification message
        if status == "success":
            emoji = "✅"
            color = "good"
            title = "Deployment Successful"
        elif status == "failed":
            emoji = "❌"
            color = "danger"
            title = "Deployment Failed"
        else:
            emoji = "🔄"
            color = "warning"
            title = "Deployment In Progress"
        
        notification_data = {
            "text": f"{emoji} MITA Finance Deployment - {title}",
            "attachments": [
                {
                    "color": color,
                    "title": f"Release {version}",
                    "fields": [
                        {
                            "title": "Environment",
                            "value": self.environment.title(),
                            "short": True
                        },
                        {
                            "title": "Version",
                            "value": version,
                            "short": True
                        },
                        {
                            "title": "Commit",
                            "value": f"{git_info['commit_sha'][:8]} - {git_info['commit_message']}",
                            "short": False
                        },
                        {
                            "title": "Author",
                            "value": git_info['commit_author'],
                            "short": True
                        },
                        {
                            "title": "Branch",
                            "value": git_info['branch'],
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                            "short": True
                        }
                    ],
                    "footer": "MITA Finance Deployment System",
                    "ts": int(datetime.utcnow().timestamp())
                }
            ]
        }
        
        try:
            response = requests.post(webhook_url, json=notification_data)
            response.raise_for_status()
            logger.info(f"✅ Sent deployment notification: {status}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to send deployment notification: {e}")
    
    def full_release_cycle(
        self,
        version: str,
        projects: Optional[List[str]] = None,
        deployment_url: Optional[str] = None,
        notify: bool = True
    ) -> Dict[str, Any]:
        """Execute a full release cycle"""
        
        logger.info(f"🚀 Starting full release cycle for version: {version}")
        
        try:
            # Step 1: Create release
            release_info = self.create_release(version, projects)
            
            # Step 2: Set commits
            self.set_commits(version)
            
            # Step 3: Create deployment
            deployment_info = self.create_deployment(
                version, 
                environment=self.environment,
                url=deployment_url
            )
            
            # Step 4: Finalize release
            finalized_release = self.finalize_release(version)
            
            # Step 5: Send notification
            if notify:
                self.notify_deployment(version, "success")
            
            logger.info(f"🎉 Successfully completed release cycle for {version}")
            
            return {
                "release": finalized_release,
                "deployment": deployment_info,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"💥 Release cycle failed: {e}")
            
            if notify:
                self.notify_deployment(version, "failed")
            
            raise


def get_version_from_environment() -> str:
    """Get version from environment variables or Git"""
    
    # Check for explicit version
    version = os.getenv("RELEASE_VERSION")
    if version:
        return version
    
    # Check for CI/CD version variables
    version = os.getenv("CI_COMMIT_TAG") or os.getenv("GITHUB_REF_NAME") or os.getenv("BUILD_VERSION")
    if version:
        return version
    
    # Try to get from Git tag
    try:
        git_tag = subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match"], 
            universal_newlines=True,
            stderr=subprocess.DEVNULL
        ).strip()
        return git_tag
    except subprocess.CalledProcessError:
        pass
    
    # Generate version from Git commit
    try:
        commit_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], 
            universal_newlines=True
        ).strip()
        
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"auto-{timestamp}-{commit_sha}"
        
    except subprocess.CalledProcessError:
        # Fallback to timestamp
        return f"auto-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def main():
    """Main CLI function"""
    
    parser = argparse.ArgumentParser(description="MITA Finance Sentry Release Manager")
    
    parser.add_argument("--org", required=True, help="Sentry organization slug")
    parser.add_argument("--project", required=True, help="Sentry project slug")
    parser.add_argument("--token", help="Sentry auth token (or use SENTRY_AUTH_TOKEN env var)")
    parser.add_argument("--version", help="Release version (auto-generated if not provided)")
    parser.add_argument("--environment", default="production", help="Deployment environment")
    parser.add_argument("--deployment-url", help="Deployment URL")
    parser.add_argument("--no-notify", action="store_true", help="Skip deployment notifications")
    parser.add_argument("--projects", nargs="+", help="Additional projects to include in release")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create release command
    create_parser = subparsers.add_parser("create", help="Create a new release")
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Create deployment for existing release")
    
    # Full cycle command
    full_parser = subparsers.add_parser("full-cycle", help="Execute full release cycle")
    
    # Finalize command
    finalize_parser = subparsers.add_parser("finalize", help="Finalize a release")
    
    args = parser.parse_args()
    
    # Get auth token
    auth_token = args.token or os.getenv("SENTRY_AUTH_TOKEN")
    if not auth_token:
        logger.error("❌ Sentry auth token required. Use --token or set SENTRY_AUTH_TOKEN environment variable")
        sys.exit(1)
    
    # Get version
    version = args.version or get_version_from_environment()
    logger.info(f"Using version: {version}")
    
    # Initialize release manager
    release_manager = SentryReleaseManager(
        org_slug=args.org,
        project_slug=args.project,
        auth_token=auth_token,
        environment=args.environment
    )
    
    try:
        if args.command == "create":
            release_manager.create_release(version, args.projects)
            
        elif args.command == "deploy":
            release_manager.create_deployment(version, url=args.deployment_url)
            
        elif args.command == "finalize":
            release_manager.finalize_release(version)
            
        else:  # full-cycle or default
            release_manager.full_release_cycle(
                version=version,
                projects=args.projects,
                deployment_url=args.deployment_url,
                notify=not args.no_notify
            )
        
        logger.info("✅ Operation completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()