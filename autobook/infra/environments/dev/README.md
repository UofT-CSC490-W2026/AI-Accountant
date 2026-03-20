# Dev Environment

Root module that wires all 13 reusable modules together with dev-appropriate values.

## Prerequisites

1. **Bootstrap applied** — S3 bucket + DynamoDB lock table exist
2. **Global applied** — DNS zone, ACM cert, GitHub OIDC provider exist
3. **AWS credentials configured** — `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` or IAM role
4. **Qdrant Cloud account** — API key and account ID from cloud.qdrant.io

## How to apply

```bash
# Set secrets (never in terraform.tfvars)
export TF_VAR_db_password="your-secure-database-password"
export TF_VAR_qdrant_cloud_api_key="your-qdrant-api-key"
export TF_VAR_qdrant_cloud_account_id="your-qdrant-account-id"

# Initialize (downloads providers, configures backend)
cd environments/dev
terraform init

# Preview changes
terraform plan

# Apply
terraform apply
```

## What gets created

| Module | Resources | Key output |
|--------|-----------|------------|
| networking | VPC, 4 subnets, IGW, NAT, 5 security groups | vpc_id, subnet IDs, SG IDs |
| iam | Execution role, 8 task roles, deploy role | role ARNs |
| storage | S3 bucket with versioning + lifecycle | bucket_id, bucket_arn |
| auth | Cognito user pool + app client | user_pool_id, client_id |
| database | RDS PostgreSQL (db.t4g.micro) | db_address |
| cache | ElastiCache Redis (single node) | redis_endpoint |
| secrets | Secrets Manager (DB credentials JSON) | secret ARN |
| compute | ECS cluster, 8 services, ALB, 8 ECR repos | ecr_urls, alb_dns_name |
| dns | Route53 A record (api-dev.autobook.tech) | api_fqdn |
| api-gateway | WebSocket API (MOCK integration) | websocket_url |
| ml | SageMaker role (endpoint when model_image set) | endpoint_name |
| vector-search | Qdrant Cloud cluster (1 node, 500m/1Gi) | qdrant_url |
| monitoring | 20 alarms, dashboard, SNS topic, $100 budget | dashboard_url |

## Module dependency order

```
global (remote state read)
  |
  ├── networking (standalone)
  ├── iam ← global (oidc_provider_arn), storage (bucket_arn)
  ├── storage (standalone)
  ├── auth (standalone)
  ├── api_gateway (standalone)
  ├── vector_search (standalone, qdrant-cloud provider)
  |
  ├── database ← networking
  ├── cache ← networking
  ├── ml ← networking
  |
  ├── secrets ← database
  |
  ├── compute ← networking, iam, auth, storage, secrets, cache, global
  |
  ├── dns ← compute, global
  └── monitoring ← compute, database
```

Terraform resolves this automatically — you just run `terraform apply`.

## Secrets

| Secret | How to pass | Used by |
|--------|-------------|---------|
| DB password | `TF_VAR_db_password` | database, secrets modules |
| Qdrant API key | `TF_VAR_qdrant_cloud_api_key` | qdrant-cloud provider |
| Qdrant account ID | `TF_VAR_qdrant_cloud_account_id` | qdrant-cloud provider |

Never commit these to the repository. CI/CD stores them as GitHub Actions secrets.

## Dev vs prod differences

| Setting | Dev | Prod |
|---------|-----|------|
| DB instance | db.t4g.micro | db.t4g.medium+ |
| DB multi-AZ | false | true |
| Redis nodes | 1 | 3 (failover) |
| S3 force_destroy | true | false |
| MFA | OPTIONAL | ON |
| SageMaker | serverless | real-time GPU |
| Qdrant nodes | 1 | 3 |
| Budget | $100 | $500+ |
| Deletion protection | false | true |

## Key outputs

After `terraform apply`, these values are displayed:

```
api_url                 = "https://api-dev.autobook.tech"
websocket_url           = "wss://abc123.execute-api.ca-central-1.amazonaws.com/dev"
cognito_user_pool_id    = "ca-central-1_AbCdEf"
cognito_client_id       = "1234567890abcdef"
ecr_urls                = { "api" = "609092547371.dkr.ecr...", ... }
deploy_role_arn         = "arn:aws:iam::609092547371:role/autobook-dev-github-actions"
ecs_cluster_name        = "autobook-dev"
qdrant_url              = "https://abc123.ca-central-1-0.aws.cloud.qdrant.io:6333"
sagemaker_endpoint_name = null  (until model_image is set)
dashboard_url           = "https://ca-central-1.console.aws.amazon.com/cloudwatch/..."
```
