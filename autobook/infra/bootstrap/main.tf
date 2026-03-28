# --- S3 bucket: stores .tfstate files for all stacks ---
resource "aws_s3_bucket" "state" {
  bucket = "${var.project}-tfstate-${var.account_id}" # Globally unique name

  lifecycle {
    prevent_destroy = true # Never accidentally delete state
  }
}

# Keep every version of the state file — allows rollback
resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Encrypt state at rest — state contains sensitive values
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # AWS-managed key, no extra cost
    }
  }
}

# Block all public access — state files are private
resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- DynamoDB table: prevents concurrent terraform apply ---
resource "aws_dynamodb_table" "locks" {
  name         = "${var.project}-terraform-locks"
  billing_mode = "PAY_PER_REQUEST" # No cost when idle
  hash_key     = "LockID"          # Primary key — Terraform writes a row here during apply

  attribute {
    name = "LockID"
    type = "S" # String
  }

  lifecycle {
    prevent_destroy = true # Never accidentally delete the lock table
  }
}
