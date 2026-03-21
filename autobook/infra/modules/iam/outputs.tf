# --- Values other modules need from IAM ---

# Compute module attaches this to every ECS task definition
# Gives the ECS agent (not the container) permission to pull images, write logs, read secrets
output "execution_role_arn" {
  description = "ECS execution role ARN — used by ECS agent for image pulls, logs, secrets"
  value       = aws_iam_role.execution.arn
}

# Compute module uses this to assign the API ECS service its task role
output "task_role_arns" {
  description = "Map of ECS service name → task role ARN (API only)"
  value       = { for name, role in aws_iam_role.task : name => role.arn }
}

# Lambda module uses this to assign each worker its execution role
output "lambda_role_arns" {
  description = "Map of Lambda worker name → role ARN"
  value       = { for name, role in aws_iam_role.lambda : name => role.arn }
}

# WS relay ECS service role
output "ws_relay_role_arn" {
  description = "WS relay ECS task role ARN"
  value       = aws_iam_role.ws_relay.arn
}

# GitHub Actions workflow uses this to assume AWS permissions for CI/CD deploys
output "github_actions_role_arn" {
  description = "GitHub Actions deploy role ARN — assumed via OIDC for CI/CD"
  value       = aws_iam_role.github_actions.arn
}
