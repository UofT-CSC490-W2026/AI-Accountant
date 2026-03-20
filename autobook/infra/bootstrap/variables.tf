variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

variable "region" {
  type        = string
  description = "AWS region for all resources"
}

variable "account_id" {
  type        = string
  description = "AWS account ID, used to make S3 bucket name globally unique"
}
