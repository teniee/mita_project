#!/bin/bash
# Script to apply Analytics Module migration to Supabase
# This script applies migration 0013_add_analytics_tables.py

set -e  # Exit on error

echo "🚀 MITA Analytics Migration Script"
echo "===================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ ERROR: DATABASE_URL environment variable is not set${NC}"
    echo ""
    echo "Please set your Supabase DATABASE_URL:"
    echo "export DATABASE_URL='postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres'"
    echo ""
    echo "Example:"
    echo "export DATABASE_URL='postgresql://postgres:mypassword@db.xxxxx.supabase.co:5432/postgres'"
    exit 1
fi

echo -e "${GREEN}✅ DATABASE_URL is set${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "alembic.ini" ]; then
    echo -e "${RED}❌ ERROR: alembic.ini not found${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

echo -e "${GREEN}✅ Found alembic.ini${NC}"
echo ""

# Check if migration file exists
MIGRATION_FILE="alembic/versions/0013_add_analytics_tables.py"
if [ ! -f "$MIGRATION_FILE" ]; then
    echo -e "${RED}❌ ERROR: Migration file not found: $MIGRATION_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found migration file: $MIGRATION_FILE${NC}"
echo ""

# Show current migration status
echo "📊 Current migration status:"
echo "----------------------------"
python3 -c "
import subprocess
try:
    result = subprocess.run(['alembic', 'current'], capture_output=True, text=True, check=True)
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print('Could not get current status')
    print(e.stderr)
"
echo ""

# Ask for confirmation
echo -e "${YELLOW}⚠️  This will apply the following changes to your Supabase database:${NC}"
echo "   1. Create table: feature_usage_logs"
echo "   2. Create table: feature_access_logs"
echo "   3. Create table: paywall_impression_logs"
echo "   4. Add indexes for performance"
echo ""
read -p "Do you want to continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Migration cancelled${NC}"
    exit 0
fi

# Create backup reminder
echo -e "${YELLOW}💡 IMPORTANT: Make sure you have a recent database backup!${NC}"
echo "   You can create a backup in Supabase Dashboard > Database > Backups"
echo ""
read -p "Do you have a recent backup? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${RED}Please create a backup before proceeding${NC}"
    exit 0
fi

# Apply migration
echo "🔄 Applying migration..."
echo "========================"
echo ""

if python3 -m alembic upgrade head; then
    echo ""
    echo -e "${GREEN}✅ Migration applied successfully!${NC}"
    echo ""

    # Show new migration status
    echo "📊 New migration status:"
    echo "------------------------"
    python3 -c "
import subprocess
try:
    result = subprocess.run(['alembic', 'current'], capture_output=True, text=True, check=True)
    print(result.stdout)
except subprocess.CalledProcessError as e:
    print('Could not get current status')
"
    echo ""

    # Verify tables were created
    echo "🔍 Verifying tables were created..."
    echo "------------------------------------"
    python3 << 'EOF'
import os
import psycopg2

db_url = os.environ.get("DATABASE_URL")
try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    tables = ['feature_usage_logs', 'feature_access_logs', 'paywall_impression_logs']

    for table in tables:
        cur.execute(f"""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = '{table}'
        """)
        exists = cur.fetchone()[0]

        if exists:
            print(f"✅ Table '{table}' exists")
        else:
            print(f"❌ Table '{table}' NOT found")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error verifying tables: {e}")
EOF

    echo ""
    echo -e "${GREEN}🎉 Analytics module migration completed successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Test the analytics endpoints in your API"
    echo "2. Update your Flutter app to use the new AnalyticsService"
    echo "3. Monitor the application logs for any issues"
    echo ""

else
    echo ""
    echo -e "${RED}❌ Migration failed!${NC}"
    echo ""
    echo "Please check the error messages above."
    echo "You can rollback using: alembic downgrade -1"
    echo ""
    exit 1
fi
