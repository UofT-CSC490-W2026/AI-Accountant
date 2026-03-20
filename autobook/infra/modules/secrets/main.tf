# Naming convention
locals {
  name = "${var.project}-${var.environment}-db-credentials" # e.g. "autobook-dev-db-credentials"

  # Default db_name and db_username to the project name (matching the database module)
  db_name     = coalesce(var.db_name, var.project)
  db_username = coalesce(var.db_username, var.project)
}

# =============================================================================
# SECRETS MANAGER SECRET — the container that holds the secret
# =============================================================================
# A Secrets Manager secret is two things:
#   1. The "secret" itself — a named container (this resource)
#   2. The "secret version" — the actual value inside it (next resource)
#
# Why Secrets Manager instead of environment variables or .env files?
#   - Values are encrypted at rest (AES-256)
#   - Access controlled by IAM (only the ECS execution role can read)
#   - Audit trail in CloudTrail (who read which secret, when)
#   - Can rotate credentials without redeploying containers
#   - ECS injects secrets at container startup — never in the image or task definition
resource "aws_secretsmanager_secret" "db_credentials" {
  name = local.name # Secret name — IAM policies reference this via naming pattern

  # How long to wait before permanently deleting (after a terraform destroy)
  # 0 = delete immediately. In prod, set to 7-30 for accidental deletion recovery.
  recovery_window_in_days = var.recovery_window_in_days

  tags = { Name = local.name }
}

# =============================================================================
# SECRET VERSION — the actual credentials (JSON)
# =============================================================================
# Stores the DB connection details as a JSON object:
#   { "host": "...", "port": 5432, "dbname": "autobook", "username": "autobook", "password": "..." }
#
# ECS can pull individual fields from the JSON using the ARN format:
#   arn:...:secret:autobook-dev-db-credentials:host::
#   arn:...:secret:autobook-dev-db-credentials:password::
#
# IMPORTANT: This value ends up in the Terraform state file in plain text.
# Our state is stored in S3 with AES-256 encryption and restricted access,
# which is the standard mitigation. Never store state locally or unencrypted.
resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id

  # JSON blob with all fields needed to connect to the database
  secret_string = jsonencode({
    host     = var.db_address    # RDS hostname from database module
    port     = var.db_port       # Default: 5432
    dbname   = local.db_name     # Database name (default: project name)
    username = local.db_username # Master username (default: project name)
    password = var.db_password   # Injected via TF_VAR_db_password
  })
}
