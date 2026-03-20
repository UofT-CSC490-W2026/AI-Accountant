# Naming convention
locals {
  name = "${var.project}-${var.environment}" # e.g. "autobook-dev"

  # Resolve budget alert email — defaults to the same operational alert email
  budget_email = coalesce(var.budget_alert_email, var.alert_email)
}

# Look up current region — used in dashboard URL output
data "aws_region" "current" {}

# =============================================================================
# SNS TOPIC — notification channel for all alarms
# =============================================================================
# SNS (Simple Notification Service) is AWS's pub/sub messaging service.
# CloudWatch alarms publish to this topic when they fire.
# The email subscription delivers the alarm notification to your inbox.
#
# Flow: CloudWatch alarm fires → publishes to SNS topic → SNS sends email
resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts" # e.g. "autobook-dev-alerts"

  tags = { Name = "${local.name}-alerts" }
}

# Email subscription — delivers alarm notifications to the team
# IMPORTANT: After terraform apply, AWS sends a confirmation email.
# You MUST click the confirmation link or no alerts will be delivered.
resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"         # Deliver via email (alternatives: SMS, Lambda, HTTPS)
  endpoint  = var.alert_email # Email address to receive notifications
}

# =============================================================================
# ECS ALARMS — per-service CPU and memory monitoring
# =============================================================================
# ECS Fargate reports CPU and memory utilization to CloudWatch automatically.
# We create one CPU alarm and one memory alarm per service (8 services × 2 = 16 alarms).
#
# Why per-service? Different services have different resource profiles:
#   - LLM Worker: CPU-heavy (orchestrating Bedrock calls)
#   - Model Worker: memory-heavy (ML inference data)
#   - API Service: both (handling HTTP + DB queries)
#
# If all services shared one alarm, a spike in one service could be masked
# by low utilization in others.

# CPU alarm per ECS service — fires when CPU stays above threshold
resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  for_each = toset(var.service_names) # One alarm per service

  alarm_name          = "${local.name}-${each.key}-cpu" # e.g. "autobook-dev-api-cpu"
  alarm_description   = "ECS service ${each.key} CPU utilization > ${var.ecs_cpu_threshold}%"
  comparison_operator = "GreaterThanThreshold" # Fire when metric > threshold
  evaluation_periods  = var.evaluation_periods # How many consecutive periods must breach (default: 2)
  metric_name         = "CPUUtilization"       # Built-in ECS metric (0-100%)
  namespace           = "AWS/ECS"              # CloudWatch namespace for ECS metrics
  period              = var.period             # Evaluation window in seconds (default: 300 = 5 min)
  statistic           = "Average"              # Average across all tasks in the service
  threshold           = var.ecs_cpu_threshold  # Default: 80%
  treat_missing_data  = "notBreaching"         # No data = OK (service might be scaled to zero)

  # Dimensions narrow the metric to this specific cluster + service
  dimensions = {
    ClusterName = var.cluster_name # Which ECS cluster
    ServiceName = each.key         # Which service within the cluster
  }

  alarm_actions = [aws_sns_topic.alerts.arn] # Send notification when alarm fires
  ok_actions    = [aws_sns_topic.alerts.arn] # Send notification when alarm clears
}

