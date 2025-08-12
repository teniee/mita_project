# Security Infrastructure for MITA Finance
# Comprehensive security setup including KMS, Secrets Manager, WAF, and compliance controls

# KMS Keys for encryption
resource "aws_kms_key" "main" {
  description             = "MITA Finance primary encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow EKS service"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-primary-key"
  })
}

resource "aws_kms_alias" "main" {
  name          = "alias/${local.cluster_name}-primary"
  target_key_id = aws_kms_key.main.key_id
}

# Dedicated KMS key for EKS secrets
resource "aws_kms_key" "eks" {
  description             = "MITA Finance EKS secrets encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-eks-key"
  })
}

resource "aws_kms_alias" "eks" {
  name          = "alias/${local.cluster_name}-eks"
  target_key_id = aws_kms_key.eks.key_id
}

# KMS key for EBS encryption
resource "aws_kms_key" "ebs" {
  description             = "MITA Finance EBS encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-ebs-key"
  })
}

resource "aws_kms_alias" "ebs" {
  name          = "alias/${local.cluster_name}-ebs"
  target_key_id = aws_kms_key.ebs.key_id
}

# Secrets Manager secrets
resource "aws_secretsmanager_secret" "db_password" {
  name        = "${local.cluster_name}/database/master-password"
  description = "Database master password for MITA Finance"
  kms_key_id  = aws_kms_key.main.arn
  
  replica {
    region     = "us-west-2"
    kms_key_id = aws_kms_key.main.arn
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-db-password"
  })
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}

resource "aws_secretsmanager_secret" "redis_auth" {
  name        = "${local.cluster_name}/redis/auth-token"
  description = "Redis authentication token for MITA Finance"
  kms_key_id  = aws_kms_key.main.arn
  
  replica {
    region     = "us-west-2"
    kms_key_id = aws_kms_key.main.arn
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-redis-auth"
  })
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id     = aws_secretsmanager_secret.redis_auth.id
  secret_string = random_password.redis_auth_token.result
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name        = "${local.cluster_name}/application/jwt-secret"
  description = "JWT signing secret for MITA Finance"
  kms_key_id  = aws_kms_key.main.arn
  
  replica {
    region     = "us-west-2"
    kms_key_id = aws_kms_key.main.arn
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-jwt-secret"
  })
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id = aws_secretsmanager_secret.jwt_secret.id
  secret_string = jsonencode({
    jwt_secret = base64encode(random_password.db_password.result)
    secret_key = base64encode(random_password.redis_auth_token.result)
  })
}

# WAF for Application Load Balancer
resource "aws_wafv2_web_acl" "main" {
  name  = "${local.cluster_name}-web-acl"
  description = "WAF for MITA Finance Application"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  # Rate limiting rule
  rule {
    name     = "RateLimitRule"
    priority = 1

    override_action {
      none {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
        
        scope_down_statement {
          byte_match_statement {
            search_string = "/api/"
            field_to_match {
              uri_path {}
            }
            text_transformation {
              priority = 0
              type     = "LOWERCASE"
            }
            positional_constraint = "CONTAINS"
          }
        }
      }
    }

    action {
      block {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitRule"
      sampled_requests_enabled   = true
    }
  }

  # IP reputation rule
  rule {
    name     = "IPReputationRule"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    action {
      block {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "IPReputationRule"
      sampled_requests_enabled   = true
    }
  }

  # Core rule set
  rule {
    name     = "CoreRuleSet"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
        
        excluded_rule {
          name = "SizeRestrictions_BODY"
        }
        
        excluded_rule {
          name = "GenericRFI_BODY"
        }
      }
    }

    action {
      block {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CoreRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # SQL injection protection
  rule {
    name     = "SQLInjectionRule"
    priority = 4

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    action {
      block {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLInjectionRule"
      sampled_requests_enabled   = true
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-waf"
  })

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.cluster_name}-web-acl"
    sampled_requests_enabled   = true
  }
}

# GuardDuty for threat detection
resource "aws_guardduty_detector" "main" {
  enable = true
  
  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = true
        }
      }
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-guardduty"
  })
}

# Security Hub
resource "aws_securityhub_account" "main" {}

resource "aws_securityhub_standards_subscription" "aws_foundational" {
  standards_arn = "arn:aws:securityhub:::ruleset/finding-format/aws-foundational-security-standard/v/1.0.0"
  depends_on    = [aws_securityhub_account.main]
}

resource "aws_securityhub_standards_subscription" "cis" {
  standards_arn = "arn:aws:securityhub:::ruleset/finding-format/cis-aws-foundations-benchmark/v/1.2.0"
  depends_on    = [aws_securityhub_account.main]
}

# CloudTrail for audit logging
resource "aws_cloudtrail" "main" {
  name           = "${local.cluster_name}-cloudtrail"
  s3_bucket_name = aws_s3_bucket.cloudtrail.id
  
  event_selector {
    read_write_type                 = "All"
    include_management_events       = true
    
    data_resource {
      type   = "AWS::S3::Object"
      values = ["${aws_s3_bucket.app_data.arn}/*"]
    }
    
    data_resource {
      type   = "AWS::S3::Bucket"
      values = [aws_s3_bucket.app_data.arn]
    }
  }

  depends_on = [aws_s3_bucket_policy.cloudtrail]

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-cloudtrail"
  })
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket = "${local.cluster_name}-cloudtrail-logs"
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-cloudtrail-bucket"
  })
}

resource "aws_s3_bucket_versioning" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.main.arn
        sse_algorithm     = "aws:kms"
      }
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.cloudtrail.arn
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cloudtrail.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      }
    ]
  })
}

# Config for compliance monitoring
resource "aws_config_configuration_recorder" "main" {
  name     = "${local.cluster_name}-config-recorder"
  role_arn = aws_iam_role.config.arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }
}

resource "aws_config_delivery_channel" "main" {
  name           = "${local.cluster_name}-config-delivery-channel"
  s3_bucket_name = aws_s3_bucket.config.id
}

resource "aws_iam_role" "config" {
  name = "${local.cluster_name}-config-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "config" {
  role       = aws_iam_role.config.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/ConfigRole"
}

resource "aws_s3_bucket" "config" {
  bucket = "${local.cluster_name}-config-bucket"
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-config-bucket"
  })
}

resource "aws_s3_bucket_encryption" "config" {
  bucket = aws_s3_bucket.config.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.main.arn
        sse_algorithm     = "aws:kms"
      }
    }
  }
}

resource "aws_s3_bucket_public_access_block" "config" {
  bucket = aws_s3_bucket.config.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}