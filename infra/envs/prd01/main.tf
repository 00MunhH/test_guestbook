# prd01 = app01 아키텍처: EC2 + Docker + EFS (단일, 수동 서비스 배포)

module "network" {
  source               = "../../modules/network"
  name                 = var.name
  vpc_cidr             = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = false # EC2는 퍼블릭 서브넷에 두므로 NAT 불필요
}

module "security" {
  source            = "../../modules/security"
  name              = var.name
  vpc_id            = module.network.vpc_id
  app_port          = 8000
  create_alb_sg     = false
  app_ingress_cidrs = var.app_ingress_cidrs
  ssh_ingress_cidrs = var.ssh_ingress_cidrs
  create_efs_sg     = true
}

module "efs" {
  source            = "../../modules/efs"
  name              = var.name
  subnet_ids        = module.network.public_subnet_ids
  security_group_id = module.security.efs_sg_id
  access_point_path = "/data"
}

# EC2 부팅 시 Docker/EFS 유틸 설치 + EFS 마운트 (서비스 코드 배포는 README 참고하여 수동)
locals {
  user_data = <<-EOT
    #!/bin/bash
    set -e
    dnf update -y
    dnf install -y docker git amazon-efs-utils
    systemctl enable --now docker
    usermod -aG docker ec2-user
    mkdir -p /usr/libexec/docker/cli-plugins
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
      -o /usr/libexec/docker/cli-plugins/docker-compose
    chmod +x /usr/libexec/docker/cli-plugins/docker-compose
    # buildx 플러그인 (compose build에 필요: 0.17+)
    curl -SL https://github.com/docker/buildx/releases/latest/download/buildx-v0.19.3.linux-amd64 \
      -o /usr/libexec/docker/cli-plugins/docker-buildx
    chmod +x /usr/libexec/docker/cli-plugins/docker-buildx
    mkdir -p /mnt/efs
    mount -t efs -o tls ${module.efs.file_system_id}:/ /mnt/efs
    mkdir -p /mnt/efs/guestbook/uploads
    echo '${module.efs.file_system_id}:/ /mnt/efs efs _netdev,tls 0 0' >> /etc/fstab
  EOT
}

module "ec2" {
  source            = "../../modules/ec2"
  name              = var.name
  subnet_id         = module.network.public_subnet_ids[0]
  security_group_id = module.security.app_sg_id
  instance_type     = var.instance_type
  key_name          = var.key_name
  user_data         = local.user_data
  associate_eip     = true
}
