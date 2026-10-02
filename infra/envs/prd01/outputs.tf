output "ec2_public_ip" {
  description = "EC2 공인 IP (http://<IP>:8000)"
  value       = module.ec2.public_ip
}

output "efs_id" {
  value = module.efs.file_system_id
}

output "vpc_id" {
  value = module.network.vpc_id
}
