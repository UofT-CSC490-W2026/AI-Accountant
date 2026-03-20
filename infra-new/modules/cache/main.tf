# Naming convention
locals {
  name = "${var.project}-${var.environment}-redis" # e.g. "autobook-dev-redis"
}

# =============================================================================
# REDIS SUBNET GROUP — tells ElastiCache which subnets it can launch in
# =============================================================================
# ElastiCache requires this — it picks subnets to place nodes in.
# Private subnets = Redis is not reachable from the internet.
resource "aws_elasticache_subnet_group" "main" {
  name       = local.name
  subnet_ids = var.private_subnet_ids # From networking module

  tags = { Name = local.name }
}

# =============================================================================
# ELASTICACHE REPLICATION GROUP — Redis instance
# =============================================================================
# One Redis instance serves all three roles for the application:
#   1. Job queues — 7 queues (files, precedent, model, llm, resolution, post, flywheel)
#   2. Hot caches — per-user cache (tier 1) + shared cache (tier 2)
#   3. Pub/sub   — real-time notifications ("entry posted", "transactions ready")
#
# We use a replication group (not a standalone cluster) because it supports:
#   - Single-node mode for dev (num_cache_clusters = 1, cheapest)
#   - Multi-node with automatic failover for prod (num_cache_clusters = 2+)
#   - Same resource type either way — no code change between environments
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = local.name # Unique name in AWS
  description          = "${local.name} — queues, caches, pub/sub"

  # --- Engine: always Redis ---
  engine         = "redis"
  engine_version = var.engine_version # e.g. "7.1"

  # --- Size: controlled by caller ---
  node_type = var.node_type # Machine size (CPU, memory, max connections)

  # --- Topology: controlled by caller ---
  num_cache_clusters         = var.num_cache_clusters         # 1 = primary only, 2+ = primary + replicas
  automatic_failover_enabled = var.automatic_failover_enabled # Requires 2+ nodes
  multi_az_enabled           = var.multi_az_enabled           # Requires failover enabled

  # --- Network: private subnets, ECS-only access ---
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [var.redis_sg_id]

  # --- Encryption: always on ---
  # At rest: encrypts data stored on disk (snapshots, swap files)
  at_rest_encryption_enabled = true
  # In transit: encrypts data between app and Redis (TLS)
  # Redis 7+ allows enabling/disabling this without replacing the cluster
  transit_encryption_enabled = true

  # --- Backups: controlled by caller ---
  snapshot_retention_limit = var.snapshot_retention_limit # 0 = no snapshots

  # --- Maintenance: controlled by caller ---
  apply_immediately = var.apply_immediately # Apply changes now vs next maintenance window

  # --- Upgrades: auto-apply minor patches (security fixes) ---
  auto_minor_version_upgrade = true

  tags = { Name = local.name }
}
