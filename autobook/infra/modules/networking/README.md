# Networking

Creates the VPC and all network infrastructure that every other module depends on.

## What it creates

- **VPC** (10.0.0.0/16) — private network, 65,536 addresses
- **2 public subnets** — across 2 availability zones, for ALB
- **2 private subnets** — across 2 availability zones, for RDS, Redis, ECS workers
- **Internet Gateway** — connects public subnets to the internet
- **NAT Gateway** — lets private subnets make outbound calls without being reachable
- **Route tables** — public routes through IGW, private routes through NAT
- **5 security groups** — firewall rules for ALB, App, DB, Redis, SageMaker
- **S3 VPC endpoint** — free private shortcut to S3, avoids NAT costs

## Security group chain

```
Internet → ALB (443) → App (8000) → DB (5432)
                                   → Redis (6379)
                                   → SageMaker (443)
```

Each layer only accepts traffic from the layer before it.

## Usage

```hcl
module "networking" {
  source = "../../modules/networking"

  project     = "autobook"
  environment = "dev"
  region      = "ca-central-1"
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name for resource naming |
| environment | string | — | dev or prod |
| region | string | — | AWS region |
| vpc_cidr | string | 10.0.0.0/16 | IP range for the VPC |
| public_subnet_cidrs | list(string) | ["10.0.1.0/24", "10.0.2.0/24"] | Public subnet IP ranges |
| private_subnet_cidrs | list(string) | ["10.0.10.0/24", "10.0.11.0/24"] | Private subnet IP ranges |

## Outputs

| Name | Description |
|------|-------------|
| vpc_id | VPC ID |
| public_subnet_ids | Public subnet IDs |
| private_subnet_ids | Private subnet IDs |
| alb_sg_id | ALB security group ID |
| app_sg_id | App security group ID |
| db_sg_id | DB security group ID |
| redis_sg_id | Redis security group ID |
| sagemaker_sg_id | SageMaker security group ID |
