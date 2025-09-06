#!/usr/bin/env python3
"""
Python 3.9 Compatibility Verification Script
===========================================
This script verifies that all Python files in the MITA Finance codebase are Python 3.9 compatible.
"""

import ast
import glob
import re
import sys
from pathlib import Path

def check_union_syntax(file_path):
    """Check for Python 3.10+ union syntax (|) in type annotations."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match type union syntax but exclude regex patterns
        union_patterns = [
            r':\s*[A-Za-z][A-Za-z0-9_]*\s*\|\s*[A-Za-z][A-Za-z0-9_]*',  # parameter annotations
            r'->\s*[A-Za-z][A-Za-z0-9_]*\s*\|\s*[A-Za-z][A-Za-z0-9_]*',  # return annotations
        ]
        
        # Patterns to exclude (these are NOT union types)
        exclude_patterns = [
            r're\.compile\(.*\)',  # regex patterns
            r'r["\'].*["\']',      # raw strings (often regex)
        ]
        
        issues = []
        for pattern in union_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                # Check if this match is inside a regex or raw string
                line_start = content.rfind('\n', 0, match.start()) + 1
                line_end = content.find('\n', match.end())
                if line_end == -1:
                    line_end = len(content)
                line_content = content[line_start:line_end]
                
                # Skip if this is in a regex pattern
                is_regex = any(re.search(exclude_pattern, line_content) for exclude_pattern in exclude_patterns)
                if is_regex:
                    continue
                
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    'type': 'union_syntax',
                    'line': line_num,
                    'match': match.group(),
                    'pattern': pattern
                })
        
        return issues
    except Exception as e:
        return [{'type': 'read_error', 'error': str(e)}]

def check_ast_compatibility(file_path):
    """Check if file can be parsed by Python AST (syntax compatibility)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        ast.parse(content)
        return True
    except SyntaxError as e:
        return {'error': str(e), 'line': e.lineno}
    except Exception as e:
        return {'error': str(e), 'line': None}

def main():
    """Main verification function."""
    print("MITA Finance - Python 3.9 Compatibility Verification")
    print("=" * 55)
    print(f"Python version: {sys.version}")
    print()
    
    # Find all Python files
    python_files = []
    for pattern in ['app/**/*.py', 'scripts/**/*.py', '*.py']:
        python_files.extend(glob.glob(pattern, recursive=True))
    
    # Filter out __pycache__ and generated files
    python_files = [f for f in python_files if '__pycache__' not in f and '.pyc' not in f]
    
    print(f"Found {len(python_files)} Python files to check")
    print()
    
    # Check for compatibility issues
    total_issues = 0
    files_with_issues = 0
    
    for file_path in python_files:
        print(f"Checking: {file_path}", end=" ... ")
        
        # Check union syntax
        union_issues = check_union_syntax(file_path)
        
        # Check AST compatibility
        ast_result = check_ast_compatibility(file_path)
        
        if union_issues or ast_result is not True:
            print("ISSUES FOUND")
            files_with_issues += 1
            
            if union_issues:
                print(f"  Union syntax issues:")
                for issue in union_issues:
                    if issue['type'] == 'union_syntax':
                        print(f"    Line {issue['line']}: {issue['match']}")
                    else:
                        print(f"    Error: {issue.get('error', 'Unknown error')}")
                    total_issues += 1
            
            if ast_result is not True:
                print(f"  AST parsing error:")
                print(f"    {ast_result['error']}")
                if ast_result['line']:
                    print(f"    Line: {ast_result['line']}")
                total_issues += 1
        else:
            print("OK")
    
    print()
    print("=" * 55)
    print("VERIFICATION SUMMARY")
    print("=" * 55)
    print(f"Total files checked: {len(python_files)}")
    print(f"Files with issues: {files_with_issues}")
    print(f"Total issues found: {total_issues}")
    
    if total_issues == 0:
        print()
        print("✅ SUCCESS: All Python files are Python 3.9 compatible!")
        print("✅ No union syntax (|) issues found")
        print("✅ All files parse correctly")
        return 0
    else:
        print()
        print("❌ FAILED: Python 3.9 compatibility issues found")
        print("❌ Please fix the issues listed above")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)