# --- Backup Vault ---
resource "aws_backup_vault" "main" {
  name          = "autobook-vault-${var.env}"
  force_destroy = var.env == "dev"

  tags = { Name = "autobook-vault-${var.env}" }
}

# --- Backup Plan ---
resource "aws_backup_plan" "main" {
  name = "autobook-daily-${var.env}"

  rule {
    rule_name         = "daily-3am"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 3 * * ? *)"

    lifecycle {
      delete_after = var.env == "prod" ? 30 : 7
    }
  }

  tags = { Name = "autobook-daily-${var.env}" }
}

# --- Backup Selection ---
resource "aws_backup_selection" "rds" {
  name         = "autobook-rds-${var.env}"
  plan_id      = aws_backup_plan.main.id
  iam_role_arn = aws_iam_role.backup.arn
  resources    = [var.db_instance_arn]
}

# --- Backup Service Role ---
resource "aws_iam_role" "backup" {
  name = "autobook-backup-${var.env}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "backup.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "backup_restores" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}
