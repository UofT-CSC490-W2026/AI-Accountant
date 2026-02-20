variable "env" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "ca-central-1"
}

variable "domain_name" {
  type    = string
  default = "autobook.app"
}

variable "api_subdomain" {
  type    = string
  default = "api"
  # "api" for prod, "dev-api" for dev
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "github_repo" {
  type    = string
  default = "your-org/autobook"
}

variable "alert_email" {
  type = string
}

# Shared naming — single source of truth
variable "bucket_name_prefix" {
  type    = string
  default = "autobook"
}

variable "secret_name_prefix" {
  type    = string
  default = "autobook"
}

# ECS naming — referenced by both compute module and CI/CD
variable "cluster_name_prefix" {
  type    = string
  default = "autobook"
}

variable "service_name_prefix" {
  type    = string
  default = "autobook-api"
}
# Actual names: autobook-${env} (cluster), autobook-api-${env} (service/task family)

# DR — only set when restoring from snapshot
variable "restore_snapshot_id" {
  type    = string
  default = null
}
