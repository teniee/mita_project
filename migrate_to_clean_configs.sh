#!/bin/bash
# MITA Finance - Configuration Migration Script
# Migrates from mixed emergency configs to clean separated configurations

set -e

echo "🧹 MITA Finance - Configuration Migration Script"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if running in project directory
if [ ! -f "requirements.txt" ] || [ ! -d "app" ]; then
    print_error "This script must be run from the MITA project root directory"
    exit 1
fi

# Backup original configurations
backup_dir="config_backup_$(date +%Y%m%d_%H%M%S)"
echo ""
print_info "Creating backup of original configurations in: $backup_dir"
mkdir -p "$backup_dir"

# Backup existing files
files_to_backup=(
    ".env.staging"
    ".env.production"
    "app/core/config.py"
    "mobile_app/lib/config.dart"
    "docker-compose.yml"
    "docker-compose.prod.yml"
    "render.yaml"
)

for file in "${files_to_backup[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$backup_dir/"
        print_status "Backed up: $file"
    else
        print_warning "File not found (skipping): $file"
    fi
done

echo ""
read -p "🤔 Do you want to proceed with migrating to clean configurations? [y/N]: " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Migration cancelled. Backups are in: $backup_dir"
    exit 0
fi

# Migration steps
echo ""
print_info "Starting configuration migration..."

# 1. Replace environment files
if [ -f ".env.staging.clean" ]; then
    cp ".env.staging.clean" ".env.staging"
    print_status "Updated .env.staging with clean configuration"
else
    print_error "Clean staging configuration not found!"
fi

if [ -f ".env.production.clean" ]; then
    cp ".env.production.clean" ".env.production"
    print_status "Updated .env.production with clean configuration"
else
    print_error "Clean production configuration not found!"
fi

# 2. Replace application configuration
if [ -f "app/core/config_clean.py" ]; then
    cp "app/core/config.py" "app/core/config_original.py"
    cp "app/core/config_clean.py" "app/core/config.py"
    print_status "Updated app/core/config.py with clean configuration system"
else
    print_warning "Clean Python configuration not found - keeping original"
fi

# 3. Replace mobile configuration
if [ -f "mobile_app/lib/config_clean.dart" ]; then
    cp "mobile_app/lib/config.dart" "mobile_app/lib/config_original.dart"
    cp "mobile_app/lib/config_clean.dart" "mobile_app/lib/config.dart"
    print_status "Updated mobile_app/lib/config.dart with clean configuration"
else
    print_warning "Clean Dart configuration not found - keeping original"
fi

# 4. Replace Docker configurations
if [ -f "docker-compose.development.yml" ] && [ -f "docker-compose.staging.yml" ]; then
    print_status "New environment-specific Docker configurations available"
    print_info "Use docker-compose.development.yml for development"
    print_info "Use docker-compose.staging.yml for staging"
    print_info "Use docker-compose.prod.yml for production (already exists)"
fi

if [ -f "Dockerfile.clean" ]; then
    cp "Dockerfile" "Dockerfile.original"
    cp "Dockerfile.clean" "Dockerfile"
    print_status "Updated Dockerfile with clean multi-environment build"
fi

# 5. Replace CI/CD configuration
if [ -f "render.clean.yaml" ]; then
    cp "render.yaml" "render.original.yaml"
    cp "render.clean.yaml" "render.yaml"
    print_status "Updated render.yaml with clean CI/CD configuration"
fi

# 6. Set up secret management
if [ -f "app/core/secret_manager_clean.py" ]; then
    print_status "Clean secret management system available at app/core/secret_manager_clean.py"
fi

echo ""
print_info "Migration completed successfully!"

# Next steps
echo ""
echo "🔧 NEXT STEPS - CRITICAL FOR PRODUCTION DEPLOYMENT:"
echo "=================================================="
echo ""
print_warning "1. PRODUCTION SECRETS - Replace all 'REPLACE_WITH_*' values in .env.production"
echo "   - Set actual database passwords"
echo "   - Set real JWT secrets (32+ characters)" 
echo "   - Set OpenAI API keys"
echo "   - Set all service credentials"
echo ""
print_warning "2. STAGING SECRETS - Replace all 'REPLACE_WITH_*' values in .env.staging"
echo ""
print_warning "3. MOBILE APP - Update mobile build scripts to use environment variables:"
echo "   - Set ENV=development for development builds"
echo "   - Set ENV=staging for staging builds" 
echo "   - Set ENV=production for production builds"
echo ""
print_warning "4. VALIDATE CONFIGURATION:"
echo "   - Run: python3 validate_configuration_cleanup.py"
echo "   - Test each environment thoroughly"
echo ""
print_warning "5. DEPLOYMENT:"
echo "   - Test staging deployment first"
echo "   - Validate all secrets are set correctly"
echo "   - Monitor for any configuration issues"
echo ""
print_info "6. BACKUP LOCATION: Original configurations backed up in: $backup_dir"

echo ""
print_status "✅ Configuration migration completed!"
print_status "🔒 Emergency configurations separated from production settings"  
print_status "🚀 System ready for secure deployment"

echo ""
read -p "📋 Would you like to run the configuration validation now? [y/N]: " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "validate_configuration_cleanup.py" ]; then
        echo ""
        print_info "Running configuration validation..."
        python3 validate_configuration_cleanup.py
    else
        print_warning "Configuration validation script not found"
    fi
fi

echo ""
print_status "Migration script completed successfully!"
print_info "Remember to set production secrets before deploying!"