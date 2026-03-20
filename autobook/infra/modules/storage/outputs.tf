# --- Values other modules need from storage ---

# IAM module needs this to scope S3 permissions for api, file, flywheel roles
output "bucket_arn" {
  description = "S3 bucket ARN — used by IAM module to create scoped S3 policies"
  value       = aws_s3_bucket.main.arn
}

# Compute module needs this so ECS containers know which bucket to read/write
output "bucket_id" {
  description = "S3 bucket name — passed as env var to ECS containers"
  value       = aws_s3_bucket.main.id
}
