#!/bin/bash
# Migration Script for MITA Backend
# This script creates and runs database migrations for the new models

set -e  # Exit on error

echo "=================================================="
echo "MITA Database Migration Script"
echo "=================================================="
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is not set"
    echo ""
    echo "Please set your database URL:"
    echo "  export DATABASE_URL='postgresql://user:password@localhost:5432/mita_db'"
    echo ""
    echo "Or if using .env file, run:"
    echo "  source .env"
    echo ""
    exit 1
fi

echo "✅ DATABASE_URL is configured"
echo ""

# Show current database URL (masked for security)
DB_URL_MASKED=$(echo $DATABASE_URL | sed 's/:\/\/[^:]*:[^@]*@/:\/\/***:***@/')
echo "📊 Database: $DB_URL_MASKED"
echo ""

# Create migration
echo "📝 Creating migration for new models..."
echo "   - Challenge & ChallengeParticipation"
echo "   - OCRJob"
echo "   - FeatureUsageLog, FeatureAccessLog, PaywallImpressionLog"
echo "   - UserPreference"
echo ""

python3 -m alembic revision --autogenerate -m "Add challenge, OCR, analytics, and preference models"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration created successfully!"
    echo ""
else
    echo ""
    echo "❌ Migration creation failed"
    exit 1
fi

# Ask user if they want to apply migration
echo "=================================================="
echo "Apply migration to database?"
echo "=================================================="
echo ""
echo "This will create the following tables:"
echo "  - challenges"
echo "  - challenge_participations"
echo "  - ocr_jobs"
echo "  - feature_usage_logs"
echo "  - feature_access_logs"
echo "  - paywall_impression_logs"
echo "  - user_preferences"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    echo ""
    echo "🚀 Applying migration..."
    python3 -m alembic upgrade head

    if [ $? -eq 0 ]; then
        echo ""
        echo "=================================================="
        echo "✅ MIGRATION COMPLETE!"
        echo "=================================================="
        echo ""
        echo "All new tables have been created successfully."
        echo "Your backend is now ready for production!"
        echo ""
    else
        echo ""
        echo "❌ Migration failed"
        exit 1
    fi
else
    echo ""
    echo "Migration cancelled. Run this script again when ready."
    echo ""
fi
