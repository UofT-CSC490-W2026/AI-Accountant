# =============================================================================
# DEV ENVIRONMENT — wires all 13 modules together with dev-appropriate values
# =============================================================================
# This is the root module for the dev environment. It:
#   1. Reads shared resources from the global stack (DNS zone, TLS cert, OIDC)
#   2. Calls each module with dev-specific variable values
#   3. Passes outputs between modules (e.g. networking → database)
#
# To apply:
#   cd environments/dev
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
# Everything else depends on this: databases, containers, and load balancers
# all need a VPC, subnets, and security groups.
#
# Dev uses all defaults: 10.0.0.0/16 VPC, 2 public + 2 private subnets.
module "networking" {
  source = "../../modules/networking"

  project     = var.project     # "autobook"
  environment = var.environment # "dev"
  region      = var.region      # "ca-central-1" — determines which AZs are available
}

# =============================================================================
# IAM — roles and permissions
# =============================================================================
# Creates IAM roles that control what each service is allowed to do:
#   - Execution role: shared by all ECS services (pull images, read secrets, write logs)
#   - Task roles: one per service with least-privilege permissions
#   - Deploy role: GitHub Actions assumes this via OIDC to deploy
#
# Depends on storage (needs s3_bucket_arn to scope S3 permissions).
# No dependency on networking — can be created in parallel with networking.
module "iam" {
  source = "../../modules/iam"

  project           = var.project
  environment       = var.environment
  oidc_provider_arn = data.terraform_remote_state.global.outputs.oidc_provider_arn # GitHub OIDC from global
  github_repo       = var.github_repo                                              # "UofT-CSC490-W2026/AI-Accountant"
  s3_bucket_arn     = module.storage.bucket_arn                                    # Scopes S3 permissions to our bucket
  queue_arns        = module.queuing.queue_arns                                    # Scopes SQS permissions per service

  # WS relay permissions
  ws_connections_table_arn = module.api_gateway.connections_table_arn
  ws_api_arn               = "arn:aws:execute-api:${var.region}:${var.account_id}:${module.api_gateway.api_id}"
}

# =============================================================================
# STORAGE — S3 bucket for file uploads and model artifacts
# =============================================================================
# Creates the S3 bucket where:
#   - File Worker reads uploaded bank statements / CSVs
#   - Flywheel Worker stores model training artifacts
#   - Processed files transition to cheaper storage after 90 days
#
# Standalone — no dependency on networking.
module "storage" {
  source = "../../modules/storage"

  project       = var.project
  environment   = var.environment
  account_id    = var.account_id # Makes bucket name globally unique
  force_destroy = true           # Dev: allow easy teardown (prod: false)
}

# =============================================================================
# AUTH — Cognito user pool for authentication
# =============================================================================
# Creates the Cognito user pool and app client that handles:
#   - User registration and login (email + password)
#   - JWT token issuance (access + refresh tokens)
#   - MFA (optional in dev, enforced in prod)
#
# The API Service validates tokens from Cognito on every request.
# Frontend uses the client_id to initiate auth flows.
#
# Standalone — no dependency on networking.
module "auth" {
  source = "../../modules/auth"

  project     = var.project
  environment = var.environment
  callback_urls = [
    "http://localhost:5173/auth/callback",
    "https://autobook.tech/auth/callback",
    "https://www.autobook.tech/auth/callback",
    "https://ai-accountant490.netlify.app/auth/callback",
  ]
  logout_urls = [
    "http://localhost:5173/login",
    "https://autobook.tech/login",
    "https://www.autobook.tech/login",
    "https://ai-accountant490.netlify.app/login",
  ]
}

# =============================================================================
# DATABASE — RDS PostgreSQL
# =============================================================================
# Creates the PostgreSQL database that stores all application data:
#   9 tables (users, transactions, journal_entries, journal_lines,
#   chart_of_accounts, clarification_tasks, pattern_store,
#   model_training_data, confidence_calibration_data)
#
# Depends on networking: placed in private subnets, secured by DB security group.
module "database" {
  source = "../../modules/database"

