# --- Values other modules need from monitoring ---

# The SNS topic ARN can be used by other modules or services to publish alerts
# e.g. application-level custom alarms, Lambda error notifications
output "sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications — use to add more alarm actions"
  value       = aws_sns_topic.alerts.arn
}

# The dashboard URL for quick access from documentation or runbooks
output "dashboard_url" {
  description = "CloudWatch dashboard URL — direct link to the monitoring dashboard"
  value       = "https://${data.aws_region.current.region}.console.aws.amazon.com/cloudwatch/home#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}
