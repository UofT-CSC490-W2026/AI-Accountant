# --- Values other modules need from the database ---

# Secrets module needs this to build the connection string (host in credentials JSON)
output "db_address" {
  description = "Database hostname (e.g. autobook-dev-db.abc123.ca-central-1.rds.amazonaws.com)"
  value       = aws_db_instance.main.address
}

# Monitoring module needs this to create CloudWatch alarms for this database
output "db_instance_id" {
  description = "RDS instance identifier — used by CloudWatch alarms"
  value       = aws_db_instance.main.identifier
}

# Backup module needs this to know which database to include in backup plans
output "db_instance_arn" {
  description = "RDS instance ARN — used by backup plans"
  value       = aws_db_instance.main.arn
}
