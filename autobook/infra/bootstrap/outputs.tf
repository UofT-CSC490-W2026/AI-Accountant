# Values needed by every other stack's backend.tf

output "state_bucket" {
  description = "S3 bucket name for Terraform state storage"
  value       = aws_s3_bucket.state.id # Bucket name, e.g. "autobook-tfstate-123456789"
}

output "lock_table" {
  description = "DynamoDB table name for Terraform state locking"
  value       = aws_dynamodb_table.locks.name # Table name, e.g. "autobook-terraform-locks"
}
