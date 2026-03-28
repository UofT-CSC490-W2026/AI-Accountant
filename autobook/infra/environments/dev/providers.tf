# =============================================================================
# AWS PROVIDER — configures how Terraform talks to AWS
# =============================================================================
# This is the main provider used by 12 of 13 modules.
# Credentials come from environment (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)
# or from an IAM instance role — never hardcoded here.
provider "aws" {
  region = var.region # ca-central-1 (Canadian data residency)

  # Default tags are applied to EVERY resource created by this provider
  # No need to repeat these in each module — they're inherited automatically
  default_tags {
    tags = {
      Project     = var.project     # "autobook" — identifies which project owns this resource
      Environment = var.environment # "dev" — distinguishes dev from prod resources
      ManagedBy   = "terraform"     # Signals that manual changes will be overwritten
    }
  }
}

# =============================================================================
# QDRANT CLOUD PROVIDER — manages Qdrant vector database clusters
# =============================================================================
# Separate provider from AWS — Qdrant Cloud has its own API.
# Credentials come from TF_VAR_ environment variables (never in tfvars):
#   export TF_VAR_qdrant_cloud_api_key="..."
#   export TF_VAR_qdrant_cloud_account_id="..."
provider "qdrant-cloud" {
  api_key    = var.qdrant_cloud_api_key    # Qdrant Cloud management API key
  account_id = var.qdrant_cloud_account_id # Qdrant Cloud account identifier
}
