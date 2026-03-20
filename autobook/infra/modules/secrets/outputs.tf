# --- Values other modules need from secrets ---

# Compute module needs this to inject DB credentials into ECS containers
# ECS task definitions reference this ARN in the "secrets" block:
#   { "name": "DB_HOST", "valueFrom": "arn:...:secret:autobook-dev-db-credentials:host::" }
# The ECS agent reads the secret at container startup and sets env vars — the
# credentials never appear in the task definition or Docker image.
output "db_credentials_secret_arn" {
  description = "Secrets Manager ARN for DB credentials — used by ECS to inject env vars"
  value       = aws_secretsmanager_secret.db_credentials.arn
}
