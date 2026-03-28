# --- Values other modules need from networking ---

# Almost every module needs this — it's the network everything lives in
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

# ALB goes in public subnets (needs to receive internet traffic)
output "public_subnet_ids" {
  description = "IDs of public subnets (internet-facing resources go here)"
  value       = [for s in aws_subnet.public : s.id]
}

# RDS, Redis, ECS workers go in private subnets (no direct internet access)
output "private_subnet_ids" {
  description = "IDs of private subnets (databases, caches, workers go here)"
  value       = [for s in aws_subnet.private : s.id]
}

# Compute module attaches this to the ALB — allows HTTPS from the internet
output "alb_sg_id" {
  description = "Security group for the ALB — allows HTTPS from the internet"
  value       = aws_security_group.alb.id
}

# Compute module attaches this to ECS services — only ALB can reach them
output "app_sg_id" {
  description = "Security group for ECS services — allows traffic from ALB only"
  value       = aws_security_group.app.id
}

# Database module attaches this to RDS — only ECS services can reach it
output "db_sg_id" {
  description = "Security group for RDS — allows traffic from ECS services only"
  value       = aws_security_group.db.id
}

# Cache module attaches this to ElastiCache — only ECS services can reach it
output "redis_sg_id" {
  description = "Security group for ElastiCache Redis — allows traffic from ECS services only"
  value       = aws_security_group.redis.id
}

# ML module attaches this to SageMaker — only ECS services can reach it
output "sagemaker_sg_id" {
  description = "Security group for SageMaker — allows traffic from ECS services only"
  value       = aws_security_group.sagemaker.id
}