  project            = var.project
  environment        = var.environment
  private_subnet_ids = module.networking.private_subnet_ids # Private subnets (no internet)
  db_sg_id           = module.networking.db_sg_id           # Only ECS can reach port 5432
  db_instance_class  = var.db_instance_class                # "db.t4g.micro" for dev
  db_password        = var.db_password                      # From TF_VAR_db_password
  # Dev defaults: 20 GB storage, no multi-AZ, 7-day backups, no deletion protection
}

# =============================================================================
# QUEUING — SQS queues for inter-service message passing
# =============================================================================
# Creates 7 SQS standard queues + 7 dead-letter queues for the pipeline:
#   files → precedent → model → llm → resolution → post → flywheel
#
# Each queue connects two services (e.g. API enqueues to files, File Worker
# dequeues from files). Messages are durable, retried automatically, and
# moved to a DLQ after 3 failed attempts.
#
# Standalone — no dependency on networking (SQS is a managed service).
module "queuing" {
  source = "../../modules/queuing"

  project     = var.project
  environment = var.environment
  # Dev uses all defaults: 30s visibility, 4-day retention, 14-day DLQ retention,
  # 3 max receives, 20s long polling
}

# =============================================================================
# CACHE — ElastiCache Redis
# =============================================================================
# Creates the Redis cluster that serves two roles:
#   1. Caches (per-user tier 1 cache, shared tier 2 cache, reference data)
#   2. Pub/sub (real-time event notifications to WebSocket clients)
#
# Depends on networking: placed in private subnets, secured by Redis security group.
module "cache" {
  source = "../../modules/cache"

  project            = var.project
  environment        = var.environment
  private_subnet_ids = module.networking.private_subnet_ids # Private subnets (no internet)
  redis_sg_id        = module.networking.redis_sg_id        # Only ECS can reach port 6379
  node_type          = "cache.t4g.micro"                    # Smallest: 0.5 GB, ~$12/mo (dev only)
  # Hardcoded (not a tfvars variable) because cache sizing rarely changes per-deploy
  # unlike db_instance_class which is a common tuning knob. Dev defaults: single node, no snapshots
}

# =============================================================================
# SECRETS — Secrets Manager for DB credentials
# =============================================================================
# Stores database connection details as a JSON blob in AWS Secrets Manager:
#   {"host": "...", "port": 5432, "dbname": "autobook", "username": "autobook", "password": "..."}
#
# ECS containers read individual fields at startup via the `valueFrom` ARN syntax.
# This keeps the password out of task definitions and environment variables.
#
# Depends on database: needs db_address to build the connection JSON.
module "secrets" {
  source = "../../modules/secrets"

  project     = var.project
  environment = var.environment
  db_address  = module.database.db_address # RDS hostname from database module
  db_password = var.db_password            # Same password used to create the database
  # Dev defaults: immediate deletion (no recovery window), default port/name/username
}

# =============================================================================
# COMPUTE — ECS cluster, API service, ALB, ECR repo
# =============================================================================
# Creates the API service infrastructure:
#   - ECS cluster with Container Insights
#   - ECR repo for API Docker image
#   - Task definition (container config, env vars, secrets)
#   - ECS Fargate service behind ALB
#   - ALB with HTTPS listener (TLS termination)
#   - CloudWatch log group
#
# Workers are handled by the lambda-workers module below.
module "compute" {
  source = "../../modules/compute"

  project     = var.project
  environment = var.environment

  # --- From networking ---
  vpc_id             = module.networking.vpc_id             # ALB target group needs VPC
  public_subnet_ids  = module.networking.public_subnet_ids  # ALB sits in public subnets
  private_subnet_ids = module.networking.private_subnet_ids # ECS tasks run in private subnets
  alb_sg_id          = module.networking.alb_sg_id          # ALB firewall (allows HTTPS from internet)
  app_sg_id          = module.networking.app_sg_id          # ECS firewall (allows traffic from ALB only)

