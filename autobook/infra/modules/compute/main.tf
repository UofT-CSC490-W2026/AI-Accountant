# Naming convention + data sources
locals {
  name      = "${var.project}-${var.environment}" # e.g. "autobook-dev"
  redis_url = "rediss://${var.redis_endpoint}:${var.redis_port}/0"

  # Service names derived from the IAM module's task_role_arns map keys
  # After Lambda migration, this only contains ["api"]
  service_names = keys(var.task_role_arns)

  # The only ECS service — workers moved to Lambda
  api_service = "api"

  # SQS queue URL environment variables.
  # API enqueues to the normalizer queue to kick off the pipeline.
  sqs_env = {
    api = [
      { name = "SQS_QUEUE_NORMALIZER", value = var.queue_urls["normalizer"] },
    ]
  }
}

# Get current region for log configuration and ECR URLs
data "aws_region" "current" {}

# =============================================================================
# ECS CLUSTER — a logical grouping of services
# =============================================================================
# A cluster is just a namespace — it doesn't create any servers.
# With Fargate, AWS manages the underlying servers. You only define tasks.
resource "aws_ecs_cluster" "main" {
  name = local.name # e.g. "autobook-dev"

  # CloudWatch Container Insights — collects CPU, memory, network metrics per service
  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = local.name }
}

# =============================================================================
# ECR REPOSITORIES — Docker image storage (one per service)
# =============================================================================
# ECR is like Docker Hub but private and inside your AWS account.
# CI/CD pushes images here, ECS pulls them when starting containers.
# One repo per service so each service has its own image with its own code.
resource "aws_ecr_repository" "main" {
  for_each = toset(local.service_names)

  name = "${local.name}-${each.key}" # e.g. "autobook-dev-api"

  # Scan images for known vulnerabilities (CVEs) on every push
  image_scanning_configuration {
    scan_on_push = true
  }

  # IMMUTABLE = each tag can only be used once (prevents overwriting production images)
  # MUTABLE = tags can be reused (e.g. :latest always points to newest)
  # We use MUTABLE because CI/CD pushes :latest on every deploy across all environments.
  # This is acceptable because the lifecycle { ignore_changes = [task_definition] } on
  # ECS services means the actual running image is controlled by CI/CD, not Terraform.
  image_tag_mutability = "MUTABLE"

  tags = { Name = "${local.name}-${each.key}" }
}

# =============================================================================
# ECR LIFECYCLE POLICY — auto-delete old images to prevent unbounded storage cost
# =============================================================================
# Without this, every CI/CD push accumulates images forever.
# We keep the 20 most recent images and delete the rest.
# At ~200 MB per image, 20 images ≈ 4 GB — well within free tier (500 MB free, then ~$0.10/GB).
resource "aws_ecr_lifecycle_policy" "main" {
  for_each = aws_ecr_repository.main

  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only the 20 most recent images"
      selection = {
        tagStatus   = "any" # Apply to both tagged and untagged images
        countType   = "imageCountMoreThan"
        countNumber = 20 # Keep 20, delete older ones
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# =============================================================================
# CLOUDWATCH LOG GROUPS — container stdout/stderr goes here
# =============================================================================
# Every line your container prints to stdout or stderr is captured by the
# ECS agent and stored in CloudWatch Logs. One log group per service for
# easy filtering — you can search "show me only LLM worker errors."
resource "aws_cloudwatch_log_group" "main" {
  for_each = toset(local.service_names)

  name              = "/ecs/${local.name}-${each.key}" # e.g. "/ecs/autobook-dev-api"
  retention_in_days = var.log_retention_days           # Default: 30 days, then auto-deleted

  tags = { Name = "${local.name}-${each.key}" }
}

# =============================================================================
# ALB — Application Load Balancer (internet → API service)
# =============================================================================
# The ALB is the single entry point from the internet to the backend.
# It receives HTTPS requests, terminates TLS, and forwards HTTP to the
# API service containers. Only the API service sits behind the ALB —
# workers consume from SQS queues and don't receive HTTP traffic.
resource "aws_lb" "main" {
  name               = local.name            # e.g. "autobook-dev"
  internal           = false                 # Internet-facing (not internal)
  load_balancer_type = "application"         # Layer 7 (HTTP/HTTPS), not Layer 4 (TCP)
  security_groups    = [var.alb_sg_id]       # Allows HTTPS from the internet
  subnets            = var.public_subnet_ids # Must be in public subnets to receive internet traffic

  tags = { Name = local.name }
}

# --- ALB Target Group: where the ALB sends traffic ---
# A target group is a list of "targets" (containers) that can handle requests.
# The ALB distributes incoming requests across all healthy targets.
# Fargate requires target_type = "ip" (not "instance") because there are no EC2 instances.
resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api" # e.g. "autobook-dev-api"
  port        = var.container_port  # Port the container listens on (8000)
  protocol    = "HTTP"              # ALB terminates TLS, forwards plain HTTP to containers
  vpc_id      = var.vpc_id
  target_type = "ip" # Required for Fargate (containers get their own IPs)

  # Health check — ALB pings this endpoint to decide if a container is healthy
  # Unhealthy containers are removed from the target group (no traffic sent to them)
  health_check {
    path                = var.health_check_path # Default: "/health"
    protocol            = "HTTP"
    matcher             = "200" # Only 200 = healthy
    interval            = 30    # Check every 30 seconds
    timeout             = 5     # Fail if no response in 5 seconds
    healthy_threshold   = 2     # 2 consecutive passes = healthy
    unhealthy_threshold = 3     # 3 consecutive fails = unhealthy
  }

  # Create new target group before destroying old one (avoids downtime during changes)
  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name}-api" }
}

