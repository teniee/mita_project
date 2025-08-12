# VPC Configuration for MITA Finance
# Multi-AZ VPC with public, private, and data subnets for security isolation

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs = local.azs
  
  # Public subnets for load balancers and NAT gateways
  public_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 1),  # 10.0.1.0/24
    cidrsubnet(var.vpc_cidr, 8, 2),  # 10.0.2.0/24
    cidrsubnet(var.vpc_cidr, 8, 3),  # 10.0.3.0/24
  ]
  
  # Private subnets for application workloads
  private_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 10), # 10.0.10.0/24
    cidrsubnet(var.vpc_cidr, 8, 11), # 10.0.11.0/24
    cidrsubnet(var.vpc_cidr, 8, 12), # 10.0.12.0/24
  ]
  
  # Database subnets for RDS and ElastiCache
  database_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 20), # 10.0.20.0/24
    cidrsubnet(var.vpc_cidr, 8, 21), # 10.0.21.0/24
    cidrsubnet(var.vpc_cidr, 8, 22), # 10.0.22.0/24
  ]
  
  # Isolated subnets for management/bastion
  intra_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 30), # 10.0.30.0/24
  ]

  # NAT Gateway configuration
  enable_nat_gateway     = true
  single_nat_gateway     = false  # Multi-AZ NAT for HA
  enable_vpn_gateway     = false
  one_nat_gateway_per_az = true

  # DNS configuration
  enable_dns_hostnames = var.enable_dns_hostnames
  enable_dns_support   = var.enable_dns_support

  # Database subnet group
  create_database_subnet_group = true
  database_subnet_group_name   = "${local.cluster_name}-db-subnet-group"

  # ElastiCache subnet group
  create_elasticache_subnet_group = true
  elasticache_subnet_group_name   = "${local.cluster_name}-cache-subnet-group"

  # VPC Flow Logs for security monitoring
  enable_flow_log                      = var.enable_flow_logs
  create_flow_log_cloudwatch_iam_role  = true
  create_flow_log_cloudwatch_log_group = true
  flow_log_destination_type            = "cloud-watch-logs"
  flow_log_cloudwatch_log_group_retention_in_days = 30

  # Tags for EKS cluster discovery
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
    "kubernetes.io/cluster/${local.cluster_name}" = "shared"
  }

  database_subnet_tags = {
    Type = "database"
  }

  tags = local.common_tags
}

# Additional Security Groups
resource "aws_security_group" "database_sg" {
  name_prefix = "${local.cluster_name}-database-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for RDS database"

  ingress {
    description = "PostgreSQL from EKS"
    from_port   = 5432
    to_port     = 5432
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
    Name = "${local.cluster_name}-database-sg"
  })
}

resource "aws_security_group" "redis_sg" {
  name_prefix = "${local.cluster_name}-redis-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for Redis cache"

  ingress {
    description = "Redis from EKS"
    from_port   = 6379
    to_port     = 6379
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
    Name = "${local.cluster_name}-redis-sg"
  })
}

resource "aws_security_group" "eks_additional_sg" {
  name_prefix = "${local.cluster_name}-eks-additional-"
  vpc_id      = module.vpc.vpc_id
  description = "Additional security group for EKS cluster"

  ingress {
    description = "HTTPS from ALB"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  ingress {
    description = "HTTP from ALB"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
  }

  ingress {
    description = "API Server port from ALB"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
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
    Name = "${local.cluster_name}-eks-additional-sg"
  })
}

resource "aws_security_group" "alb_sg" {
  name_prefix = "${local.cluster_name}-alb-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for Application Load Balancer"

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
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
    Name = "${local.cluster_name}-alb-sg"
  })
}