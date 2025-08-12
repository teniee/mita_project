#!/bin/bash

# MITA Task Queue Production Deployment Script
# This script deploys and configures the task queue system for production

set -e  # Exit on any error
set -u  # Exit on undefined variables

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
NUM_WORKERS="${NUM_WORKERS:-6}"
ENABLE_MONITORING="${ENABLE_MONITORING:-true}"
WORKER_TIMEOUT="${WORKER_TIMEOUT:-600}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if we're running in production
check_environment() {
    log "Checking environment configuration..."
    
    if [ "$ENVIRONMENT" != "production" ]; then
        warning "Not running in production environment. Current: $ENVIRONMENT"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    success "Environment check passed"
}

# Validate Redis connection
check_redis() {
    log "Checking Redis connection..."
    
    if ! python3 -c "
import redis
import sys
try:
    r = redis.from_url('$REDIS_URL')
    r.ping()
    print('Redis connection successful')
except Exception as e:
    print(f'Redis connection failed: {e}')
    sys.exit(1)
"; then
        error "Redis connection failed"
        exit 1
    fi
    
    success "Redis connection verified"
}

# Check database connection
check_database() {
    log "Checking database connection..."
    
    python3 -c "
from app.core.session import get_db
from sqlalchemy import text

try:
    db = next(get_db())
    db.execute(text('SELECT 1'))
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
finally:
    if 'db' in locals():
        db.close()
" || {
        error "Database connection failed"
        exit 1
    }
    
    success "Database connection verified"
}

# Check required environment variables
check_env_vars() {
    log "Checking required environment variables..."
    
    REQUIRED_VARS=(
        "DATABASE_URL"
        "REDIS_URL"
        "JWT_SECRET"
        "SECRET_KEY"
        "OPENAI_API_KEY"
    )
    
    MISSING_VARS=()
    
    for var in "${REQUIRED_VARS[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            MISSING_VARS+=("$var")
        fi
    done
    
    if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
        error "Missing required environment variables:"
        for var in "${MISSING_VARS[@]}"; do
            error "  - $var"
        done
        exit 1
    fi
    
    success "Environment variables verified"
}

# Install/update dependencies
install_dependencies() {
    log "Installing/updating dependencies..."
    
    pip install -r requirements.txt
    
    success "Dependencies installed"
}

# Run database migrations
run_migrations() {
    log "Running database migrations..."
    
    python3 -m alembic upgrade head
    
    success "Database migrations completed"
}

# Start workers with proper configuration
start_workers() {
    log "Starting task queue workers..."
    
    # Stop any existing workers
    pkill -f "app.worker" || true
    sleep 2
    
    # Create log directory
    mkdir -p logs/workers
    
    # Start workers with different configurations
    
    # High priority workers (2 workers for critical/high queues)
    for i in {1..2}; do
        log "Starting high priority worker $i..."
        WORKER_ID="high_priority_worker_$i" \
        WORKER_QUEUES="critical,high" \
        WORKER_MAX_JOBS=50 \
        WORKER_JOB_TIMEOUT=$WORKER_TIMEOUT \
        python3 -m app.worker > logs/workers/high_priority_$i.log 2>&1 &
        
        echo $! > logs/workers/high_priority_$i.pid
    done
    
    # Normal priority workers (3 workers for default queue)
    for i in {1..3}; do
        log "Starting normal priority worker $i..."
        WORKER_ID="normal_priority_worker_$i" \
        WORKER_QUEUES="default" \
        WORKER_MAX_JOBS=100 \
        WORKER_JOB_TIMEOUT=$WORKER_TIMEOUT \
        python3 -m app.worker > logs/workers/normal_priority_$i.log 2>&1 &
        
        echo $! > logs/workers/normal_priority_$i.pid
    done
    
    # Low priority worker (1 worker for low queue and long-running tasks)
    log "Starting low priority worker..."
    WORKER_ID="low_priority_worker_1" \
    WORKER_QUEUES="low" \
    WORKER_MAX_JOBS=200 \
    WORKER_JOB_TIMEOUT=1800 \
    python3 -m app.worker > logs/workers/low_priority_1.log 2>&1 &
    
    echo $! > logs/workers/low_priority_1.pid
    
    success "Workers started successfully"
}

# Start task scheduler
start_scheduler() {
    log "Starting task scheduler..."
    
    # Stop existing scheduler
    pkill -f "rq_scheduler" || true
    sleep 2
    
    mkdir -p logs
    python3 scripts/rq_scheduler.py > logs/scheduler.log 2>&1 &
    echo $! > logs/scheduler.pid
    
    success "Task scheduler started"
}

# Verify worker health
verify_workers() {
    log "Verifying worker health..."
    
    sleep 5  # Give workers time to start
    
    # Check worker status using the health endpoint
    python3 -c "
import requests
import sys

try:
    response = requests.get('http://localhost:8000/health/tasks', timeout=10)
    if response.status_code == 200:
        data = response.json()['data']
        worker_count = data['components']['workers']['total_workers']
        if worker_count >= $NUM_WORKERS:
            print(f'Workers healthy: {worker_count} active')
        else:
            print(f'Warning: Expected $NUM_WORKERS workers, found {worker_count}')
            sys.exit(1)
    else:
        print(f'Health check failed: {response.status_code}')
        sys.exit(1)
except Exception as e:
    print(f'Worker verification failed: {e}')
    sys.exit(1)
" || {
        error "Worker health verification failed"
        exit 1
    }
    
    success "Workers are healthy and responding"
}

