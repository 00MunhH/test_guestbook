output "app_sg_id" {
  value = aws_security_group.app.id
}

output "alb_sg_id" {
  value = try(aws_security_group.alb[0].id, null)
}

output "efs_sg_id" {
  value = try(aws_security_group.efs[0].id, null)
}

output "rds_sg_id" {
  value = try(aws_security_group.rds[0].id, null)
}

output "redis_sg_id" {
  value = try(aws_security_group.redis[0].id, null)
}