# --- HTTPS Listener: terminate TLS and forward to target group ---
# The listener is the ALB's "ear" — it listens on port 443 (HTTPS), decrypts
# TLS using the ACM certificate, and forwards the plain HTTP request to containers.
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443 # HTTPS port
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06" # TLS 1.3 (latest, most secure)
  certificate_arn   = var.cert_arn                          # ACM wildcard cert from global stack

  # Default action: forward all HTTPS traffic to the API target group
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  tags = { Name = "${local.name}-https" }
}


# =============================================================================
# ECS TASK DEFINITION — API container configuration
# =============================================================================
# A task definition is a blueprint for running a container. It specifies:
#   - Which Docker image to use (from ECR)
#   - How much CPU and memory to allocate
#   - What environment variables to set
#   - What secrets to inject from Secrets Manager
#   - Where to send logs
#
# Task definitions are immutable — each change creates a new "revision."
# CI/CD creates new revisions and updates the service to use them.
resource "aws_ecs_task_definition" "main" {
  for_each = toset(local.service_names)

  family                   = "${local.name}-${each.key}" # e.g. "autobook-dev-api"
  network_mode             = "awsvpc"                    # Each task gets its own IP (required for Fargate)
  requires_compatibilities = ["FARGATE"]                 # Run on Fargate (serverless, no EC2 to manage)
  cpu                      = var.cpu                     # CPU units (256 = 0.25 vCPU)
  memory                   = var.memory                  # Memory in MB

  # Execution role: used by the ECS AGENT — pull images, write logs, read secrets
  execution_role_arn = var.execution_role_arn

  # Task role: used by YOUR APPLICATION CODE — S3, SageMaker, Bedrock, etc.
  # Each service gets its own role with only the permissions it needs
  task_role_arn = var.task_role_arns[each.key]

  # --- Container definition (JSON) ---
  # Defines what runs inside the task. One container per task in our case.
  container_definitions = jsonencode([{
    name      = each.key                                                     # Container name = service name
    image     = "${aws_ecr_repository.main[each.key].repository_url}:latest" # Bootstrap placeholder — CI/CD overrides via new task definition revisions
    essential = true                                                         # If this container dies, the task dies

    # Port mappings — only the API service exposes a port (for ALB traffic)
    # Workers don't receive HTTP traffic — they pull from SQS queues
    portMappings = each.key == local.api_service ? [{
      containerPort = var.container_port # e.g. 8000
      hostPort      = var.container_port # Must match containerPort on Fargate
      protocol      = "tcp"
    }] : []

    # --- Environment variables (plain text) ---
    # Injected at container startup. These are NOT secrets — safe to see in task definition.
    environment = concat(
      [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "REDIS_URL", value = local.redis_url },
        { name = "S3_BUCKET", value = var.s3_bucket_id },
      ],
      # Only the API service needs Cognito config (to validate auth tokens)
      each.key == local.api_service ? [
        { name = "COGNITO_USER_POOL_ID", value = var.user_pool_id },
        { name = "COGNITO_CLIENT_ID", value = var.client_id },
        { name = "COGNITO_DOMAIN", value = var.cognito_domain },
      ] : [],
      # Per-service SQS queue URLs — each service only gets the queues it uses
      lookup(local.sqs_env, each.key, [])
    )

    # --- Secrets (from Secrets Manager) ---
    # The ECS agent reads the secret at startup and sets env vars.
    # The ":field::" suffix extracts a single field from the JSON secret.
    # These NEVER appear in the task definition — only the ARN reference does.
    secrets = [
      { name = "DB_HOST", valueFrom = "${var.db_credentials_secret_arn}:host::" },
      { name = "DB_PORT", valueFrom = "${var.db_credentials_secret_arn}:port::" },
      { name = "DB_NAME", valueFrom = "${var.db_credentials_secret_arn}:dbname::" },
      { name = "DB_USER", valueFrom = "${var.db_credentials_secret_arn}:username::" },
      { name = "DB_PASSWORD", valueFrom = "${var.db_credentials_secret_arn}:password::" },
    ]

    # --- Logging: send stdout/stderr to CloudWatch ---
    logConfiguration = {
      logDriver = "awslogs" # AWS CloudWatch Logs driver (built into Fargate)
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.main[each.key].name # Log group per service
        "awslogs-region"        = data.aws_region.current.region               # Same region as the cluster
        "awslogs-stream-prefix" = each.key                                     # Prefix for log stream names
      }
    }
  }])

  tags = { Name = "${local.name}-${each.key}" }
}

