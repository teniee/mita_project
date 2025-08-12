# Terraform Outputs for MITA Finance Infrastructure

# Network Outputs
output "vpc_id" {
  description = "ID of the VPC where resources are created"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnets
}

output "database_subnets" {
  description = "List of IDs of database subnets"
  value       = module.vpc.database_subnets
}

# EKS Outputs
output "cluster_id" {
  description = "The ID/name of the EKS cluster"
  value       = module.eks.cluster_id
}

output "cluster_arn" {
  description = "The Amazon Resource Name (ARN) of the cluster"
  value       = module.eks.cluster_arn
}

output "cluster_endpoint" {
  description = "Endpoint for your Kubernetes API server"
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "The Kubernetes version for the cluster"
  value       = module.eks.cluster_version
}

output "cluster_platform_version" {
  description = "Platform version for the cluster"
  value       = module.eks.cluster_platform_version
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster for the OpenID Connect identity provider"
  value       = module.eks.cluster_oidc_issuer_url
}

output "oidc_provider_arn" {
  description = "The ARN of the OIDC Provider if enabled"
  value       = module.eks.oidc_provider_arn
}

# Database Outputs
output "db_instance_arn" {
  description = "The ARN of the RDS instance"
  value       = module.rds.db_instance_arn
  sensitive   = true
}

output "db_instance_id" {
  description = "The RDS instance ID"
  value       = module.rds.db_instance_id
}

output "db_instance_endpoint" {
  description = "The RDS instance endpoint"
  value       = module.rds.db_instance_endpoint
  sensitive   = true
}

output "db_instance_port" {
  description = "The RDS instance port"
  value       = module.rds.db_instance_port
}

output "db_instance_name" {
  description = "The database name"
  value       = module.rds.db_instance_name
}

output "db_instance_username" {
  description = "The master username for the database"
  value       = module.rds.db_instance_username
  sensitive   = true
}

output "db_read_replica_endpoint" {
  description = "The read replica endpoint"
  value       = aws_db_instance.read_replica_1.endpoint
  sensitive   = true
}

output "db_dr_replica_endpoint" {
  description = "The disaster recovery replica endpoint"
  value       = aws_db_instance.read_replica_dr.endpoint
  sensitive   = true
}

# Redis Outputs
output "redis_cluster_id" {
  description = "The ID of the ElastiCache replication group"
  value       = aws_elasticache_replication_group.redis.id
}

output "redis_cluster_address" {
  description = "The address of the replication group configuration endpoint when cluster mode is enabled"
  value       = aws_elasticache_replication_group.redis.configuration_endpoint_address
  sensitive   = true
}

output "redis_cluster_port" {
  description = "The port number on which the configuration endpoint will accept connections"
  value       = aws_elasticache_replication_group.redis.port
}

# Security Outputs
output "kms_key_id" {
  description = "The globally unique identifier for the key"
  value       = aws_kms_key.main.key_id
}

output "kms_key_arn" {
  description = "The Amazon Resource Name (ARN) of the key"
  value       = aws_kms_key.main.arn
}

output "eks_kms_key_arn" {
  description = "The Amazon Resource Name (ARN) of the EKS encryption key"
  value       = aws_kms_key.eks.arn
}

output "ebs_kms_key_arn" {
  description = "The Amazon Resource Name (ARN) of the EBS encryption key"
  value       = aws_kms_key.ebs.arn
}

# Secrets Manager Outputs
output "db_password_secret_arn" {
  description = "The ARN of the database password secret"
  value       = aws_secretsmanager_secret.db_password.arn
  sensitive   = true
}

output "redis_auth_secret_arn" {
  description = "The ARN of the Redis auth token secret"
  value       = aws_secretsmanager_secret.redis_auth.arn
  sensitive   = true
}

output "jwt_secret_arn" {
  description = "The ARN of the JWT secret"
  value       = aws_secretsmanager_secret.jwt_secret.arn
  sensitive   = true
}

# Storage Outputs
output "app_data_bucket_id" {
  description = "The name of the application data bucket"
  value       = aws_s3_bucket.app_data.id
}

output "app_data_bucket_arn" {
  description = "The ARN of the application data bucket"
  value       = aws_s3_bucket.app_data.arn
}

output "backups_bucket_id" {
  description = "The name of the backups bucket"
  value       = aws_s3_bucket.backups.id
}

output "backups_bucket_arn" {
  description = "The ARN of the backups bucket"
  value       = aws_s3_bucket.backups.arn
}

output "cloudfront_distribution_id" {
  description = "The identifier for the distribution"
  value       = aws_cloudfront_distribution.assets.id
}

output "cloudfront_distribution_domain_name" {
  description = "The domain name corresponding to the distribution"
  value       = aws_cloudfront_distribution.assets.domain_name
}