# Set up monitoring (if enabled)
setup_monitoring() {
    if [ "$ENABLE_MONITORING" = "true" ]; then
        log "Setting up monitoring..."
        
        # Start metrics collection
        python3 -c "
from app.core.task_metrics import get_task_metrics
metrics = get_task_metrics()
print('Task metrics collection started')
" || warning "Failed to start metrics collection"
        
        # Verify Prometheus metrics endpoint
        python3 -c "
import requests
try:
    response = requests.get('http://localhost:8000/metrics', timeout=5)
    if response.status_code == 200:
        print('Metrics endpoint is responding')
    else:
        print(f'Metrics endpoint error: {response.status_code}')
except Exception as e:
    print(f'Metrics endpoint check failed: {e}')
" || warning "Metrics endpoint verification failed"
        
        success "Monitoring setup completed"
    else
        warning "Monitoring disabled"
    fi
}

# Create systemd services (optional)
create_systemd_services() {
    if [ "$USER" = "root" ] && command -v systemctl &> /dev/null; then
        log "Creating systemd services..."
        
        # Create worker service
        cat > /etc/systemd/system/mita-workers.service << EOF
[Unit]
Description=MITA Task Queue Workers
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=mita
Group=mita
WorkingDirectory=/opt/mita
Environment=PYTHONPATH=/opt/mita
Environment=ENVIRONMENT=production
EnvironmentFile=-/opt/mita/.env.production
ExecStart=/opt/mita/scripts/deploy_task_system.sh start-workers
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=mixed
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

        # Create scheduler service
        cat > /etc/systemd/system/mita-scheduler.service << EOF
[Unit]
Description=MITA Task Scheduler
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=mita
Group=mita
WorkingDirectory=/opt/mita
Environment=PYTHONPATH=/opt/mita
Environment=ENVIRONMENT=production
EnvironmentFile=-/opt/mita/.env.production
ExecStart=/usr/bin/python3 scripts/rq_scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        systemctl daemon-reload
        systemctl enable mita-workers
        systemctl enable mita-scheduler
        
        success "Systemd services created and enabled"
    else
        warning "Systemd services not created (not running as root or systemctl not available)"
    fi
}

# Cleanup function
cleanup() {
    log "Performing cleanup..."
    
    # Remove old log files (keep last 7 days)
    find logs/ -name "*.log" -mtime +7 -delete 2>/dev/null || true
    
    success "Cleanup completed"
}

# Status check function
check_status() {
    log "Checking task system status..."
    
    echo "=== Worker Processes ==="
    ps aux | grep "app.worker" | grep -v grep || echo "No workers running"
    
    echo -e "\n=== Scheduler Process ==="
    ps aux | grep "rq_scheduler" | grep -v grep || echo "No scheduler running"
    
    echo -e "\n=== Queue Status ==="
    python3 -c "
from app.core.task_queue import task_queue
import json
stats = task_queue.get_queue_stats()
print(json.dumps(stats, indent=2))
"
    
    echo -e "\n=== Recent Logs ==="
    if [ -d logs/workers ]; then
        echo "Worker logs:"
        for log_file in logs/workers/*.log; do
            if [ -f "$log_file" ]; then
                echo "--- $(basename $log_file) ---"
                tail -n 5 "$log_file"
                echo
            fi
        done
    fi
}

# Stop function
stop_services() {
    log "Stopping task system services..."
    
    # Stop workers
    if [ -d logs/workers ]; then
        for pid_file in logs/workers/*.pid; do
            if [ -f "$pid_file" ]; then
                PID=$(cat "$pid_file")
                if kill -0 "$PID" 2>/dev/null; then
                    log "Stopping worker with PID $PID"
                    kill -TERM "$PID"
                    sleep 2
                    if kill -0 "$PID" 2>/dev/null; then
                        kill -KILL "$PID"
                    fi
                fi
                rm -f "$pid_file"
            fi
        done
    fi
    
    # Stop scheduler
    if [ -f logs/scheduler.pid ]; then
        PID=$(cat logs/scheduler.pid)
        if kill -0 "$PID" 2>/dev/null; then
            log "Stopping scheduler with PID $PID"
            kill -TERM "$PID"
            sleep 2
            if kill -0 "$PID" 2>/dev/null; then
                kill -KILL "$PID"
            fi
        fi
        rm -f logs/scheduler.pid
    fi
    
    success "Task system services stopped"
}

# Main execution
main() {
    case "${1:-deploy}" in
        "deploy")
            log "Starting MITA Task Queue deployment..."
            check_environment
            check_env_vars
            check_redis
            check_database
            install_dependencies
            run_migrations
            start_workers
            start_scheduler
            verify_workers
            setup_monitoring
            create_systemd_services
            cleanup
            success "Task Queue deployment completed successfully!"
            ;;
        "start")
            start_workers
            start_scheduler
            verify_workers
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            stop_services
            sleep 2
            start_workers
            start_scheduler
            verify_workers
            ;;
        "status")
            check_status
            ;;
        "start-workers")
            start_workers
            ;;
        *)
            echo "Usage: $0 {deploy|start|stop|restart|status|start-workers}"
            echo ""
            echo "Commands:"
            echo "  deploy       - Full deployment (default)"
            echo "  start        - Start workers and scheduler"
            echo "  stop         - Stop all services"
            echo "  restart      - Restart all services"
            echo "  status       - Show system status"
            echo "  start-workers- Start only workers (for systemd)"
            exit 1
            ;;
    esac
}

# Trap signals for cleanup
trap cleanup EXIT

# Run main function
main "$@"