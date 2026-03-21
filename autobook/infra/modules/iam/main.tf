# Naming convention + data sources
locals {
  name = "${var.project}-${var.environment}" # e.g. "autobook-dev"

  # API runs on ECS Fargate — keeps the ECS trust policy
  ecs_services = ["api"]

  # Workers run on Lambda — triggered by SQS event source mappings
  lambda_services = ["normalizer", "precedent", "ml_inference", "agent",
    "resolution", "posting", "flywheel"]

  # ECS trust policy — allows the ECS service to assume roles on behalf of containers
  ecs_trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })

  # Lambda trust policy — allows Lambda service to assume roles for workers
  lambda_trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Get AWS account ID and region without requiring them as variables
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# ECS EXECUTION ROLE — used by the ECS agent, NOT by your application code
# =============================================================================
resource "aws_iam_role" "execution" {
  name               = "${local.name}-ecs-execution"
  assume_role_policy = local.ecs_trust_policy

  tags = { Name = "${local.name}-ecs-execution" }
}

resource "aws_iam_role_policy_attachment" "execution_base" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

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
# ECS TASK ROLE — API only
# =============================================================================
resource "aws_iam_role" "task" {
  for_each = toset(local.ecs_services)

  name               = "${local.name}-${each.key}-task"
  assume_role_policy = local.ecs_trust_policy

  tags = { Name = "${local.name}-${each.key}-task" }
}

# =============================================================================
# LAMBDA EXECUTION ROLES — one per worker, least privilege
# =============================================================================
resource "aws_iam_role" "lambda" {
  for_each = toset(local.lambda_services)

  name               = "${local.name}-${each.key}-lambda"
  assume_role_policy = local.lambda_trust_policy

  tags = { Name = "${local.name}-${each.key}-lambda" }
}

# CloudWatch Logs — Lambda needs to write logs
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  for_each   = toset(local.lambda_services)
  role       = aws_iam_role.lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# VPC access — all workers need DB (PostgreSQL) and/or Redis
resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  for_each   = toset(local.lambda_services)
  role       = aws_iam_role.lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Secrets Manager — Lambda Extension reads DB credentials
resource "aws_iam_role_policy" "lambda_secrets" {
  for_each = toset(local.lambda_services)

  name = "secrets-access"
  role = aws_iam_role.lambda[each.key].id

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
# SERVICE-SPECIFIC POLICIES — S3, SageMaker, Bedrock
# =============================================================================

# --- S3 policies (api, normalizer, flywheel) ---

resource "aws_iam_role_policy" "api_s3" {
  name = "s3-upload"
  role = aws_iam_role.task["api"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "s3:PutObject"
      Resource = "${var.s3_bucket_arn}/*"
    }]
  })
}

resource "aws_iam_role_policy" "normalizer_s3" {
  name = "s3-read"
  role = aws_iam_role.lambda["normalizer"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:DeleteObject"]
      Resource = "${var.s3_bucket_arn}/*"
    }]
  })
}

resource "aws_iam_role_policy" "flywheel_s3" {
  name = "s3-training-data"
  role = aws_iam_role.lambda["flywheel"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      Resource = [
        var.s3_bucket_arn,
        "${var.s3_bucket_arn}/*"
      ]
    }]
  })
}

# --- SageMaker policies (ml_inference, flywheel) ---

resource "aws_iam_role_policy" "ml_inference_sagemaker" {
  name = "sagemaker-invoke"
  role = aws_iam_role.lambda["ml_inference"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sagemaker:InvokeEndpoint"
      Resource = "arn:aws:sagemaker:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:endpoint/${local.name}-*"
    }]
  })
}

resource "aws_iam_role_policy" "flywheel_sagemaker" {
  name = "sagemaker-training"
  role = aws_iam_role.lambda["flywheel"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:CreateTrainingJob",
          "sagemaker:DescribeTrainingJob",
          "sagemaker:StopTrainingJob"
        ]
        Resource = "arn:aws:sagemaker:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:training-job/${local.name}-*"
      },
      {
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

# --- SQS policies ---

# API: enqueue to normalizer
resource "aws_iam_role_policy" "api_sqs" {
  name = "sqs-send-normalizer"
  role = aws_iam_role.task["api"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sqs:SendMessage"
      Resource = var.queue_arns["normalizer"]
    }]
  })
}

