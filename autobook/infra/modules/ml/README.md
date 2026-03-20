# ML

Creates a SageMaker inference endpoint for the transaction classification model (tier 2).

## What it creates

- **SageMaker execution role** — IAM role for pulling ECR images, writing logs, accessing S3 (always created)
- **SageMaker model** — container image + VPC config (conditional: only when `model_image` is provided)
- **Endpoint configuration** — serverless (dev) or real-time (prod) compute settings (conditional)
- **Endpoint** — the live inference service that ECS containers call (conditional)

## How inference works

```
1. Transaction arrives at Model Worker (ECS):
   Model Worker → checks Redis cache (tier 2 shared cache)
     → cache miss → calls SageMaker endpoint

2. SageMaker inference:
   Model Worker → sagemaker:InvokeEndpoint(EndpointName="autobook-dev-classifier")
     → SageMaker routes to container → model returns classification
       → Model Worker caches result in Redis

3. Model retraining (flywheel):
   Flywheel Worker → sagemaker:CreateTrainingJob(RoleArn=sagemaker_role_arn)
     → SageMaker pulls training data from S3 → trains model
       → writes new model artifacts to S3
         → hot-swap onto endpoint
```

## Serverless vs real-time inference

| Feature | Serverless (default) | Real-time |
|---------|---------------------|-----------|
| Cold start | ~1 min first request | None (always warm) |
| GPU | No | Yes |
| Scale-to-zero | Yes | No |
| Cost when idle | $0 | Instance cost |
| Max memory | 6 GB | Instance-dependent |
| Best for | Dev, low traffic | Prod, low latency |

## Conditional creation

When `model_image = null` (default), only the IAM role is created. This lets you:
1. Deploy the infrastructure before any model exists
2. Reference the role ARN in flywheel training jobs
3. Add the endpoint later by setting `model_image` to an ECR URI

## Usage

```hcl
# Dev — role only (no model image yet)
module "ml" {
  source = "../../modules/ml"

  project            = "autobook"
  environment        = "dev"
  private_subnet_ids = module.networking.private_subnet_ids
  sagemaker_sg_id    = module.networking.sagemaker_sg_id
}

# Dev — with model (serverless, scale-to-zero)
module "ml" {
  source = "../../modules/ml"

  project            = "autobook"
  environment        = "dev"
  private_subnet_ids = module.networking.private_subnet_ids
  sagemaker_sg_id    = module.networking.sagemaker_sg_id
  model_image        = "123456.dkr.ecr.ca-central-1.amazonaws.com/autobook-dev-model:latest"
}

# Prod — real-time with GPU
module "ml" {
  source = "../../modules/ml"

  project            = "autobook"
  environment        = "prod"
  private_subnet_ids = module.networking.private_subnet_ids
  sagemaker_sg_id    = module.networking.sagemaker_sg_id
  model_image        = "123456.dkr.ecr.ca-central-1.amazonaws.com/autobook-prod-model:latest"
  serverless         = false
  instance_type      = "ml.g4dn.xlarge"
  instance_count     = 2
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| private_subnet_ids | list(string) | — | Private subnet IDs (from networking) |
| sagemaker_sg_id | string | — | SageMaker security group ID (from networking) |
| model_image | string | null | ECR image URI (null = role only, no endpoint) |
| serverless | bool | true | Use serverless inference (true) or real-time (false) |
| serverless_memory_mb | number | 2048 | Memory for serverless inference (1024-6144 MB) |
| serverless_max_concurrency | number | 5 | Max concurrent serverless invocations |
| instance_type | string | ml.g4dn.xlarge | Instance type for real-time inference |
| instance_count | number | 1 | Number of instances for real-time inference |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| endpoint_name | SageMaker endpoint name (null if no model) | Model Worker, Flywheel Worker (env var) |
| sagemaker_role_arn | SageMaker execution role ARN | Flywheel Worker (iam:PassRole for training jobs) |
