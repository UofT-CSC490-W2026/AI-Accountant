# Monitoring

Creates CloudWatch alarms, a dashboard, an SNS notification topic, and an AWS budget for the Autobook system.

## What it creates

- **SNS topic + email subscription** — notification channel for all alarms
- **ECS alarms** — per-service CPU and memory (8 services × 2 = 16 alarms)
- **RDS alarms** — CPU, connection count, free storage (3 alarms)
- **ALB alarm** — 5xx error count (1 alarm)
- **CloudWatch dashboard** — single-pane-of-glass with 7 widgets
- **AWS budget** — monthly cost limit with alerts at 80% (forecasted) and 100% (actual)

## Alarm summary

| Alarm | Metric | Default Threshold | Why |
|-------|--------|-------------------|-----|
| ECS CPU (×8) | CPUUtilization | > 80% | Service is compute-bound |
| ECS Memory (×8) | MemoryUtilization | > 80% | Approaching OOM kill |
| RDS CPU | CPUUtilization | > 80% | Expensive queries or missing indexes |
| RDS Connections | DatabaseConnections | > 50 | Approaching max_connections |
| RDS Storage | FreeStorageSpace | < 1 GB | Disk full stops all writes |
| ALB 5xx | HTTPCode_ELB_5XX_Count | > 10 per 5 min | Backend errors reaching clients |

All thresholds are configurable variables — tune after observing real traffic.

## Dashboard layout

```
+----------------------------+----------------------------+
| ECS CPU (all 8 services)   | ECS Memory (all 8 services)|
+----------------------------+----------------------------+
| RDS CPU                    | RDS Connections             |
+----------------------------+----------------------------+
| ALB Request Count          | ALB 5xx Errors              |
+----------------------------+----------------------------+
| RDS Free Storage           |                             |
+----------------------------+----------------------------+
```

Each widget includes a red threshold annotation line matching the alarm configuration.

## How notifications flow

```
CloudWatch alarm fires
  → publishes to SNS topic (autobook-dev-alerts)
    → SNS delivers email to alert_email

AWS Budget threshold crossed
  → AWS sends email directly to budget_alert_email
```

Note: SNS email subscriptions require confirmation. After `terraform apply`, check your inbox and click the confirmation link.

## Usage

```hcl
# Dev
module "monitoring" {
  source = "../../modules/monitoring"

  project     = "autobook"
  environment = "dev"
  alert_email = "team@example.com"

  cluster_name  = module.compute.cluster_name
  service_names = module.compute.service_names
  alb_arn_suffix = module.compute.alb_arn_suffix
  db_instance_id = module.database.db_instance_id

  monthly_budget_usd = "50.0"
}

# Prod — higher thresholds, larger budget
module "monitoring" {
  source = "../../modules/monitoring"

  project     = "autobook"
  environment = "prod"
  alert_email = "ops@example.com"

  cluster_name  = module.compute.cluster_name
  service_names = module.compute.service_names
  alb_arn_suffix = module.compute.alb_arn_suffix
  db_instance_id = module.database.db_instance_id

  rds_connections_threshold = 200
  alb_5xx_threshold         = 50
  monthly_budget_usd        = "500.0"
  budget_alert_email        = "finance@example.com"
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| alert_email | string | — | Email for alarm notifications |
| cluster_name | string | — | ECS cluster name (from compute) |
| service_names | list(string) | — | ECS service names (from compute) |
| alb_arn_suffix | string | — | ALB ARN suffix (from compute) |
| db_instance_id | string | — | RDS instance ID (from database) |
| ecs_cpu_threshold | number | 80 | ECS CPU alarm threshold % |
| ecs_memory_threshold | number | 80 | ECS memory alarm threshold % |
| rds_cpu_threshold | number | 80 | RDS CPU alarm threshold % |
| rds_connections_threshold | number | 50 | RDS connection count threshold |
| rds_free_storage_threshold | number | 1073741824 | RDS free storage threshold (bytes) |
| alb_5xx_threshold | number | 10 | ALB 5xx count threshold per period |
| evaluation_periods | number | 2 | Consecutive periods before alarm fires |
| period | number | 300 | Evaluation period in seconds |
| monthly_budget_usd | string | 50.0 | Monthly AWS budget limit (USD) |
| budget_alert_email | string | null | Budget alert email (null = alert_email) |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| sns_topic_arn | SNS topic ARN for alarm notifications | other modules adding custom alarms |
| dashboard_url | Direct link to CloudWatch dashboard | team reference |
