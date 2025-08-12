# Monitoring and Observability Infrastructure for MITA Finance
# Comprehensive monitoring stack with Prometheus, Grafana, ELK, and alerting

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "eks_cluster" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main.arn

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-eks-logs"
  })
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/mita/${var.environment}/application"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.main.arn

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-app-logs"
  })
}

resource "aws_cloudwatch_log_group" "audit" {
  name              = "/mita/${var.environment}/audit"
  retention_in_days = 2557  # 7 years for financial compliance
  kms_key_id        = aws_kms_key.main.arn

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-audit-logs"
  })
}

# OpenSearch (Elasticsearch) for log aggregation
resource "aws_opensearch_domain" "logs" {
  domain_name    = "${local.cluster_name}-logs"
  engine_version = "OpenSearch_2.3"

  cluster_config {
    instance_type            = "t3.small.search"
    instance_count           = 3
    dedicated_master_enabled = true
    master_instance_type     = "t3.small.search"
    master_instance_count    = 3
    zone_awareness_enabled   = true
    
    zone_awareness_config {
      availability_zone_count = 3
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = 100
    throughput  = 250
  }

  encrypt_at_rest {
    enabled    = true
    kms_key_id = aws_kms_key.main.arn
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  vpc_options {
    subnet_ids         = module.vpc.private_subnets
    security_group_ids = [aws_security_group.opensearch.id]
  }

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "es:*"
        Principal = "*"
        Effect   = "Allow"
        Resource = "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${local.cluster_name}-logs/*"
      }
    ]
  })

  log_publishing_options {
    cloudwatch_log_group_arn = "${aws_cloudwatch_log_group.opensearch_index_slow_logs.arn}:*"
    log_type                 = "INDEX_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = "${aws_cloudwatch_log_group.opensearch_search_slow_logs.arn}:*"
    log_type                 = "SEARCH_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = "${aws_cloudwatch_log_group.opensearch_es_application_logs.arn}:*"
    log_type                 = "ES_APPLICATION_LOGS"
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-opensearch"
  })

  depends_on = [aws_iam_service_linked_role.opensearch]
}

resource "aws_iam_service_linked_role" "opensearch" {
  aws_service_name = "opensearchservice.amazonaws.com"
}

resource "aws_security_group" "opensearch" {
  name_prefix = "${local.cluster_name}-opensearch-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for OpenSearch cluster"

  ingress {
    description = "HTTPS from EKS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    security_groups = [aws_security_group.eks_additional_sg.id]
  }

  ingress {
    description = "HTTP from EKS"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    security_groups = [aws_security_group.eks_additional_sg.id]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-opensearch-sg"
  })
}

# CloudWatch Log Groups for OpenSearch
resource "aws_cloudwatch_log_group" "opensearch_index_slow_logs" {
  name              = "/aws/opensearch/domains/${local.cluster_name}-logs/index-slow-logs"
  retention_in_days = 14

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-opensearch-index-slow-logs"
  })
}

resource "aws_cloudwatch_log_group" "opensearch_search_slow_logs" {
  name              = "/aws/opensearch/domains/${local.cluster_name}-logs/search-slow-logs"
  retention_in_days = 14

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-opensearch-search-slow-logs"
  })
}

resource "aws_cloudwatch_log_group" "opensearch_es_application_logs" {
  name              = "/aws/opensearch/domains/${local.cluster_name}-logs/application-logs"
  retention_in_days = 14

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-opensearch-application-logs"
  })
}

# SNS Topics for Alerting
resource "aws_sns_topic" "critical_alerts" {
  name         = "${local.cluster_name}-critical-alerts"
  display_name = "MITA Critical Alerts"
  kms_master_key_id = aws_kms_key.main.arn

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-critical-alerts"
  })
}

resource "aws_sns_topic" "warning_alerts" {
  name         = "${local.cluster_name}-warning-alerts"
  display_name = "MITA Warning Alerts"
  kms_master_key_id = aws_kms_key.main.arn

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-warning-alerts"
  })
}

# CloudWatch Alarms for infrastructure
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${local.cluster_name}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EKS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EKS cluster CPU utilization"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]
  ok_actions          = [aws_sns_topic.warning_alerts.arn]

  dimensions = {
    ClusterName = local.cluster_name
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-high-cpu-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "database_connections" {
  alarm_name          = "${local.cluster_name}-db-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS database connections"
  alarm_actions       = [aws_sns_topic.warning_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = module.rds.db_instance_id
  }

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-db-connections-alarm"
  })
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.cluster_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/EKS", "cluster_failed_request_count", "ClusterName", local.cluster_name],
            ["AWS/EKS", "cluster_request_total", "ClusterName", local.cluster_name]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "EKS API Server Requests"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", module.rds.db_instance_id],
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", module.rds.db_instance_id]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "RDS Performance"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 24
        height = 6

        properties = {
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "CacheClusterId", aws_elasticache_replication_group.redis.id],
            ["AWS/ElastiCache", "DatabaseMemoryUsagePercentage", "CacheClusterId", aws_elasticache_replication_group.redis.id]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "ElastiCache Performance"
          period  = 300
        }
      }
    ]
  })
}

# X-Ray for distributed tracing
resource "aws_xray_sampling_rule" "main" {
  rule_name      = "${local.cluster_name}-sampling-rule"
  priority       = 9000
  version        = 1
  reservoir_size = 1
  fixed_rate     = 0.1
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"

  tags = merge(local.common_tags, {
    Name = "${local.cluster_name}-xray-sampling"
  })
}