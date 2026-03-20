# =============================================================================
# LAMBDA WORKERS — 7 pipeline workers triggered by SQS
# =============================================================================
# Each worker:
#   1. Is triggered by its SQS queue via event source mapping (no polling code)
#   2. Runs in VPC private subnets (DB + Redis access)
#   3. Reads DB credentials via AWS Parameters and Secrets Lambda Extension
#   4. Sends results to the next queue in the pipeline
#
# Pipeline: normalizer → precedent → ml_inference → agent → resolution → posting → flywheel

locals {
  name      = "${var.project}-${var.environment}" # e.g. "autobook-dev"
  redis_url = "redis://${var.redis_endpoint}:${var.redis_port}/0"

  worker_names = ["normalizer", "precedent", "ml_inference", "agent",
    "resolution", "posting", "flywheel"]

  # Per-worker SQS queue URL environment variables.
  # Each worker gets its input queue (for the event source mapping) and
  # output queue URL(s) it sends results to.
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
# SECRETS EXTENSION LAYER — caching proxy for Secrets Manager
# =============================================================================
# The AWS Parameters and Secrets Lambda Extension runs as a sidecar.
# It caches secrets locally at localhost:2773, avoiding a Secrets Manager
# API call on every invocation. Auto-refreshes on TTL expiry.
data "aws_lambda_layer_version" "secrets_extension" {
  layer_name = "AWS-Parameters-and-Secrets-Lambda-Extension"
}

# =============================================================================
# PLACEHOLDER ZIP — bootstrap deployment artifact
# =============================================================================
# Lambda requires a deployment package at creation time. This placeholder
# lets Terraform create the functions; CI/CD replaces the code on first deploy.
# lifecycle { ignore_changes = [filename, source_code_hash] } prevents
# Terraform from reverting to the placeholder on subsequent applies.
data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"

  source {
    content  = "def handler(event, context): pass"
    filename = "handler.py"
  }
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
# LAMBDA FUNCTIONS — one per worker
# =============================================================================
resource "aws_lambda_function" "worker" {
  for_each = toset(local.worker_names)

  function_name = "${local.name}-${each.key}"
  role          = var.lambda_role_arns[each.key]
  handler       = "services.${each.key}.handler.handler"
  runtime       = "python3.12"
  memory_size   = var.memory_size
  timeout       = var.timeout

  # Bootstrap placeholder — CI/CD replaces on first deploy
  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  # VPC access for DB and Redis
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.app_sg_id]
  }

  # Secrets Extension layer — caching proxy for Secrets Manager
  layers = [data.aws_lambda_layer_version.secrets_extension.arn]

  environment {
    variables = merge(
      {
        ENVIRONMENT    = var.environment
        DB_SECRET_ARN  = var.db_credentials_secret_arn
        REDIS_URL      = local.redis_url
        S3_BUCKET      = var.s3_bucket_id
      },
      local.sqs_env[each.key]
    )
  }

  # CI/CD updates code and config — don't revert to placeholder
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }

  depends_on = [aws_cloudwatch_log_group.worker]

  tags = { Name = "${local.name}-${each.key}" }
}

# =============================================================================
# SQS EVENT SOURCE MAPPINGS — trigger Lambda from queue
# =============================================================================
# When a message arrives in the queue, Lambda automatically invokes the
# worker function. No polling code needed — AWS handles the plumbing.
resource "aws_lambda_event_source_mapping" "worker" {
  for_each = toset(local.worker_names)

  event_source_arn = var.queue_arns[each.key]
  function_name    = aws_lambda_function.worker[each.key].arn
  batch_size       = var.sqs_batch_size
  enabled          = true
}
