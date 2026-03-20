# --- Required inputs from the calling environment (dev/prod) ---

# Used in resource names like "autobook-dev-public-a"
variable "project" {
  type        = string
  description = "Project name, used in resource naming (e.g. 'autobook')"
}

# Determines naming and any env-specific logic
variable "environment" {
  type        = string
  description = "Deployment environment (dev or prod), used in resource naming"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

# Subnets are placed in availability zones within this region (e.g. ca-central-1a, ca-central-1b)
variable "region" {
  type        = string
  description = "AWS region — subnets are placed in availability zones within this region"
}

# The overall IP range for the VPC — all subnets must fit within this
# /16 = 65,536 addresses, more than enough for dev and prod
variable "vpc_cidr" {
  type        = string
  description = "IP address range for the entire VPC (e.g. '10.0.0.0/16' = 65,536 addresses)"
  default     = "10.0.0.0/16"
}

# Public subnets hold internet-facing resources (ALB)
# Two subnets in two AZs for redundancy — if one AZ goes down, the other still works
variable "public_subnet_cidrs" {
  type        = list(string)
  description = "IP ranges for public subnets — resources here are reachable from the internet"
  default     = ["10.0.1.0/24", "10.0.2.0/24"] # 256 addresses each
}

# Private subnets hold internal resources (database, Redis, ECS workers)
# Not reachable from the internet — only accessible from within the VPC
variable "private_subnet_cidrs" {
  type        = list(string)
  description = "IP ranges for private subnets — resources here are NOT reachable from the internet"
  default     = ["10.0.10.0/24", "10.0.11.0/24"] # 256 addresses each
}