# =============================================================================
# ECS SERVICE — API service (workers moved to Lambda)
# =============================================================================
# A service ensures that the desired number of tasks are always running.
# If a task dies (crash, health check failure), the service starts a new one.
# The API service is attached to the ALB to receive HTTP traffic.
resource "aws_ecs_service" "main" {
  for_each = toset(local.service_names)

  name            = "${local.name}-${each.key}"                # e.g. "autobook-dev-api"
  cluster         = aws_ecs_cluster.main.id                    # Which cluster to run in
  task_definition = aws_ecs_task_definition.main[each.key].arn # Which task definition to use
  desired_count   = var.desired_count                          # How many copies (0 = none until CI/CD deploys)
  launch_type     = "FARGATE"                                  # Serverless — no EC2 to manage

  # --- Network: private subnets, app security group ---
  network_configuration {
    subnets          = var.private_subnet_ids # Run in private subnets (use NAT for outbound)
    security_groups  = [var.app_sg_id]        # Only ALB can reach these on port 8000
    assign_public_ip = false                  # No public IP — private subnets use NAT Gateway
  }

  # --- ALB attachment (API service only) ---
  # Workers don't receive HTTP traffic — they pull from SQS queues.
  # The dynamic block creates a load_balancer block only for the API service.
  dynamic "load_balancer" {
    for_each = each.key == local.api_service ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.api.arn # Register container as ALB target
      container_name   = each.key                    # Must match container name in task definition
      container_port   = var.container_port          # Must match containerPort in task definition
    }
  }

  # Give newly started containers time to pass health checks before marking them unhealthy
  # Only applies to services with a load balancer (API service)
  health_check_grace_period_seconds = each.key == local.api_service ? 60 : null

  # --- Lifecycle: don't fight with CI/CD ---
  # CI/CD creates new task definition revisions and updates the service.
  # Without this, the next terraform apply would revert to the old revision.
  # Auto-scaling may change desired_count — Terraform shouldn't revert that either.
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }

  tags = { Name = "${local.name}-${each.key}" }
}
