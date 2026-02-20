output "vpc_id"             { value = aws_vpc.main.id }
output "public_subnet_ids"  { value = [aws_subnet.public_a.id, aws_subnet.public_b.id] }
output "private_subnet_ids" { value = [aws_subnet.private_a.id, aws_subnet.private_b.id] }
output "alb_sg_id"          { value = aws_security_group.alb.id }
output "app_sg_id"          { value = aws_security_group.app.id }
output "db_sg_id"           { value = aws_security_group.db.id }