  # --- From IAM ---
  execution_role_arn = module.iam.execution_role_arn # Shared role: pull images, read secrets, write logs
  task_role_arns     = module.iam.task_role_arns     # Per-service roles: {"api" = "arn:...", ...}

  # --- From global ---
  cert_arn = data.terraform_remote_state.global.outputs.cert_arn # TLS cert for HTTPS on ALB

  # --- From queuing ---
  queue_urls = module.queuing.queue_urls # SQS queue URLs per service

  # --- From cache ---
  redis_endpoint = module.cache.redis_endpoint # Redis hostname for cache/pubsub
  redis_port     = module.cache.redis_port     # 6379

  # --- From storage ---
  s3_bucket_id = module.storage.bucket_id # S3 bucket name for file uploads

  # --- From secrets ---
  db_credentials_secret_arn = module.secrets.db_credentials_secret_arn # DB creds JSON ARN

  # --- From auth ---
  user_pool_id   = module.auth.user_pool_id   # Cognito pool ID (API validates tokens)
  client_id      = module.auth.client_id      # Cognito client ID (passed to frontend)
  cognito_domain = module.auth.cognito_domain # Cognito hosted UI domain (OAuth token exchange)

  # --- WS relay service ---
  ws_relay_role_arn          = module.iam.ws_relay_role_arn
  ws_connections_table_name  = module.api_gateway.connections_table_name
  ws_connections_table_arn   = module.api_gateway.connections_table_arn
  ws_api_endpoint            = module.api_gateway.api_endpoint
  ws_api_id                  = module.api_gateway.api_id

  # Dev defaults: 0.25 vCPU, 512 MB memory, 0 desired count (CI/CD deploys first),
  # 30-day log retention, /health check path
}

# =============================================================================
# LAMBDA WORKERS — 7 pipeline workers triggered by SQS
# =============================================================================
# Creates Lambda functions for the processing pipeline:
#   normalizer → precedent → ml_inference → agent → resolution → posting → flywheel
#
# Each worker is triggered by its SQS queue via event source mapping.
# Runs in VPC private subnets for DB/Redis access. Reads DB credentials
# via the AWS Parameters and Secrets Lambda Extension.
#
# Depends on networking, IAM, queuing, secrets, cache, and storage.
module "lambda_workers" {
  source = "../../modules/lambda-workers"

  project     = var.project
  environment = var.environment

  # --- From networking ---
  private_subnet_ids = module.networking.private_subnet_ids # Same subnets as ECS
  app_sg_id          = module.networking.app_sg_id          # Same SG — allows DB, Redis, NAT

  # --- From IAM ---
  lambda_role_arns = module.iam.lambda_role_arns # Per-worker least-privilege roles

  # --- From queuing ---
  queue_arns = module.queuing.queue_arns # SQS ARNs for event source mappings
  queue_urls = module.queuing.queue_urls # SQS URLs for downstream sends

  # --- From secrets ---
  db_credentials_secret_arn = module.secrets.db_credentials_secret_arn # DB creds via extension

  # --- From cache ---
  redis_endpoint = module.cache.redis_endpoint
  redis_port     = module.cache.redis_port

  # --- From storage ---
  s3_bucket_id = module.storage.bucket_id

  # Dev defaults: 512 MB memory, 60s timeout, 30-day log retention, batch size 1
}

# =============================================================================
# DNS — Route53 record for API subdomain
# =============================================================================
# Creates the DNS record that maps api-dev.autobook.tech → ALB.
# Without this, the API is only reachable via the ALB's auto-generated hostname
# (e.g. autobook-dev-alb-123456.ca-central-1.elb.amazonaws.com).
#
# Depends on compute (ALB) and global (DNS zone).
module "dns" {
  source = "../../modules/dns"

