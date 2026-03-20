# Cache

Creates the ElastiCache Redis instance that serves as the application's queue broker, hot cache, and pub/sub system.

## What it creates

- **Redis subnet group** — places Redis in private subnets (no internet access)
- **ElastiCache replication group** — single Redis instance serving 3 roles:
  - **7 job queues** — files, precedent, model, llm, resolution, post, flywheel
  - **2 hot caches** — per-user cache (tier 1 lookups), shared cache (tier 2 before SageMaker)
  - **Pub/sub** — real-time notifications (entry posted, transactions ready)

## Usage

```hcl
# Dev — small, single node, no backups
module "cache" {
  source = "../../modules/cache"

  project            = "autobook"
  environment        = "dev"
  private_subnet_ids = module.networking.private_subnet_ids
  redis_sg_id        = module.networking.redis_sg_id
  node_type          = "cache.t4g.micro"
}

# Prod — larger, with failover and daily snapshots
module "cache" {
  source = "../../modules/cache"

  project                    = "autobook"
  environment                = "prod"
  private_subnet_ids         = module.networking.private_subnet_ids
  redis_sg_id                = module.networking.redis_sg_id
  node_type                  = "cache.r7g.large"
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  snapshot_retention_limit   = 7
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| private_subnet_ids | list(string) | — | Subnets for Redis |
| redis_sg_id | string | — | Security group allowing ECS access |
| node_type | string | — | Machine size |
| engine_version | string | "7.1" | Redis version |
| num_cache_clusters | number | 1 | Total nodes (1 = no replicas) |
| automatic_failover_enabled | bool | false | Failover to replica on primary failure |
| multi_az_enabled | bool | false | Spread nodes across AZs |
| snapshot_retention_limit | number | 0 | Days to keep daily snapshots |
| apply_immediately | bool | true | Apply changes without waiting for maintenance |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| redis_endpoint | Primary endpoint hostname | compute (ECS container env vars) |
| redis_port | Port number (6379) | compute (ECS container env vars) |
