#!/usr/bin/env python3
"""
Sentry Alert Rules Setup Script for MITA Finance
Automatically configures comprehensive alert rules and notification channels
"""

import os
import sys
import json
import yaml
import requests
import argparse
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SentryAlertsManager:
    """Manages Sentry alert rules and notification channels"""
    
    def __init__(
        self,
        org_slug: str,
        project_slug: str,
        auth_token: str,
        config_file: str = "config/sentry/alert_rules.yaml"
    ):
        self.org_slug = org_slug
        self.project_slug = project_slug
        self.auth_token = auth_token
        self.config_file = config_file
        self.base_url = "https://sentry.io/api/0"
        
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
        
        # Load configuration
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load alert rules configuration from YAML file"""
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Substitute environment variables
            config_str = json.dumps(config)
            for env_var in os.environ:
                if env_var.startswith(('SLACK_', 'PAGERDUTY_', 'WEBHOOK_', 'EMAIL_')):
                    config_str = config_str.replace(f"${{{env_var}}}", os.environ[env_var])
            
            return json.loads(config_str)
            
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found")
            raise
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def setup_all_alerts(self, environment: str = "production"):
        """Set up all alert rules for the specified environment"""
        
        logger.info(f"Setting up Sentry alerts for {environment} environment")
        
        if environment not in self.config:
            logger.error(f"Environment {environment} not found in configuration")
            return False
        
        env_config = self.config[environment]
        success_count = 0
        total_count = len(env_config)
        
        # Set up each alert rule
        for rule_name, rule_config in env_config.items():
            try:
                logger.info(f"Setting up alert rule: {rule_name}")
                
                if self._create_alert_rule(rule_name, rule_config, environment):
                    success_count += 1
                    logger.info(f"✅ Successfully created alert rule: {rule_name}")
                else:
                    logger.error(f"❌ Failed to create alert rule: {rule_name}")
                    
            except Exception as e:
                logger.error(f"❌ Error setting up alert rule {rule_name}: {e}")
        
        logger.info(f"Alert setup complete: {success_count}/{total_count} rules created successfully")
        
        # Set up notification channels
        if success_count > 0:
            self._setup_notification_channels()
        
        return success_count == total_count
    
    def _create_alert_rule(
        self, 
        rule_name: str, 
        rule_config: Dict[str, Any],
        environment: str
    ) -> bool:
        """Create a single alert rule"""
        
        # Build alert rule data structure
        alert_rule_data = {
            "name": rule_config.get("name", rule_name),
            "environment": environment,
            "dataset": "errors",  # Default dataset
            "query": self._build_query_from_conditions(rule_config.get("conditions", [])),
            "timeWindow": rule_config.get("time_window", 60),  # Default 1 minute
            "triggers": self._build_triggers(rule_config.get("triggers", [])),
            "projects": [self.project_slug],
            "owner": f"team:{self.org_slug}",
            "thresholdType": 0,  # Above threshold
            "includeAllProjects": False
        }
        
        # Add frequency if specified
        if "frequency" in rule_config:
            alert_rule_data["frequency"] = rule_config["frequency"]
        
        url = f"{self.base_url}/organizations/{self.org_slug}/alert-rules/"
        
        try:
            response = requests.post(url, headers=self.headers, json=alert_rule_data)
            
            if response.status_code == 201:
                alert_rule = response.json()
                logger.debug(f"Created alert rule with ID: {alert_rule.get('id')}")
                
                # Set up actions for this alert rule
                if "actions" in rule_config:
                    self._setup_alert_actions(alert_rule["id"], rule_config["actions"])
                
                return True
                
            elif response.status_code == 400:
                error_data = response.json()
                if "already exists" in str(error_data).lower():
                    logger.warning(f"Alert rule '{rule_name}' already exists, updating...")
                    return self._update_existing_alert_rule(rule_name, alert_rule_data)
                else:
                    logger.error(f"Bad request creating alert rule: {error_data}")
                    return False
            else:
                logger.error(f"Failed to create alert rule: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return False
    
    def _build_query_from_conditions(self, conditions: List[Dict[str, Any]]) -> str:
        """Build Sentry query string from conditions"""
        
        if not conditions:
            return "event.type:error"  # Default query
        
        query_parts = []
        
        for condition in conditions:
            filter_config = condition.get("filter", {})
            key = filter_config.get("key", "")
            match = filter_config.get("match", "equals")
            value = filter_config.get("value", "")
            
            if match == "equals":
                query_parts.append(f"{key}:{value}")
            elif match == "not_equals":
                query_parts.append(f"!{key}:{value}")
            elif match == "contains":
                query_parts.append(f"{key}:*{value}*")
            elif match == "gte":
                query_parts.append(f"{key}:>={value}")
            elif match == "lte":
                query_parts.append(f"{key}:<={value}")
        
        return " AND ".join(query_parts) if query_parts else "event.type:error"
    
    def _build_triggers(self, triggers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build triggers configuration"""
        
        sentry_triggers = []
        
        for i, trigger in enumerate(triggers):
            sentry_trigger = {
                "id": str(i + 1),
                "label": trigger.get("label", f"Trigger {i + 1}"),
                "thresholdType": trigger.get("threshold_type", 0),
                "alertThreshold": trigger.get("alert_threshold", 1),
                "resolveThreshold": trigger.get("resolve_threshold", 0),
                "actions": []
            }
            
            sentry_triggers.append(sentry_trigger)
        
        return sentry_triggers
    
    def _setup_alert_actions(self, alert_rule_id: str, actions: List[Dict[str, Any]]):
        """Set up actions for an alert rule"""
        
        for action in actions:
            action_type = action.get("type")
            
            if action_type == "email":
                self._create_email_action(alert_rule_id, action)
            elif action_type == "slack":
                self._create_slack_action(alert_rule_id, action)
            elif action_type == "pagerduty":
                self._create_pagerduty_action(alert_rule_id, action)
            elif action_type == "webhook":
                self._create_webhook_action(alert_rule_id, action)
    
    def _create_email_action(self, alert_rule_id: str, action: Dict[str, Any]):
        """Create email notification action"""
        
        target_type = action.get("target_type", "team")
        target_identifier = action.get("target_identifier")
        
        action_data = {
            "type": "email",
            "targetType": target_type,
            "targetIdentifier": target_identifier,
            "params": {}
        }
        
        self._create_action(alert_rule_id, action_data)
    
    def _create_slack_action(self, alert_rule_id: str, action: Dict[str, Any]):
        """Create Slack notification action"""
        
        target_identifier = action.get("target_identifier")
        tags = action.get("tags", "")
        
        # Get Slack integration
        slack_integration = self._get_slack_integration()
        if not slack_integration:
            logger.warning("Slack integration not found, skipping Slack action")
            return
        
        action_data = {
            "type": "slack",
            "targetType": "specific",
            "targetIdentifier": target_identifier,
            "integrationId": slack_integration["id"],
            "params": {
                "channel": target_identifier,
                "tags": tags
            }
        }
        
        self._create_action(alert_rule_id, action_data)
    
    def _create_pagerduty_action(self, alert_rule_id: str, action: Dict[str, Any]):
        """Create PagerDuty notification action"""
        
        target_identifier = action.get("target_identifier")
        
        # Get PagerDuty integration
        pagerduty_integration = self._get_pagerduty_integration()
        if not pagerduty_integration:
            logger.warning("PagerDuty integration not found, skipping PagerDuty action")
            return
        
        action_data = {
            "type": "pagerduty",
            "targetType": "specific",
            "targetIdentifier": target_identifier,
            "integrationId": pagerduty_integration["id"]
        }
        
        self._create_action(alert_rule_id, action_data)
    
    def _create_webhook_action(self, alert_rule_id: str, action: Dict[str, Any]):
        """Create webhook notification action"""
        
        webhook_url = action.get("target_identifier")
        
        action_data = {
            "type": "webhook",
            "targetType": "specific", 
            "targetIdentifier": webhook_url,
            "params": {
                "url": webhook_url
            }
        }
        
        self._create_action(alert_rule_id, action_data)
    
    def _create_action(self, alert_rule_id: str, action_data: Dict[str, Any]):
        """Create an action for an alert rule"""
        
        url = f"{self.base_url}/organizations/{self.org_slug}/alert-rules/{alert_rule_id}/actions/"
        
        try:
            response = requests.post(url, headers=self.headers, json=action_data)
            
            if response.status_code == 201:
                logger.debug(f"Created action for alert rule {alert_rule_id}")
            else:
                logger.warning(f"Failed to create action: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create action: {e}")
    
    def _get_slack_integration(self) -> Optional[Dict[str, Any]]:
        """Get Slack integration"""
        return self._get_integration("slack")
    
    def _get_pagerduty_integration(self) -> Optional[Dict[str, Any]]:
        """Get PagerDuty integration"""
        return self._get_integration("pagerduty")
    
    def _get_integration(self, provider: str) -> Optional[Dict[str, Any]]:
        """Get integration by provider"""
        
        url = f"{self.base_url}/organizations/{self.org_slug}/integrations/"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            integrations = response.json()
            for integration in integrations:
                if integration.get("provider", {}).get("key") == provider:
                    return integration
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get integrations: {e}")
            return None
    
    def _update_existing_alert_rule(self, rule_name: str, alert_rule_data: Dict[str, Any]) -> bool:
        """Update existing alert rule"""
        
        # First, get the existing rule
        existing_rule = self._find_existing_alert_rule(rule_name)
        if not existing_rule:
            logger.error(f"Could not find existing alert rule: {rule_name}")
            return False
        
        rule_id = existing_rule["id"]
        url = f"{self.base_url}/organizations/{self.org_slug}/alert-rules/{rule_id}/"
        
        try:
            response = requests.put(url, headers=self.headers, json=alert_rule_data)
            
            if response.status_code == 200:
                logger.info(f"Updated existing alert rule: {rule_name}")
                return True
            else:
                logger.error(f"Failed to update alert rule: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update alert rule: {e}")
            return False
    
    def _find_existing_alert_rule(self, rule_name: str) -> Optional[Dict[str, Any]]:
        """Find existing alert rule by name"""
        
        url = f"{self.base_url}/organizations/{self.org_slug}/alert-rules/"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            alert_rules = response.json()
            for rule in alert_rules:
                if rule.get("name") == rule_name:
                    return rule
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get alert rules: {e}")
            return None
    
    def _setup_notification_channels(self):
        """Set up notification channels (integrations)"""
        
        logger.info("Setting up notification channels...")
        
        notification_config = self.config.get("notification_channels", {})
        
        # Set up Slack integration
        if "slack" in notification_config:
            self._setup_slack_integration(notification_config["slack"])
        
        # Set up PagerDuty integration  
        if "pagerduty" in notification_config:
            self._setup_pagerduty_integration(notification_config["pagerduty"])
        
        logger.info("Notification channels setup complete")
    
    def _setup_slack_integration(self, slack_config: Dict[str, Any]):
        """Set up Slack integration"""
        
        logger.info("Setting up Slack integration...")
        
        channels = slack_config.get("channels", {})
        for channel_name, channel_config in channels.items():
            webhook_url = channel_config.get("webhook_url")
            if webhook_url and webhook_url != "${SLACK_WEBHOOK_URL}":
                logger.info(f"Slack webhook configured for {channel_name}: {webhook_url[:50]}...")
            else:
                logger.warning(f"Slack webhook URL not configured for {channel_name}")
    
    def _setup_pagerduty_integration(self, pagerduty_config: Dict[str, Any]):
        """Set up PagerDuty integration"""
        
        logger.info("Setting up PagerDuty integration...")
        
        services = pagerduty_config.get("services", {})
        for service_name, service_config in services.items():
            integration_key = service_config.get("integration_key")
            if integration_key and not integration_key.startswith("${"):
                logger.info(f"PagerDuty integration key configured for {service_name}")
            else:
                logger.warning(f"PagerDuty integration key not configured for {service_name}")
    
    def list_alert_rules(self) -> List[Dict[str, Any]]:
        """List all existing alert rules"""
        
        url = f"{self.base_url}/organizations/{self.org_slug}/alert-rules/"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get alert rules: {e}")
            return []
    
    def delete_alert_rule(self, rule_id: str) -> bool:
        """Delete an alert rule"""
        
        url = f"{self.base_url}/organizations/{self.org_slug}/alert-rules/{rule_id}/"
        
        try:
            response = requests.delete(url, headers=self.headers)
            
            if response.status_code == 204:
                logger.info(f"Deleted alert rule: {rule_id}")
                return True
            else:
                logger.error(f"Failed to delete alert rule: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete alert rule: {e}")
            return False
    
    def validate_configuration(self) -> bool:
        """Validate the alert configuration"""
        
        logger.info("Validating alert configuration...")
        
        required_env_vars = [
            "SLACK_FINANCE_WEBHOOK",
            "SLACK_SECURITY_WEBHOOK", 
            "SLACK_COMPLIANCE_WEBHOOK",
            "PAGERDUTY_FINANCE_KEY",
            "PAGERDUTY_SECURITY_KEY"
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"Missing environment variables: {missing_vars}")
            logger.warning("Some alert actions may not work properly")
        
        # Validate configuration structure
        required_sections = ["production", "notification_channels"]
        for section in required_sections:
            if section not in self.config:
                logger.error(f"Missing required configuration section: {section}")
                return False
        
        logger.info("Configuration validation complete")
        return True


