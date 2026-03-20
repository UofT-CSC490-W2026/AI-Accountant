# =============================================================================
# CORE — project identity and region
# =============================================================================

# Used in resource names across all modules (e.g. "autobook-prod-vpc")
variable "project" {
  type        = string
  description = "Project name, used in resource naming across all modules"
}

# Determines naming and environment-specific defaults (e.g. multi-AZ DB for prod)
variable "environment" {
  type        = string
  description = "Deployment environment (dev or prod)"
}

# AWS region where all resources are created
# ca-central-1 for Canadian data residency requirements
variable "region" {
  type        = string
  description = "AWS region for all resources"
}

# AWS account ID — used for globally unique S3 bucket naming
# Not a secret — visible in ARNs, console, and our backend.tf bucket name
variable "account_id" {
  type        = string
  description = "AWS account ID (used in S3 bucket naming for global uniqueness)"
}

# =============================================================================
# DNS + TLS — domain configuration
# =============================================================================

# Root domain — used by DNS module to create API subdomain records
variable "domain_name" {
  type        = string
  description = "Root domain name (e.g. autobook.tech)"
}

# =============================================================================
# DATABASE — RDS configuration
# =============================================================================

# Machine size for the RDS PostgreSQL instance
# db.t4g.large: 2 vCPUs, 8 GB RAM — handles production query load
variable "db_instance_class" {
  type        = string
  description = "RDS instance size (e.g. db.t4g.large for prod)"
}

# Master password for PostgreSQL — NEVER put this in terraform.tfvars
# Pass via environment variable: export TF_VAR_db_password="your-password"
variable "db_password" {
  type        = string
  description = "RDS master password (pass via TF_VAR_db_password, never commit)"
  sensitive   = true # Prevents Terraform from showing this in console output
}

# =============================================================================
# CI/CD — GitHub Actions OIDC
# =============================================================================

# GitHub repository in "org/repo" format — used in OIDC trust policy
# Only this repo can assume the deploy role (prevents other repos from deploying)
variable "github_repo" {
  type        = string
  description = "GitHub repository (org/repo format) for OIDC deploy role trust"
}

# =============================================================================
# MONITORING — alerts and budget
# =============================================================================

# Email address for CloudWatch alarm notifications
# SNS sends a confirmation email after first apply — must click to activate
variable "alert_email" {
  type        = string
  description = "Email for alarm notifications (must confirm SNS subscription)"
}

# Monthly AWS spending limit — alerts at 80% (forecast) and 100% (actual)
variable "monthly_budget_usd" {
  type        = string
  description = "Monthly AWS budget limit in USD"
}

# =============================================================================
# QDRANT CLOUD — vector database credentials (secrets, via TF_VAR_)
# =============================================================================

# Qdrant Cloud management API key — used by the qdrant-cloud provider
# Pass via: export TF_VAR_qdrant_cloud_api_key="your-key"
variable "qdrant_cloud_api_key" {
  type        = string
  description = "Qdrant Cloud API key (pass via TF_VAR_qdrant_cloud_api_key, never commit)"
  sensitive   = true
}

# Qdrant Cloud account identifier — used by the qdrant-cloud provider
# Pass via: export TF_VAR_qdrant_cloud_account_id="your-id"
variable "qdrant_cloud_account_id" {
  type        = string
  description = "Qdrant Cloud account ID (pass via TF_VAR_qdrant_cloud_account_id, never commit)"
  sensitive   = true
}
