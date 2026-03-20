# IAM

Creates all IAM roles and policies for ECS services and CI/CD deployments.

## What it creates

- **ECS execution role** — shared by all services, lets the ECS agent pull images from ECR, write logs to CloudWatch, and read secrets from Secrets Manager
- **8 ECS task roles** — one per service, each with only the AWS permissions that service needs (least privilege):

| Service | AWS Permissions |
|---------|----------------|
| api | S3 write (file uploads) |
| file | S3 read + delete (raw files) |
| precedent | none (uses DB + Redis via credentials) |
| model | SageMaker invoke (ML inference) |
| llm | Bedrock invoke (LLM calls) |
| resolution | none |
| posting | none |
| flywheel | SageMaker training + S3 read/write |

- **GitHub Actions deploy role** — OIDC-based (no stored credentials), can push to ECR and deploy to ECS

## Usage

```hcl
# Dev
module "iam" {
  source = "../../modules/iam"

  project           = "autobook"
  environment       = "dev"
  oidc_provider_arn = data.terraform_remote_state.global.outputs.oidc_provider_arn
  github_repo       = "UofT-CSC490-W2026/AI-Accountant"
  s3_bucket_arn     = module.storage.bucket_arn
}

# Prod — same structure, different env name
module "iam" {
  source = "../../modules/iam"

  project           = "autobook"
  environment       = "prod"
  oidc_provider_arn = data.terraform_remote_state.global.outputs.oidc_provider_arn
  github_repo       = "UofT-CSC490-W2026/AI-Accountant"
  s3_bucket_arn     = module.storage.bucket_arn
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| oidc_provider_arn | string | — | GitHub OIDC provider ARN (from global) |
| github_repo | string | — | GitHub repo (owner/repo) for deploy role trust |
| s3_bucket_arn | string | null | S3 bucket ARN for S3 policies (null = skip) |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| execution_role_arn | ECS execution role ARN | compute (all task definitions) |
| task_role_arns | Map of service name → task role ARN | compute (per-service task definitions) |
| github_actions_role_arn | GitHub Actions deploy role ARN | CI/CD workflow |

## Design decisions

- **Execution role vs task role**: execution role is for the ECS agent (infrastructure), task role is for your code (application). Separated per AWS best practice.
- **One task role per service**: services that don't call AWS APIs still get a role (ECS requires it), but with no policies attached.
- **S3 policies are conditional**: created only when `s3_bucket_arn` is provided, so the module works before the storage module is applied.
- **SageMaker/Bedrock use naming-convention wildcards**: scoped by `${project}-${environment}-*` pattern since the actual resources may not exist yet when IAM is created.
- **OIDC deploy role**: no stored AWS credentials in GitHub — temporary tokens expire after each workflow run.
