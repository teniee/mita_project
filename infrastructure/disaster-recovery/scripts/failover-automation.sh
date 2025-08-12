#!/bin/bash
# MITA Finance - Automated Disaster Recovery Failover Script
# This script handles automated failover to the disaster recovery region

set -euo pipefail

# Configuration
PRIMARY_REGION="us-east-1"
DR_REGION="us-west-2"
CLUSTER_NAME="mita-production"
DR_CLUSTER_NAME="mita-dr"
RDS_INSTANCE="mita-production-primary"
DR_RDS_INSTANCE="mita-production-dr-replica"
HOSTED_ZONE_ID="Z123EXAMPLE"
DOMAIN_NAME="api.mita.finance"

# Logging setup
LOG_FILE="/var/log/dr-failover-$(date +%Y%m%d-%H%M%S).log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

# Function to check primary region health
check_primary_health() {
    log "Checking primary region health..."
    
    # Check EKS cluster
    if ! aws eks describe-cluster --region "$PRIMARY_REGION" --name "$CLUSTER_NAME" &>/dev/null; then
        log "Primary EKS cluster unhealthy"
        return 1
    fi
    
    # Check RDS instance
    local rds_status
    rds_status=$(aws rds describe-db-instances \
        --region "$PRIMARY_REGION" \
        --db-instance-identifier "$RDS_INSTANCE" \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text 2>/dev/null || echo "error")
    
    if [[ "$rds_status" != "available" ]]; then
        log "Primary RDS instance status: $rds_status"
        return 1
    fi
    
    # Check application health
    if ! curl -f --max-time 10 "https://${DOMAIN_NAME}/health" &>/dev/null; then
        log "Primary application health check failed"
        return 1
    fi
    
    log "Primary region is healthy"
    return 0
}

# Function to prepare DR region
prepare_dr_region() {
    log "Preparing DR region for failover..."
    
    # Scale up DR EKS cluster
    log "Scaling up DR EKS cluster..."
    aws eks update-nodegroup-config \
        --region "$DR_REGION" \
        --cluster-name "$DR_CLUSTER_NAME" \
        --nodegroup-name "primary" \
        --scaling-config minSize=3,maxSize=10,desiredSize=5
    
    # Wait for nodes to be ready
    log "Waiting for DR cluster nodes to be ready..."
    sleep 120
    
    # Verify DR cluster health
    kubectl config use-context "arn:aws:eks:${DR_REGION}:$(aws sts get-caller-identity --query Account --output text):cluster/${DR_CLUSTER_NAME}"
    
    if ! kubectl get nodes | grep -q "Ready"; then
        error_exit "DR cluster nodes are not ready"
    fi
    
    log "DR region prepared successfully"
}

# Function to promote read replica
promote_read_replica() {
    log "Promoting read replica to primary..."
    
    # Check replication lag before promotion
    local lag
    lag=$(aws rds describe-db-instances \
        --region "$DR_REGION" \
        --db-instance-identifier "$DR_RDS_INSTANCE" \
        --query 'DBInstances[0].StatusInfos[?StatusType==`read replication`].Status' \
        --output text 2>/dev/null || echo "unknown")
    
    log "Current replication lag: $lag"
    
    # Promote read replica
    aws rds promote-read-replica \
        --region "$DR_REGION" \
        --db-instance-identifier "$DR_RDS_INSTANCE"
    
    # Wait for promotion to complete
    log "Waiting for read replica promotion..."
    aws rds wait db-instance-available \
        --region "$DR_REGION" \
        --db-instance-identifier "$DR_RDS_INSTANCE"
    
    log "Read replica promoted successfully"
}

# Function to deploy application to DR region
deploy_application_dr() {
    log "Deploying application to DR region..."
    
    # Update database connection string
    local dr_db_endpoint
    dr_db_endpoint=$(aws rds describe-db-instances \
        --region "$DR_REGION" \
        --db-instance-identifier "$DR_RDS_INSTANCE" \
        --query 'DBInstances[0].Endpoint.Address' \
        --output text)
    
    # Deploy using Helm
    helm upgrade --install mita-dr \
        ./infrastructure/helm/mita-production \
        --namespace mita-production \
        --create-namespace \
        --values ./infrastructure/helm/mita-production/values-dr.yaml \
        --set database.host="$dr_db_endpoint" \
        --set environment="dr" \
        --wait \
        --timeout=600s
    
    # Wait for deployment to be ready
    kubectl wait --for=condition=available \
        --timeout=300s \
        deployment/mita-backend \
        -n mita-production
    
    log "Application deployed to DR region successfully"
}

