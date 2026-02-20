output "dashboard_url"   { value = "https://ca-central-1.console.aws.amazon.com/cloudwatch/home?region=ca-central-1#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}" }
output "alarm_topic_arn" { value = aws_sns_topic.alarms.arn }
