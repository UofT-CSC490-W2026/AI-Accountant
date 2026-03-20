# =============================================================================
# REQUIRED INPUTS — from other modules, caller must provide all of these
# =============================================================================

# --- Naming ---

variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

variable "environment" {
  type        = string
  description = "Deployment environment, used in resource naming"
}

# --- From networking module ---

# ALB goes in public subnets (needs to receive internet traffic)
variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs — ALB is placed here"
}

# ECS services go in private subnets (no direct internet access, use NAT for outbound)
variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs — ECS tasks run here"
}

# Firewall for the ALB — allows HTTPS from the internet
variable "alb_sg_id" {
  type        = string
  description = "Security group for the ALB (allows HTTPS from internet)"
}

# Firewall for ECS services — only allows traffic from the ALB
variable "app_sg_id" {
  type        = string
  description = "Security group for ECS services (allows traffic from ALB only)"
}

# Needed by ALB target group to know which VPC it belongs to
variable "vpc_id" {
  type        = string
  description = "VPC ID from networking module"
}

# --- From IAM module ---

# Shared by all 8 services — lets the ECS agent pull images, write logs, read secrets
variable "execution_role_arn" {
  type        = string
  description = "ECS execution role ARN (image pull, logs, secrets)"
}

# Map of service name → role ARN — each service gets its own least-privilege permissions
# Example: {"api" = "arn:...", "file" = "arn:...", "llm" = "arn:...", ...}
variable "task_role_arns" {
  type        = map(string)
  description = "Map of service name → task role ARN from IAM module"
}

# --- From global stack ---

# TLS certificate for HTTPS — attached to the ALB listener
variable "cert_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS (from global stack)"
}

# --- From cache module ---

variable "redis_endpoint" {
  type        = string
  description = "Redis primary endpoint hostname"
}

variable "redis_port" {
  type        = number
  description = "Redis port number"
}

# --- From storage module ---

variable "s3_bucket_id" {
  type        = string
  description = "S3 bucket name — passed as env var to containers"
}

# --- From secrets module ---

# ECS reads individual fields from this JSON secret at container startup:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
variable "db_credentials_secret_arn" {
  type        = string
  description = "Secrets Manager ARN for DB credentials JSON"
}

# --- From auth module ---

# Only the API service needs these — used to validate user auth tokens
variable "user_pool_id" {
  type        = string
  description = "Cognito user pool ID (API service uses for auth validation)"
}

variable "client_id" {
  type        = string
  description = "Cognito app client ID (passed to frontend config)"
}

# --- From queuing module ---

# Map of queue name → SQS URL. Each service gets only the queue URLs it needs
# as environment variables (e.g. API gets SQS_QUEUE_FILES_URL, File Worker gets
# SQS_QUEUE_FILES_URL + SQS_QUEUE_PRECEDENT_URL).
# Example: {"files" = "https://sqs.ca-central-1.amazonaws.com/123.../autobook-dev-files", ...}
variable "queue_urls" {
  type        = map(string)
  description = "Map of SQS queue name → URL from queuing module — injected as container env vars"
}

# =============================================================================
# OPTIONAL INPUTS — safe defaults provided
# =============================================================================

# Port the API container listens on — must match the application's port
variable "container_port" {
  type        = number
  description = "Port the API container listens on (must match app config)"
  default     = 8000
}

# Fargate CPU allocation — 256 = 0.25 vCPU (smallest Fargate size)
# Valid values: 256, 512, 1024, 2048, 4096
# Same value for all 8 services — this is the BOOTSTRAP default only.
# CI/CD creates per-service task definition revisions with appropriate sizing.
# lifecycle { ignore_changes = [task_definition] } prevents Terraform from reverting.
variable "cpu" {
  type        = number
  description = "CPU units per task (256 = 0.25 vCPU) — bootstrap default, CI/CD overrides per service"
  default     = 256
}

# Fargate memory allocation — must be compatible with CPU value
# For 256 CPU: 512 or 1024 MB. For 512 CPU: 1024-4096 MB.
# Same bootstrap-only reasoning as cpu above.
variable "memory" {
  type        = number
  description = "Memory in MB per task — bootstrap default, CI/CD overrides per service"
  default     = 512
}

# How many copies of each service to run
# 0 = infrastructure exists but no containers are running (CI/CD deploys first)
variable "desired_count" {
  type        = number
  description = "Number of tasks per service (0 = no running containers until CI/CD deploys)"
  default     = 0
}

# How many days to keep container logs in CloudWatch
variable "log_retention_days" {
  type        = number
  description = "Days to keep container logs in CloudWatch"
  default     = 30
}

# URL path the ALB uses to check if the API service is healthy
variable "health_check_path" {
  type        = string
  description = "Health check endpoint for the API service"
  default     = "/health"
}
