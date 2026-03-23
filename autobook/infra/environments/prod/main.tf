# =============================================================================
# PROD ENVIRONMENT — wires all 13 modules together with production values
# =============================================================================
# This is the root module for the prod environment. Same architecture as dev,
# but with hardened settings: multi-AZ database, Redis failover, MFA enforced,
# deletion protection, longer backup retention, and GPU-backed ML inference.
#
# To apply:
#   cd environments/prod
#   export TF_VAR_db_password="..."
#   export TF_VAR_qdrant_cloud_api_key="..."
#   export TF_VAR_qdrant_cloud_account_id="..."
#   terraform init
#   terraform plan
#   terraform apply

# =============================================================================
# GLOBAL REMOTE STATE — read outputs from the global stack
# =============================================================================
# The global stack (infra/global/) creates account-level resources:
#   - Route53 DNS zone (zone_id)
#   - ACM wildcard TLS certificate (cert_arn)
#   - GitHub OIDC provider (oidc_provider_arn)
#
# We read these outputs here so modules can reference them without recreating.
# This is a read-only data source — it cannot modify the global stack.
data "terraform_remote_state" "global" {
  backend = "s3"

  config = {
    bucket = "autobook-tfstate-609092547371" # Same S3 bucket as our backend
    key    = "global/terraform.tfstate"      # The global stack's state file key
    region = var.region                      # ca-central-1
  }
}

# =============================================================================
# NETWORKING — VPC, subnets, security groups
# =============================================================================
# Creates the virtual network where all AWS resources live.
# Prod uses the same VPC layout as dev — no need for different CIDRs because
# dev and prod are isolated by having separate VPCs (separate state files).
module "networking" {
  source = "../../modules/networking"

  project     = var.project     # "autobook"
  environment = var.environment # "prod"
  region      = var.region      # "ca-central-1"
}

# =============================================================================
# IAM — roles and permissions
# =============================================================================
# Creates IAM roles that control what each service is allowed to do.
# Same role structure as dev — permissions are environment-scoped by naming
# convention (e.g. "autobook-prod-*" ARN patterns in policies).
# Depends on storage (needs s3_bucket_arn to scope S3 permissions).
module "iam" {
  source = "../../modules/iam"

  project           = var.project
  environment       = var.environment
  oidc_provider_arn = data.terraform_remote_state.global.outputs.oidc_provider_arn
  github_repo       = var.github_repo
  s3_bucket_arn     = module.storage.bucket_arn
  queue_arns        = module.queuing.queue_arns
}

# =============================================================================
# STORAGE — S3 bucket for file uploads and model artifacts
# =============================================================================
# Prod: force_destroy = false prevents accidental deletion of production data.
# In dev this is true for easy teardown — in prod we protect the bucket.
module "storage" {
  source = "../../modules/storage"

  project       = var.project
  environment   = var.environment
  account_id    = var.account_id
  force_destroy = false # PROD: protect bucket from accidental deletion
}

# =============================================================================
# AUTH — Cognito user pool for authentication
# =============================================================================
# Prod: MFA is enforced (ON) — all users must set up TOTP authenticator.
# Dev uses OPTIONAL MFA. This is the main security difference.
module "auth" {
  source = "../../modules/auth"

  project           = var.project
  environment       = var.environment
  mfa_configuration = "ON" # PROD: all users must use MFA (dev = OPTIONAL)
}

# =============================================================================
# DATABASE — RDS PostgreSQL
# =============================================================================
# Prod hardening vs dev:
#   - db.t4g.large (8 GB RAM vs 1 GB) — handles concurrent queries from 8 services
#   - multi_az = true — automatic failover if primary AZ goes down
#   - deletion_protection = true — prevents accidental terraform destroy
#   - 30-day backup retention (vs 7 in dev) — more recovery options
#   - skip_final_snapshot = false — creates a snapshot before any deletion
module "database" {
  source = "../../modules/database"

