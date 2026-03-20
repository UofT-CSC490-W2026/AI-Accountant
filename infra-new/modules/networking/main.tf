# Naming convention used throughout
locals {
  name = "${var.project}-${var.environment}"  # e.g. "autobook-dev"
  azs  = ["${var.region}a", "${var.region}b"] # Two availability zones for redundancy
}

# =============================================================================
# VPC — your private network in AWS
# =============================================================================
# Everything lives inside this. Without it, resources have no network.
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr # IP range for the entire network
  enable_dns_support   = true         # Allow DNS resolution inside the VPC
  enable_dns_hostnames = true         # Give resources DNS names (needed by RDS)

  tags = { Name = local.name }
}

# =============================================================================
# SUBNETS — subdivisions of the VPC
# =============================================================================
# Public subnets: internet-facing. ALB goes here.
# Two subnets in two availability zones — if one AZ goes down, the other still works.
# Keyed by AZ so reordering CIDRs won't destroy/recreate subnets.
resource "aws_subnet" "public" {
  for_each = { for i, cidr in var.public_subnet_cidrs : local.azs[i] => cidr }

  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value # Each subnet gets its own IP range
  availability_zone = each.key   # Spread across AZs

  tags = { Name = "${local.name}-public-${each.key}" }
}

# Private subnets: no direct internet access. Database, Redis, ECS workers go here.
# Keyed by AZ so reordering CIDRs won't destroy/recreate subnets.
resource "aws_subnet" "private" {
  for_each = { for i, cidr in var.private_subnet_cidrs : local.azs[i] => cidr }

  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value
  availability_zone = each.key

  tags = { Name = "${local.name}-private-${each.key}" }
}

# =============================================================================
# INTERNET GATEWAY — the door between your VPC and the internet
# =============================================================================
# Without this, nothing in the VPC can reach or be reached from the internet.
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id # Attach to our VPC

  tags = { Name = local.name }
}

# =============================================================================
# NAT GATEWAY — lets private subnets make outbound internet calls
# =============================================================================
# ECS containers in private subnets need to pull Docker images, call AWS APIs
# (Bedrock, SageMaker, etc). NAT lets them reach out without being reachable from outside.

# NAT needs a public IP address (Elastic IP)
resource "aws_eip" "nat" {
  domain = "vpc" # Allocate an IP in the VPC address space

  tags = { Name = "${local.name}-nat" }
}

# NAT Gateway sits in a public subnet and routes private subnet traffic to the internet.
# Single NAT to save cost (~$32/mo). If this AZ goes down, private subnet outbound fails —
# acceptable for this project. For HA, add a second NAT in the other AZ (~$64/mo total).
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id                     # Use the Elastic IP above
  subnet_id     = aws_subnet.public[local.azs[0]].id # Place in first public subnet

  tags = { Name = local.name }

  depends_on = [aws_internet_gateway.main] # IGW must exist before NAT can route
}

# =============================================================================
# ROUTE TABLES — rules that tell subnets where to send traffic
# =============================================================================

# Public route table: send internet traffic through the Internet Gateway
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"                  # All internet-bound traffic
    gateway_id = aws_internet_gateway.main.id # Goes through IGW
  }

  tags = { Name = "${local.name}-public" }
}

# Private route table: send internet traffic through NAT Gateway
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"             # All internet-bound traffic
    nat_gateway_id = aws_nat_gateway.main.id # Goes through NAT (outbound only)
  }

  tags = { Name = "${local.name}-private" }
}

# Link each subnet to its route table — keyed by AZ to match subnets
resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

# =============================================================================
# SECURITY GROUPS — firewall rules per resource type
# =============================================================================
# Each group defines who can talk to that resource and on what port.
# Chain: Internet → ALB (443) → App (8000) → DB (5432) / Redis (6379) / SageMaker (443)

# ALB: accepts HTTPS from the internet
resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-alb-" # name_prefix avoids conflicts on recreate
  description = "ALB — allows HTTPS (443) from the internet"
  vpc_id      = aws_vpc.main.id

  # Inbound: HTTPS only — port 80 is intentionally closed.
  # This is a backend API endpoint (api.autobook.tech), not a website.
  # Frontend (autobook.tech, www.autobook.tech) is served by Netlify,
  # which handles HTTP→HTTPS redirects automatically.
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # The whole internet
  }

  # Outbound: allow all (ALB needs to reach ECS containers)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # All protocols
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-alb" }
}

# App (ECS): only accepts traffic from the ALB
resource "aws_security_group" "app" {
  name_prefix = "${local.name}-app-"
  description = "ECS services — allows port 8000 from ALB only"
  vpc_id      = aws_vpc.main.id

  # Inbound: port 8000 from ALB only (not the internet)
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id] # Only ALB can reach this
  }

  # Outbound: allow all (containers need to call AWS services, DB, Redis, etc)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-app" }
}

# Database (RDS): only accepts traffic from ECS services
resource "aws_security_group" "db" {
  name_prefix = "${local.name}-db-"
  description = "RDS — allows port 5432 (PostgreSQL) from ECS services only"
  vpc_id      = aws_vpc.main.id

  # Inbound: PostgreSQL port from app containers only
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id] # Only ECS can reach the DB
  }

  # Outbound: allow all — RDS needs to reach AWS services (CloudWatch, S3 for backups)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-db" }
}

# Redis (ElastiCache): only accepts traffic from ECS services
resource "aws_security_group" "redis" {
  name_prefix = "${local.name}-redis-"
  description = "Redis — allows port 6379 from ECS services only"
  vpc_id      = aws_vpc.main.id

  # Inbound: Redis port from app containers only
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id] # Only ECS can reach Redis
  }

  # Outbound: allow all — ElastiCache needs outbound for replication and AWS internal APIs
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-redis" }
}

# SageMaker: only accepts traffic from ECS services
resource "aws_security_group" "sagemaker" {
  name_prefix = "${local.name}-sagemaker-"
  description = "SageMaker — allows HTTPS (443) from ECS services only"
  vpc_id      = aws_vpc.main.id

  # Inbound: HTTPS from app containers only
  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id] # Only ECS can reach SageMaker
  }

  # Outbound: allow all — SageMaker needs to reach S3, ECR, CloudWatch
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name}-sagemaker" }
}

# =============================================================================
# VPC ENDPOINT — private shortcut to S3 (skips internet, free)
# =============================================================================
# Without this, S3 traffic goes through NAT Gateway which costs money per GB.
# Gateway endpoint routes S3 traffic directly over AWS internal network.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"                        # S3 service in our region
  vpc_endpoint_type = "Gateway"                                               # Free, no hourly charge
  route_table_ids   = [aws_route_table.public.id, aws_route_table.private.id] # Both route tables use it

  tags = { Name = "${local.name}-s3" }
}
