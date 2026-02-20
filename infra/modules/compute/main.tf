# --- ECR ---
resource "aws_ecr_repository" "api" {
  name         = "${var.service_name_prefix}-${var.env}"
  force_delete = var.env == "dev"

  tags = { Name = "${var.service_name_prefix}-${var.env}" }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 30 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = { type = "expire" }
    }]
  })
}

# --- ALB ---
resource "aws_lb" "main" {
  name               = "autobook-${var.env}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_sg_id]
  subnets            = var.public_subnet_ids

  tags = { Name = "autobook-${var.env}" }
}

resource "aws_lb_target_group" "api" {
  name                 = "autobook-api-${var.env}"
  port                 = 8000
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
  target_type          = "ip"
  deregistration_delay = 30

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "autobook-api-${var.env}" }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.cert_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# --- CloudWatch Log Group ---
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/autobook-${var.env}"
  retention_in_days = var.env == "prod" ? 30 : 14

  tags = { Name = "autobook-${var.env}" }
}

# --- ECS Cluster ---
resource "aws_ecs_cluster" "main" {
  name = "${var.cluster_name_prefix}-${var.env}"

  tags = { Name = "${var.cluster_name_prefix}-${var.env}" }
}

# --- ECS Task Definition ---
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.service_name_prefix}-${var.env}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "ENV", value = var.env },
      { name = "S3_BUCKET", value = var.s3_bucket },
      { name = "COGNITO_POOL_ID", value = var.cognito_pool_id },
      { name = "COGNITO_CLIENT_ID", value = var.cognito_client_id },
      { name = "AWS_DEFAULT_REGION", value = var.aws_region },
    ]

    secrets = [{
      name      = "DB_CREDENTIALS"
      valueFrom = var.db_credentials_secret_arn
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])

  tags = { Name = "${var.service_name_prefix}-${var.env}" }
}

# --- ECS Service ---
resource "aws_ecs_service" "api" {
  name            = "${var.service_name_prefix}-${var.env}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.public_subnet_ids
    security_groups  = [var.app_sg_id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  health_check_grace_period_seconds = 60
  enable_execute_command            = true

  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = { Name = "${var.service_name_prefix}-${var.env}" }
}

# --- DNS ---
resource "aws_route53_record" "api" {
  zone_id = var.zone_id
  name    = "${var.api_subdomain}.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
