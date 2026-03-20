# --- Required inputs (no defaults — caller must provide) ---

# Used in the subdomain name like "api.autobook.tech"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in the subdomain name — dev gets "api-dev.autobook.tech", prod gets "api.autobook.tech"
variable "environment" {
  type        = string
  description = "Deployment environment, used in subdomain naming"
}

# The root domain — from global stack's Route53 zone
# Example: "autobook.tech"
variable "domain_name" {
  type        = string
  description = "Root domain name (e.g. 'autobook.tech')"
}

# Route53 zone ID — the DNS zone where we create the record
# From global stack output
variable "zone_id" {
  type        = string
  description = "Route53 hosted zone ID from global stack"
}

# ALB DNS name — the load balancer's AWS-assigned hostname
# Example: "autobook-dev-123456.ca-central-1.elb.amazonaws.com"
# From compute module output
variable "alb_dns_name" {
  type        = string
  description = "ALB DNS name from compute module"
}

# ALB hosted zone ID — AWS-internal zone for the ALB (needed for alias records)
# This is NOT the same as the Route53 zone_id — it's an AWS-managed zone for the ALB
# From compute module output
variable "alb_zone_id" {
  type        = string
  description = "ALB hosted zone ID from compute module (for alias record)"
}

# --- Optional inputs ---

# Subdomain prefix for the API endpoint
# Dev uses "api-dev" → api-dev.autobook.tech
# Prod uses "api" → api.autobook.tech
variable "api_subdomain" {
  type        = string
  description = "Subdomain prefix for the API (e.g. 'api' or 'api-dev')"
  default     = null # null = auto-generate from environment
}
