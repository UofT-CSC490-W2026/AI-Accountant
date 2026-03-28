# --- Values other modules need from the cache ---

# Compute module needs this so ECS containers can connect to Redis
# This is the primary endpoint — handles both reads and writes
# Apps use this single endpoint for queues, caches, and pub/sub
output "redis_endpoint" {
  description = "Redis primary endpoint hostname — use this to connect from application code"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

# Compute module needs this to build the full connection URL (rediss://host:port)
# Note: rediss:// (with double s) because transit_encryption_enabled = true (TLS).
# Using redis:// (single s) will fail to connect — TLS is required.
# ElastiCache Redis always uses port 6379
output "redis_port" {
  description = "Redis port number (always 6379)"
  value       = aws_elasticache_replication_group.main.port
}
