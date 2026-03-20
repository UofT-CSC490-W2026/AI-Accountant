# --- Required inputs (no defaults — caller must provide) ---

# Used in secret name like "autobook-dev-db-credentials"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in secret name like "autobook-dev-db-credentials"
variable "environment" {
  type        = string
  description = "Deployment environment, used in resource naming"
}

# Database hostname from the database module — e.g. "autobook-dev-db.abc123.ca-central-1.rds.amazonaws.com"
# This is stored inside the secret JSON so ECS containers know where to connect
variable "db_address" {
  type        = string
  description = "RDS hostname from database module"
}

# Master password for the database — same value passed to the database module
# Injected via TF_VAR_db_password at runtime, never in code or tfvars
variable "db_password" {
  type        = string
  description = "Database master password (injected via TF_VAR_db_password)"
  sensitive   = true
}

# --- Optional inputs (safe defaults matching the database module) ---

# Database port — PostgreSQL default is 5432
variable "db_port" {
  type        = number
  description = "Database port number"
  default     = 5432
}

# Database name — defaults to the project name (same as database module's db_name)
variable "db_name" {
  type        = string
  description = "Database name (must match what the database module created)"
  default     = null # null = use var.project
}

# Database username — defaults to the project name (same as database module's username)
variable "db_username" {
  type        = string
  description = "Database master username (must match what the database module created)"
  default     = null # null = use var.project
}

# How many days Secrets Manager waits before permanently deleting a secret.
# Default: 0 (dev-friendly — allows immediate re-creation after terraform destroy).
# With a non-zero window, the secret name is "reserved" during the recovery period,
# blocking terraform apply if you destroy and recreate the environment.
# Prod overrides to 7 for accidental deletion recovery.
variable "recovery_window_in_days" {
  type        = number
  description = "Days before a deleted secret is permanently removed (0 = immediate)"
  default     = 0
}
