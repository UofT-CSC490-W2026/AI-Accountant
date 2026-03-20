# Compute

Creates the ECS Fargate cluster, container registries, and all 8 services — the runtime that actually runs the application.

## What it creates

- **ECS cluster** — logical namespace for all services (Fargate = serverless, no EC2 to manage)
- **8 ECR repositories** — private Docker image storage, one per service
- **8 CloudWatch log groups** — container logs (stdout/stderr), one per service
- **ALB** — internet-facing load balancer that routes HTTPS traffic to the API service
- **ALB target group** — health-checked list of API containers
- **HTTPS listener** — terminates TLS using ACM cert, forwards HTTP to containers
- **8 ECS task definitions** — container blueprints (image, CPU, memory, env vars, secrets)
- **8 ECS services** — keep desired number of containers running, restart on failure

## Architecture

```
Internet
  → ALB (public subnets, HTTPS:443)
    → API service (private subnets, port 8000)

Redis queues
  → file, precedent, model, llm, resolution, posting, flywheel (private subnets, no ALB)
```

Only the API service sits behind the ALB. The other 7 services are workers that consume from Redis queues.

## Usage

```hcl
module "compute" {
  source = "../../modules/compute"

  project            = "autobook"
  environment        = "dev"
  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids
  alb_sg_id          = module.networking.alb_sg_id
  app_sg_id          = module.networking.app_sg_id

  execution_role_arn = module.iam.execution_role_arn
  task_role_arns     = module.iam.task_role_arns
  cert_arn           = data.terraform_remote_state.global.outputs.cert_arn

  redis_endpoint            = module.cache.redis_endpoint
  redis_port                = module.cache.redis_port
  s3_bucket_id              = module.storage.bucket_id
  db_credentials_secret_arn = module.secrets.db_credentials_secret_arn
  user_pool_id              = module.auth.user_pool_id
  client_id                 = module.auth.client_id
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| vpc_id | string | — | VPC ID |
| public_subnet_ids | list(string) | — | Public subnets (ALB) |
| private_subnet_ids | list(string) | — | Private subnets (ECS tasks) |
| alb_sg_id | string | — | ALB security group |
| app_sg_id | string | — | ECS services security group |
| execution_role_arn | string | — | ECS execution role |
| task_role_arns | map(string) | — | Per-service task role ARNs |
| cert_arn | string | — | ACM certificate for HTTPS |
| redis_endpoint | string | — | Redis hostname |
| redis_port | number | — | Redis port |
| s3_bucket_id | string | — | S3 bucket name |
| db_credentials_secret_arn | string | — | DB credentials secret ARN |
| user_pool_id | string | — | Cognito user pool ID |
| client_id | string | — | Cognito app client ID |
| container_port | number | 8000 | API container port |
| cpu | number | 256 | CPU units per task (256 = 0.25 vCPU) |
| memory | number | 512 | Memory in MB per task |
| desired_count | number | 0 | Tasks per service (0 = wait for CI/CD) |
| log_retention_days | number | 30 | Days to keep container logs |
| health_check_path | string | "/health" | ALB health check endpoint |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| cluster_name | ECS cluster name | monitoring (CloudWatch alarms) |
| service_names | List of ECS service names | monitoring (per-service alarms) |
| alb_dns_name | ALB DNS name | dns (api subdomain record) |
| alb_zone_id | ALB hosted zone ID | dns (alias record) |
| alb_arn_suffix | ALB ARN suffix | monitoring (ALB metrics) |
| ecr_urls | Map of service → ECR URL | CI/CD (push Docker images) |

## Deployment flow

1. `terraform apply` → creates all infrastructure, ECR repos are empty, `desired_count = 0`
2. CI/CD pushes Docker images to ECR repos
3. CI/CD creates new task definition revisions with the real image tags
4. CI/CD updates ECS services → containers start pulling from ECR
5. ALB health check confirms API is healthy → traffic flows

## Design notes

- **`lifecycle { ignore_changes = [task_definition, desired_count] }`** — prevents Terraform from reverting CI/CD deployments or auto-scaling changes
- **`target_type = "ip"`** — required for Fargate (containers get their own IPs, not EC2 instances)
- **Service names from IAM** — derived from `task_role_arns` keys to guarantee consistency
- **Container Insights enabled** — collects per-service CPU/memory/network metrics automatically