# Monitoring Outputs
output "opensearch_endpoint" {
  description = "Domain-specific endpoint used to submit index, search, and data upload requests"
  value       = aws_opensearch_domain.logs.endpoint
  sensitive   = true
}

output "opensearch_domain_arn" {
  description = "ARN of the domain"
  value       = aws_opensearch_domain.logs.arn
}

output "critical_alerts_topic_arn" {
  description = "The ARN of the SNS topic for critical alerts"
  value       = aws_sns_topic.critical_alerts.arn
}

output "warning_alerts_topic_arn" {
  description = "The ARN of the SNS topic for warning alerts"
  value       = aws_sns_topic.warning_alerts.arn
}

# WAF Outputs
output "waf_web_acl_arn" {
  description = "The ARN of the WAF WebACL"
  value       = aws_wafv2_web_acl.main.arn
}

output "waf_web_acl_id" {
  description = "The ID of the WAF WebACL"
  value       = aws_wafv2_web_acl.main.id
}

# GuardDuty Outputs
output "guardduty_detector_id" {
  description = "The ID of the GuardDuty detector"
  value       = aws_guardduty_detector.main.id
}

# Backup Outputs
output "backup_vault_arn" {
  description = "The ARN of the backup vault"
  value       = aws_backup_vault.main.arn
}

output "backup_plan_arn" {
  description = "The ARN of the backup plan"
  value       = aws_backup_plan.database_backup.arn
}

# IRSA Role ARNs
output "ebs_csi_irsa_role_arn" {
  description = "IAM role ARN for EBS CSI driver"
  value       = module.ebs_csi_irsa_role.iam_role_arn
}

output "aws_load_balancer_controller_irsa_role_arn" {
  description = "IAM role ARN for AWS Load Balancer Controller"
  value       = module.aws_load_balancer_controller_irsa_role.iam_role_arn
}

output "external_dns_irsa_role_arn" {
  description = "IAM role ARN for External DNS"
  value       = module.external_dns_irsa_role.iam_role_arn
}

output "cluster_autoscaler_irsa_role_arn" {
  description = "IAM role ARN for Cluster Autoscaler"
  value       = module.cluster_autoscaler_irsa_role.iam_role_arn
}

output "s3_irsa_role_arn" {
  description = "IAM role ARN for S3 access"
  value       = module.s3_irsa_role.iam_role_arn
}

# Regional Information
output "region" {
  description = "AWS region where resources are created"
  value       = data.aws_region.current.name
}

output "availability_zones" {
  description = "List of availability zones used"
  value       = local.azs
}

output "account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
  sensitive   = true
}

# Useful for kubectl configuration
output "kubectl_config" {
  description = "kubectl config as JSON"
  value = jsonencode({
    apiVersion      = "v1"
    kind            = "Config"
    current-context = "terraform"
    contexts = [{
      name = "terraform"
      context = {
        cluster = "terraform"
        user    = "terraform"
      }
    }]
    clusters = [{
      name = "terraform"
      cluster = {
        certificate-authority-data = module.eks.cluster_certificate_authority_data
        server                     = module.eks.cluster_endpoint
      }
    }]
    users = [{
      name = "terraform"
      user = {
        token = data.aws_eks_cluster_auth.cluster.token
      }
    }]
  })
  sensitive = true
}

data "aws_eks_cluster_auth" "cluster" {
  name = module.eks.cluster_id
}

# Connection strings (sensitive, for application configuration)
output "database_url" {
  description = "Complete database connection URL"
  value       = "postgresql://${module.rds.db_instance_username}:${urlencode(random_password.db_password.result)}@${module.rds.db_instance_endpoint}:${module.rds.db_instance_port}/${module.rds.db_instance_name}?sslmode=require"
  sensitive   = true
}

output "redis_url" {
  description = "Complete Redis connection URL"
  value       = "redis://:${urlencode(random_password.redis_auth_token.result)}@${aws_elasticache_replication_group.redis.configuration_endpoint_address}:${aws_elasticache_replication_group.redis.port}/0"
  sensitive   = true
}

# Cost optimization information
output "estimated_monthly_cost" {
  description = "Estimated monthly cost breakdown"
  value = {
    eks_cluster      = "~$75 (control plane only)"
    eks_nodes        = "~$200-400 (depending on instance types and count)"
    rds_primary      = "~$300-500 (db.r6g.xlarge Multi-AZ)"
    rds_read_replica = "~$150-250 (db.r6g.large)"
    rds_dr_replica   = "~$150-250 (cross-region)"
    elasticache      = "~$200-300 (cache.r6g.large cluster)"
    s3_storage       = "~$50-100 (depending on usage)"
    data_transfer    = "~$50-200 (depending on traffic)"
    cloudwatch       = "~$30-50 (logging and metrics)"
    backups          = "~$20-40 (automated backups)"
    total_estimated  = "~$1,225-2,165 per month"
    note            = "Costs are estimates and may vary based on usage patterns, data transfer, and other factors"
  }
}