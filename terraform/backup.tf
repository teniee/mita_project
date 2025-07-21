terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

variable "backup_bucket" {
  default = "mita-backups"
}

resource "aws_s3_bucket" "db_backups" {
  bucket        = var.backup_bucket
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "expire" {
  bucket = aws_s3_bucket.db_backups.id

  rule {
    id     = "expire-old"
    status = "Enabled"

    expiration {
      days = 7
    }
  }
}
