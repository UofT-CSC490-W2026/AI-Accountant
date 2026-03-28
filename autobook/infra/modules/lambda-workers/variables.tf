# =============================================================================
# REQUIRED INPUTS — from other modules
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

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs — Lambda functions run here for DB/Redis access"
}

variable "app_sg_id" {
  type        = string
  description = "Security group for Lambda functions (same as ECS — allows DB, Redis, NAT)"
}

# --- From IAM module ---

variable "lambda_role_arns" {
  type        = map(string)
  description = "Map of worker name → Lambda execution role ARN from IAM module"
}

# --- From queuing module ---

variable "queue_arns" {
  type        = map(string)
  description = "Map of queue name → SQS ARN — used for event source mappings"
}

variable "queue_urls" {
  type        = map(string)
  description = "Map of queue name → SQS URL — injected as env vars for downstream sends"
}

# --- From secrets module ---

variable "db_credentials_secret_arn" {
  type        = string
  description = "Secrets Manager ARN for DB credentials — read via Lambda Extension"
}

# --- From cache module ---

variable "redis_endpoint" {
  type        = string
  description = "Redis primary endpoint hostname"
  default     = "localhost"
}

variable "redis_port" {
  type        = number
  description = "Redis port number"
  default     = 6379
}

# --- From storage module ---

variable "s3_bucket_id" {
  type        = string
  description = "S3 bucket name — passed as env var for file access"
}

# =============================================================================
# OPTIONAL INPUTS — safe defaults provided
# =============================================================================

variable "memory_size" {
  type        = number
  description = "Lambda memory in MB (also scales CPU proportionally)"
  default     = 512
}

variable "timeout" {
  type        = number
  description = "Lambda timeout in seconds (max 900)"
  default     = 60
}

variable "log_retention_days" {
  type        = number
  description = "Days to keep Lambda logs in CloudWatch"
  default     = 30
}

variable "sqs_batch_size" {
  type        = number
  description = "Max messages per Lambda invocation from SQS"
  default     = 1
}

# --- From ML module ---

variable "sagemaker_endpoint_name" {
  type        = string
  description = "SageMaker endpoint name — injected into ml_inference worker (null = heuristic only)"
  default     = null
}