# Normalizer: receive from normalizer, send to precedent
resource "aws_iam_role_policy" "normalizer_sqs" {
  name = "sqs-normalizer-to-precedent"
  role = aws_iam_role.lambda["normalizer"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = var.queue_arns["normalizer"]
      },
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = var.queue_arns["precedent"]
      }
    ]
  })
}

# Precedent (tier 1): receive from precedent, send to ml_inference or posting
resource "aws_iam_role_policy" "precedent_sqs" {
  name = "sqs-precedent-to-ml-inference-or-posting"
  role = aws_iam_role.lambda["precedent"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = var.queue_arns["precedent"]
      },
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = [var.queue_arns["ml_inference"], var.queue_arns["posting"]]
      }
    ]
  })
}

# ML inference (tier 2): receive from ml_inference, send to agent or posting
resource "aws_iam_role_policy" "ml_inference_sqs" {
  name = "sqs-ml-inference-to-agent-or-posting"
  role = aws_iam_role.lambda["ml_inference"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = var.queue_arns["ml_inference"]
      },
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = [var.queue_arns["agent"], var.queue_arns["posting"]]
      }
    ]
  })
}

# Agent (tier 3): receive from agent, send to resolution or posting
resource "aws_iam_role_policy" "agent_sqs" {
  name = "sqs-agent-to-resolution-or-posting"
  role = aws_iam_role.lambda["agent"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = var.queue_arns["agent"]
      },
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = [var.queue_arns["resolution"], var.queue_arns["posting"]]
      }
    ]
  })
}

# Resolution: receive from resolution, send to posting
resource "aws_iam_role_policy" "resolution_sqs" {
  name = "sqs-resolution-to-posting"
  role = aws_iam_role.lambda["resolution"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = var.queue_arns["resolution"]
      },
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = var.queue_arns["posting"]
      }
    ]
  })
}

# Posting: receive from posting, send to flywheel
resource "aws_iam_role_policy" "posting_sqs" {
  name = "sqs-posting-to-flywheel"
  role = aws_iam_role.lambda["posting"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = var.queue_arns["posting"]
      },
      {
        Effect   = "Allow"
        Action   = "sqs:SendMessage"
        Resource = var.queue_arns["flywheel"]
      }
    ]
  })
}

# Flywheel: receive from flywheel (terminal — no next queue)
resource "aws_iam_role_policy" "flywheel_sqs" {
  name = "sqs-flywheel-receive"
  role = aws_iam_role.lambda["flywheel"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      Resource = var.queue_arns["flywheel"]
    }]
  })
}

# --- Bedrock policy (agent) ---

resource "aws_iam_role_policy" "agent_bedrock" {
  name = "bedrock-invoke"
  role = aws_iam_role.lambda["agent"].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = "arn:aws:bedrock:${data.aws_region.current.region}::foundation-model/*"
    }]
  })
}

# =============================================================================
# GITHUB ACTIONS DEPLOY ROLE — CI/CD without stored credentials
# =============================================================================
resource "aws_iam_role" "github_actions" {
  name = "${local.name}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = var.oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })

  tags = { Name = "${local.name}-github-actions" }
}

# Deploy permissions — ECR + ECS for API, Lambda for workers
resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "ecr-ecs-lambda-deploy"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = "arn:aws:ecr:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:repository/${local.name}-*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:RegisterTaskDefinition",
          "ecs:DescribeTaskDefinition"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices"
        ]
        Resource = "arn:aws:ecs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:service/${local.name}/*"
      },
      {
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [
          aws_iam_role.execution.arn,
          aws_iam_role.task["api"].arn
        ]
        Condition = {
          StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" }
        }
      },
      {
        # Lambda deploy permissions for workers
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:GetFunction",
          "lambda:UpdateFunctionConfiguration"
        ]
        Resource = "arn:aws:lambda:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:function:${local.name}-*"
      }
    ]
  })
}
