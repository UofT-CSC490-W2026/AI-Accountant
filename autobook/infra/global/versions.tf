# Pin Terraform and provider versions to prevent breaking changes
terraform {
  required_version = ">= 1.5.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws" # Plugin that translates .tf into AWS API calls
      version = "~> 6.0"        # Any 6.x, block 7.0+
    }
  }
}
