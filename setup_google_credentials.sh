#!/bin/bash
# Script to setup Google Cloud Vision credentials

set -e

echo "🔧 Setting up Google Cloud Vision credentials..."

# 1. Create config directory
mkdir -p /home/user/mita_project/config
echo "✅ Created config directory"

# 2. Instructions
echo ""
echo "📋 Next steps:"
echo "1. Copy your downloaded JSON file to:"
echo "   /home/user/mita_project/config/google-vision-credentials.json"
echo ""
echo "2. Run this command:"
echo "   cp ~/Downloads/mita-finance-*.json /home/user/mita_project/config/google-vision-credentials.json"
echo ""
echo "3. Set permissions:"
echo "   chmod 600 /home/user/mita_project/config/google-vision-credentials.json"
echo ""
echo "4. Verify the file:"
echo "   head -n 3 /home/user/mita_project/config/google-vision-credentials.json"
echo ""
echo "   Should show:"
echo "   {"
echo "     \"type\": \"service_account\","
echo "     \"project_id\": \"mita-finance-photo-recognition\","
echo ""
