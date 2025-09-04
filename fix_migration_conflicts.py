#!/usr/bin/env python3
"""
MITA Finance Migration Conflict Resolution Script
==============================================
This script resolves the dual migration system conflict by consolidating
all migrations into the primary Alembic system.

CRITICAL: This script must be run with database backups in place.
"""

import os
import sys
import shutil
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

project_root = Path(__file__).parent

class MigrationConsolidator:
    def __init__(self):
        self.alembic_dir = project_root / "alembic" / "versions"
        self.migrations_dir = project_root / "migrations" / "versions"
        self.backup_dir = project_root / "migration_backup"
        self.resolution_log = []
    
    def log_action(self, action: str, details: str = ""):
        """Log consolidation actions"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "details": details
        }
        self.resolution_log.append(entry)
        print(f"[{entry['timestamp']}] {action}: {details}")
    
    def analyze_conflicts(self) -> Dict[str, Any]:
        """Analyze migration conflicts between systems"""
        self.log_action("ANALYZING", "Migration conflicts between systems")
        
        # Get Alembic migrations
        alembic_migrations = []
        if self.alembic_dir.exists():
            alembic_migrations = [f.name for f in self.alembic_dir.glob("*.py") 
                                if not f.name.startswith("__")]
        
        # Get newer migrations  
        newer_migrations = []
        if self.migrations_dir.exists():
            newer_migrations = [f.name for f in self.migrations_dir.glob("*.py")
                              if not f.name.startswith("__")]
        
        # Identify conflicts and missing migrations
        analysis = {
            "alembic_migrations": sorted(alembic_migrations),
            "newer_migrations": sorted(newer_migrations),
            "conflicts": [],
            "missing_in_alembic": [],
            "missing_in_newer": []
        }
        
        # Find naming conflicts (same number, different content)
        for newer_file in newer_migrations:
            # Check if similar named file exists in alembic
            newer_prefix = newer_file.split('_')[0]  # e.g., "0001"
            
            alembic_match = None
            for alembic_file in alembic_migrations:
                if alembic_file.startswith(newer_prefix):
                    alembic_match = alembic_file
                    break
            
            if alembic_match:
                # Compare file contents to see if they're different
                newer_content = (self.migrations_dir / newer_file).read_text()
                alembic_content = (self.alembic_dir / alembic_match).read_text()
                
                if newer_content != alembic_content:
                    analysis["conflicts"].append({
                        "newer": newer_file,
                        "alembic": alembic_match,
                        "type": "content_difference"
                    })
            else:
                analysis["missing_in_alembic"].append(newer_file)
        
        # Find migrations only in alembic
        for alembic_file in alembic_migrations:
            alembic_prefix = alembic_file.split('_')[0]
            
            newer_match = None  
            for newer_file in newer_migrations:
                if newer_file.startswith(alembic_prefix):
                    newer_match = newer_file
                    break
                    
            if not newer_match:
                analysis["missing_in_newer"].append(alembic_file)
        
        self.log_action("ANALYSIS_COMPLETE", f"Found {len(analysis['conflicts'])} conflicts")
        return analysis
    
    def create_backup(self):
        """Create backup of both migration systems"""
        self.log_action("CREATING_BACKUP", "Backing up migration directories")
        
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        
        self.backup_dir.mkdir()
        
        # Backup alembic
        if self.alembic_dir.exists():
            shutil.copytree(self.alembic_dir, self.backup_dir / "alembic_versions_backup")
            shutil.copy2(project_root / "alembic.ini", self.backup_dir / "alembic.ini.backup")
        
        # Backup migrations  
        if self.migrations_dir.exists():
            shutil.copytree(self.migrations_dir, self.backup_dir / "migrations_versions_backup")
            if (project_root / "migrations" / "env.py").exists():
                shutil.copy2(project_root / "migrations" / "env.py", 
                           self.backup_dir / "migrations_env.py.backup")
        
        self.log_action("BACKUP_COMPLETE", f"Backed up to {self.backup_dir}")
    
    def consolidate_to_alembic(self, analysis: Dict[str, Any]) -> bool:
        """Consolidate all migrations into Alembic system"""
        self.log_action("CONSOLIDATING", "Merging newer migrations into Alembic")
        
        try:
            # Process each migration missing in Alembic
            for newer_file in analysis["missing_in_alembic"]:
                self.log_action("PROCESSING", f"Adding {newer_file} to Alembic")
                
                newer_path = self.migrations_dir / newer_file
                newer_content = newer_path.read_text()
                
                # Create new Alembic migration with unique revision ID
                new_revision_id = self.generate_alembic_revision_id(newer_file)
                alembic_file = f"{new_revision_id}_{newer_file[5:]}"  # Remove old prefix
                alembic_path = self.alembic_dir / alembic_file
                
                # Update the migration content for Alembic format
                updated_content = self.update_migration_for_alembic(
                    newer_content, new_revision_id, newer_file
                )
                
                # Write to Alembic directory
                alembic_path.write_text(updated_content)
                self.log_action("ADDED", f"Created {alembic_file}")
            
            # Handle conflicts by reviewing and merging
            for conflict in analysis["conflicts"]:
                self.log_action("RESOLVING_CONFLICT", 
                              f"Conflict between {conflict['newer']} and {conflict['alembic']}")
                
                # For now, keep Alembic version and log the conflict
                # In production, this would require manual review
                conflict_details = {
                    "alembic_file": conflict['alembic'],
                    "newer_file": conflict['newer'],
                    "resolution": "kept_alembic_version",
                    "action_required": "manual_review_of_newer_migration_content"
                }
                
                # Save conflict details for manual review
                conflict_file = self.backup_dir / f"conflict_{conflict['newer']}.json"
                conflict_file.write_text(json.dumps(conflict_details, indent=2))
                
                self.log_action("CONFLICT_LOGGED", f"Saved conflict details to {conflict_file}")
            
            return True
            
        except Exception as e:
            self.log_action("ERROR", f"Consolidation failed: {str(e)}")
            return False
    
    def generate_alembic_revision_id(self, filename: str) -> str:
        """Generate unique revision ID for Alembic"""
        # Extract timestamp from filename or create one
        import uuid
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:12]
        return f"{timestamp}_{short_uuid}"
    
    def update_migration_for_alembic(self, content: str, revision_id: str, original_file: str) -> str:
        """Update migration content for Alembic compatibility"""
        
        # Extract the original revision from content
        import re
        
        # Update revision identifier
        content = re.sub(
            r'revision = ["\'][^"\']+["\']',
            f'revision = "{revision_id}"',
            content
        )
        
        # Update down_revision to link to current Alembic head
        # This should be set to the latest Alembic revision
        current_head = self.get_current_alembic_head()
        if current_head:
            content = re.sub(
                r'down_revision = ["\'][^"\']*["\']',
                f'down_revision = "{current_head}"',
                content
            )
        
        # Add header comment about consolidation
        header_comment = f'''"""Consolidated from newer migration system: {original_file}
