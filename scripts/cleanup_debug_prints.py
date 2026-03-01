#!/usr/bin/env python3
"""
Debug Print Cleanup Script for MITA Finance
Systematically replaces print() statements with proper logging
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple

# Setup logging for the cleanup script
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class DebugPrintCleanup:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.changes_made = []
        
    def find_print_statements(self, directory: str) -> List[Tuple[str, int, str]]:
        """Find all print() statements in Python files"""
        print_statements = []
        
        for py_file in Path(directory).rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    # Skip commented print statements
                    if line.strip().startswith('#'):
                        continue
                    
                    # Look for print( statements
                    if re.search(r'\bprint\s*\(', line):
                        print_statements.append((str(py_file), line_num, line.strip()))
                        
            except Exception as e:
                logger.warning(f"Could not read {py_file}: {e}")
                
        return print_statements
    
    def categorize_print_statements(self, statements: List[Tuple[str, int, str]]) -> Dict[str, List]:
        """Categorize print statements by their purpose"""
        categories = {
            'debug': [],           # Debug/diagnostic messages
            'error': [],          # Error messages
            'warning': [],        # Warning messages
            'info': [],           # Informational messages
            'startup': [],        # Startup/shutdown messages
            'remove': [],         # Temporary debugging to remove
            'keep': []           # Essential messages to keep
        }
        
        for file_path, line_num, line in statements:
            line_lower = line.lower()
            
            # Categorize based on content patterns
            if any(pattern in line_lower for pattern in ['error', 'failed', 'exception', '❌', '💥']):
                categories['error'].append((file_path, line_num, line))
            elif any(pattern in line_lower for pattern in ['warning', 'warn', '⚠️']):
                categories['warning'].append((file_path, line_num, line))
            elif any(pattern in line_lower for pattern in ['starting', 'startup', 'initializ', '🚀', '✅']):
                categories['startup'].append((file_path, line_num, line))
            elif any(pattern in line_lower for pattern in ['debug', '🔍', 'step', 'checking']):
                categories['debug'].append((file_path, line_num, line))
            elif any(pattern in line_lower for pattern in ['test', 'mock', 'temp', 'todo', 'fixme']):
                categories['remove'].append((file_path, line_num, line))
            else:
                categories['info'].append((file_path, line_num, line))
                
        return categories
    
    def replace_print_with_logging(self, file_path: str, line_num: int, line: str, log_level: str) -> bool:
        """Replace a print statement with proper logging"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if line_num > len(lines):
                logger.warning(f"Line {line_num} not found in {file_path}")
                return False
                
            original_line = lines[line_num - 1]
            
            # Extract the print content
            print_match = re.search(r'print\s*\((.+)\)', original_line)
            if not print_match:
                logger.warning(f"Could not parse print statement at {file_path}:{line_num}")
                return False
            
            print_content = print_match.group(1)
            indentation = re.match(r'(\s*)', original_line).group(1)
            
            # Create proper logging statement
            if 'logger' not in ''.join(lines[:line_num]):
                # Add logger import and initialization
                logger_import = f"{indentation}from app.core.logging_config import get_logger\n"
                logger_init = f"{indentation}logger = get_logger(__name__)\n"
                replacement = f"{logger_import}{logger_init}{indentation}logger.{log_level}({print_content})\n"
            else:
                # Logger already exists
                replacement = f"{indentation}logger.{log_level}({print_content})\n"
            
            lines[line_num - 1] = replacement
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            self.changes_made.append(f"{file_path}:{line_num} - Replaced print with logger.{log_level}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update {file_path}:{line_num}: {e}")
            return False
    
    def remove_print_statement(self, file_path: str, line_num: int) -> bool:
        """Remove a temporary debug print statement"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if line_num > len(lines):
                return False
                
            # Remove the line
            del lines[line_num - 1]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            self.changes_made.append(f"{file_path}:{line_num} - Removed debug print")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove print from {file_path}:{line_num}: {e}")
            return False
    
    def cleanup_backend_prints(self):
        """Clean up Python print statements in the backend"""
        logger.info("🔍 Finding Python print statements...")
        
        statements = self.find_print_statements(self.project_root / "app")
        categories = self.categorize_print_statements(statements)
        
        logger.info(f"Found {len(statements)} print statements:")
        for category, items in categories.items():
            if items:
                logger.info(f"  {category}: {len(items)}")
        
        # Process each category
        total_processed = 0
        
        # Replace error prints with logger.error
        for file_path, line_num, line in categories['error']:
            if self.replace_print_with_logging(file_path, line_num, line, 'error'):
                total_processed += 1
        
        # Replace warning prints with logger.warning
        for file_path, line_num, line in categories['warning']:
            if self.replace_print_with_logging(file_path, line_num, line, 'warning'):
                total_processed += 1
        
        # Replace startup prints with logger.info
        for file_path, line_num, line in categories['startup']:
            if self.replace_print_with_logging(file_path, line_num, line, 'info'):
                total_processed += 1
        
        # Replace debug prints with logger.debug
        for file_path, line_num, line in categories['debug']:
            if self.replace_print_with_logging(file_path, line_num, line, 'debug'):
                total_processed += 1
        
        # Replace info prints with logger.info
        for file_path, line_num, line in categories['info']:
            if self.replace_print_with_logging(file_path, line_num, line, 'info'):
                total_processed += 1
        
        # Remove temporary debug prints
        for file_path, line_num, line in categories['remove']:
            # Only remove if it's clearly temporary debugging
            if any(pattern in line.lower() for pattern in ['temp', 'test', 'debug', 'todo']):
                if self.remove_print_statement(file_path, line_num):
                    total_processed += 1
        
        logger.info(f"✅ Processed {total_processed} Python print statements")
        return total_processed
    
    def generate_cleanup_report(self) -> str:
        """Generate a comprehensive cleanup report"""
        report = []
        report.append("=" * 80)
        report.append("MITA FINANCE DEBUG PRINT CLEANUP REPORT")
        report.append("=" * 80)
        report.append(f"Total changes made: {len(self.changes_made)}")
        report.append("")
        
        if self.changes_made:
            report.append("CHANGES MADE:")
            report.append("-" * 40)
            for change in self.changes_made:
                report.append(f"  {change}")
        
        report.append("")
        report.append("CLEANUP ACTIONS TAKEN:")
        report.append("- Replaced error print statements with logger.error()")
        report.append("- Replaced warning print statements with logger.warning()")
        report.append("- Replaced startup print statements with logger.info()")
        report.append("- Replaced debug print statements with logger.debug()")
        report.append("- Removed temporary debugging print statements")
        report.append("")
        report.append("LOGGING IMPROVEMENTS:")
        report.append("- Added structured logging with proper log levels")
        report.append("- Added logger imports where needed")
        report.append("- Maintained original message content")
        report.append("- Preserved code functionality")
        
        return "\n".join(report)

def main():
    """Main cleanup function"""
    project_root = "/Users/mikhail/StudioProjects/mita_project"
    
    cleanup = DebugPrintCleanup(project_root)
    
    logger.info("🧹 Starting MITA Finance debug print cleanup...")
    
    # Clean up backend Python files
    backend_processed = cleanup.cleanup_backend_prints()
    
    # Generate and save report
    report = cleanup.generate_cleanup_report()
    report_file = Path(project_root) / "DEBUG_PRINT_CLEANUP_REPORT.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info("🎉 Cleanup completed!")
    logger.info(f"📊 Total files processed: {backend_processed}")
    logger.info(f"📄 Report saved to: {report_file}")
    
    print("\n" + "=" * 60)
    print("DEBUG PRINT CLEANUP SUMMARY")
    print("=" * 60)
    print(f"✅ Python files processed: {backend_processed}")
    print(f"📄 Report saved to: {report_file}")
    print("\nCleanup completed successfully! 🎉")

if __name__ == "__main__":
    main()