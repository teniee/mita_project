#!/bin/bash
# =====================================================================
# MITA Subscription System Deployment Script
# =====================================================================
# This script deploys the complete subscription management system
# with proper security, monitoring, and production configurations.

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_ENV="${DEPLOY_ENV:-production}"
VERSION="${VERSION:-1.0.0}"
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF="${VCS_REF:-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Error handling
error_exit() {
    log_error "$1"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required commands
    local required_commands=("docker" "docker-compose" "python3" "psql" "git")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            error_exit "$cmd is required but not installed."
        fi
    done
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        error_exit "Docker daemon is not running."
    fi
    
    # Check minimum Docker Compose version
    local compose_version
    compose_version=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    if [[ $(echo "$compose_version 1.27.0" | tr " " "\n" | sort -V | head -n1) != "1.27.0" ]]; then
        error_exit "Docker Compose version 1.27.0 or higher is required. Found: $compose_version"
    fi
    
    # Check Python version
    local python_version
    python_version=$(python3 --version | grep -oE '[0-9]+\.[0-9]+')
    if [[ $(echo "$python_version 3.11" | tr " " "\n" | sort -V | head -n1) != "3.11" ]]; then
        error_exit "Python 3.11 or higher is required. Found: $python_version"
    fi
    
    log_success "Prerequisites check passed"
}

# Validate environment configuration
validate_environment() {
    log_info "Validating environment configuration..."
    
    # Check for required environment variables
    local required_vars=(
        "DB_PASSWORD"
        "APPLE_SHARED_SECRET"
        "GOOGLE_PACKAGE_NAME"
        "SENTRY_DSN"
    )
    
    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        printf '%s\n' "${missing_vars[@]}"
        error_exit "Please set all required environment variables"
    fi
    
    # Check for secrets directory
    if [[ ! -d "$SCRIPT_DIR/secrets" ]]; then
        log_warning "Secrets directory not found. Creating..."
        mkdir -p "$SCRIPT_DIR/secrets"
        chmod 700 "$SCRIPT_DIR/secrets"
    fi
    
    # Check for Google service account file
    if [[ ! -f "$SCRIPT_DIR/secrets/google_service_account.json" ]]; then
        error_exit "Google service account file not found at $SCRIPT_DIR/secrets/google_service_account.json"
    fi
    
    log_success "Environment configuration validated"
}

# Setup database
setup_database() {
    log_info "Setting up database..."
    
    # Start database service
    docker-compose -f "$SCRIPT_DIR/docker-compose.subscription.yml" up -d postgres
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if docker-compose -f "$SCRIPT_DIR/docker-compose.subscription.yml" exec -T postgres pg_isready -U "${DB_USER:-mita_subscription}" &> /dev/null; then
            break
        fi
        ((attempt++))
        sleep 2
    done
    
    if [[ $attempt -eq $max_attempts ]]; then
        error_exit "Database failed to become ready within expected time"
    fi
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose -f "$SCRIPT_DIR/docker-compose.subscription.yml" exec -T postgres psql -U "${DB_USER:-mita_subscription}" -d "${DB_NAME:-mita}" -f /docker-entrypoint-initdb.d/01-schema.sql
    
    log_success "Database setup completed"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    
    # Build subscription manager image
    docker build \
        -f "$SCRIPT_DIR/Dockerfile.subscription-manager" \
        --build-arg BUILD_DATE="$BUILD_DATE" \
        --build-arg VCS_REF="$VCS_REF" \
        --build-arg VERSION="$VERSION" \
        -t "mita/subscription-manager:$VERSION" \
        -t "mita/subscription-manager:latest" \
        "$SCRIPT_DIR"
    
    log_success "Docker images built successfully"
}

# Deploy services
deploy_services() {
    log_info "Deploying services..."
    
    # Set environment variables for Docker Compose
    export BUILD_DATE
    export VCS_REF
    export VERSION
    
    # Deploy all services
    docker-compose -f "$SCRIPT_DIR/docker-compose.subscription.yml" up -d
    
    # Wait for services to be healthy
    log_info "Waiting for services to become healthy..."
    local services=("subscription-manager" "postgres" "redis" "prometheus" "grafana")
    local max_wait=300  # 5 minutes
    local start_time
    start_time=$(date +%s)
    
    for service in "${services[@]}"; do
        log_info "Checking health of $service..."
        while true; do
            local current_time
            current_time=$(date +%s)
            if [[ $((current_time - start_time)) -gt $max_wait ]]; then
                error_exit "Service $service failed to become healthy within $max_wait seconds"
            fi
            
            local health_status
            health_status=$(docker-compose -f "$SCRIPT_DIR/docker-compose.subscription.yml" ps -q "$service" | xargs docker inspect --format='{{.State.Health.Status}}' 2>/dev/null || echo "unhealthy")
            
            if [[ "$health_status" == "healthy" ]] || [[ "$health_status" == "" ]]; then
                log_success "$service is healthy"
                break
            fi
            
            sleep 10
        done
    done
    
    log_success "All services are running and healthy"
}

# Setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring and alerting..."
    
    # Import Grafana dashboards
    local grafana_url="http://localhost:3000"
    local max_attempts=30
    local attempt=0
    
    # Wait for Grafana to be ready
    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s "$grafana_url/api/health" &> /dev/null; then
            break
        fi
        ((attempt++))
        sleep 2
    done
    
    if [[ $attempt -eq $max_attempts ]]; then
        log_warning "Grafana not ready for dashboard import"
    else
        log_info "Grafana is ready, dashboards will be auto-provisioned"
    fi
    
    # Setup log rotation
    if command -v logrotate &> /dev/null; then
        log_info "Setting up log rotation..."
        sudo cp "$SCRIPT_DIR/config/logrotate.d/mita-subscription" /etc/logrotate.d/
        sudo chown root:root /etc/logrotate.d/mita-subscription
        sudo chmod 644 /etc/logrotate.d/mita-subscription
    fi
    
    log_success "Monitoring setup completed"
}

