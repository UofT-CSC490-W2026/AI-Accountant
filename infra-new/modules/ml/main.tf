# Naming convention
locals {
  name = "${var.project}-${var.environment}" # e.g. "autobook-dev"

  # Whether to create the actual SageMaker model + endpoint
  # When model_image is null, only the IAM role is created — the endpoint
  # is deployed later when the first model image is pushed to ECR
  create_endpoint = var.model_image != null
}

# Look up current account ID and region — used in IAM policy ARNs
# This avoids requiring account_id/region as input variables
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# IAM ROLE — SageMaker execution role (always created)
# =============================================================================
# SageMaker needs an IAM role to:
#   - Pull the model container image from ECR
#   - Write logs to CloudWatch
#   - Read model artifacts from S3 (if applicable)
#
# This role is always created even when the endpoint doesn't exist yet,
# because the flywheel worker needs to reference it when creating training jobs
# (iam:PassRole requires the role to exist)
resource "aws_iam_role" "sagemaker" {
  name = "${local.name}-sagemaker-execution"

  # Trust policy — only SageMaker can assume this role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
      Action    = "sts:AssumeRole"

      # Limit to our account — prevents cross-account confusion deputy attacks
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })

  tags = { Name = "${local.name}-sagemaker-execution" }
}

# --- ECR access — pull model container images ---
# SageMaker needs to pull the inference container from our ECR repository
resource "aws_iam_role_policy" "sagemaker_ecr" {
  name = "ecr-pull"
  role = aws_iam_role.sagemaker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecr:GetDownloadUrlForLayer",     # Download image layers
        "ecr:BatchGetImage",              # Get image manifest
        "ecr:BatchCheckLayerAvailability" # Check if layers exist
      ]
      # Scoped to our project's ECR repos — no access to other repos
      Resource = "arn:aws:ecr:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:repository/${local.name}-*"
      },
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken" # Get login credentials for ECR
        Resource = "*"                         # This action doesn't support resource-level restrictions
    }]
  })
}

# --- CloudWatch Logs — write inference logs ---
# SageMaker writes container stdout/stderr to CloudWatch for debugging
resource "aws_iam_role_policy" "sagemaker_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.sagemaker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",  # Create log group if it doesn't exist
        "logs:CreateLogStream", # Create log stream per container
        "logs:PutLogEvents"     # Write log entries
      ]
      # Scoped to /aws/sagemaker/ prefix — SageMaker's default log location
      Resource = "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/sagemaker/*"
    }]
  })
}

# --- S3 access — read model artifacts, write training output ---
# SageMaker loads model weights from S3 at startup and writes training artifacts
resource "aws_iam_role_policy" "sagemaker_s3" {
  name = "s3-model-artifacts"
  role = aws_iam_role.sagemaker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject", # Read model artifacts (model.tar.gz)
        "s3:PutObject", # Write training output
        "s3:ListBucket" # List objects in bucket
      ]
      # Scoped to our project's bucket — model artifacts stored under models/ prefix
      Resource = [
        "arn:aws:s3:::${local.name}-*",
        "arn:aws:s3:::${local.name}-*/*"
      ]
    }]
  })
}

# =============================================================================
# MODEL — defines the container image and model artifacts location
# =============================================================================
# A SageMaker Model points to:
#   1. A Docker container image (our inference code)
#   2. Optionally, model artifacts in S3 (pre-trained weights)
#
# Conditional: only created when model_image is provided
resource "aws_sagemaker_model" "main" {
  count = local.create_endpoint ? 1 : 0

  name               = "${local.name}-classifier"
  execution_role_arn = aws_iam_role.sagemaker.arn # IAM role for pulling images, logging, S3

  # Primary inference container — runs our classification model
  primary_container {
    image = var.model_image # ECR image URI (e.g. 123456.dkr.ecr.ca-central-1.amazonaws.com/autobook-dev-model:latest)
    # model_data_url is omitted — model weights are baked into the container image
    # If using S3-stored weights, add: model_data_url = "s3://bucket/model.tar.gz"
  }

  # VPC config — places SageMaker in our private subnets so ECS can reach it
  # without going over the internet
  vpc_config {
    subnets            = var.private_subnet_ids # Private subnets (same as ECS)
    security_group_ids = [var.sagemaker_sg_id]  # Only allows traffic from ECS services
  }

  tags = { Name = "${local.name}-classifier" }
}

# =============================================================================
# ENDPOINT CONFIGURATION — how the endpoint runs (serverless vs real-time)
# =============================================================================
# Endpoint config defines the compute behind the endpoint:
#   - Serverless: scale-to-zero, pay-per-invocation, no GPU (dev)
#   - Real-time: always-on instances, GPU available (prod)
#
# Conditional: only created when model_image is provided
resource "aws_sagemaker_endpoint_configuration" "main" {
  count = local.create_endpoint ? 1 : 0

  name = "${local.name}-classifier"

  # Production variant — defines the model and compute resources
  production_variants {
    variant_name           = "primary"                        # Name for this variant (required even with one)
    model_name             = aws_sagemaker_model.main[0].name # Which model to serve
    initial_variant_weight = 1.0                              # 100% of traffic to this variant

    # --- Serverless config (scale-to-zero, no GPU) ---
    # Used in dev: no cost when idle, ~1 min cold start on first request
    dynamic "serverless_config" {
      for_each = var.serverless ? [1] : [] # Only add this block when serverless = true

      content {
        memory_size_in_mb = var.serverless_memory_mb       # RAM allocation (1024-6144 MB)
        max_concurrency   = var.serverless_max_concurrency # Max parallel invocations
      }
    }

    # --- Real-time config (always-on instances) ---
    # Used in prod: consistent latency, GPU available, higher cost
    # These fields are only set when serverless = false
    instance_type          = var.serverless ? null : var.instance_type  # e.g. ml.g4dn.xlarge
    initial_instance_count = var.serverless ? null : var.instance_count # Number of instances
  }

  tags = { Name = "${local.name}-classifier" }
}

# =============================================================================
# ENDPOINT — the live inference endpoint that ECS services call
# =============================================================================
# The endpoint is the actual running service that accepts InvokeEndpoint API calls.
# ECS containers call it with: sagemaker:InvokeEndpoint(EndpointName=this_name)
#
# Conditional: only created when model_image is provided
resource "aws_sagemaker_endpoint" "main" {
  count = local.create_endpoint ? 1 : 0

  name                 = "${local.name}-classifier"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.main[0].name # Points to the config above

  tags = { Name = "${local.name}-classifier" }
}
