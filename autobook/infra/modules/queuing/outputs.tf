# --- Values other modules need from queuing ---

# Compute module injects these as environment variables into ECS containers.
# Each worker reads its input/output queue URLs from env vars at startup.
# Map: {"files" = "https://sqs.ca-central-1.amazonaws.com/123.../autobook-dev-files", ...}
output "queue_urls" {
  description = "Map of queue name → SQS queue URL — injected as env vars into ECS containers"
  value       = { for name, queue in aws_sqs_queue.main : name => queue.url }
}

# IAM module uses these to scope SQS permissions per service.
# Each service only gets send/receive access to the queues it actually uses.
# Map: {"files" = "arn:aws:sqs:ca-central-1:123...:autobook-dev-files", ...}
output "queue_arns" {
  description = "Map of queue name → SQS queue ARN — used by IAM for per-service permissions"
  value       = { for name, queue in aws_sqs_queue.main : name => queue.arn }
}

# Monitoring module can alarm on DLQ depth — a non-empty DLQ means failures.
# Map: {"files" = "https://sqs.ca-central-1.amazonaws.com/123.../autobook-dev-files-dlq", ...}
output "dlq_urls" {
  description = "Map of queue name → dead-letter queue URL — for monitoring and message replay"
  value       = { for name, queue in aws_sqs_queue.dlq : name => queue.url }
}

# Monitoring module uses these ARNs for CloudWatch alarm dimensions.
# Map: {"files" = "arn:aws:sqs:ca-central-1:123...:autobook-dev-files-dlq", ...}
output "dlq_arns" {
  description = "Map of queue name → dead-letter queue ARN — used by monitoring for alarms"
  value       = { for name, queue in aws_sqs_queue.dlq : name => queue.arn }
}