def main():
    """Main CLI function"""
    
    parser = argparse.ArgumentParser(description="MITA Finance Sentry Alerts Setup")
    
    parser.add_argument("--org", required=True, help="Sentry organization slug")
    parser.add_argument("--project", required=True, help="Sentry project slug") 
    parser.add_argument("--token", help="Sentry auth token (or use SENTRY_AUTH_TOKEN env var)")
    parser.add_argument("--config", default="config/sentry/alert_rules.yaml", help="Configuration file path")
    parser.add_argument("--environment", default="production", help="Environment to set up alerts for")
    parser.add_argument("--validate-only", action="store_true", help="Only validate configuration")
    parser.add_argument("--list-rules", action="store_true", help="List existing alert rules")
    parser.add_argument("--delete-rule", help="Delete alert rule by ID")
    
    args = parser.parse_args()
    
    # Get auth token
    auth_token = args.token or os.getenv("SENTRY_AUTH_TOKEN")
    if not auth_token:
        logger.error("❌ Sentry auth token required. Use --token or set SENTRY_AUTH_TOKEN environment variable")
        sys.exit(1)
    
    # Initialize alerts manager
    alerts_manager = SentryAlertsManager(
        org_slug=args.org,
        project_slug=args.project,
        auth_token=auth_token,
        config_file=args.config
    )
    
    try:
        if args.validate_only:
            if alerts_manager.validate_configuration():
                logger.info("✅ Configuration is valid")
            else:
                logger.error("❌ Configuration validation failed")
                sys.exit(1)
                
        elif args.list_rules:
            rules = alerts_manager.list_alert_rules()
            logger.info(f"Found {len(rules)} alert rules:")
            for rule in rules:
                logger.info(f"  - {rule['name']} (ID: {rule['id']}) - {rule.get('environment', 'N/A')}")
                
        elif args.delete_rule:
            if alerts_manager.delete_alert_rule(args.delete_rule):
                logger.info("✅ Alert rule deleted successfully")
            else:
                logger.error("❌ Failed to delete alert rule")
                sys.exit(1)
                
        else:
            # Validate configuration first
            if not alerts_manager.validate_configuration():
                logger.error("❌ Configuration validation failed")
                sys.exit(1)
            
            # Set up alerts
            if alerts_manager.setup_all_alerts(args.environment):
                logger.info("✅ All alert rules set up successfully")
            else:
                logger.error("❌ Some alert rules failed to set up")
                sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()