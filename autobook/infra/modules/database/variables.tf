# --- Required inputs (no defaults — caller must provide) ---

# Used in resource names like "autobook-dev-db"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in resource names like "autobook-dev-db"
variable "environment" {
  type        = string
  description = "Deployment environment, used in resource naming"
}

# Database is placed in private subnets — not reachable from internet
variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs from networking module"
}

# Firewall rule — only ECS services can connect on port 5432
variable "db_sg_id" {
  type        = string
  description = "Security group ID from networking module"
}

# Machine size — determines CPU, memory, cost
variable "db_instance_class" {
  type        = string
  description = "RDS instance size (e.g. 'db.t4g.micro', 'db.t4g.medium')"
}

# Master password — never hardcoded, injected via TF_VAR_db_password
variable "db_password" {
  type        = string
  description = "Master password for the database"
  sensitive   = true
}

# --- Optional inputs (safe defaults provided) ---

# Disk space — 20 is the RDS minimum
variable "allocated_storage" {
  type        = number
  description = "Storage in GB (20 = RDS minimum)"
  default     = 20
}

# Standby copy in a second AZ — if primary fails, standby takes over automatically
variable "multi_az" {
  type        = bool
  description = "Deploy a standby replica in a second availability zone for failover"
  default     = false
}

# How many days of automated backups to keep
variable "backup_retention_period" {
  type        = number
  description = "Days to keep automated backups (0 = disabled)"
  default     = 7
}

# Prevents accidental deletion — must be disabled manually before destroy
# Default: false (dev-friendly — allows easy teardown). Prod overrides to true.
variable "deletion_protection" {
  type        = bool
  description = "Block deletion until this is explicitly disabled"
  default     = false
}

# Whether to take a final snapshot when the database is deleted
# Default: true (dev-friendly — skip snapshot for fast teardown). Prod overrides to false.
# Together with deletion_protection=false, this means dev can be destroyed freely.
# Prod sets deletion_protection=true + skip_final_snapshot=false for safety.
variable "skip_final_snapshot" {
  type        = bool
  description = "Skip final snapshot on delete (true = no snapshot, data is lost)"
  default     = true
}

# Restore from an existing snapshot instead of creating an empty database
variable "restore_snapshot_id" {
  type        = string
  description = "RDS snapshot ID to restore from (null = create fresh)"
  default     = null
}
