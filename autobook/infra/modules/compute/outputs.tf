# --- Values other modules need from compute ---

# Monitoring module needs this to create CloudWatch alarms for the ECS cluster
output "cluster_name" {
  description = "ECS cluster name — used by monitoring for CloudWatch alarms"
  value       = aws_ecs_cluster.main.name
}

# Monitoring module needs this to create per-service alarms (API only after Lambda migration)
output "service_names" {
  description = "List of ECS service names — API only, workers moved to Lambda"
  value       = [for s in aws_ecs_service.main : s.name]
}

# DNS module needs this to create an A record pointing api.autobook.tech → ALB
output "alb_dns_name" {
  description = "ALB DNS name — used by DNS module for api subdomain record"
  value       = aws_lb.main.dns_name
}

# DNS module needs this for the Route53 alias record (AWS-internal routing)
output "alb_zone_id" {
  description = "ALB hosted zone ID — used by DNS module for alias record"
  value       = aws_lb.main.zone_id
}

# Monitoring module needs this to create ALB-specific CloudWatch alarms (5xx rate, etc.)
output "alb_arn_suffix" {
  description = "ALB ARN suffix — used by monitoring for ALB CloudWatch metrics"
  value       = aws_lb.main.arn_suffix
}

# CI/CD pipeline needs these to know where to push Docker images
# Map of service name → ECR repo URL, e.g. {"api" = "123456789.dkr.ecr.ca-central-1.amazonaws.com/autobook-dev-api"}
output "ecr_urls" {
  description = "Map of service name → ECR repository URL — used by CI/CD to push images"
  value       = { for name, repo in aws_ecr_repository.main : name => repo.repository_url }
}

output "ws_relay_ecr_url" {
  description = "ECR repository URL for the WS relay service"
  value       = aws_ecr_repository.ws_relay.repository_url
}
