# Naming convention + data sources
locals {
  name = "${var.project}-${var.environment}" # e.g. "autobook-dev"

  # The 8 ECS services — each gets its own task role with least-privilege permissions
  # These are fixed for this project (defined in system design, not per-environment)
  service_names = ["api", "file", "precedent", "model", "llm", "resolution", "posting", "flywheel"]

  # Shared trust policy — allows the ECS service to assume roles on behalf of containers
  # Both execution role and task roles use this same trust policy
  ecs_trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        # Prevents confused deputy attacks — only our account can trigger role assumption
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

# Get AWS account ID and region without requiring them as variables
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# ECS EXECUTION ROLE — used by the ECS agent, NOT by your application code
# =============================================================================
# The ECS agent runs alongside your container. It needs permissions to:
#   1. Pull Docker images from ECR (your container registry)
#   2. Write container logs to CloudWatch
#   3. Read secrets from Secrets Manager (inject as env vars at container start)
#
# This role is shared by all 8 services — they all need the same agent permissions.
resource "aws_iam_role" "execution" {
  name               = "${local.name}-ecs-execution" # e.g. "autobook-dev-ecs-execution"
  assume_role_policy = local.ecs_trust_policy        # Only ECS can assume this role

  tags = { Name = "${local.name}-ecs-execution" }
}

# AWS managed policy — covers ECR image pull + CloudWatch log write
# This is the standard policy AWS recommends for ECS execution roles
resource "aws_iam_role_policy_attachment" "execution_base" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Secrets Manager access — read DB credentials to inject as container env vars
# Scoped to secrets with our naming prefix (e.g. "autobook-dev-*")
resource "aws_iam_role_policy" "execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = "arn:aws:secretsmanager:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:secret:${local.name}-*"
    }]
  })
}

# =============================================================================
# ECS TASK ROLES — one per service, least privilege
# =============================================================================
# Unlike the execution role (used by the ECS agent), task roles are used by
# YOUR APPLICATION CODE running inside the container.
#
# Each of the 8 services gets its own role so it only has the AWS permissions
# it actually needs. Services with no AWS needs (precedent, resolution, posting)
# still get a role — ECS requires one — but it has no extra policies.
resource "aws_iam_role" "task" {
  for_each = toset(local.service_names)

  name               = "${local.name}-${each.key}-task" # e.g. "autobook-dev-api-task"
  assume_role_policy = local.ecs_trust_policy           # Only ECS can assume this role

  tags = { Name = "${local.name}-${each.key}-task" }
}

# =============================================================================
# SERVICE-SPECIFIC POLICIES — S3, SageMaker, Bedrock
# =============================================================================
# Only services that call AWS APIs get policies. The rest (precedent, resolution,
# posting) have empty roles — they talk to PostgreSQL and Redis via credentials
# and endpoints, not IAM.

# --- S3 policies (api, file, flywheel) ---
# These are only created when s3_bucket_arn is provided (i.e., storage module exists)

# API service: upload user files to S3
resource "aws_iam_role_policy" "api_s3" {
  count = var.s3_bucket_arn != null ? 1 : 0 # Skip if storage module not ready

  name = "s3-upload"
  role = aws_iam_role.task["api"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "s3:PutObject"           # Upload only — can't read or delete
      Resource = "${var.s3_bucket_arn}/*" # Any object in the data bucket
    }]
  })
}

# File worker: read raw files from S3, delete after processing
resource "aws_iam_role_policy" "file_s3" {
  count = var.s3_bucket_arn != null ? 1 : 0

  name = "s3-read"
  role = aws_iam_role.task["file"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:DeleteObject"] # Read + cleanup
      Resource = "${var.s3_bucket_arn}/*"
    }]
  })
}

# Flywheel worker: read/write training data and model artifacts in S3
resource "aws_iam_role_policy" "flywheel_s3" {
  count = var.s3_bucket_arn != null ? 1 : 0

  name = "s3-training-data"
  role = aws_iam_role.task["flywheel"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"] # Full read/write
      Resource = [
        var.s3_bucket_arn,       # ListBucket needs the bucket itself
        "${var.s3_bucket_arn}/*" # Get/Put needs the objects
      ]
    }]
  })
}

# --- SageMaker policies (model, flywheel) ---