# Memory alarm per ECS service — fires before OOM (Out Of Memory) kills
# OOM kills cause container restarts with no error logs — hard to debug
# This alarm gives you warning time to increase task memory or fix a leak
resource "aws_cloudwatch_metric_alarm" "ecs_memory" {
  for_each = toset(var.service_names)

  alarm_name          = "${local.name}-${each.key}-memory"
  alarm_description   = "ECS service ${each.key} memory utilization > ${var.ecs_memory_threshold}%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.evaluation_periods
  metric_name         = "MemoryUtilization" # Built-in ECS metric (0-100%)
  namespace           = "AWS/ECS"
  period              = var.period
  statistic           = "Average"
  threshold           = var.ecs_memory_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = each.key
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# =============================================================================
# RDS ALARMS — database health monitoring
# =============================================================================
# RDS reports CPU, connections, and storage metrics to CloudWatch automatically.
# These three alarms cover the most common database failure modes:
#   1. CPU: runaway queries, missing indexes, or connection storm
#   2. Connections: approaching max_connections causes new connections to fail
#   3. Storage: disk full causes writes to fail and can corrupt the database

# RDS CPU alarm — high CPU usually means expensive queries or missing indexes
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.name}-rds-cpu"
  alarm_description   = "RDS CPU utilization > ${var.rds_cpu_threshold}%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.evaluation_periods
  metric_name         = "CPUUtilization" # Built-in RDS metric (0-100%)
  namespace           = "AWS/RDS"        # CloudWatch namespace for RDS metrics
  period              = var.period
  statistic           = "Average"
  threshold           = var.rds_cpu_threshold

  dimensions = {
    DBInstanceIdentifier = var.db_instance_id # Which RDS instance to monitor
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# RDS connections alarm — too many connections approaching max_connections limit
# When max_connections is hit, new connections get "too many connections" errors
# This alarm fires before that happens so you can investigate
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "${local.name}-rds-connections"
  alarm_description   = "RDS connection count > ${var.rds_connections_threshold}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.evaluation_periods
  metric_name         = "DatabaseConnections" # Number of active DB connections
  namespace           = "AWS/RDS"
  period              = var.period
  statistic           = "Average"
  threshold           = var.rds_connections_threshold

  dimensions = {
    DBInstanceIdentifier = var.db_instance_id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# RDS free storage alarm — fires when available storage drops below threshold
# Running out of storage stops all writes and can require manual intervention
resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "${local.name}-rds-storage"
  alarm_description   = "RDS free storage < ${var.rds_free_storage_threshold / 1073741824} GB"
  comparison_operator = "LessThanThreshold" # Fire when metric < threshold (low storage = bad)
  evaluation_periods  = var.evaluation_periods
  metric_name         = "FreeStorageSpace" # Available storage in bytes
  namespace           = "AWS/RDS"
  period              = var.period
  statistic           = "Average"
  threshold           = var.rds_free_storage_threshold

  dimensions = {
    DBInstanceIdentifier = var.db_instance_id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# =============================================================================
# ALB ALARM — HTTP 5xx errors reaching clients
# =============================================================================
# 5xx errors mean the backend returned an error to the client.
# A sustained spike usually means the API Service is unhealthy (crash loop,
# DB connection failure, or unhandled exception).
#
# We monitor HTTPCode_ELB_5XX_Count — 5xx errors generated by the ALB itself
# (e.g., 502 when targets are unavailable, 503 when no healthy targets, 504 timeout).
# This does NOT include application-level 5xx — those are tracked by
# HTTPCode_Target_5XX_Count (a separate metric, not alarmed here).
# ALB 5xx is more critical because it means the infrastructure is failing,
# not just the app returning an error.
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${local.name}-alb-5xx"
  alarm_description   = "ALB 5xx errors > ${var.alb_5xx_threshold} per ${var.period / 60} min"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.evaluation_periods
  metric_name         = "HTTPCode_ELB_5XX_Count" # 5xx responses generated by the ALB
  namespace           = "AWS/ApplicationELB"     # CloudWatch namespace for ALB metrics
  period              = var.period
  statistic           = "Sum" # Total count (not average — we want raw error count)
  threshold           = var.alb_5xx_threshold
  treat_missing_data  = "notBreaching" # No data = no errors = OK

  dimensions = {
    LoadBalancer = var.alb_arn_suffix # Which ALB to monitor
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

# =============================================================================
# CLOUDWATCH DASHBOARD — single-pane-of-glass for system health
# =============================================================================
# A dashboard groups multiple metrics into visual widgets.
# This gives the team one URL to check system health instead of
# navigating through multiple CloudWatch pages.
#
# Layout: 4 rows
#   Row 1: ECS CPU + Memory (all services on one graph)
#   Row 2: RDS CPU + Connections
#   Row 3: ALB requests + 5xx errors
#   Row 4: RDS storage
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = local.name # e.g. "autobook-dev"

  # Dashboard body is JSON — defines widgets, their position, and metrics
  dashboard_body = jsonencode({
    widgets = [
      # --- Row 1: ECS CPU utilization (all services) ---
      {
        type   = "metric"
        x      = 0  # Column position (0-23)
        y      = 0  # Row position
        width  = 12 # Half the dashboard width (24 max)
        height = 6  # Standard widget height
        properties = {
          title   = "ECS CPU Utilization"
          region  = data.aws_region.current.region
          view    = "timeSeries" # Line chart over time
          stacked = false        # Overlay lines (not stacked area)
          metrics = [
            # One line per service — all on the same chart for comparison
            for name in var.service_names : [
              "AWS/ECS", "CPUUtilization",     # Namespace + Metric
              "ClusterName", var.cluster_name, # Dimension 1
              "ServiceName", name              # Dimension 2
            ]
          ]
          annotations = {
            horizontal = [{
              label = "Alarm threshold"
              value = var.ecs_cpu_threshold
              color = "#d62728" # Red line at the threshold
            }]
          }
        }
      },

      # --- Row 1: ECS Memory utilization (all services) ---
      {
        type   = "metric"
        x      = 12 # Right half of the dashboard
        y      = 0
        width  = 12
        height = 6
        properties = {
          title   = "ECS Memory Utilization"
          region  = data.aws_region.current.region
          view    = "timeSeries"
          stacked = false
          metrics = [
            for name in var.service_names : [
              "AWS/ECS", "MemoryUtilization",
              "ClusterName", var.cluster_name,
              "ServiceName", name
            ]
          ]
          annotations = {
            horizontal = [{
              label = "Alarm threshold"
              value = var.ecs_memory_threshold
              color = "#d62728"
            }]
          }
        }
      },

      # --- Row 2: RDS CPU utilization ---
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "RDS CPU Utilization"
          region  = data.aws_region.current.region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.db_instance_id]
          ]
          annotations = {
            horizontal = [{
              label = "Alarm threshold"
              value = var.rds_cpu_threshold
              color = "#d62728"
            }]
          }
        }
      },

      # --- Row 2: RDS Database Connections ---
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title   = "RDS Database Connections"
          region  = data.aws_region.current.region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "DatabaseConnections", "DBInstanceIdentifier", var.db_instance_id]
          ]
          annotations = {
            horizontal = [{
              label = "Alarm threshold"
              value = var.rds_connections_threshold
              color = "#d62728"
            }]
          }
        }
      },

      # --- Row 3: ALB Request Count ---
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title   = "ALB Request Count"
          region  = data.aws_region.current.region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix]
          ]
        }
      },

      # --- Row 3: ALB 5xx Errors ---
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title   = "ALB 5xx Errors"
          region  = data.aws_region.current.region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", var.alb_arn_suffix]
          ]
          annotations = {
            horizontal = [{
              label = "Alarm threshold"
              value = var.alb_5xx_threshold
              color = "#d62728"
            }]
          }
        }
      },

      # --- Row 4: RDS Free Storage Space ---
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6
        properties = {
          title   = "RDS Free Storage Space (bytes)"
          region  = data.aws_region.current.region
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["AWS/RDS", "FreeStorageSpace", "DBInstanceIdentifier", var.db_instance_id]
          ]
          annotations = {
            horizontal = [{
              label = "Alarm threshold"
              value = var.rds_free_storage_threshold
              color = "#d62728"
            }]
          }
        }
      }
    ]
  })
}

# =============================================================================
# AWS BUDGET — cost alerting to prevent surprise bills
# =============================================================================
# AWS Budgets tracks your spending against a defined limit.
# Two notifications:
#   1. At 80% — early warning to investigate what's driving cost
#   2. At 100% — budget exceeded, take action (scale down, review resources)
#
# This catches mistakes like:
#   - Forgot to scale down after a load test
#   - SageMaker endpoint left running (not scaled to zero)
#   - NAT gateway cost spike from unexpected egress traffic
resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"                 # Track actual dollar spend (not usage)
  limit_amount = var.monthly_budget_usd # Monthly limit in USD
  limit_unit   = "USD"
  time_unit    = "MONTHLY" # Reset budget each month

  # Alert at 80% of budget — early warning
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80 # 80% of budget
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED" # Alert based on projected spend (not actual)
    subscriber_email_addresses = [local.budget_email]
  }

  # Alert at 100% of budget — budget exceeded
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100 # 100% of budget
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL" # Alert based on actual spend
    subscriber_email_addresses = [local.budget_email]
  }
}
