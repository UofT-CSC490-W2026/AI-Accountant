variable "project" {
  type        = string
  description = "Project name, used in resource naming and tags"
}

variable "region" {
  type        = string
  description = "AWS region for all resources"
}

variable "domain_name" {
  type        = string
  description = "Root domain name for the application"
}

variable "frontend_ip" {
  type        = string
  description = "IP address of the frontend hosting provider (Netlify)"
}

variable "frontend_cname" {
  type        = string
  description = "CNAME target for www subdomain (Netlify)"
}
