output "instance_id" {
  description = "EC2 instance ID — use with aws ssm start-session --target <this>"
  value       = aws_instance.bastion.id
}
