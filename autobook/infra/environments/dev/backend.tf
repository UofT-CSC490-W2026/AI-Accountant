# =============================================================================
# REMOTE STATE — store Terraform state in S3 with DynamoDB locking
# =============================================================================
# Terraform state tracks what resources exist and their current configuration.
# Without remote state, only the person who ran `terraform apply` has the state
# file, and no one else can safely modify the infrastructure.
#
# S3 stores the state file (encrypted at rest).
# DynamoDB prevents two people from running `terraform apply` at the same time
# (state locking) — without this, simultaneous applies can corrupt state.
#
# The bucket and table were created by the bootstrap stack.
# The key must be unique per stack — two stacks sharing a key = data loss.
terraform {
  backend "s3" {
    bucket         = "autobook-tfstate-609092547371" # From bootstrap output (includes account ID for uniqueness)
    key            = "env/dev/terraform.tfstate"     # Unique path — dev and prod each get their own key
    region         = "ca-central-1"                  # Must match the bucket's region
    dynamodb_table = "autobook-terraform-locks"      # From bootstrap output
    encrypt        = true                            # Encrypt state at rest (contains sensitive values)
  }
}
