# Naming convention
locals {
  name = "${var.project}-${var.environment}-db" # e.g. "autobook-dev-db"
}

# =============================================================================
# DB SUBNET GROUP — tells RDS which subnets it can launch in
# =============================================================================
# RDS requires this — it picks one of these subnets to place the instance.
# Private subnets = database is not reachable from the internet.
resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = var.private_subnet_ids # From networking module

  tags = { Name = local.name }
}

# =============================================================================
# RDS INSTANCE — PostgreSQL database
# =============================================================================
# Stores all application data: users, transactions, journal entries,
# pattern store, training data, calibration data. 9 tables, one instance.
resource "aws_db_instance" "main" {
  identifier = local.name # Unique name in AWS

  # --- Engine: always PostgreSQL 16 ---
  # Pinned to 16 (latest stable with full AWS RDS support as of 2026).
  # Hardcoded intentionally — engine upgrades should be deliberate, not accidental.
  engine         = "postgres"
  engine_version = "16"

  # --- Size: controlled by caller ---
  instance_class    = var.db_instance_class # Machine size
  allocated_storage = var.allocated_storage # Disk space in GB
  storage_type      = "gp3"                 # General Purpose SSD v3 — cheaper and faster than gp2
  # gp3: 3000 IOPS baseline (free), $0.08/GB
  # gp2: IOPS tied to size (3 IOPS/GB), $0.10/GB

  # --- Credentials ---
  # Database name and username both use the project name ("autobook").
  # This is safe because our project name is lowercase alphanumeric — valid for RDS naming.
  # If the project name ever contained hyphens or special chars, RDS would reject it.
  db_name  = var.project     # Database name created on first launch
  username = var.project     # Master username
  password = var.db_password # Injected via TF_VAR, never in code
  # NOTE: The password is stored in plain text in Terraform state. Our state backend
  # (S3 with AES-256 encryption + restricted access) is the standard mitigation.
  # There is no way to avoid this with Terraform's architecture.

  # --- Network: private subnets, ECS-only access ---
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.db_sg_id]

  # --- Encryption: always on ---
  storage_encrypted = true

  # --- Performance Insights: query-level monitoring (free for 7 days) ---
  # Shows which SQL queries consume the most CPU, I/O, and time.
  # Essential for identifying slow queries before they become production issues.
  # Free tier retains 7 days of data — no cost unless extended.
  performance_insights_enabled          = true
  performance_insights_retention_period = 7 # Days to retain (7 = free tier)

  # --- Availability: controlled by caller ---
  multi_az = var.multi_az

  # --- Backups: controlled by caller ---
  backup_retention_period    = var.backup_retention_period
  auto_minor_version_upgrade = true # Always auto-apply security patches

  # --- Deletion safety: controlled by caller ---
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${local.name}-final"

  # --- Snapshot restore ---
  snapshot_identifier = var.restore_snapshot_id

  lifecycle {
    ignore_changes = [snapshot_identifier] # After first restore, don't re-restore on every apply
  }

  tags = { Name = local.name }
}
