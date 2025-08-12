# Storage Infrastructure for MITA Finance
# S3 buckets for application data, backups, and compliance

# Primary application data bucket
resource "aws_s3_bucket" "app_data" {
  bucket = "${local.cluster_name}-app-data"
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-app-data"
    Purpose = "application-data"
  })
}

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.main.arn
        sse_algorithm     = "aws:kms"
      }
      bucket_key_enabled = true
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    id     = "financial_data_lifecycle"
    status = "Enabled"

    # Receipt images lifecycle
    filter {
      prefix = "receipts/"
    }

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }

    transition {
      days          = 2557  # 7 years
      storage_class = "DEEP_ARCHIVE"
    }

    # Keep forever for financial compliance
    expiration {
      days = 0
    }
  }

  rule {
    id     = "temp_data_cleanup"
    status = "Enabled"

    filter {
      prefix = "temp/"
    }

    expiration {
      days = 7
    }
  }
}

# Cross-region replication for disaster recovery
resource "aws_s3_bucket" "app_data_replica" {
  provider = aws.us_west_2
  bucket   = "${local.cluster_name}-app-data-replica"
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-app-data-replica"
    Purpose = "disaster-recovery"
  })
}

resource "aws_s3_bucket_versioning" "app_data_replica" {
  provider = aws.us_west_2
  bucket   = aws_s3_bucket.app_data_replica.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "app_data_replica" {
  provider = aws.us_west_2
  bucket   = aws_s3_bucket.app_data_replica.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = "arn:aws:kms:us-west-2:${data.aws_caller_identity.current.account_id}:alias/aws/s3"
        sse_algorithm     = "aws:kms"
      }
      bucket_key_enabled = true
    }
  }
}

resource "aws_s3_bucket_replication_configuration" "app_data" {
  role   = aws_iam_role.replication.arn
  bucket = aws_s3_bucket.app_data.id

  rule {
    id     = "entire_bucket"
    status = "Enabled"

    destination {
      bucket        = aws_s3_bucket.app_data_replica.arn
      storage_class = "STANDARD_IA"
      
      encryption_configuration {
        replica_kms_key_id = "arn:aws:kms:us-west-2:${data.aws_caller_identity.current.account_id}:alias/aws/s3"
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.app_data]
}

# IAM role for S3 replication
resource "aws_iam_role" "replication" {
  name = "${local.cluster_name}-s3-replication"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_policy" "replication" {
  name = "${local.cluster_name}-s3-replication"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect = "Allow"
        Resource = "${aws_s3_bucket.app_data.arn}/*"
      },
      {
        Action = [
          "s3:ListBucket"
        ]
        Effect = "Allow"
        Resource = aws_s3_bucket.app_data.arn
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect = "Allow"
        Resource = "${aws_s3_bucket.app_data_replica.arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "replication" {
  role       = aws_iam_role.replication.name
  policy_arn = aws_iam_policy.replication.arn
}

# Backup bucket for automated backups
resource "aws_s3_bucket" "backups" {
  bucket = "${local.cluster_name}-backups"
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-backups"
    Purpose = "backups"
  })
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "backups" {
  bucket = aws_s3_bucket.backups.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        kms_master_key_id = aws_kms_key.main.arn
        sse_algorithm     = "aws:kms"
      }
      bucket_key_enabled = true
    }
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket = aws_s3_bucket.backups.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "backup_lifecycle"
    status = "Enabled"

    # Daily backups
    filter {
      prefix = "daily/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 95
    }
  }

  rule {
    id     = "weekly_backups"
    status = "Enabled"

    filter {
      prefix = "weekly/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }

  rule {
    id     = "monthly_backups"
    status = "Enabled"

    filter {
      prefix = "monthly/"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 2557  # 7 years for financial compliance
    }
  }
}

# CloudFront distribution for static assets
resource "aws_cloudfront_distribution" "assets" {
  origin {
    domain_name = aws_s3_bucket.app_data.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.app_data.bucket}"
    
    origin_access_control_id = aws_cloudfront_origin_access_control.assets.id
  }

  enabled = true
  
  default_cache_behavior {
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.app_data.bucket}"
    compress               = true
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # Caching for receipt images
  ordered_cache_behavior {
    path_pattern     = "/receipts/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.app_data.bucket}"
    compress         = true
    
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
    
    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 86400   # Cache for 24 hours
    default_ttl            = 86400
    max_ttl                = 31536000  # 1 year
  }

  price_class = "PriceClass_100"  # US, Canada, Europe

  restrictions {
    geo_restriction {
      restriction_type = "blacklist"
      locations        = ["CN", "RU"]  # Financial compliance
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-cloudfront"
  })
}

resource "aws_cloudfront_origin_access_control" "assets" {
  name                              = "${local.cluster_name}-assets-oac"
  description                       = "Origin Access Control for MITA assets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# S3 bucket policy for CloudFront access
resource "aws_s3_bucket_policy" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.app_data.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.assets.arn
          }
        }
      }
    ]
  })
}

# IRSA for application S3 access
module "s3_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${local.cluster_name}-s3-access"
  
  role_policy_arns = {
    s3_access = aws_iam_policy.app_s3_access.arn
  }

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["mita-production:mita-backend"]
    }
  }
}

resource "aws_iam_policy" "app_s3_access" {
  name = "${local.cluster_name}-app-s3-access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:GetObjectVersion"
        ]
        Resource = [
          "${aws_s3_bucket.app_data.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.app_data.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.main.arn
      }
    ]
  })
}