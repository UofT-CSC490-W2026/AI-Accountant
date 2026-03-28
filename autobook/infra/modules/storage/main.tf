# Naming convention
locals {
  name = "${var.project}-${var.environment}-data-${var.account_id}" # e.g. "autobook-dev-data-609092547371"
}

# =============================================================================
# S3 BUCKET — object storage for file uploads and ML training data
# =============================================================================
# Stores three types of data:
#   1. Raw file uploads — user uploads via API Service, File Worker reads and processes
#   2. Processed data — normalized transactions, moved to cheaper storage after 90 days
#   3. ML training artifacts — Flywheel Worker writes model data for SageMaker
#
# S3 bucket names must be globally unique across ALL AWS accounts worldwide.
# Appending the account ID guarantees uniqueness.
resource "aws_s3_bucket" "main" {
  bucket = local.name # Globally unique bucket name

  # force_destroy = false (default) means terraform destroy will fail if bucket
  # has objects — protects against accidental data loss
  force_destroy = var.force_destroy

  tags = { Name = local.name }
}

# =============================================================================
# VERSIONING — keep every version of every file
# =============================================================================
# If a file is overwritten or deleted, S3 keeps the old version.
# This lets you recover from accidental deletions or overwrites.
resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id

  versioning_configuration {
    status = "Enabled" # Keep all versions — can recover any past version
  }
}

# =============================================================================
# ENCRYPTION — encrypt all objects at rest
# =============================================================================
# Every object stored in this bucket is automatically encrypted on disk.
# AES-256 (SSE-S3) is AWS-managed encryption — no extra cost, no key management.
resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # AWS-managed key, free, no setup
    }
  }
}

# =============================================================================
# PUBLIC ACCESS BLOCK — prevent any public access
# =============================================================================
# This bucket stores user financial data — it must never be publicly accessible.
# These four settings block every possible way an S3 bucket can be made public.
resource "aws_s3_bucket_public_access_block" "main" {
  bucket = aws_s3_bucket.main.id

  block_public_acls       = true # Block public ACLs from being set
  block_public_policy     = true # Block public bucket policies
  ignore_public_acls      = true # Ignore any existing public ACLs
  restrict_public_buckets = true # Restrict cross-account access via public policies
}

# =============================================================================
# LIFECYCLE RULES — automatically manage storage costs
# =============================================================================
# Two rules:
#   1. Move processed files to cheaper storage after N days (saves ~45% per GB)
#   2. Clean up incomplete multipart uploads (they cost money silently)
resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  # Rule 1: Move processed files to Infrequent Access (IA) storage class
  # IA costs ~$0.0125/GB vs Standard ~$0.023/GB — good for files rarely re-read
  # Only applies to objects under the "processed/" prefix
  rule {
    id     = "processed-to-ia"
    status = var.ia_transition_days > 0 ? "Enabled" : "Disabled"

    filter {
      prefix = "processed/" # Only processed files — raw uploads stay in Standard
    }

    transition {
      days          = var.ia_transition_days # Default: 90 days
      storage_class = "STANDARD_IA"          # Infrequent Access
    }
  }

  # Rule 2: Clean up incomplete multipart uploads
  # When a large file upload is interrupted (network error, crash), the partial
  # upload stays in S3 and costs money. This rule deletes them automatically.
  rule {
    id     = "cleanup-incomplete-uploads"
    status = "Enabled"

    filter {} # Apply to all objects

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days # Default: 7 days
    }
  }

  # Versioning must be enabled before lifecycle rules that reference versions
  depends_on = [aws_s3_bucket_versioning.main]
}

# =============================================================================
# BUCKET POLICY — enforce TLS-only access
# =============================================================================
# Denies any request that doesn't use HTTPS (TLS).
# All AWS SDKs use HTTPS by default, but this policy ensures no misconfigured
# client or CLI call can accidentally send data in plain text.
# This is an AWS best practice for buckets containing sensitive data.
resource "aws_s3_bucket_policy" "tls_only" {
  bucket = aws_s3_bucket.main.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.main.arn,       # The bucket itself
        "${aws_s3_bucket.main.arn}/*" # All objects in the bucket
      ]
      Condition = {
        Bool = {
          "aws:SecureTransport" = "false" # Deny when NOT using HTTPS
        }
      }
    }]
  })

  # Public access block must exist first — otherwise this policy could be
  # interpreted as granting public access (the Deny-all + condition pattern)
  depends_on = [aws_s3_bucket_public_access_block.main]
}
