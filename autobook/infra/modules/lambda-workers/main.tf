# =============================================================================
# LAMBDA WORKERS — 7 pipeline workers triggered by SQS (container images)
# =============================================================================
# Each worker:
#   1. Is triggered by its SQS queue via event source mapping (no polling code)
#   2. Runs in VPC private subnets (DB + Redis access)
#   3. Sends results to the next queue in the pipeline
#   4. Uses Docker container images from ECR (10GB limit, same images as local dev)
#
# Pipeline: normalizer → precedent → ml_inference → agent → resolution → posting → flywheel

locals {
  name      = "${var.project}-${var.environment}" # e.g. "autobook-dev"
  redis_url = "redis://${var.redis_endpoint}:${var.redis_port}/0"

  worker_names = ["normalizer", "precedent", "ml_inference", "agent",
    "resolution", "posting", "flywheel"]

  # Dockerfile target name for each worker (uses hyphens, not underscores)
  dockerfile_targets = {
    normalizer   = "autobook-normalizer"
    precedent    = "autobook-precedent"
    ml_inference = "autobook-ml-inference"
    agent        = "autobook-agent"
    resolution   = "autobook-resolution"
    posting      = "autobook-posting"
    flywheel     = "autobook-flywheel"
  }

  # Per-worker SQS queue URL environment variables.
  sqs_env = {
    normalizer = {
      SQS_QUEUE_NORMALIZER = var.queue_urls["normalizer"]
      SQS_QUEUE_PRECEDENT  = var.queue_urls["precedent"]
    }
    precedent = {
      SQS_QUEUE_PRECEDENT    = var.queue_urls["precedent"]
      SQS_QUEUE_ML_INFERENCE = var.queue_urls["ml_inference"]
      SQS_QUEUE_POSTING      = var.queue_urls["posting"]
    }
    ml_inference = {
      SQS_QUEUE_ML_INFERENCE = var.queue_urls["ml_inference"]
      SQS_QUEUE_AGENT        = var.queue_urls["agent"]
      SQS_QUEUE_POSTING      = var.queue_urls["posting"]
    }
    agent = {
      SQS_QUEUE_AGENT      = var.queue_urls["agent"]
      SQS_QUEUE_RESOLUTION = var.queue_urls["resolution"]
      SQS_QUEUE_POSTING    = var.queue_urls["posting"]
    }
    resolution = {
      SQS_QUEUE_RESOLUTION = var.queue_urls["resolution"]
      SQS_QUEUE_POSTING    = var.queue_urls["posting"]
    }
    posting = {
      SQS_QUEUE_POSTING  = var.queue_urls["posting"]
      SQS_QUEUE_FLYWHEEL = var.queue_urls["flywheel"]
    }
    flywheel = {
      SQS_QUEUE_FLYWHEEL = var.queue_urls["flywheel"]
    }
  }
}

data "aws_region" "current" {}

# =============================================================================
# ECR REPOSITORIES — Docker image storage for workers
# =============================================================================
resource "aws_ecr_repository" "worker" {
  for_each = toset(local.worker_names)

  name                 = "${local.name}-${each.key}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${local.name}-${each.key}" }
}

resource "aws_ecr_lifecycle_policy" "worker" {
  for_each = aws_ecr_repository.worker

  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only the 20 most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

# =============================================================================
# CLOUDWATCH LOG GROUPS — Lambda stdout/stderr
# =============================================================================
resource "aws_cloudwatch_log_group" "worker" {
  for_each = toset(local.worker_names)

  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = var.log_retention_days

  tags = { Name = "${local.name}-${each.key}" }
}

# =============================================================================
# LAMBDA FUNCTIONS — container image deployment
# =============================================================================
resource "aws_lambda_function" "worker" {
  for_each = toset(local.worker_names)

  function_name = "${local.name}-${each.key}"
  role          = var.lambda_role_arns[each.key]
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.worker[each.key].repository_url}:latest"
  memory_size   = var.memory_size
  timeout       = var.timeout

  # Override the Dockerfile CMD with the Lambda handler
  image_config {
    command = ["services.${each.key}.handler.handler"]
  }

  # VPC access for DB and Redis
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.app_sg_id]
  }

  environment {
    variables = merge(
      {
        ENVIRONMENT   = var.environment
        DB_SECRET_ARN = var.db_credentials_secret_arn
        REDIS_URL     = local.redis_url
        S3_BUCKET     = var.s3_bucket_id
      },
      local.sqs_env[each.key]
    )
  }

  # CI/CD updates image_uri — don't revert to initial
  lifecycle {
    ignore_changes = [image_uri]
  }

  depends_on = [aws_cloudwatch_log_group.worker]

  tags = { Name = "${local.name}-${each.key}" }
}

# =============================================================================
# SQS EVENT SOURCE MAPPINGS — trigger Lambda from queue
# =============================================================================
resource "aws_lambda_event_source_mapping" "worker" {
  for_each = toset(local.worker_names)

  event_source_arn = var.queue_arns[each.key]
  function_name    = aws_lambda_function.worker[each.key].arn
  batch_size       = var.sqs_batch_size
  enabled          = true
}
