# prd02 = app02 아키텍처: ECS Fargate(단일 태스크) + EFS + ALB

data "aws_caller_identity" "current" {}

module "network" {
  source               = "../../modules/network"
  name                 = var.name
  vpc_cidr             = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = true # 프라이빗 서브넷의 ECS가 ECR/SSM/인터넷 접근
}

module "security" {
  source        = "../../modules/security"
  name          = var.name
  vpc_id        = module.network.vpc_id
  app_port      = 8000
  create_alb_sg = true
  create_efs_sg = true
}

module "ecr" {
  source = "../../modules/ecr"
  name   = "guestbook-${var.name}"
}

module "efs" {
  source            = "../../modules/efs"
  name              = var.name
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.security.efs_sg_id
  access_point_path = "/data"
}

module "alb" {
  source            = "../../modules/alb"
  name              = var.name
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  alb_sg_id         = module.security.alb_sg_id
  target_port       = 8000
  target_type       = "ip"
  health_check_path = "/"
}

locals {
  # 환경변수(EFS 경로). DB/업로드는 EFS 마운트 지점(/data)에.
  environment = {
    DATABASE_URL       = "sqlite:////data/guestbook.db"
    UPLOAD_DIR         = "/data/uploads"
    KAKAO_REDIRECT_URI = var.kakao_redirect_uri
    ADMIN_USERNAME     = var.admin_username
  }
  # 시크릿: SSM 파라미터 ARN (사전 등록 필요)
  secret_arn_prefix = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_prefix}"
  secrets = {
    KAKAO_REST_API_KEY  = "${local.secret_arn_prefix}/KAKAO_REST_API_KEY"
    KAKAO_CLIENT_SECRET = "${local.secret_arn_prefix}/KAKAO_CLIENT_SECRET"
    SESSION_SECRET_KEY  = "${local.secret_arn_prefix}/SESSION_SECRET_KEY"
    ADMIN_PASSWORD      = "${local.secret_arn_prefix}/ADMIN_PASSWORD"
  }
}

module "ecs" {
  source           = "../../modules/ecs"
  name             = var.name
  region           = var.region
  vpc_id           = module.network.vpc_id
  subnet_ids       = module.network.private_subnet_ids
  assign_public_ip = false
  app_sg_id        = module.security.app_sg_id
  image            = "${module.ecr.repository_url}:${var.image_tag}"
  container_port   = 8000
  desired_count    = 1
  target_group_arn = module.alb.target_group_arn
  environment      = local.environment
  secrets          = local.secrets

  # EFS 마운트
  efs_file_system_id  = module.efs.file_system_id
  efs_access_point_id = module.efs.access_point_id
  efs_container_path  = "/data"

  # 단일 태스크 유지 (롤링 중 중복 금지)
  min_healthy_percent = 0
  max_percent         = 100
}