# Model worker: call the SageMaker endpoint for ML inference (tier 2 classification)
resource "aws_iam_role_policy" "model_sagemaker" {
  name = "sagemaker-invoke"
  role = aws_iam_role.task["model"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sagemaker:InvokeEndpoint" # Call the model for predictions
      Resource = "arn:aws:sagemaker:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:endpoint/${local.name}-*"
    }]
  })
}

# Flywheel worker: create SageMaker training jobs for model retraining
# (Fast learner every 128 examples, slow learner every 1,280 examples)
resource "aws_iam_role_policy" "flywheel_sagemaker" {
  name = "sagemaker-training"
  role = aws_iam_role.task["flywheel"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:CreateTrainingJob",   # Start a training job
          "sagemaker:DescribeTrainingJob", # Check training status
          "sagemaker:StopTrainingJob"      # Cancel if needed
        ]
        Resource = "arn:aws:sagemaker:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:training-job/${local.name}-*"
      },
      {
        # SageMaker training jobs need to assume their own role — we must allow
        # the flywheel to "pass" that role to SageMaker
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.name}-sagemaker-*"
        Condition = {
          StringEquals = { "iam:PassedToService" = "sagemaker.amazonaws.com" }
        }
      }
    ]
  })
}

# --- Bedrock policy (llm) ---

# LLM worker: call foundation models (Claude, etc.) via AWS Bedrock for tier 3
resource "aws_iam_role_policy" "llm_bedrock" {
  name = "bedrock-invoke"
  role = aws_iam_role.task["llm"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",                  # Synchronous model calls
        "bedrock:InvokeModelWithResponseStream" # Streaming responses
      ]
      # Foundation models are AWS-managed — the ARN has no account ID
      # Scoped to our region (ca-central-1) for least privilege
      Resource = "arn:aws:bedrock:${data.aws_region.current.region}::foundation-model/*"
    }]
  })
}

# =============================================================================
# GITHUB ACTIONS DEPLOY ROLE — CI/CD without stored credentials
# =============================================================================
# GitHub Actions authenticates via OIDC (OpenID Connect):
#   1. GitHub sends a signed JWT token to AWS
#   2. AWS verifies the token against the OIDC provider (created in global stack)
#   3. If the repo matches the trust policy, AWS issues temporary credentials
#   4. Credentials expire after the workflow run — nothing to rotate or leak
resource "aws_iam_role" "github_actions" {
  name = "${local.name}-github-actions" # e.g. "autobook-dev-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.oidc_provider_arn } # Trust GitHub's OIDC provider
      Action    = "sts:AssumeRoleWithWebIdentity"       # OIDC-specific assume action
      Condition = {
        StringEquals = {
          # Only accept tokens intended for AWS (audience check)
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          # Only accept tokens from our specific repo (any branch/tag)
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })

  tags = { Name = "${local.name}-github-actions" }
}

# Deploy permissions — push images to ECR, update ECS services
resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "ecr-ecs-deploy"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # ECR login — account-level operation, cannot be scoped to specific repos
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        # ECR push — scoped to our project's repositories only
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability", # Check if layer already exists
          "ecr:PutImage",                    # Push the image
          "ecr:InitiateLayerUpload",         # Start uploading a layer
          "ecr:UploadLayerPart",             # Upload layer chunks
          "ecr:CompleteLayerUpload",         # Finish layer upload
          "ecr:BatchGetImage",               # Read image manifests
          "ecr:GetDownloadUrlForLayer"       # Download layer data
        ]
        Resource = "arn:aws:ecr:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:repository/${local.name}-*"
      },
      {
        # ECS task definitions — account-level operations, cannot be scoped to specific resources
        Effect = "Allow"
        Action = [
          "ecs:RegisterTaskDefinition", # Create new version of task definition
          "ecs:DescribeTaskDefinition"  # Read current task definition
        ]
        Resource = "*" # These are account-level APIs — AWS does not support resource-level scoping
      },
      {
        # ECS service operations — scoped to our project's services only
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",   # Tell service to use new task definition
          "ecs:DescribeServices" # Check deployment status
        ]
        Resource = "arn:aws:ecs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:service/${local.name}/*"
      },
      {
        # PassRole — allows GitHub Actions to pass our IAM roles to ECS
        # Required when registering task definitions that reference these roles
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = concat(
          [aws_iam_role.execution.arn],              # Execution role
          [for role in aws_iam_role.task : role.arn] # All 8 task roles
        )
        Condition = {
          StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      }
    ]
  })
}
