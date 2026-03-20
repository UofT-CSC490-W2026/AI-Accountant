# Store state in the S3 bucket created by bootstrap
terraform {
  backend "s3" {
    bucket         = "autobook-tfstate-609092547371" # From bootstrap output
    key            = "global/terraform.tfstate"      # Unique per stack
    region         = "ca-central-1"
    dynamodb_table = "autobook-terraform-locks" # From bootstrap output
    encrypt        = true                       # Encrypt state at rest
  }
}
