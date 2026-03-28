# =============================================================================
# SSM BASTION — tiny EC2 relay for RDS access via port forwarding
# =============================================================================
# No public IP, no inbound ports, no SSH keys. Access is via SSM Session
# Manager only, authenticated through IAM. Used for:
#   - pgAdmin/DBeaver connections to RDS (via port forwarding)
#   - Running one-off SQL migrations
#   - Database inspection and debugging
#
# Cost: ~$3-4/month for t4g.nano (can be stopped when not in use).
#
# Usage:
#   aws ssm start-session \
#     --target <instance-id> \
#     --document-name AWS-StartPortForwardingSessionToRemoteHost \
#     --parameters '{"host":["<rds-endpoint>"],"portNumber":["5432"],"localPortNumber":["5432"]}'

locals {
  name = "${var.project}-${var.environment}-bastion"
}

# Latest Amazon Linux 2023 AMI (SSM Agent pre-installed)
data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

# IAM role for the EC2 instance — allows SSM Session Manager
resource "aws_iam_role" "bastion" {
  name = local.name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = { Name = local.name }
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.bastion.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "bastion" {
  name = local.name
  role = aws_iam_role.bastion.name
}

# The EC2 instance — t4g.nano, no public IP, private subnet
resource "aws_instance" "bastion" {
  ami                    = data.aws_ssm_parameter.ami.value
  instance_type          = "t4g.nano"
  subnet_id              = var.private_subnet_id
  vpc_security_group_ids = [var.app_sg_id]
  iam_instance_profile   = aws_iam_instance_profile.bastion.name

  # No public IP — access only via SSM
  associate_public_ip_address = false

  # Minimal root volume
  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }

  tags = { Name = local.name }
}
