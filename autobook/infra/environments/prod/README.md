# Prod Environment

Root module that wires all 13 reusable modules together with production-hardened values.

## Prerequisites

1. **Bootstrap applied** — S3 bucket + DynamoDB lock table exist
2. **Global applied** — DNS zone, ACM cert, GitHub OIDC provider exist
3. **Dev tested** — apply dev first to catch issues before prod
4. **AWS credentials configured** — `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` or IAM role
5. **Qdrant Cloud account** — API key and account ID from cloud.qdrant.io

## How to apply

```bash
# Set secrets (never in terraform.tfvars)
export TF_VAR_db_password="your-secure-database-password"
export TF_VAR_qdrant_cloud_api_key="your-qdrant-api-key"
export TF_VAR_qdrant_cloud_account_id="your-qdrant-account-id"

# Initialize (downloads providers, configures backend)
cd environments/prod
terraform init

# Preview changes — review carefully before applying to prod
terraform plan

# Apply
terraform apply
```

## What gets created

| Module | Resources | Prod difference vs dev |
|--------|-----------|----------------------|
| networking | VPC, 4 subnets, IGW, NAT, 5 SGs | Same |
| iam | Execution role, 8 task roles, deploy role | Same (scoped by naming convention) |
| storage | S3 bucket with versioning + lifecycle | force_destroy = false |
| auth | Cognito user pool + app client | MFA = ON (enforced) |
| database | RDS PostgreSQL (db.t4g.large) | Multi-AZ, deletion protection, 30-day backups |
| cache | ElastiCache Redis (3 nodes) | Automatic failover, multi-AZ, snapshots |
| secrets | Secrets Manager (DB credentials JSON) | 7-day recovery window |
| compute | ECS cluster, 8 services, ALB, 8 ECR repos | Same (CI/CD manages task sizes) |
| dns | Route53 A record (api.autobook.tech) | "api" subdomain (not "api-dev") |
| api-gateway | WebSocket API (MOCK integration) | 500 req/sec, 200 burst |
| ml | SageMaker role + endpoint (when activated) | Real-time GPU: ml.g5.xlarge (A10G) |
| vector-search | Qdrant Cloud cluster (3 nodes) | 1000m CPU, 2Gi RAM per node |
| monitoring | 20 alarms, dashboard, SNS, $300 budget | Higher connection/5xx thresholds |

## Prod hardening summary

| Category | Setting | Dev | Prod |
|----------|---------|-----|------|
| **Database** | Instance | db.t4g.micro (1 GB) | db.t4g.large (8 GB) |
| | Multi-AZ | false | true |
| | Deletion protection | false | true |
| | Backup retention | 7 days | 30 days |
| | Final snapshot | skip | create |
| **Cache** | Nodes | 1 | 3 (primary + 2 replicas) |
| | Failover | disabled | automatic |
| | Snapshots | disabled | 7 days |
| **Auth** | MFA | OPTIONAL | ON (enforced) |
| **Storage** | Force destroy | true | false |
| **Secrets** | Recovery window | 0 (immediate) | 7 days |
| **ML** | Mode | Serverless (CPU) | Real-time GPU (A10G) |
| | Instance | — | ml.g5.xlarge ($1.41/hr) |
| **Vector search** | Nodes | 1 | 3 |
| | Resources | 500m / 1Gi | 1000m / 2Gi |
| **WebSocket** | Rate limit | 100 req/sec | 500 req/sec |
| **Monitoring** | RDS connections alarm | 50 | 200 |
| | ALB 5xx alarm | 10 | 50 |
| | Budget | $100 | $300 |

## Estimated monthly cost (prod, all running)

| Service | Cost |
|---------|------|
| RDS db.t4g.large (multi-AZ) | ~$100 |
| NAT Gateway | ~$32 |
| ElastiCache (3 nodes) | ~$40 |
| ALB | ~$16 |
| ECS Fargate (8 services) | ~$20-80 (varies with scale) |
| SageMaker A10G (when active) | ~$1.41/hr (pay per use) |
| Qdrant Cloud (3 nodes) | ~$50-100 |
| S3, CloudWatch, Secrets | ~$5 |
| **Total (no SageMaker)** | **~$260-370** |

SageMaker endpoint is $0 when model_image is null. Only costs money when activated.

## Secrets

| Secret | How to pass | Used by |
|--------|-------------|---------|
| DB password | `TF_VAR_db_password` | database, secrets modules |
| Qdrant API key | `TF_VAR_qdrant_cloud_api_key` | qdrant-cloud provider |
| Qdrant account ID | `TF_VAR_qdrant_cloud_account_id` | qdrant-cloud provider |

Never commit these to the repository. CI/CD stores them as GitHub Actions secrets.

## Key outputs

After `terraform apply`, these values are displayed:

```
api_url                 = "https://api.autobook.tech"
websocket_url           = "wss://abc123.execute-api.ca-central-1.amazonaws.com/prod"
cognito_user_pool_id    = "ca-central-1_XyZaBc"
cognito_client_id       = "abcdef1234567890"
ecr_urls                = { "api" = "609092547371.dkr.ecr...", ... }
deploy_role_arn         = "arn:aws:iam::609092547371:role/autobook-prod-github-actions"
ecs_cluster_name        = "autobook-prod"
qdrant_url              = "https://xyz789.ca-central-1-0.aws.cloud.qdrant.io:6333"
sagemaker_endpoint_name = null  (until model_image is set)
dashboard_url           = "https://ca-central-1.console.aws.amazon.com/cloudwatch/..."
```

## Destroying prod

Prod has safety guards. To destroy, you must first:

```bash
# 1. Disable deletion protection on RDS
terraform apply -var="deletion_protection=false"  # (requires adding variable override)

# 2. Then destroy
terraform destroy
```

This prevents accidental `terraform destroy` from wiping production data.
