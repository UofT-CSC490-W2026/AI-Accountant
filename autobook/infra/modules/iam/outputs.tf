# --- Values other modules need from IAM ---

# Compute module attaches this to every ECS task definition
# Gives the ECS agent (not the container) permission to pull images, write logs, read secrets
output "execution_role_arn" {
  description = "ECS execution role ARN — used by ECS agent for image pulls, logs, secrets"
  value       = aws_iam_role.execution.arn
}

# Compute module uses this to assign each ECS service its own task role
# Map of service name → role ARN, e.g. {"api" = "arn:...", "llm" = "arn:..."}
output "task_role_arns" {
  description = "Map of service name → task role ARN — per-service least-privilege permissions"
  value       = { for name, role in aws_iam_role.task : name => role.arn }
}

# GitHub Actions workflow uses this to assume AWS permissions for CI/CD deploys
output "github_actions_role_arn" {
  description = "GitHub Actions deploy role ARN — assumed via OIDC for CI/CD"
  value       = aws_iam_role.github_actions.arn
}
