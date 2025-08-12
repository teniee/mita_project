# AWS Secrets Manager Configuration for MITA Finance
# Provides secure, encrypted storage for all application secrets

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Local variables for consistent naming
locals {
  environment = var.environment
  project     = "mita-finance"
  
  common_tags = {
    Project     = local.project
    Environment = local.environment
    ManagedBy   = "terraform"
    Compliance  = "SOX,PCI-DSS,GDPR"
    CostCenter  = "infrastructure"
  }
  
  # Secret definitions with rotation configurations
  secrets = {
    # Critical secrets - 30 day rotation
    "database/primary" = {
      description = "Primary PostgreSQL database credentials"
      rotation_days = 30
      category = "critical"
      compliance_tags = ["SOX", "PCI-DSS"]
    }
    "database/readonly" = {
      description = "Read-only database credentials"
      rotation_days = 30
      category = "critical"
      compliance_tags = ["SOX", "PCI-DSS"]
    }
    "auth/jwt-secret" = {
      description = "JWT signing secret for authentication"
      rotation_days = 30
      category = "critical"
      compliance_tags = ["SOX", "PCI-DSS"]
    }
    "auth/jwt-previous-secret" = {
      description = "Previous JWT secret for token migration"
      rotation_days = 30
      category = "critical"
      compliance_tags = ["SOX", "PCI-DSS"]
    }
    "app/secret-key" = {
      description = "Application encryption secret key"
      rotation_days = 30
      category = "critical"
      compliance_tags = ["SOX", "PCI-DSS"]
    }
    
    # High priority secrets - 60 day rotation
    "cache/redis-auth" = {
      description = "Redis authentication credentials"
      rotation_days = 60
      category = "high"
      compliance_tags = ["PCI-DSS"]
    }
    "external/openai-api-key" = {
      description = "OpenAI API key for AI features"
      rotation_days = 60
      category = "high"
      compliance_tags = ["DATA-PROTECTION"]
    }
    "aws/backup-credentials" = {
      description = "AWS credentials for backup operations"
      rotation_days = 60
      category = "high"
      compliance_tags = ["SOX"]
    }
    
    # Medium priority secrets - 90 day rotation
    "notifications/smtp-credentials" = {
      description = "SMTP credentials for email notifications"
      rotation_days = 90
      category = "medium"
      compliance_tags = ["GDPR"]
    }
    "apple/app-store-secret" = {
      description = "Apple App Store shared secret for IAP"
      rotation_days = 90
      category = "medium"
      compliance_tags = ["PCI-DSS"]
    }
    "apple/push-credentials" = {
      description = "Apple Push Notification Service credentials"
      rotation_days = 180
      category = "medium"
      compliance_tags = ["GDPR"]
    }
    "firebase/service-account" = {
      description = "Firebase service account credentials"
      rotation_days = 180
      category = "medium"
      compliance_tags = ["GDPR", "DATA-PROTECTION"]
    }
    
    # Low priority secrets - 180 day rotation
    "monitoring/sentry-dsn" = {
      description = "Sentry DSN for error monitoring"
      rotation_days = 180
      category = "low"
      compliance_tags = ["INTERNAL"]
    }
    "monitoring/grafana-admin" = {
      description = "Grafana admin credentials"
      rotation_days = 90
      category = "low"
      compliance_tags = ["INTERNAL"]
    }
  }
}

# KMS Key for Secrets Manager encryption
resource "aws_kms_key" "secrets_manager" {
  description              = "KMS key for MITA Finance Secrets Manager encryption"
  key_usage               = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  deletion_window_in_days = 7
  
  # Enable key rotation
  enable_key_rotation = true
  
  # Policy for key usage
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableSecretsManagerAccess"
        Effect = "Allow"
        Principal = {
          Service = "secretsmanager.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
      },
      {
        Sid    = "EnableEKSClusterAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/mita-${local.environment}-eks-node-role"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "EnableAdministratorAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })
  
  tags = merge(local.common_tags, {
    Name = "${local.project}-${local.environment}-secrets-kms"
    Type = "encryption"
  })
}

# KMS Key Alias
resource "aws_kms_alias" "secrets_manager" {
  name          = "alias/${local.project}-${local.environment}-secrets"
  target_key_id = aws_kms_key.secrets_manager.key_id
}

# Create secrets in AWS Secrets Manager
resource "aws_secretsmanager_secret" "secrets" {
  for_each = local.secrets
  
  name        = "${local.project}/${local.environment}/${each.key}"
  description = each.value.description
  kms_key_id  = aws_kms_key.secrets_manager.arn
  
  # Force delete for non-production environments
  force_overwrite_replica_secret = local.environment != "production"
  recovery_window_in_days       = local.environment == "production" ? 30 : 0
  
  tags = merge(local.common_tags, {
    Name        = "${local.project}-${local.environment}-${replace(each.key, "/", "-")}"
    Category    = each.value.category
    Compliance  = join(",", each.value.compliance_tags)
    Rotation    = "${each.value.rotation_days}d"
  })
}

# Create secret versions with placeholder values
resource "aws_secretsmanager_secret_version" "secrets" {
  for_each = local.secrets
  
  secret_id = aws_secretsmanager_secret.secrets[each.key].id
  
  # Generate initial secure values based on secret type
  secret_string = jsonencode({
    value = "PLACEHOLDER_${upper(replace(each.key, "/", "_"))}_REPLACE_WITH_ACTUAL_VALUE"
    created_at = timestamp()
    category = each.value.category
    compliance_tags = each.value.compliance_tags
    rotation_required_days = each.value.rotation_days
  })
  
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Lambda execution role for secret rotation
resource "aws_iam_role" "secret_rotation_lambda" {
  name = "${local.project}-${local.environment}-secret-rotation"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# IAM policy for secret rotation Lambda
resource "aws_iam_role_policy" "secret_rotation_lambda" {
  name = "${local.project}-${local.environment}-secret-rotation-policy"
  role = aws_iam_role.secret_rotation_lambda.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue",
          "secretsmanager:UpdateSecretVersionStage"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${local.project}/${local.environment}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.secrets_manager.arn
      },
      {
        Effect = "Allow"
        Action = [
          "rds:ModifyDBInstance",
          "rds:ModifyDBCluster"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/Project" = local.project
            "aws:ResourceTag/Environment" = local.environment
          }
        }
      }
    ]
  })
}

