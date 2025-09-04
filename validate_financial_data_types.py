#!/usr/bin/env python3
"""
MITA Finance Financial Data Type Validation Script
===============================================
Validates that all financial columns use proper Numeric types
instead of Float to prevent precision errors in financial calculations.

This is CRITICAL for financial compliance and data integrity.
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import psycopg2
from psycopg2.extras import RealDictCursor

class FinancialDataTypeValidator:
    """Validator for financial data types in MITA database"""
    
    def __init__(self):
        self.db_url = self.get_database_url()
        self.validation_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "running",
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
            "column_analysis": {},
            "compliance_status": "unknown"
        }
        
        # Critical financial columns that MUST use Numeric type
        self.critical_financial_columns = {
            "transactions": ["amount"],
            "expenses": ["amount"],
            "users": ["annual_income"],
            "goals": ["target_amount", "saved_amount"],
            "subscriptions": ["price", "amount"] if self.table_exists("subscriptions") else [],
            "budget_advice": ["suggested_amount"] if self.table_exists("budget_advice") else []
        }
    
    def get_database_url(self) -> str:
        """Get database URL from environment or alembic.ini"""
        db_url = os.getenv("DATABASE_URL")
        
        if not db_url:
            # Try to get from alembic.ini
            alembic_ini = os.path.join(project_root, "alembic.ini")
            if os.path.exists(alembic_ini):
                with open(alembic_ini, 'r') as f:
                    for line in f:
                        if line.startswith("sqlalchemy.url"):
                            db_url = line.split("=", 1)[1].strip()
                            break
        
        if not db_url:
            raise Exception("DATABASE_URL not found in environment or alembic.ini")
        
        return db_url
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists in database"""
        try:
            conn = psycopg2.connect(self.db_url)
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    );
                """, (table_name,))
                return cursor.fetchone()[0]
        except Exception:
            return False
        finally:
            try:
                conn.close()
            except:
                pass
    
    def add_critical_issue(self, issue: str):
        """Add a critical compliance issue"""
        self.validation_results["critical_issues"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "issue": issue,
            "severity": "CRITICAL"
        })
        print(f"🚨 CRITICAL: {issue}")
    
    def add_warning(self, warning: str):
        """Add a warning"""
        self.validation_results["warnings"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "warning": warning,
            "severity": "WARNING"  
        })
        print(f"⚠️ WARNING: {warning}")
    
    def add_recommendation(self, recommendation: str):
        """Add a recommendation"""
        self.validation_results["recommendations"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "recommendation": recommendation,
            "priority": "HIGH"
        })
        print(f"💡 RECOMMENDATION: {recommendation}")
    
    def validate_financial_data_types(self):
        """Main validation of financial data types"""
        print("🔍 Validating Financial Data Types...")
        print("=" * 50)
        
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            total_issues = 0
            total_columns_checked = 0
            
            for table_name, columns in self.critical_financial_columns.items():
                if not columns:  # Skip if table doesn't exist
                    continue
                    
                print(f"\n📊 Analyzing table: {table_name}")
                
                # Get column information
                cursor.execute("""
                    SELECT 
                        column_name,
                        data_type,
                        numeric_precision,
                        numeric_scale,
                        is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = %s 
                    AND table_schema = 'public'
                    ORDER BY column_name
                """, (table_name,))
                
                table_columns = cursor.fetchall()
                table_analysis = {
                    "columns_found": len(table_columns),
                    "financial_columns": {},
                    "issues": []
                }
                
                for column_info in table_columns:
                    column_name = column_info['column_name']
                    
                    if column_name in columns:
                        total_columns_checked += 1
                        
                        data_type = column_info['data_type']
                        precision = column_info['numeric_precision']
                        scale = column_info['numeric_scale']
                        nullable = column_info['is_nullable']
                        
                        column_analysis = {
                            "data_type": data_type,
                            "numeric_precision": precision,
                            "numeric_scale": scale,
                            "is_nullable": nullable,
                            "compliance_status": "unknown",
                            "issues": []
                        }
                        
                        # Critical validation: Check for Float types
                        if data_type in ['double precision', 'real', 'float8', 'float4']:
                            issue = f"Table {table_name}.{column_name} uses {data_type} instead of NUMERIC - CRITICAL precision risk"
                            self.add_critical_issue(issue)
                            column_analysis["compliance_status"] = "CRITICAL_VIOLATION"
                            column_analysis["issues"].append(issue)
                            table_analysis["issues"].append(issue)
                            total_issues += 1
                            
                        # Check for proper Numeric configuration
                        elif data_type == 'numeric':
                            if precision is None or scale is None:
                                issue = f"Table {table_name}.{column_name} uses NUMERIC without precision/scale specification"
                                self.add_warning(issue)
                                column_analysis["compliance_status"] = "WARNING"
                                column_analysis["issues"].append(issue)
                            elif precision < 12 or scale != 2:
                                issue = f"Table {table_name}.{column_name} uses NUMERIC({precision},{scale}) - recommend NUMERIC(12,2) for financial data"
                                self.add_warning(issue)
                                column_analysis["compliance_status"] = "SUBOPTIMAL"
                                column_analysis["issues"].append(issue)
                            else:
                                print(f"    ✅ {column_name}: NUMERIC({precision},{scale}) - COMPLIANT")
                                column_analysis["compliance_status"] = "COMPLIANT"
                        
                        # Check for other problematic types
                        elif data_type in ['integer', 'bigint', 'smallint']:
                            issue = f"Table {table_name}.{column_name} uses {data_type} - may not support decimal amounts"
                            self.add_warning(issue)
                            column_analysis["compliance_status"] = "WARNING"
                            column_analysis["issues"].append(issue)
                        
                        # Unknown/other types
                        else:
                            issue = f"Table {table_name}.{column_name} uses unexpected type: {data_type}"
                            self.add_warning(issue)
                            column_analysis["compliance_status"] = "UNKNOWN"
                            column_analysis["issues"].append(issue)
                        
                        table_analysis["financial_columns"][column_name] = column_analysis
                
                self.validation_results["column_analysis"][table_name] = table_analysis
                
                if table_analysis["issues"]:
                    print(f"    ⚠️ Found {len(table_analysis['issues'])} issues in {table_name}")
                else:
                    print(f"    ✅ No issues found in {table_name}")
            
            cursor.close()
            conn.close()
            
            # Overall compliance assessment
            critical_count = len(self.validation_results["critical_issues"])
            warning_count = len(self.validation_results["warnings"])
            
            print(f"\n📊 Validation Summary:")
            print(f"  Total financial columns checked: {total_columns_checked}")
            print(f"  Critical issues: {critical_count}")
            print(f"  Warnings: {warning_count}")
            
            if critical_count > 0:
                self.validation_results["compliance_status"] = "CRITICAL_VIOLATIONS"
                self.validation_results["status"] = "failed"
                print(f"🚨 CRITICAL VIOLATIONS DETECTED - FINANCIAL COMPLIANCE AT RISK")
            elif warning_count > 0:
                self.validation_results["compliance_status"] = "WARNINGS"  
                self.validation_results["status"] = "warnings"
                print(f"⚠️ Warnings found - should be addressed for optimal compliance")
            else:
                self.validation_results["compliance_status"] = "COMPLIANT"
                self.validation_results["status"] = "passed"
                print(f"✅ All financial data types are compliant")
                
        except Exception as e:
            error = f"Financial data type validation failed: {str(e)}"
            self.add_critical_issue(error)
            self.validation_results["status"] = "error"
            print(f"💥 {error}")
    
    def check_data_samples(self):
        """Check actual data samples for precision issues"""
        print(f"\n🔍 Checking Data Samples for Precision Issues...")
        
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            precision_checks = [
                ("transactions", "amount", "Check for floating point precision artifacts"),
                ("expenses", "amount", "Check for floating point precision artifacts"),
            ]
            
            for table, column, description in precision_checks:
                print(f"  Checking {table}.{column}...")
                
                try:
                    # Check for values with more than 2 decimal places (precision artifacts)
                    cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM {table} 
                        WHERE {column}::text ~ '\\.[0-9]{{3,}}'
                        LIMIT 5
                    """)
                    
                    precision_artifacts = cursor.fetchone()[0]
                    
                    if precision_artifacts > 0:
                        issue = f"Found {precision_artifacts} records in {table}.{column} with >2 decimal places - likely Float precision artifacts"
                        self.add_critical_issue(issue)
                    else:
                        print(f"    ✅ No precision artifacts found in {table}.{column}")
                        
                    # Check for very small fractional amounts (common with Float errors)
                    cursor.execute(f"""
                        SELECT COUNT(*)
                        FROM {table}
                        WHERE {column} > 0 
                        AND {column} < 0.01
                        AND {column}::text ~ '\\.[0-9]{{3,}}'
                    """)
                    
                    tiny_amounts = cursor.fetchone()[0]
                    
                    if tiny_amounts > 0:
                        issue = f"Found {tiny_amounts} records in {table}.{column} with tiny fractional amounts - possible Float precision errors"
                        self.add_warning(issue)
                        
                except Exception as e:
                    print(f"    ⚠️ Could not check {table}.{column}: {str(e)}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            error = f"Data sample validation failed: {str(e)}"
            self.add_warning(error)
    
    def generate_fix_sql(self):
        """Generate SQL statements to fix data type issues"""
        print(f"\n🔧 Generating Fix SQL Statements...")
        
        fix_statements = []
        
        for table_name, table_analysis in self.validation_results["column_analysis"].items():
            for column_name, column_info in table_analysis["financial_columns"].items():
                if column_info["compliance_status"] in ["CRITICAL_VIOLATION", "WARNING", "SUBOPTIMAL"]:
                    
                    current_type = column_info["data_type"]
                    
                    if current_type in ['double precision', 'real', 'float8', 'float4']:
                        # Critical: Convert Float to Numeric
                        fix_sql = f"""
-- CRITICAL: Fix {table_name}.{column_name} - Float to Numeric conversion
ALTER TABLE {table_name} 
ALTER COLUMN {column_name} 
TYPE NUMERIC(12,2) 
USING {column_name}::NUMERIC(12,2);
"""
                        fix_statements.append(fix_sql)
                        
                    elif current_type == 'numeric' and (
                        column_info["numeric_precision"] != 12 or 
                        column_info["numeric_scale"] != 2
                    ):
                        # Optimize precision
                        fix_sql = f"""
-- OPTIMIZE: Standardize {table_name}.{column_name} precision
ALTER TABLE {table_name}
ALTER COLUMN {column_name}
TYPE NUMERIC(12,2);
"""
                        fix_statements.append(fix_sql)
        
        if fix_statements:
            fix_file = os.path.join(project_root, "fix_financial_data_types.sql")
            with open(fix_file, 'w') as f:
                f.write("-- MITA Finance Data Type Fix Script\n")
                f.write(f"-- Generated: {datetime.utcnow().isoformat()}\n")
                f.write("-- CRITICAL: Run this script during maintenance window\n")
                f.write("-- BACKUP DATABASE BEFORE RUNNING\n\n")
                f.write("BEGIN;\n\n")
                
                for statement in fix_statements:
                    f.write(statement)
                    f.write("\n")
                
                f.write("\n-- Verify changes\n")
                f.write("SELECT table_name, column_name, data_type, numeric_precision, numeric_scale\n")
                f.write("FROM information_schema.columns\n")
                f.write("WHERE table_name IN ('transactions', 'expenses', 'users', 'goals')\n")
                f.write("AND column_name LIKE '%amount%'\n")
                f.write("ORDER BY table_name, column_name;\n\n")
                f.write("COMMIT;\n")
            
            print(f"🔧 Fix SQL generated: {fix_file}")
            self.add_recommendation(f"Run fix script: {fix_file}")
        else:
            print("✅ No fix SQL needed - data types are compliant")
    
    def save_validation_report(self):
        """Save validation report to file"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(project_root, f"financial_data_validation_{timestamp}.json")
        
        with open(report_file, 'w') as f:
            json.dump(self.validation_results, f, indent=2)
        
        print(f"📊 Validation report saved: {report_file}")
        return report_file

def main():
    print("🏦 MITA Finance Data Type Validation")
    print("=" * 50)
    print("Validating financial column data types for compliance...")
    print()
    
    try:
        validator = FinancialDataTypeValidator()
        
        # Run validation
        validator.validate_financial_data_types()
        validator.check_data_samples()
        validator.generate_fix_sql()
        
        # Save report
        report_file = validator.save_validation_report()
        
        print(f"\n📋 Validation Complete")
        print(f"📊 Report: {report_file}")
        
        # Exit with appropriate code
        critical_issues = len(validator.validation_results["critical_issues"])
        if critical_issues > 0:
            print(f"\n🚨 CRITICAL: {critical_issues} critical issues found")
            print("🚫 Financial compliance violations detected - fix immediately")
            return 1
        elif len(validator.validation_results["warnings"]) > 0:
            print(f"\n⚠️ Warnings found - should be addressed")
            return 0
        else:
            print(f"\n✅ All financial data types are compliant")
            return 0
            
    except Exception as e:
        print(f"💥 Validation failed: {str(e)}")
        return 2

if __name__ == "__main__":
    sys.exit(main())