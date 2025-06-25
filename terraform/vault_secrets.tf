terraform {
  required_version = ">= 1.3"
  required_providers {
    vault = {
      source = "hashicorp/vault"
      version = ">= 3.0"
    }
  }
}

provider "vault" {
  address = var.vault_address
  token   = var.vault_token
}

variable "vault_address" {}
variable "vault_token" {}
variable "env" { default = "prod" }

resource "vault_kv_secret_v2" "mita_secrets" {
  mount = "secret"
  name  = "mita/${var.env}/app"

  data_json = jsonencode({
    DATABASE_URL = var.database_url
    REDIS_URL    = var.redis_url
    SENTRY_DSN   = var.sentry_dsn
  })
}

variable "database_url" {}
variable "redis_url" {}
variable "sentry_dsn" {}