# External Secrets Operator service account IAM role
resource "aws_iam_role" "external_secrets_operator" {
  name = "${local.project}-${local.environment}-external-secrets"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${replace(data.aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(data.aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}:sub" = "system:serviceaccount:external-secrets-system:external-secrets"
            "${replace(data.aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
  
  tags = local.common_tags
}

# IAM policy for External Secrets Operator
resource "aws_iam_role_policy" "external_secrets_operator" {
  name = "${local.project}-${local.environment}-external-secrets-policy"
  role = aws_iam_role.external_secrets_operator.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${local.project}/${local.environment}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = aws_kms_key.secrets_manager.arn
      }
    ]
  })
}

# Secret replication for disaster recovery (only in production)
resource "aws_secretsmanager_secret_replica" "secrets" {
  for_each = local.environment == "production" ? local.secrets : {}
  
  secret_id = aws_secretsmanager_secret.secrets[each.key].arn
  region    = var.backup_region
  
  kms_key_id = aws_kms_key.secrets_manager.arn
  
  replica_tags = merge(local.common_tags, {
    Type = "replica"
    ReplicationSource = data.aws_region.current.name
  })
}

# CloudWatch Log Group for secret access auditing
resource "aws_cloudwatch_log_group" "secret_access_audit" {
  name              = "/aws/secretsmanager/${local.project}/${local.environment}/audit"
  retention_in_days = local.environment == "production" ? 2555 : 90  # 7 years for production
  
  kms_key_id = aws_kms_key.secrets_manager.arn
  
  tags = merge(local.common_tags, {
    Type = "audit-log"
    Compliance = "SOX,PCI-DSS"
  })
}

# EventBridge rule for secret access monitoring
resource "aws_cloudwatch_event_rule" "secret_access" {
  name        = "${local.project}-${local.environment}-secret-access"
  description = "Monitor secret access events for security audit"
  
  event_pattern = jsonencode({
    source      = ["aws.secretsmanager"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventSource = ["secretsmanager.amazonaws.com"]
      eventName   = ["GetSecretValue"]
      resources   = {
        ARN = [{
          prefix = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${local.project}/${local.environment}/"
        }]
      }
    }
  })
  
  tags = local.common_tags
}

# CloudWatch Event Target for secret access alerts
resource "aws_cloudwatch_event_target" "secret_access_alert" {
  rule      = aws_cloudwatch_event_rule.secret_access.name
  target_id = "SecretAccessLogTarget"
  arn       = aws_cloudwatch_log_group.secret_access_audit.arn
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_eks_cluster" "main" {
  name = "${local.project}-${local.environment}"
}

# Variables
variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
  validation {
    condition = contains(["staging", "production"], var.environment)
    error_message = "Environment must be either staging or production."
  }
}

variable "backup_region" {
  description = "AWS region for secret replication"
  type        = string
  default     = "us-west-2"
}

# Outputs
output "secrets_manager_kms_key_arn" {
  description = "ARN of the KMS key used for Secrets Manager encryption"
  value       = aws_kms_key.secrets_manager.arn
}

output "external_secrets_operator_role_arn" {
  description = "ARN of the IAM role for External Secrets Operator"
  value       = aws_iam_role.external_secrets_operator.arn
}

output "secret_arns" {
  description = "ARNs of all created secrets"
  value = {
    for k, v in aws_secretsmanager_secret.secrets : k => v.arn
  }
  sensitive = true
}

output "secret_names" {
  description = "Names of all created secrets in Secrets Manager"
  value = {
    for k, v in aws_secretsmanager_secret.secrets : k => v.name
  }
}

output "audit_log_group_name" {
  description = "Name of the CloudWatch log group for audit logs"
  value       = aws_cloudwatch_log_group.secret_access_audit.name
}