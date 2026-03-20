# --- Required inputs (no defaults — caller must provide) ---

# Used in resource names like "autobook-dev-sagemaker-endpoint"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in resource names and SageMaker endpoint naming
variable "environment" {
  type        = string
  description = "Deployment environment (dev, prod)"
}

# SageMaker endpoints live in private subnets — no internet access needed,
# but ECS services reach them over the VPC network
variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for SageMaker endpoint (from networking module)"
}

# Controls which services can call the SageMaker endpoint (HTTPS on 443)
variable "sagemaker_sg_id" {
  type        = string
  description = "Security group ID for SageMaker (from networking module)"
}

# --- Optional inputs (safe defaults provided) ---

# The ECR image URI for the ML model container
# When null, only the SageMaker execution role is created — no model/endpoint
# This lets the module be deployed before any model image exists
variable "model_image" {
  type        = string
  description = "ECR image URI for the ML model (null = skip endpoint creation, role only)"
  default     = null
}

# Serverless inference provisions compute on-demand and scales to zero when idle
# Real-time inference keeps instances running (needed for GPU or low-latency)
variable "serverless" {
  type        = bool
  description = "Use serverless inference (true) or real-time inference (false)"
  default     = true
}

# --- Serverless inference settings (only used when serverless = true) ---

# Memory allocation in MB — SageMaker provisions proportional CPU
# Valid values: 1024, 2048, 3072, 4096, 5120, 6144
variable "serverless_memory_mb" {
  type        = number
  description = "Memory for serverless inference in MB (1024-6144)"
  default     = 2048
}

# Maximum concurrent invocations before SageMaker throttles
# Each invocation gets its own container — higher = more parallel capacity
variable "serverless_max_concurrency" {
  type        = number
  description = "Max concurrent invocations for serverless inference"
  default     = 5
}

# --- Real-time inference settings (only used when serverless = false) ---

# Instance type for real-time inference
# ml.g4dn.xlarge: 1 T4 GPU, 4 vCPUs, 16GB RAM — cheapest GPU option
variable "instance_type" {
  type        = string
  description = "Instance type for real-time inference (e.g. ml.g4dn.xlarge)"
  default     = "ml.g4dn.xlarge"
}

# Number of instances behind the endpoint
# 1 for dev (cost savings), 2+ for prod (high availability)
variable "instance_count" {
  type        = number
  description = "Number of instances for real-time inference"
  default     = 1
}
