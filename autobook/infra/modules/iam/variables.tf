# --- Required inputs (no defaults — caller must provide) ---

# Used in role names like "autobook-dev-ecs-execution"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in role names like "autobook-dev-ecs-execution"
variable "environment" {
  type        = string
  description = "Deployment environment, used in resource naming"
}

# ARN of the GitHub OIDC provider (created in global stack)
# Allows GitHub Actions to assume AWS roles without stored credentials
variable "oidc_provider_arn" {
  type        = string
  description = "GitHub OIDC provider ARN from global stack"
}

# GitHub repo in "owner/repo" format — controls which repo can assume the deploy role
# Example: "UofT-CSC490-W2026/AI-Accountant"
variable "github_repo" {
  type        = string
  description = "GitHub repo (owner/repo) allowed to assume the deploy role"
}

# --- Optional inputs (provided when other modules are ready) ---

# ARN of the S3 data bucket — used to scope S3 permissions for api, file, flywheel services
# null = S3 policies are not created (useful when storage module hasn't been applied yet)
variable "s3_bucket_arn" {
  type        = string
  description = "S3 bucket ARN from storage module — used to scope S3 IAM policies"
}

# Map of queue name → ARN from the queuing module.
# Used to create per-service SQS policies (each service only gets access
# to the queues it sends to / receives from).
# Example: {"files" = "arn:aws:sqs:...:autobook-dev-files", "precedent" = "arn:...", ...}
variable "queue_arns" {
  type        = map(string)
  description = "Map of SQS queue name → ARN from queuing module — scopes per-service SQS permissions"
}