  project                 = var.project
  environment             = var.environment
  private_subnet_ids      = module.networking.private_subnet_ids
  db_sg_id                = module.networking.db_sg_id
  db_instance_class       = var.db_instance_class # "db.t4g.large"
  db_password             = var.db_password       # From TF_VAR_db_password
  multi_az                = true                  # PROD: standby replica in second AZ
  deletion_protection     = true                  # PROD: block accidental deletion
  backup_retention_period = 30                    # PROD: 30 days of backups (dev = 7)
  skip_final_snapshot     = false                 # PROD: snapshot before deletion
}

# =============================================================================
# QUEUING — SQS queues for inter-service message passing
# =============================================================================
# Same 7 queues + 7 DLQs as dev. SQS is fully managed — no prod-specific
# sizing needed. Throughput scales automatically, messages are durable.
module "queuing" {
  source = "../../modules/queuing"

  project     = var.project
  environment = var.environment
  # Prod uses same defaults as dev — SQS scales automatically
}

# =============================================================================
# CACHE — ElastiCache Redis
# =============================================================================
# Prod: 3 nodes with automatic failover across AZs.
# If the primary node fails, Redis automatically promotes a replica.
# Dev uses 1 node (no failover) to save cost.
module "cache" {
  source = "../../modules/cache"

  project            = var.project
  environment        = var.environment
  private_subnet_ids = module.networking.private_subnet_ids
  redis_sg_id        = module.networking.redis_sg_id
  node_type          = "cache.r7g.large" # PROD: 13 GB RAM, handles caches + pub/sub under load
  # Hardcoded (not a tfvars variable) — cache sizing is set once per environment, not tuned per-deploy
  num_cache_clusters         = 3    # PROD: 1 primary + 2 replicas (dev = 1)
  automatic_failover_enabled = true # PROD: auto-promote replica on failure (dev = false)
  multi_az_enabled           = true # PROD: spread across AZs (dev = false)
  snapshot_retention_limit   = 7    # PROD: 7 days of Redis snapshots (dev = 0)
}

# =============================================================================
# SECRETS — Secrets Manager for DB credentials
# =============================================================================
# Prod: 7-day recovery window before permanent deletion.
# If someone accidentally deletes the secret, you have 7 days to recover it.
# Dev uses 0 (immediate deletion) for easy teardown.
module "secrets" {
  source = "../../modules/secrets"

  project                 = var.project
  environment             = var.environment
  db_address              = module.database.db_address
  db_password             = var.db_password
  recovery_window_in_days = 7 # PROD: 7-day recovery window (dev = 0)
}

# =============================================================================
# COMPUTE — ECS cluster, 8 services, ALB, ECR repos
# =============================================================================
# Same wiring as dev — the module creates 8 services with the same architecture.
# Prod differences are handled by CI/CD (larger task sizes, higher desired_count)
# via the lifecycle { ignore_changes = [task_definition, desired_count] } block
# in the compute module.
module "compute" {
  source = "../../modules/compute"

  project     = var.project
  environment = var.environment

  # --- From networking ---
  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids
  alb_sg_id          = module.networking.alb_sg_id
  app_sg_id          = module.networking.app_sg_id

  # --- From IAM ---
  execution_role_arn = module.iam.execution_role_arn
  task_role_arns     = module.iam.task_role_arns

  # --- From global ---
  cert_arn = data.terraform_remote_state.global.outputs.cert_arn

  # --- From queuing ---
  queue_urls = module.queuing.queue_urls

  # --- From cache ---
  redis_endpoint = module.cache.redis_endpoint
  redis_port     = module.cache.redis_port

  # --- From storage ---
  s3_bucket_id = module.storage.bucket_id

  # --- From secrets ---
  db_credentials_secret_arn = module.secrets.db_credentials_secret_arn

  # --- From auth ---
  user_pool_id    = module.auth.user_pool_id
  client_id       = module.auth.client_id
  cognito_domain  = module.auth.cognito_domain
}

