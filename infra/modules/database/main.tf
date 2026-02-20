resource "aws_db_subnet_group" "main" {
  name       = "autobook-${var.env}"
  subnet_ids = var.private_subnet_ids

  tags = { Name = "autobook-${var.env}" }
}

resource "aws_db_instance" "main" {
  identifier = "autobook-db-${var.env}"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage = 20
  storage_encrypted = true

  db_name  = "autobook"
  username = "autobook"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.db_sg_id]

  auto_minor_version_upgrade = true
  backup_retention_period    = var.env == "prod" ? 30 : 7
  multi_az                   = var.env == "prod"
  skip_final_snapshot        = var.env != "prod"
  final_snapshot_identifier  = var.env == "prod" ? "autobook-db-final-${var.env}" : null
  deletion_protection        = var.env == "prod"

  snapshot_identifier = var.restore_snapshot_id

  lifecycle {
    ignore_changes = [snapshot_identifier]
  }

  tags = { Name = "autobook-db-${var.env}" }
}
