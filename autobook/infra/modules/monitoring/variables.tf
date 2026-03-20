# --- Required inputs (no defaults — caller must provide) ---

# Used in resource names like "autobook-dev-cpu-alarm"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in resource names and alarm descriptions
variable "environment" {
  type        = string
  description = "Deployment environment (dev, prod)"
}

# Email address that receives alarm notifications
# SNS sends a confirmation email — must be confirmed before alerts arrive
variable "alert_email" {
  type        = string
  description = "Email address for alarm notifications (must confirm subscription)"
}

# --- From compute module ---

# ECS cluster name — used as the "ClusterName" dimension in CloudWatch metrics
# CloudWatch groups all ECS metrics under this cluster
variable "cluster_name" {
  type        = string
  description = "ECS cluster name (from compute module) — CloudWatch metric dimension"
}

# List of ECS service names — one alarm per service for CPU and memory
# e.g. ["api", "file", "precedent-matcher", "model", "llm", "resolution", "posting", "flywheel"]
variable "service_names" {
  type        = list(string)
  description = "ECS service names (from compute module) — creates per-service alarms"
}

# The ARN suffix identifies this specific ALB in CloudWatch metrics
# Format: "app/autobook-dev-alb/abc123def456"
variable "alb_arn_suffix" {
  type        = string
  description = "ALB ARN suffix (from compute module) — CloudWatch metric dimension"
}

# --- From database module ---

# RDS instance identifier — used as the "DBInstanceIdentifier" dimension
variable "db_instance_id" {
  type        = string
  description = "RDS instance identifier (from database module) — CloudWatch metric dimension"
}

# --- Optional inputs (safe defaults provided) ---

# Alarm thresholds — starting values, tune after real traffic (D64)
# These are percentages (0-100) unless otherwise noted

# ECS CPU utilization threshold — triggers when a service is compute-bound
variable "ecs_cpu_threshold" {
  type        = number
  description = "ECS CPU utilization % that triggers alarm"
  default     = 80
}

# ECS memory utilization threshold — triggers before OOM kills
variable "ecs_memory_threshold" {
  type        = number
  description = "ECS memory utilization % that triggers alarm"
  default     = 80
}

# RDS CPU threshold — high DB CPU usually means missing indexes or heavy queries
variable "rds_cpu_threshold" {
  type        = number
  description = "RDS CPU utilization % that triggers alarm"
  default     = 80
}

# RDS database connections threshold — approaching max_connections causes failures
# Default 50 is conservative for db.t3.micro (max ~85 connections)
variable "rds_connections_threshold" {
  type        = number
  description = "RDS connection count that triggers alarm"
  default     = 50
}

# RDS free storage threshold in bytes — triggers before disk full
# 1 GB = 1,073,741,824 bytes — enough warning time to expand or clean up
variable "rds_free_storage_threshold" {
  type        = number
  description = "RDS free storage in bytes below which alarm triggers"
  default     = 1073741824 # 1 GB
}

# ALB 5xx error count — backend errors reaching clients
# Per 5-minute evaluation period
variable "alb_5xx_threshold" {
  type        = number
  description = "ALB 5xx error count per period that triggers alarm"
  default     = 10
}

# How many consecutive periods must breach before alarm fires
# 2 × 5min = 10 minutes of sustained breach to avoid flapping
variable "evaluation_periods" {
  type        = number
  description = "Number of consecutive periods to evaluate before alarming"
  default     = 2
}

# Length of each evaluation period in seconds
# 300s = 5 minutes — standard CloudWatch granularity
variable "period" {
  type        = number
  description = "Length of each evaluation period in seconds"
  default     = 300
}

# --- Budget ---

# Monthly budget limit in USD — alerts at 80% and 100%
# $50 is conservative for a dev environment with scale-to-zero
variable "monthly_budget_usd" {
  type        = string
  description = "Monthly AWS budget limit in USD (alerts at 80% and 100%)"
  default     = "50.0"
}

# Budget alert email — may differ from operational alerts
# Uses the same alert_email by default
variable "budget_alert_email" {
  type        = string
  description = "Email for budget alerts (null = use alert_email)"
  default     = null
}