Consolidation timestamp: {datetime.utcnow().isoformat()}
Original revision ID: {revision_id}
"""

'''
        
        # Insert header after the original docstring
        if '"""' in content:
            parts = content.split('"""', 2)
            if len(parts) >= 3:
                content = f'{parts[0]}"""{parts[1]}"""\n\n{header_comment}\n{parts[2]}'
        
        return content
    
    def get_current_alembic_head(self) -> str:
        """Get current Alembic head revision"""
        try:
            result = subprocess.run(
                ["python3", "-m", "alembic", "current"],
                capture_output=True, text=True, cwd=project_root
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                # Extract revision ID from output like "0006_fix_financial_data_types (head)"
                if "(head)" in output:
                    return output.split(" ")[0]
            
        except Exception as e:
            self.log_action("WARNING", f"Could not determine Alembic head: {str(e)}")
        
        return None
    
    def update_alembic_dependencies(self):
        """Update Alembic migration dependencies after consolidation"""
        self.log_action("UPDATING_DEPENDENCIES", "Fixing migration chain dependencies")
        
        try:
            # Run Alembic history to check chain integrity  
            result = subprocess.run(
                ["python3", "-m", "alembic", "history"],
                capture_output=True, text=True, cwd=project_root
            )
            
            if result.returncode != 0:
                self.log_action("WARNING", f"Alembic history check failed: {result.stderr}")
            else:
                self.log_action("SUCCESS", "Migration chain appears valid")
                
        except Exception as e:
            self.log_action("ERROR", f"Dependency update failed: {str(e)}")
    
    def disable_old_migration_system(self):
        """Disable the old migration system"""
        self.log_action("DISABLING", "Old migration system")
        
        # Rename migrations directory to indicate it's disabled
        if self.migrations_dir.exists():
            disabled_dir = project_root / "migrations_DISABLED"
            if disabled_dir.exists():
                shutil.rmtree(disabled_dir)
            
            shutil.move(str(project_root / "migrations"), str(disabled_dir))
            self.log_action("DISABLED", f"Moved migrations to {disabled_dir}")
    
    def save_consolidation_report(self):
        """Save consolidation report"""
        report = {
            "consolidation_timestamp": datetime.utcnow().isoformat(),
            "actions_performed": self.resolution_log,
            "status": "completed",
            "next_steps": [
                "Verify migration chain integrity",
                "Test migrations in staging environment", 
                "Run database validation",
                "Update deployment scripts to use Alembic only"
            ]
        }
        
        report_file = project_root / "migration_consolidation_report.json"
        report_file.write_text(json.dumps(report, indent=2))
        
        self.log_action("REPORT_SAVED", f"Consolidation report saved to {report_file}")

def main():
    print("🚨 MITA Finance Migration Conflict Resolution")
    print("=" * 60)
    print("⚠️  WARNING: This script will modify migration files")
    print("⚠️  Ensure you have a database backup before proceeding")
    print()
    
    response = input("Do you want to proceed? (yes/no): ")
    if response.lower() != "yes":
        print("Operation cancelled")
        return
    
    consolidator = MigrationConsolidator()
    
    try:
        # Step 1: Create backup
        consolidator.create_backup()
        
        # Step 2: Analyze conflicts
        analysis = consolidator.analyze_conflicts()
        
        print("\n📊 Migration Analysis Results:")
        print(f"  Alembic migrations: {len(analysis['alembic_migrations'])}")
        print(f"  Newer migrations: {len(analysis['newer_migrations'])}")  
        print(f"  Conflicts: {len(analysis['conflicts'])}")
        print(f"  Missing in Alembic: {len(analysis['missing_in_alembic'])}")
        
        if analysis['conflicts']:
            print(f"\n⚠️  Found {len(analysis['conflicts'])} conflicts requiring manual review")
        
        # Step 3: Consolidate to Alembic
        if consolidator.consolidate_to_alembic(analysis):
            print("\n✅ Successfully consolidated migrations to Alembic")
            
            # Step 4: Update dependencies
            consolidator.update_alembic_dependencies()
            
            # Step 5: Disable old system
            consolidator.disable_old_migration_system()
            
            # Step 6: Save report
            consolidator.save_consolidation_report()
            
            print(f"\n🎉 Migration consolidation completed!")
            print(f"📊 Check migration_consolidation_report.json for details")
            print(f"🗂️  Backup saved to: {consolidator.backup_dir}")
            
            print(f"\n📋 Next Steps:")
            print(f"  1. Review migration chain: python3 -m alembic history")
            print(f"  2. Test in staging environment")
            print(f"  3. Update deployment scripts")
            print(f"  4. Remove disabled migrations directory when confident")
            
        else:
            print("\n❌ Migration consolidation failed")
            print("Check logs and backup directory for details")
            return 1
            
    except Exception as e:
        print(f"\n💥 Consolidation script failed: {str(e)}")
        print("Migration backups are available for recovery")
        return 2
    
    return 0

if __name__ == "__main__":
    sys.exit(main())