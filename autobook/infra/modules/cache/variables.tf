# --- Required inputs (no defaults — caller must provide) ---

# Used in resource names like "autobook-dev-redis"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in resource names like "autobook-dev-redis"
variable "environment" {
  type        = string
  description = "Deployment environment, used in resource naming"
}

# Redis is placed in private subnets — not reachable from internet
variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs from networking module"
}

# Firewall rule — only ECS services can connect on port 6379
variable "redis_sg_id" {
  type        = string
  description = "Security group ID from networking module"
}

# Machine size — determines CPU, memory, max connections
# Examples: "cache.t4g.micro" (dev, ~$12/mo), "cache.r7g.large" (prod, ~$200/mo)
variable "node_type" {
  type        = string
  description = "ElastiCache node size (e.g. 'cache.t4g.micro', 'cache.r7g.large')"
}

# --- Optional inputs (safe defaults provided) ---

# Redis 7.1 is the latest stable version (as of 2026)
variable "engine_version" {
  type        = string
  description = "Redis engine version"
  default     = "7.1"
}

# Number of nodes in the replication group (1 = primary only, 2+ = primary + replicas)
# Dev: 1 (no redundancy, cheapest). Prod: 2+ (automatic failover if primary fails).
variable "num_cache_clusters" {
  type        = number
  description = "Total nodes: 1 = primary only, 2+ = primary + read replicas for failover"
  default     = 1
}

# Automatic failover — if the primary node dies, a replica takes over automatically
# Requires num_cache_clusters >= 2 (you need a replica to fail over to)
variable "automatic_failover_enabled" {
  type        = bool
  description = "Enable automatic failover to a replica if primary fails (requires 2+ nodes)"
  default     = false
}

# Multi-AZ — place primary and replica in different availability zones
# If an entire AZ goes down, the replica in the other AZ takes over
# Requires automatic_failover_enabled = true
variable "multi_az_enabled" {
  type        = bool
  description = "Place nodes in different AZs for resilience (requires failover enabled)"
  default     = false
}

# How many days of daily snapshots to keep (0 = no snapshots)
# Snapshots let you restore Redis to a previous point in time
variable "snapshot_retention_limit" {
  type        = number
  description = "Days to keep daily Redis snapshots (0 = disabled)"
  default     = 0
}

# Whether to apply changes immediately or wait for the next maintenance window
# true = changes apply now (may cause brief downtime). false = changes apply during maintenance.
variable "apply_immediately" {
  type        = bool
  description = "Apply changes immediately instead of waiting for maintenance window"
  default     = true
}
