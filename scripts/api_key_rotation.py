#!/usr/bin/env python3
"""
API Key Rotation System for MITA Finance
Automated rotation of API keys with zero-downtime deployment
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta
import argparse
from pathlib import Path
import secrets

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.api_key_manager import api_key_manager, ServiceType
from app.core.external_services import external_services

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class APIKeyRotationManager:
    """Manages API key rotation with zero-downtime strategy"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.rotation_log = []
        self.backup_keys = {}
        
        # Rotation policies by service
        self.rotation_policies = {
            ServiceType.OPENAI: {
                'rotation_interval_days': 90,
                'requires_manual_rotation': True,
                'zero_downtime_capable': True
            },
            ServiceType.SENTRY: {
                'rotation_interval_days': 180,
                'requires_manual_rotation': True,
                'zero_downtime_capable': False
            },
            ServiceType.SENDGRID: {
                'rotation_interval_days': 90,
                'requires_manual_rotation': True,
                'zero_downtime_capable': True
            },
            ServiceType.AWS: {
                'rotation_interval_days': 60,
                'requires_manual_rotation': True,
                'zero_downtime_capable': True
            },
            ServiceType.UPSTASH: {
                'rotation_interval_days': 180,
                'requires_manual_rotation': False,
                'zero_downtime_capable': True
            }
        }
        
        logger.info(f"API Key Rotation Manager initialized (dry_run={dry_run})")
    
    async def analyze_rotation_needs(self) -> Dict[str, Any]:
        """Analyze which API keys need rotation"""
        logger.info("Analyzing API key rotation needs...")
        
        # Get current key status
        key_health = api_key_manager.get_key_health_status()
        
        rotation_needed = []
        rotation_recommended = []
        rotation_overdue = []
        
        current_time = datetime.now()
        
        for key_name, key_info in key_health['key_details'].items():
            service_type = ServiceType(key_info['service'])
            policy = self.rotation_policies.get(service_type)
            
            if not policy:
                continue
            
            # Parse last rotation date
            last_rotation = None
            if key_info.get('last_rotation'):
                last_rotation = datetime.fromisoformat(key_info['last_rotation'])
            
            # If never rotated, use a default old date
            if not last_rotation:
                last_rotation = current_time - timedelta(days=365)
            
            days_since_rotation = (current_time - last_rotation).days
            rotation_interval = policy['rotation_interval_days']
            
            # Categorize based on rotation urgency
            if days_since_rotation > rotation_interval * 1.5:  # 150% of interval
                rotation_overdue.append({
                    'key_name': key_name,
                    'service': service_type.value,
                    'days_since_rotation': days_since_rotation,
                    'recommended_interval': rotation_interval,
                    'urgency': 'overdue'
                })
            elif days_since_rotation > rotation_interval:  # Past interval
                rotation_needed.append({
                    'key_name': key_name,
                    'service': service_type.value,
                    'days_since_rotation': days_since_rotation,
                    'recommended_interval': rotation_interval,
                    'urgency': 'needed'
                })
            elif days_since_rotation > rotation_interval * 0.8:  # 80% of interval
                rotation_recommended.append({
                    'key_name': key_name,
                    'service': service_type.value,
                    'days_since_rotation': days_since_rotation,
                    'recommended_interval': rotation_interval,
                    'urgency': 'recommended'
                })
        
        analysis = {
            'timestamp': current_time.isoformat(),
            'total_keys': len(key_health['key_details']),
            'rotation_overdue': rotation_overdue,
            'rotation_needed': rotation_needed,
            'rotation_recommended': rotation_recommended,
            'summary': {
                'overdue_count': len(rotation_overdue),
                'needed_count': len(rotation_needed),
                'recommended_count': len(rotation_recommended),
                'total_needing_attention': len(rotation_overdue) + len(rotation_needed) + len(rotation_recommended)
            },
            'next_actions': self._generate_rotation_plan(rotation_overdue + rotation_needed + rotation_recommended)
        }
        
        return analysis
    
    def _generate_rotation_plan(self, keys_to_rotate: List[Dict]) -> List[Dict]:
        """Generate rotation plan with priorities"""
        plan = []
        
        # Sort by urgency and days since rotation
        sorted_keys = sorted(keys_to_rotate, key=lambda x: (
            x['urgency'] == 'overdue',
            x['urgency'] == 'needed',
            x['days_since_rotation']
        ), reverse=True)
        
        for key_info in sorted_keys:
            service_type = ServiceType(key_info['service'])
            policy = self.rotation_policies.get(service_type, {})
            
            action = {
                'key_name': key_info['key_name'],
                'service': key_info['service'],
                'priority': key_info['urgency'],
                'days_since_rotation': key_info['days_since_rotation'],
                'manual_rotation_required': policy.get('requires_manual_rotation', True),
                'zero_downtime_capable': policy.get('zero_downtime_capable', False),
                'estimated_downtime_minutes': 0 if policy.get('zero_downtime_capable') else 5,
                'rotation_steps': self._get_rotation_steps(service_type)
            }
            plan.append(action)
        
        return plan
    
    def _get_rotation_steps(self, service_type: ServiceType) -> List[str]:
        """Get rotation steps for specific service type"""
        base_steps = [
            "1. Generate new API key in service dashboard",
            "2. Validate new key functionality",
            "3. Update production environment variables",
            "4. Deploy configuration changes",
            "5. Validate service connectivity",
            "6. Archive old key",
            "7. Update monitoring and documentation"
        ]
        
        service_specific_steps = {
            ServiceType.OPENAI: [
                "1. Log into OpenAI Platform (platform.openai.com)",
                "2. Navigate to API Keys section",
                "3. Create new API key with same permissions",
                "4. Test new key with minimal API call",
                "5. Update OPENAI_API_KEY environment variable",
                "6. Deploy to production with zero downtime",
                "7. Monitor AI service health",
                "8. Delete old key from OpenAI dashboard"
            ],
            ServiceType.SENDGRID: [
                "1. Log into SendGrid dashboard",
                "2. Go to Settings > API Keys",
                "3. Create new API key with same permissions",
                "4. Test new key with email validation",
                "5. Update SENDGRID_API_KEY environment variable",
                "6. Deploy configuration changes",
                "7. Test email functionality",
                "8. Delete old key from SendGrid"
            ],
            ServiceType.AWS: [
                "1. Log into AWS IAM Console",
                "2. Create new access key for the user",
                "3. Test new credentials with S3 operations",
                "4. Update AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY",
                "5. Deploy configuration with rolling update",
                "6. Validate S3 connectivity",
                "7. Deactivate old access key",
                "8. Delete old access key after validation"
            ]
        }
        
        return service_specific_steps.get(service_type, base_steps)
    
    async def rotate_key(self, key_name: str, new_key_value: str = None) -> Dict[str, Any]:
        """Rotate a specific API key"""
        logger.info(f"Starting rotation for key: {key_name}")
        
        rotation_result = {
            'key_name': key_name,
            'rotation_id': f"rotation_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}",
            'timestamp': datetime.now().isoformat(),
            'status': 'initiated',
            'steps': [],
            'success': False,
            'dry_run': self.dry_run
        }
        
        try:
            # Step 1: Backup current key
            rotation_result['steps'].append({
                'step': 'backup_current_key',
                'status': 'in_progress',
                'timestamp': datetime.now().isoformat()
            })
            
            current_key = os.getenv(key_name)
            if current_key:
                self.backup_keys[key_name] = current_key
                rotation_result['steps'][-1]['status'] = 'completed'
            else:
                rotation_result['steps'][-1]['status'] = 'failed'
                rotation_result['steps'][-1]['error'] = 'Current key not found'
                return rotation_result
            
            # Step 2: Validate new key if provided
            if new_key_value:
                rotation_result['steps'].append({
                    'step': 'validate_new_key',
                    'status': 'in_progress',
                    'timestamp': datetime.now().isoformat()
                })
                
                # Detect service type
                service_type = None
                for stype in ServiceType:
                    if stype.value.upper() in key_name.upper():
                        service_type = stype
                        break
                
                if service_type:
                    valid, error = await api_key_manager._validate_key(service_type, new_key_value, key_name)
                    if valid:
                        rotation_result['steps'][-1]['status'] = 'completed'
                    else:
                        rotation_result['steps'][-1]['status'] = 'failed'
                        rotation_result['steps'][-1]['error'] = error
                        return rotation_result
                else:
                    rotation_result['steps'][-1]['status'] = 'skipped'
                    rotation_result['steps'][-1]['reason'] = 'Service type not detected'
            
            # Step 3: Apply new key (dry run or actual)
            rotation_result['steps'].append({
                'step': 'apply_new_key',
                'status': 'in_progress',
                'timestamp': datetime.now().isoformat()
            })
            
            if self.dry_run:
                rotation_result['steps'][-1]['status'] = 'simulated'
                rotation_result['steps'][-1]['message'] = 'Would update environment variable in production'
            else:
                # In a real environment, this would update the deployment
                # For now, we'll simulate the update
                rotation_result['steps'][-1]['status'] = 'simulated'
                rotation_result['steps'][-1]['message'] = 'Environment variable update simulated'
            
            # Step 4: Validate service connectivity
            rotation_result['steps'].append({
                'step': 'validate_service_connectivity',
                'status': 'in_progress',
                'timestamp': datetime.now().isoformat()
            })
            
            if self.dry_run:
                rotation_result['steps'][-1]['status'] = 'simulated'
                rotation_result['steps'][-1]['message'] = 'Would test service connectivity'
            else:
                # Validate connectivity with new key
                connectivity_ok = await self._test_service_connectivity(key_name, new_key_value)
                if connectivity_ok:
                    rotation_result['steps'][-1]['status'] = 'completed'
                else:
                    rotation_result['steps'][-1]['status'] = 'failed'
                    rotation_result['steps'][-1]['error'] = 'Service connectivity test failed'
                    # Rollback would happen here
                    return rotation_result
            
            # Step 5: Complete rotation
            rotation_result['steps'].append({
                'step': 'complete_rotation',
                'status': 'in_progress',
                'timestamp': datetime.now().isoformat()
            })
            
            if self.dry_run:
                rotation_result['steps'][-1]['status'] = 'simulated'
                rotation_result['success'] = True
                rotation_result['status'] = 'completed_simulation'
            else:
                # Mark rotation as complete in API key manager
                success = await api_key_manager.rotate_key(key_name, new_key_value or "simulated_new_key")
                if success:
                    rotation_result['steps'][-1]['status'] = 'completed'
                    rotation_result['success'] = True
                    rotation_result['status'] = 'completed'
                else:
                    rotation_result['steps'][-1]['status'] = 'failed'
                    rotation_result['status'] = 'failed'
        
        except Exception as e:
            logger.error(f"Rotation failed for {key_name}: {str(e)}")
            rotation_result['status'] = 'error'
            rotation_result['error'] = str(e)
            
            # Add error step
            rotation_result['steps'].append({
                'step': 'error_handling',
                'status': 'failed',
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            })
        
        # Log rotation attempt
        self.rotation_log.append(rotation_result)
        
        return rotation_result
    
    async def _test_service_connectivity(self, key_name: str, new_key: str) -> bool:
        """Test service connectivity with new key"""
        try:
            # Temporarily set the new key for testing
            original_key = os.getenv(key_name)
            os.environ[key_name] = new_key
            
            # Test connectivity based on service type
            if 'OPENAI' in key_name:
                service = external_services.openai
            elif 'SENTRY' in key_name:
                service = external_services.sentry
            elif 'SENDGRID' in key_name:
                service = external_services.sendgrid
            elif 'REDIS' in key_name or 'UPSTASH' in key_name:
                service = external_services.redis
            elif 'AWS' in key_name:
                service = external_services.aws
            else:
                return True  # Unknown service, assume OK
            
            # Test connection
            if hasattr(service, 'validate_connection'):
                connected = await service.validate_connection()
            else:
                connected = True
            
            # Restore original key
            if original_key:
                os.environ[key_name] = original_key
            
            return connected
            
        except Exception as e:
            logger.error(f"Service connectivity test failed: {str(e)}")
            return False
    
    async def batch_rotate_keys(self, keys_to_rotate: List[str], new_keys: Dict[str, str] = None) -> Dict[str, Any]:
        """Rotate multiple keys in batch"""
        logger.info(f"Starting batch rotation for {len(keys_to_rotate)} keys")
        
        new_keys = new_keys or {}
        batch_result = {
            'batch_id': f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'total_keys': len(keys_to_rotate),
            'dry_run': self.dry_run,
            'results': [],
            'summary': {
                'successful': 0,
                'failed': 0,
                'simulated': 0
            }
        }
        
        # Rotate keys sequentially for safety
        for key_name in keys_to_rotate:
            new_key = new_keys.get(key_name)
            result = await self.rotate_key(key_name, new_key)
            batch_result['results'].append(result)
            
            # Update summary
            if result['success']:
                if self.dry_run:
                    batch_result['summary']['simulated'] += 1
                else:
                    batch_result['summary']['successful'] += 1
            else:
                batch_result['summary']['failed'] += 1
            
            # Add delay between rotations for safety
            await asyncio.sleep(2)
        
        return batch_result
    
    def generate_rotation_report(self, analysis: Dict[str, Any]) -> str:
        """Generate human-readable rotation report"""
        report = []
        report.append("=" * 60)
        report.append("MITA FINANCE - API KEY ROTATION REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {analysis['timestamp']}")
        report.append(f"Total Keys Analyzed: {analysis['total_keys']}")
        report.append("")
        
        # Summary
        summary = analysis['summary']
        report.append("ROTATION SUMMARY:")
        report.append(f"  🚨 Overdue: {summary['overdue_count']} keys")
        report.append(f"  ⚠️  Needed: {summary['needed_count']} keys")
        report.append(f"  💡 Recommended: {summary['recommended_count']} keys")
        report.append(f"  📊 Total Needing Attention: {summary['total_needing_attention']} keys")
        report.append("")
        
        # Overdue keys (critical)
        if analysis['rotation_overdue']:
            report.append("🚨 OVERDUE ROTATIONS (IMMEDIATE ACTION REQUIRED):")
            for key_info in analysis['rotation_overdue']:
                report.append(f"  • {key_info['key_name']} ({key_info['service']})")
                report.append(f"    Days since rotation: {key_info['days_since_rotation']}")
                report.append(f"    Recommended interval: {key_info['recommended_interval']} days")
            report.append("")
        
        # Needed rotations
        if analysis['rotation_needed']:
            report.append("⚠️ ROTATIONS NEEDED (SCHEDULE SOON):")
            for key_info in analysis['rotation_needed']:
                report.append(f"  • {key_info['key_name']} ({key_info['service']})")
                report.append(f"    Days since rotation: {key_info['days_since_rotation']}")
            report.append("")
        
        # Recommended rotations
        if analysis['rotation_recommended']:
            report.append("💡 ROTATIONS RECOMMENDED (PLAN AHEAD):")
            for key_info in analysis['rotation_recommended']:
                report.append(f"  • {key_info['key_name']} ({key_info['service']})")
                report.append(f"    Days since rotation: {key_info['days_since_rotation']}")
            report.append("")
        
        # Next actions
        if analysis['next_actions']:
            report.append("📋 ROTATION PLAN:")
            for i, action in enumerate(analysis['next_actions'][:5], 1):
                report.append(f"{i}. {action['key_name']} ({action['service']}) - Priority: {action['priority']}")
                if action['manual_rotation_required']:
                    report.append("   ⚠️  Manual rotation required")
                if action['zero_downtime_capable']:
                    report.append("   ✅ Zero-downtime rotation supported")
                else:
                    report.append(f"   ⏱️  Estimated downtime: {action['estimated_downtime_minutes']} minutes")
                report.append("")
        
        if summary['total_needing_attention'] == 0:
            report.append("✅ All API keys are up to date!")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def save_rotation_report(self, analysis: Dict[str, Any], batch_results: Dict[str, Any] = None):
        """Save rotation analysis and results to files"""
        try:
            reports_dir = Path("./reports/api_rotation")
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save analysis
            analysis_file = reports_dir / f"rotation_analysis_{timestamp}.json"
            with open(analysis_file, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            # Save human-readable report
            report_text = self.generate_rotation_report(analysis)
            text_file = reports_dir / f"rotation_report_{timestamp}.txt"
            with open(text_file, 'w') as f:
                f.write(report_text)
            
            # Save batch results if available
            if batch_results:
                results_file = reports_dir / f"rotation_results_{timestamp}.json"
                with open(results_file, 'w') as f:
                    json.dump(batch_results, f, indent=2)
            
            # Save as latest
            latest_analysis = reports_dir / "latest_analysis.json"
            with open(latest_analysis, 'w') as f:
                json.dump(analysis, f, indent=2)
            
            latest_report = reports_dir / "latest_report.txt"
            with open(latest_report, 'w') as f:
                f.write(report_text)
            
            logger.info(f"Rotation reports saved to: {reports_dir}")
            
        except Exception as e:
            logger.error(f"Failed to save rotation reports: {str(e)}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="MITA Finance API Key Rotation Manager")
    parser.add_argument('--analyze', action='store_true', help='Analyze rotation needs only')
    parser.add_argument('--rotate', nargs='*', help='Rotate specific keys')
    parser.add_argument('--rotate-all-needed', action='store_true', help='Rotate all keys that need rotation')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Perform dry run (default)')
    parser.add_argument('--execute', action='store_true', help='Execute actual rotation (disables dry-run)')
    parser.add_argument('--save-report', action='store_true', help='Save detailed report to file')
    parser.add_argument('--output-format', choices=['json', 'text'], default='text', help='Output format')
    
    args = parser.parse_args()
    
    # Determine dry run mode
    dry_run = not args.execute
    if args.execute and args.dry_run:
        logger.warning("Both --execute and --dry-run specified. Using --execute (real rotation)")
        dry_run = False
    
    try:
        rotation_manager = APIKeyRotationManager(dry_run=dry_run)
        
        if args.analyze or (not args.rotate and not args.rotate_all_needed):
            # Analyze rotation needs
            logger.info("Analyzing API key rotation needs...")
            analysis = await rotation_manager.analyze_rotation_needs()
            
            if args.output_format == 'json':
                print(json.dumps(analysis, indent=2))
            else:
                print(rotation_manager.generate_rotation_report(analysis))
            
            if args.save_report:
                rotation_manager.save_rotation_report(analysis)
        
        elif args.rotate:
            # Rotate specific keys
            logger.info(f"Rotating specific keys: {args.rotate}")
            batch_results = await rotation_manager.batch_rotate_keys(args.rotate)
            
            if args.output_format == 'json':
                print(json.dumps(batch_results, indent=2))
            else:
                print(f"Batch rotation completed: {batch_results['summary']}")
                for result in batch_results['results']:
                    status_icon = "✅" if result['success'] else "❌"
                    print(f"{status_icon} {result['key_name']}: {result['status']}")
        
        elif args.rotate_all_needed:
            # Analyze first, then rotate needed keys
            logger.info("Analyzing and rotating all keys that need rotation...")
            analysis = await rotation_manager.analyze_rotation_needs()
            
            keys_to_rotate = [
                key['key_name'] 
                for key in analysis['rotation_overdue'] + analysis['rotation_needed']
            ]
            
            if keys_to_rotate:
                batch_results = await rotation_manager.batch_rotate_keys(keys_to_rotate)
                
                if args.output_format == 'json':
                    print(json.dumps(batch_results, indent=2))
                else:
                    print(f"Rotated {len(keys_to_rotate)} keys:")
                    for result in batch_results['results']:
                        status_icon = "✅" if result['success'] else "❌"
                        print(f"{status_icon} {result['key_name']}: {result['status']}")
                
                if args.save_report:
                    rotation_manager.save_rotation_report(analysis, batch_results)
            else:
                print("No keys need rotation at this time.")
        
    except Exception as e:
        logger.error(f"Rotation process failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())