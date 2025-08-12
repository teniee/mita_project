# EKS Cluster Configuration for MITA Finance
# Production-grade Kubernetes cluster with security hardening

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.15"

  cluster_name    = local.cluster_name
  cluster_version = "1.27"

  # Cluster endpoint configuration
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = true
  cluster_endpoint_public_access_cidrs = ["0.0.0.0/0"]

  # VPC Configuration
  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.intra_subnets

  # Additional security groups
  cluster_additional_security_group_ids = [aws_security_group.eks_additional_sg.id]

  # Cluster encryption
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks.arn
    resources        = ["secrets"]
  }

  # Logging configuration
  cluster_enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cloudwatch_log_group_retention_in_days = 30

  # Managed Node Groups
  eks_managed_node_groups = {
    # Primary node group for application workloads
    primary = {
      name = "${local.cluster_name}-primary"
      
      ami_type       = "AL2_x86_64"
      instance_types = ["t3.large", "t3.xlarge"]
      capacity_type  = "ON_DEMAND"
      
      min_size     = 3
      max_size     = 10
      desired_size = 5
      
      # Subnet configuration
      subnet_ids = module.vpc.private_subnets
      
      # Launch template configuration
      create_launch_template = true
      launch_template_name   = "${local.cluster_name}-primary-lt"
      launch_template_use_name_prefix = true
      launch_template_version = "$Latest"
      
      # Instance configuration
      ebs_optimized = true
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 150
            encrypted             = true
            kms_key_id           = aws_kms_key.ebs.arn
            delete_on_termination = true
          }
        }
      }
      
      # Security configuration
      vpc_security_group_ids = [aws_security_group.eks_additional_sg.id]
      
      # Node group configuration
      force_update_version = false
      update_config = {
        max_unavailable_percentage = 25
      }
      
      # Taints and labels
      labels = {
        Environment = var.environment
        NodeGroup   = "primary"
        WorkloadType = "general"
      }
      
      tags = merge(local.common_tags, {
        Name = "${local.cluster_name}-primary-nodes"
      })
    }
    
    # Spot instances for non-critical workloads
    spot = {
      name = "${local.cluster_name}-spot"
      
      ami_type       = "AL2_x86_64"
      instance_types = ["t3.medium", "t3.large", "m5.large"]
      capacity_type  = "SPOT"
      
      min_size     = 1
      max_size     = 8
      desired_size = 3
      
      subnet_ids = module.vpc.private_subnets
      
      create_launch_template = true
      launch_template_name   = "${local.cluster_name}-spot-lt"
      launch_template_use_name_prefix = true
      
      ebs_optimized = true
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 50
            volume_type           = "gp3"
            encrypted             = true
            kms_key_id           = aws_kms_key.ebs.arn
            delete_on_termination = true
          }
        }
      }
      
      vpc_security_group_ids = [aws_security_group.eks_additional_sg.id]
      
      update_config = {
        max_unavailable_percentage = 50
      }
      
      labels = {
        Environment = var.environment
        NodeGroup   = "spot"
        WorkloadType = "batch"
      }
      
      taints = [
        {
          key    = "spot-instance"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      ]
      
      tags = merge(local.common_tags, {
        Name = "${local.cluster_name}-spot-nodes"
      })
    }
  }

  # AWS Auth ConfigMap configuration
  manage_aws_auth_configmap = true
  
  aws_auth_roles = [
    {
      rolearn  = aws_iam_role.eks_admin.arn
      username = "eks-admin"
      groups   = ["system:masters"]
    },
    {
      rolearn  = aws_iam_role.developer.arn
      username = "developer"
      groups   = ["developers"]
    }
  ]

  aws_auth_users = [
    {
      userarn  = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
      username = "root"
      groups   = ["system:masters"]
    }
  ]

  # Add-ons configuration
  cluster_addons = {
    coredns = {
      resolve_conflicts = "OVERWRITE"
      addon_version     = "v1.10.1-eksbuild.1"
    }
    
    kube-proxy = {
      resolve_conflicts = "OVERWRITE"
      addon_version     = "v1.27.1-eksbuild.1"
    }
    
    vpc-cni = {
      resolve_conflicts = "OVERWRITE"
      addon_version     = "v1.12.6-eksbuild.2"
    }
    
    aws-ebs-csi-driver = {
      resolve_conflicts = "OVERWRITE"
      addon_version     = "v1.19.0-eksbuild.2"
      service_account_role_arn = module.ebs_csi_irsa_role.iam_role_arn
    }
  }

  tags = local.common_tags
}

# IRSA for EBS CSI Driver
module "ebs_csi_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.cluster_name}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}

# IRSA for AWS Load Balancer Controller
module "aws_load_balancer_controller_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                              = "${local.cluster_name}-aws-load-balancer-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}

# IRSA for External DNS
module "external_dns_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                     = "${local.cluster_name}-external-dns"
  attach_external_dns_policy    = true
  external_dns_hosted_zone_arns = ["arn:aws:route53:::hostedzone/*"]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:external-dns"]
    }
  }
}

# IRSA for Cluster Autoscaler
module "cluster_autoscaler_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                        = "${local.cluster_name}-cluster-autoscaler"
  attach_cluster_autoscaler_policy = true
  cluster_autoscaler_cluster_ids   = [module.eks.cluster_id]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:cluster-autoscaler"]
    }
  }
}

# IAM Roles for human access
resource "aws_iam_role" "eks_admin" {
  name = "${local.cluster_name}-admin-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "mita-admin"
          }
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role" "developer" {
  name = "${local.cluster_name}-developer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Condition = {
          StringEquals = {
            "sts:ExternalId" = "mita-dev"
          }
        }
      }
    ]
  })

  tags = local.common_tags
}