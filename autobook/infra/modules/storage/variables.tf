# --- Required inputs (no defaults — caller must provide) ---

# Used in bucket name like "autobook-dev-data-609092547371"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in bucket name like "autobook-dev-data-609092547371"
variable "environment" {
  type        = string
  description = "Deployment environment, used in resource naming"
}

# AWS account ID — makes the bucket name globally unique across all AWS accounts
# S3 bucket names must be unique worldwide, not just in your account
variable "account_id" {
  type        = string
  description = "AWS account ID, appended to bucket name for global uniqueness"
}

# --- Optional inputs (safe defaults provided) ---

# Days before processed files move to Infrequent Access storage class
# IA costs ~45% less per GB but charges per retrieval — good for files rarely re-read
# 0 = no transition (everything stays in Standard)
variable "ia_transition_days" {
  type        = number
  description = "Days before processed/ objects move to Infrequent Access (0 = disabled)"
  default     = 90
}

# Days before incomplete multipart uploads are automatically cleaned up
# Incomplete uploads happen when a large file upload is interrupted — they cost money silently
variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are cleaned up"
  default     = 7
}

# Prevent accidental deletion of the bucket and all its data
variable "force_destroy" {
  type        = bool
  description = "Allow terraform destroy to delete the bucket even if it contains objects"
  default     = false
}
