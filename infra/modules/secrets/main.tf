resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.secret_name_prefix}-db-credentials-${var.env}"
  recovery_window_in_days = var.env == "prod" ? 30 : 0
  # dev: 0 = immediate deletion. Without this, terraform destroy + apply
  # blocks for 30 days ("secret already scheduled for deletion").
  # prod: 30 = safety net against accidental deletion.
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id     = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "autobook"
    password = var.db_password
    host     = var.db_address # from database module output (address, not endpoint — endpoint includes port)
    port     = 5432
    dbname   = "autobook"
  })
}
