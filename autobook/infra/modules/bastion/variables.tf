variable "project" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "private_subnet_id" {
  type        = string
  description = "Private subnet ID (same VPC as RDS)"
}

variable "app_sg_id" {
  type        = string
  description = "Security group that has access to RDS"
}