  project      = var.project
  environment  = var.environment
  domain_name  = var.domain_name                                    # "autobook.tech"
  zone_id      = data.terraform_remote_state.global.outputs.zone_id # Route53 zone from global
  alb_dns_name = module.compute.alb_dns_name                        # ALB hostname
  alb_zone_id  = module.compute.alb_zone_id                         # ALB hosted zone (AWS internal)
  # Dev default: api_subdomain = null → auto-resolves to "api-dev"
}

# =============================================================================
# API GATEWAY — WebSocket API for real-time updates
# =============================================================================
# Creates the WebSocket API that pushes real-time updates to the frontend.
# When an entry is posted, the Posting Service publishes to Redis pub/sub,
# the API Service receives it and pushes to connected clients via this WebSocket.
#
# Currently uses MOCK integrations (placeholder). Real Lambda/HTTP integrations
# are wired when the application code is ready.
#
# Standalone — no dependency on networking (WebSocket API is a managed service).
module "api_gateway" {
  source = "../../modules/api-gateway"

  project     = var.project
  environment = var.environment
  # Dev defaults: $request.body.action routing, 100 req/sec, 50 burst
}

# =============================================================================
# ML — SageMaker inference endpoint
# =============================================================================
# Creates the SageMaker infrastructure for ML model inference (tier 2).
# In dev, we start with role-only (no endpoint) because no model image exists yet.
# When the first model is trained and pushed to ECR, set model_image to activate.
#
# Depends on networking: SageMaker endpoint sits in private subnets.
module "ml" {
  source = "../../modules/ml"

  project            = var.project
  environment        = var.environment
  private_subnet_ids = module.networking.private_subnet_ids # Same private subnets as ECS
  sagemaker_sg_id    = module.networking.sagemaker_sg_id    # Only ECS can reach SageMaker
  # model_image = null (default) → role only, no endpoint created yet
  # serverless = true (default) → scale-to-zero when endpoint is eventually created
}

# =============================================================================
# VECTOR SEARCH — Qdrant Cloud cluster for RAG
# =============================================================================
# Creates the Qdrant vector database cluster that stores embeddings for RAG:
#   - Generator RAG: positive examples (correctly resolved entries)
#   - Evaluator RAG: correction examples (human-overridden entries)
#
# LLM Worker queries Qdrant for similar examples to include in prompts.
# Flywheel Worker inserts new embeddings as entries are resolved.
#
# Standalone — uses qdrant-cloud provider (not AWS). No VPC dependency.
module "vector_search" {
  source = "../../modules/vector-search"

  project     = var.project
  environment = var.environment
  # Dev defaults: ca-central-1, 1 node, 500m CPU, 1Gi RAM, JWT RBAC enabled
}

# =============================================================================
# MONITORING — CloudWatch alarms, dashboard, SNS alerts, budget
# =============================================================================
# Creates the observability layer for the entire system:
#   - 16 ECS alarms (CPU + memory per service)
#   - 3 RDS alarms (CPU, connections, storage)
#   - 1 ALB alarm (5xx errors)
#   - 1 CloudWatch dashboard (7 widgets, single-pane-of-glass)
#   - 1 SNS topic + email subscription (alarm notifications)
#   - 1 AWS budget ($100/month with alerts at 80% and 100%)
#
# Depends on compute (cluster/service names, ALB) and database (instance ID).
module "monitoring" {
  source = "../../modules/monitoring"

  project     = var.project
  environment = var.environment
  alert_email = var.alert_email # "autobook@pm.me"

  # --- From compute ---
  cluster_name   = module.compute.cluster_name   # ECS cluster for metric dimensions
  service_names  = module.compute.service_names  # 8 service names for per-service alarms
  alb_arn_suffix = module.compute.alb_arn_suffix # ALB identifier for 5xx alarm

  # --- From database ---
  db_instance_id = module.database.db_instance_id # RDS instance for DB alarms

  # --- Budget ---
  monthly_budget_usd = var.monthly_budget_usd # "$100.0"
  # Dev defaults: 80% CPU/memory thresholds, 50 connection limit, 10 5xx errors
}