# Function to update DNS for failover
update_dns_failover() {
    log "Updating DNS for failover..."
    
    # Get DR region load balancer hostname
    local dr_lb_hostname
    dr_lb_hostname=$(kubectl get ingress mita-ingress \
        -n mita-production \
        -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    
    if [[ -z "$dr_lb_hostname" ]]; then
        error_exit "Could not get DR load balancer hostname"
    fi
    
    # Create DNS change batch
    cat > /tmp/dns-changeset.json <<EOF
{
    "Changes": [{
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": "${DOMAIN_NAME}",
            "Type": "CNAME",
            "TTL": 60,
            "ResourceRecords": [{
                "Value": "${dr_lb_hostname}"
            }]
        }
    }]
}
EOF
    
    # Apply DNS change
    local change_id
    change_id=$(aws route53 change-resource-record-sets \
        --hosted-zone-id "$HOSTED_ZONE_ID" \
        --change-batch file:///tmp/dns-changeset.json \
        --query 'ChangeInfo.Id' \
        --output text)
    
    # Wait for DNS change to propagate
    log "Waiting for DNS change to propagate (Change ID: $change_id)..."
    aws route53 wait resource-record-sets-changed --id "$change_id"
    
    log "DNS updated successfully"
    
    # Clean up
    rm -f /tmp/dns-changeset.json
}

# Function to verify DR deployment
verify_dr_deployment() {
    log "Verifying DR deployment..."
    
    # Test application health
    local attempt=1
    local max_attempts=20
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f --max-time 30 "https://${DOMAIN_NAME}/health"; then
            log "DR deployment health check passed"
            break
        fi
        
        log "Attempt $attempt/$max_attempts: Health check failed, retrying in 30s..."
        sleep 30
        ((attempt++))
    done
    
    if [[ $attempt -gt $max_attempts ]]; then
        error_exit "DR deployment health check failed after $max_attempts attempts"
    fi
    
    # Test database connectivity
    kubectl exec -n mita-production deployment/mita-backend -- \
        python -c "
import os
import psycopg2
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    print('Database connection successful')
    conn.close()
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
"
    
    log "DR deployment verification completed successfully"
}

# Function to send notifications
send_notifications() {
    local status="$1"
    local message="$2"
    
    # Send Slack notification
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🚨 DR Failover Alert: $message\"}" \
            "$SLACK_WEBHOOK_URL"
    fi
    
    # Send email notification via SES
    aws ses send-email \
        --source "alerts@mita.finance" \
        --destination "ToAddresses=devops@mita.finance,leadership@mita.finance" \
        --message "Subject={Data='MITA DR Failover - $status'},Body={Text={Data='$message'}}" \
        --region us-east-1 || log "Failed to send email notification"
    
    log "Notifications sent: $message"
}

# Function to create incident record
create_incident_record() {
    local incident_id="DR-$(date +%Y%m%d-%H%M%S)"
    local incident_file="/var/log/incidents/${incident_id}.json"
    
    mkdir -p "/var/log/incidents"
    
    cat > "$incident_file" <<EOF
{
    "incident_id": "${incident_id}",
    "timestamp": "$(date -Iseconds)",
    "type": "disaster_recovery",
    "status": "in_progress",
    "primary_region": "${PRIMARY_REGION}",
    "dr_region": "${DR_REGION}",
    "actions": [],
    "timeline": []
}
EOF
    
    log "Incident record created: $incident_id"
    echo "$incident_id"
}

# Function to update incident record
update_incident_record() {
    local incident_id="$1"
    local action="$2"
    local status="$3"
    
    local incident_file="/var/log/incidents/${incident_id}.json"
    
    if [[ -f "$incident_file" ]]; then
        # Update would require jq, for now just log
        log "Incident $incident_id: $action - $status"
    fi
}

# Main failover function
main() {
    log "Starting disaster recovery failover process..."
    
    local incident_id
    incident_id=$(create_incident_record)
    
    send_notifications "STARTED" "Disaster recovery failover initiated"
    
    # Check if this is a test or actual failover
    local force_failover="${FORCE_FAILOVER:-false}"
    
    if [[ "$force_failover" != "true" ]]; then
        # Check primary region health one more time
        if check_primary_health; then
            log "Primary region appears to be healthy, aborting failover"
            send_notifications "ABORTED" "Failover aborted - primary region is healthy"
            exit 0
        fi
    fi
    
    update_incident_record "$incident_id" "health_check" "primary_unhealthy"
    
    # Step 1: Prepare DR region
    prepare_dr_region
    update_incident_record "$incident_id" "prepare_dr" "completed"
    
    # Step 2: Promote read replica
    promote_read_replica
    update_incident_record "$incident_id" "promote_replica" "completed"
    
    # Step 3: Deploy application
    deploy_application_dr
    update_incident_record "$incident_id" "deploy_app" "completed"
    
    # Step 4: Update DNS
    update_dns_failover
    update_incident_record "$incident_id" "update_dns" "completed"
    
    # Step 5: Verify deployment
    verify_dr_deployment
    update_incident_record "$incident_id" "verify_deployment" "completed"
    
    log "Disaster recovery failover completed successfully!"
    send_notifications "COMPLETED" "Disaster recovery failover completed successfully. Application is now running in DR region."
    
    # Create summary report
    cat <<EOF

========================================
DISASTER RECOVERY FAILOVER SUMMARY
========================================
Incident ID: $incident_id
Start Time: $(date -Iseconds)
Primary Region: $PRIMARY_REGION (FAILED)
DR Region: $DR_REGION (ACTIVE)
Application URL: https://${DOMAIN_NAME}

Next Steps:
1. Monitor application performance in DR region
2. Investigate primary region issues
3. Plan recovery to primary region when ready
4. Update stakeholders on status

Log File: $LOG_FILE
========================================

EOF
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi