# Database Infrastructure for MITA Finance
# Production-grade RDS PostgreSQL with Multi-AZ, read replicas, and comprehensive backup strategy

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${local.cluster_name}-db-subnet-group"
  subnet_ids = module.vpc.database_subnets

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-db-subnet-group"
  })
}

# RDS Parameter Group for PostgreSQL optimization
resource "aws_db_parameter_group" "main" {
  family = "postgres15"
  name   = "${local.cluster_name}-postgres-params"

  # Performance and security optimizations for financial services
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,pg_prewarm"
  }

  parameter {
    name  = "log_statement"
    value = "all"  # Log all statements for financial compliance
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking more than 1 second
  }

  parameter {
    name  = "log_checkpoints"
    value = "1"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_lock_waits"
    value = "1"
  }

  parameter {
    name  = "log_temp_files"
    value = "0"
  }

  parameter {
    name  = "max_connections"
    value = "200"
  }

  parameter {
    name  = "shared_buffers"
    value = "{DBInstanceClassMemory/4}"
  }

  parameter {
    name  = "effective_cache_size"
    value = "{DBInstanceClassMemory*3/4}"
  }

  parameter {
    name  = "maintenance_work_mem"
    value = "2048000"  # 2GB for maintenance operations
  }

  parameter {
    name  = "checkpoint_completion_target"
    value = "0.9"
  }

  parameter {
    name  = "wal_buffers"
    value = "16384"  # 16MB
  }

  parameter {
    name  = "default_statistics_target"
    value = "100"
  }

  parameter {
    name  = "random_page_cost"
    value = "1.1"  # SSD optimization
  }

  parameter {
    name  = "effective_io_concurrency"
    value = "200"  # SSD optimization
  }

  # Security parameters
  parameter {
    name  = "ssl"
    value = "1"
  }

  parameter {
    name  = "ssl_ciphers"
    value = "HIGH:MEDIUM:+3DES:!aNULL"
  }

  parameter {
    name  = "password_encryption"
    value = "scram-sha-256"
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-postgres-params"
  })
}

# RDS Option Group (for future extensions)
resource "aws_db_option_group" "main" {
  name                     = "${local.cluster_name}-postgres-options"
  option_group_description = "PostgreSQL option group for MITA Finance"
  engine_name              = "postgres"
  major_engine_version     = "15"

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-postgres-options"
  })
}

# Primary RDS Instance
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "${local.cluster_name}-primary"

  # Database configuration
  engine               = "postgres"
  engine_version       = "15.3"
  family               = "postgres15"
  major_engine_version = "15"
  instance_class       = "db.r6g.xlarge"  # Graviton2 for cost optimization
  allocated_storage    = 500
  max_allocated_storage = 2000
  storage_type         = "gp3"
  storage_throughput   = 500
  storage_iops         = 3000

  # Database settings
  db_name  = "mita"
  username = "mita_admin"
  password = random_password.db_password.result
  port     = 5432

  # High Availability
  multi_az               = true
  availability_zone      = null  # Let AWS choose for Multi-AZ
  
  # Network configuration
  vpc_security_group_ids = [aws_security_group.database_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  subnet_ids             = module.vpc.database_subnets

  # Parameter and option groups
  parameter_group_name = aws_db_parameter_group.main.name
  option_group_name    = aws_db_option_group.main.name

  # Backup configuration (critical for financial services)
  backup_retention_period = 35  # 5 weeks
  backup_window          = "03:00-04:00"  # UTC, during low activity
  maintenance_window     = "Sun:04:00-Sun:05:00"  # UTC
  
  copy_tags_to_snapshot = true
  skip_final_snapshot   = false
  final_snapshot_identifier_prefix = "${local.cluster_name}-final-snapshot"

  # Encryption
  storage_encrypted = true
  kms_key_id       = aws_kms_key.main.arn

  # Enhanced Monitoring
  monitoring_interval    = 60
  monitoring_role_arn   = aws_iam_role.rds_enhanced_monitoring.arn
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_kms_key_id      = aws_kms_key.main.arn
  performance_insights_retention_period = 731  # 2 years for financial compliance

  # Security
  publicly_accessible = false
  deletion_protection = true

  # Auto minor version updates
  auto_minor_version_upgrade = true
  allow_major_version_upgrade = false

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-primary-db"
    Role = "primary"
    Backup = "required"
  })
}

# Read Replica for read scaling
resource "aws_db_instance" "read_replica_1" {
  identifier = "${local.cluster_name}-read-replica-1"
  
  replicate_source_db = module.rds.db_instance_id
  instance_class      = "db.r6g.large"  # Smaller for read-only workloads
  
  # Network configuration
  vpc_security_group_ids = [aws_security_group.database_sg.id]
  availability_zone      = data.aws_availability_zones.available.names[1]  # Different AZ
  
  # Performance monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn
  
  # Performance Insights
  performance_insights_enabled     = true
  performance_insights_kms_key_id = aws_kms_key.main.arn
  performance_insights_retention_period = 31  # 1 month for read replica
  
  # Security
  publicly_accessible = false
  deletion_protection = true
  
  # Auto minor version updates
  auto_minor_version_upgrade = true
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-read-replica-1"
    Role = "read-replica"
    Purpose = "read-scaling"
  })
}

# Cross-region read replica for disaster recovery
resource "aws_db_instance" "read_replica_dr" {
  provider = aws.us_west_2
  
  identifier = "${local.cluster_name}-dr-replica"
  
  replicate_source_db = module.rds.db_instance_arn  # Cross-region requires ARN
  instance_class      = "db.r6g.large"
  
  # Performance monitoring
  monitoring_interval = 60
  
  # Security
  publicly_accessible = false
  deletion_protection = true
  
  # Auto minor version updates
  auto_minor_version_upgrade = true
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-dr-replica"
    Role = "disaster-recovery"
    Purpose = "cross-region-dr"
  })
}

# Enhanced Monitoring IAM Role
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${local.cluster_name}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-rds-enhanced-monitoring-role"
  })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Redis (ElastiCache) Configuration
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.cluster_name}-redis-subnet-group"
  subnet_ids = module.vpc.database_subnets

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-redis-subnet-group"
  })
}

resource "aws_elasticache_parameter_group" "redis" {
  family = "redis7.x"
  name   = "${local.cluster_name}-redis-params"

  # Performance and security optimizations
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"  # 5 minutes
  }

  parameter {
    name  = "tcp-keepalive"
    value = "300"
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-redis-params"
  })
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id         = "${local.cluster_name}-redis"
  description                  = "Redis cluster for MITA Finance"
  
  # Configuration
  engine               = "redis"
  engine_version       = "7.0"
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  port                 = 6379
  node_type           = "cache.r6g.large"  # Graviton2 for cost optimization
  
  # Cluster configuration
  num_cache_clusters         = 3
  automatic_failover_enabled = true
  multi_az_enabled          = true
  
  # Network configuration
  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis_sg.id]
  
  # Backup configuration
  snapshot_retention_limit = 7
  snapshot_window         = "03:00-05:00"  # UTC, during low activity
  maintenance_window      = "Sun:05:00-Sun:07:00"  # UTC
  
  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                = random_password.redis_auth_token.result
  kms_key_id                = aws_kms_key.main.arn
  
  # Logging
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow_log.name
    destination_type = "cloudwatch-logs"
    log_format      = "text"
    log_type        = "slow-log"
  }
  
  # Auto minor version upgrades
  auto_minor_version_upgrade = true
  
  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-redis-cluster"
    Purpose = "cache-and-sessions"
  })
}

# Redis CloudWatch Log Group
resource "aws_cloudwatch_log_group" "redis_slow_log" {
  name              = "/mita/${var.environment}/redis/slow-log"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main.arn

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-redis-slow-log"
  })
}

# Database backup automation using AWS Backup
resource "aws_backup_vault" "main" {
  name        = "${local.cluster_name}-backup-vault"
  kms_key_arn = aws_kms_key.main.arn

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-backup-vault"
  })
}

resource "aws_backup_plan" "database_backup" {
  name = "${local.cluster_name}-database-backup"

  rule {
    rule_name         = "daily_backup"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 2 * * ? *)"  # Daily at 2 AM UTC
    start_window      = 60   # Start within 1 hour
    completion_window = 480  # Complete within 8 hours

    lifecycle {
      cold_storage_after = 30   # Move to cold storage after 30 days
      delete_after       = 2557 # Keep for 7 years (financial compliance)
    }

    recovery_point_tags = merge(local.common_tags, {
      BackupType = "daily"
    })
  }

  rule {
    rule_name         = "weekly_backup"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 3 ? * SUN *)"  # Weekly on Sunday at 3 AM UTC
    start_window      = 60
    completion_window = 480

    lifecycle {
      cold_storage_after = 30
      delete_after       = 2557  # 7 years
    }

    recovery_point_tags = merge(local.common_tags, {
      BackupType = "weekly"
    })
  }

  rule {
    rule_name         = "monthly_backup"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 4 1 * ? *)"  # Monthly on 1st at 4 AM UTC
    start_window      = 60
    completion_window = 480

    lifecycle {
      cold_storage_after = 30
      delete_after       = 2557  # 7 years
    }

    recovery_point_tags = merge(local.common_tags, {
      BackupType = "monthly"
    })
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-database-backup-plan"
  })
}

# Backup selection
resource "aws_backup_selection" "database" {
  iam_role_arn = aws_iam_role.backup.arn
  name         = "${local.cluster_name}-database-selection"
  plan_id      = aws_backup_plan.database_backup.id

  resources = [
    module.rds.db_instance_arn,
    aws_elasticache_replication_group.redis.arn
  ]

  condition {
    string_equals {
      key   = "aws:ResourceTag/Backup"
      value = "required"
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-database-backup-selection"
  })
}

# IAM role for AWS Backup
resource "aws_iam_role" "backup" {
  name = "${local.cluster_name}-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-backup-role"
  })
}

resource "aws_iam_role_policy_attachment" "backup_service" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "backup_restore" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

# Provider for DR region
provider "aws" {
  alias  = "us_west_2"
  region = "us-west-2"
  
  default_tags {
    tags = {
      Environment = var.environment
      Project     = "MITA"
      Owner       = "DevOps"
      ManagedBy   = "Terraform"
      Purpose     = "DisasterRecovery"
    }
  }
}