# Setup cron jobs
setup_cron_jobs() {
    log_info "Setting up cron jobs..."
    
    # Install subscription management cron jobs
    if command -v crontab &> /dev/null; then
        # Create a temporary crontab file
        local temp_cron=$(mktemp)
        
        # Get existing crontab (if any) and filter out MITA entries
        (crontab -l 2>/dev/null | grep -v "# MITA Subscription Management" || true) > "$temp_cron"
        
        # Add MITA subscription management jobs
        echo "# MITA Subscription Management - Auto-generated $(date)" >> "$temp_cron"
        cat "$SCRIPT_DIR/crontab_subscription_management" >> "$temp_cron"
        
        # Install the new crontab
        crontab "$temp_cron"
        rm "$temp_cron"
        
        log_success "Cron jobs installed successfully"
    else
        log_warning "crontab not available - cron jobs not installed"
    fi
}

# Run smoke tests
run_smoke_tests() {
    log_info "Running smoke tests..."
    
    # Test subscription manager health endpoint
    if curl -f -s "http://localhost:8080/health" > /dev/null; then
        log_success "Subscription manager health check passed"
    else
        log_error "Subscription manager health check failed"
        return 1
    fi
    
    # Test database connectivity
    if docker-compose -f "$SCRIPT_DIR/docker-compose.subscription.yml" exec -T postgres pg_isready -U "${DB_USER:-mita_subscription}" &> /dev/null; then
        log_success "Database connectivity test passed"
    else
        log_error "Database connectivity test failed"
        return 1
    fi
    
    # Test Redis connectivity
    if docker-compose -f "$SCRIPT_DIR/docker-compose.subscription.yml" exec -T redis redis-cli ping | grep -q PONG; then
        log_success "Redis connectivity test passed"
    else
        log_error "Redis connectivity test failed"
        return 1
    fi
    
    # Test Prometheus metrics
    if curl -f -s "http://localhost:9090/api/v1/query?query=up" > /dev/null; then
        log_success "Prometheus metrics test passed"
    else
        log_error "Prometheus metrics test failed"
        return 1
    fi
    
    # Test Grafana
    if curl -f -s "http://localhost:3000/api/health" > /dev/null; then
        log_success "Grafana health test passed"
    else
        log_error "Grafana health test failed"
        return 1
    fi
    
    log_success "All smoke tests passed"
}

# Generate deployment report
generate_deployment_report() {
    log_info "Generating deployment report..."
    
    local report_file="/tmp/mita-subscription-deployment-report-$(date +%Y%m%d-%H%M%S).txt"
    
    cat > "$report_file" << EOF
# MITA Subscription Management System - Deployment Report
Generated: $(date)
Environment: $DEPLOY_ENV
Version: $VERSION
Build Date: $BUILD_DATE
VCS Ref: $VCS_REF

## Service Status
EOF
    
    # Add service status to report
    docker-compose -f "$SCRIPT_DIR/docker-compose.subscription.yml" ps >> "$report_file"
    
    cat >> "$report_file" << EOF

## Service URLs
- Subscription Manager Health: http://localhost:8080/health
- Subscription Manager Metrics: http://localhost:8080/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Default Credentials
- Grafana: admin / ${GRAFANA_ADMIN_PASSWORD:-admin123}

## Important Directories
- Scripts: $SCRIPT_DIR
- Secrets: $SCRIPT_DIR/secrets
- Configuration: $SCRIPT_DIR/config
- Logs: /var/log/mita (in containers)

## Next Steps
1. Update default passwords
2. Configure SSL certificates
3. Set up external monitoring alerts
4. Review security configurations
5. Schedule regular backups

## Troubleshooting
- View logs: docker-compose -f $SCRIPT_DIR/docker-compose.subscription.yml logs [service]
- Restart service: docker-compose -f $SCRIPT_DIR/docker-compose.subscription.yml restart [service]
- View metrics: curl http://localhost:8080/metrics
- Check health: curl http://localhost:8080/health

EOF
    
    log_success "Deployment report generated: $report_file"
    echo "$report_file"
}

# Main deployment function
main() {
    log_info "Starting MITA Subscription Management System deployment..."
    log_info "Environment: $DEPLOY_ENV"
    log_info "Version: $VERSION"
    log_info "Build Date: $BUILD_DATE"
    log_info "VCS Ref: $VCS_REF"
    
    # Run deployment steps
    check_prerequisites
    validate_environment
    build_images
    setup_database
    deploy_services
    setup_monitoring
    setup_cron_jobs
    
    # Run tests
    if ! run_smoke_tests; then
        log_error "Smoke tests failed - deployment may have issues"
        exit 1
    fi
    
    # Generate report
    local report_file
    report_file=$(generate_deployment_report)
    
    log_success "MITA Subscription Management System deployed successfully!"
    log_info "Deployment report: $report_file"
    
    # Display final status
    echo
    log_info "Service URLs:"
    echo "  - Subscription Manager: http://localhost:8080"
    echo "  - Grafana Dashboard: http://localhost:3000"
    echo "  - Prometheus: http://localhost:9090"
    echo
    log_info "To view logs: docker-compose -f $SCRIPT_DIR/docker-compose.subscription.yml logs -f"
    log_info "To stop services: docker-compose -f $SCRIPT_DIR/docker-compose.subscription.yml down"
}

# Handle script interruption
trap 'log_error "Deployment interrupted"; exit 1' INT TERM

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi