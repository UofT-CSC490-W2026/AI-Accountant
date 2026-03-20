# Pin Terraform and provider versions to prevent breaking changes
# This file says WHICH providers to use and their version constraints
# providers.tf says HOW to configure them (region, credentials, tags)
terraform {
  required_version = ">= 1.5.0, < 2.0.0" # Floor and ceiling — prevents accidental Terraform 2.0

  required_providers {
    # AWS provider — translates .tf resources into AWS API calls
    # Used by all modules except vector-search
    aws = {
      source  = "hashicorp/aws" # Official HashiCorp AWS provider
      version = "~> 6.0"        # Any 6.x, blocks 7.0+ (matches bootstrap + global)
    }

    # Qdrant Cloud provider — manages Qdrant vector database clusters
    # Used only by the vector-search module
    qdrant-cloud = {
      source  = "qdrant/qdrant-cloud" # Official Qdrant provider
      version = "~> 1.19"             # Pessimistic constraint on latest stable
    }
  }
}