# =============================================================================
# DNS — Route53 record for API subdomain
# =============================================================================
# Prod: api.autobook.tech (dev uses api-dev.autobook.tech)
# The dns module auto-resolves this: environment = "prod" → subdomain = "api"
module "dns" {
  source = "../../modules/dns"

  project      = var.project
  environment  = var.environment
  domain_name  = var.domain_name
  zone_id      = data.terraform_remote_state.global.outputs.zone_id
  alb_dns_name = module.compute.alb_dns_name
  alb_zone_id  = module.compute.alb_zone_id
  # Prod default: api_subdomain = null → auto-resolves to "api" (api.autobook.tech)
}

# =============================================================================
# API GATEWAY — WebSocket API for real-time updates
# =============================================================================
# Prod: higher throttle limits to handle production traffic.
# Dev uses 100 req/sec / 50 burst — prod needs more headroom.
module "api_gateway" {
  source = "../../modules/api-gateway"

  project                = var.project
  environment            = var.environment
  throttling_rate_limit  = 500 # PROD: 500 req/sec (dev = 100)
  throttling_burst_limit = 200 # PROD: 200 burst (dev = 50)
}

# =============================================================================
# ML — SageMaker inference endpoint
# =============================================================================
# Prod: real-time GPU inference with A10G for the 4 ML enrichment models:
#   - DeBERTa-v3-small (intent classifier)
#   - SpaCy rules (entity extraction, CPU)
#   - MiniLM / DeBERTa-small (bank classifier)
#   - MiniLM-L6-v2 (CCA matcher)
#
# A10G (ml.g5.xlarge): 24 GB VRAM, handles batched inference at 500+ txn/sec.
# model_image defaults to null — no endpoint (and no cost) until a model is pushed.
# Set model_image to an ECR URI to activate the endpoint.
module "ml" {
  source = "../../modules/ml"

  project            = var.project
  environment        = var.environment
  private_subnet_ids = module.networking.private_subnet_ids
  sagemaker_sg_id    = module.networking.sagemaker_sg_id
  serverless         = false          # PROD: real-time GPU (dev = serverless)
  instance_type      = "ml.g5.xlarge" # PROD: 1x A10G, 24 GB VRAM, 4 vCPUs ($1.41/hr)
  instance_count     = 1              # Single instance (scale up if needed)
  # model_image = null (default) → no endpoint until model is pushed to ECR
}

# =============================================================================
# VECTOR SEARCH — Qdrant Cloud cluster for RAG
# =============================================================================
# Prod: 3 nodes for high availability with replication.
# Larger CPU/RAM to handle more vectors and concurrent queries.
# If one node fails, the other 2 continue serving (data is replicated).
module "vector_search" {
  source = "../../modules/vector-search"

  project         = var.project
  environment     = var.environment
  number_of_nodes = 1      # Using free2 tier (single node only)
  node_cpu        = "500m" # free2 package
  node_ram        = "1Gi"  # free2 package — upgrade to gpx1 (2Gi) when needed
}

# =============================================================================
# MONITORING — CloudWatch alarms, dashboard, SNS alerts, budget
# =============================================================================
# Prod: higher thresholds for connections (more services, more traffic)
# and more 5xx tolerance (transient errors are more common at scale).
module "monitoring" {
  source = "../../modules/monitoring"

  project     = var.project
  environment = var.environment
  alert_email = var.alert_email

  # --- From compute ---
  cluster_name   = module.compute.cluster_name
  service_names  = module.compute.service_names
  alb_arn_suffix = module.compute.alb_arn_suffix

  # --- From database ---
  db_instance_id = module.database.db_instance_id

  # --- Prod thresholds ---
  rds_connections_threshold = 200 # PROD: db.t4g.large supports ~700 connections (dev = 50)
  alb_5xx_threshold         = 50  # PROD: higher tolerance at scale (dev = 10)

  # --- Budget ---
  monthly_budget_usd = var.monthly_budget_usd # "$300.0"
}
