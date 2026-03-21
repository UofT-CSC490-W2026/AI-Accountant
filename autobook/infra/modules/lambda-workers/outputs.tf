# --- Values other modules need from lambda-workers ---

# CI/CD needs these to know which functions to update
output "function_names" {
  description = "Map of worker name → Lambda function name"
  value       = { for name, fn in aws_lambda_function.worker : name => fn.function_name }
}

# Monitoring module can use these for CloudWatch alarms
output "function_arns" {
  description = "Map of worker name → Lambda function ARN"
  value       = { for name, fn in aws_lambda_function.worker : name => fn.arn }
}

# CI/CD needs these to push Docker images
output "ecr_urls" {
  description = "Map of worker name → ECR repository URL"
  value       = { for name, repo in aws_ecr_repository.worker : name => repo.repository_url }
}
