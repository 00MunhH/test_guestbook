# prd03 = app03 아키텍처: ECS Fargate(N 태스크) + RDS + ElastiCache(Redis) + S3 + ALB

data "aws_caller_identity" "current" {}

module "network" {
  source               = "../../modules/network"
  name                 = var.name
  vpc_cidr             = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = true
}

module "security" {
  source          = "../../modules/security"
  name            = var.name
  vpc_id          = module.network.vpc_id
  app_port        = 8000
  create_alb_sg   = true
  create_rds_sg   = true
  create_redis_sg = true
}

module "ecr" {
  source = "../../modules/ecr"
  name   = "guestbook-${var.name}"
}

module "s3" {
  source      = "../../modules/s3"
  name        = var.name
  bucket_name = var.s3_bucket_name
}

module "rds" {
  source            = "../../modules/rds"
  name              = var.name
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.security.rds_sg_id
  username          = var.db_username
  password          = var.db_password
}

module "redis" {
  source            = "../../modules/redis"
  name              = var.name
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.security.redis_sg_id
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

# 태스크 역할에 S3 버킷 접근 권한
data "aws_iam_policy_document" "s3_access" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${module.s3.bucket_arn}/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [module.s3.bucket_arn]
  }
}

resource "aws_iam_policy" "s3_access" {
  name   = "${var.name}-s3-access"
  policy = data.aws_iam_policy_document.s3_access.json
}

# DATABASE_URL은 RDS 생성 결과로 자동 결정되므로 Terraform이 SSM에 등록한다.
# (나머지 비밀 KAKAO_*/SESSION_SECRET_KEY/ADMIN_PASSWORD는 배포 전 수동 등록)
resource "aws_ssm_parameter" "database_url" {
  name        = "${var.ssm_prefix}/DATABASE_URL"
  type        = "SecureString"
  value       = module.rds.database_url
  overwrite   = true
  description = "RDS Postgres SQLAlchemy URL (auto-generated)"
}

locals {
  environment = {
    REDIS_URL          = module.redis.redis_url
    S3_BUCKET          = module.s3.bucket_name
    AWS_REGION         = var.region
    KAKAO_REDIRECT_URI = var.kakao_redirect_uri
    ADMIN_USERNAME     = var.admin_username
  }
  secret_arn_prefix = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_prefix}"
  secrets = {
    DATABASE_URL        = "${local.secret_arn_prefix}/DATABASE_URL"
    KAKAO_REST_API_KEY  = "${local.secret_arn_prefix}/KAKAO_REST_API_KEY"
    KAKAO_CLIENT_SECRET = "${local.secret_arn_prefix}/KAKAO_CLIENT_SECRET"
    SESSION_SECRET_KEY  = "${local.secret_arn_prefix}/SESSION_SECRET_KEY"
    ADMIN_PASSWORD      = "${local.secret_arn_prefix}/ADMIN_PASSWORD"
  }
}

module "ecs" {
  source                = "../../modules/ecs"
  name                  = var.name
  region                = var.region
  vpc_id                = module.network.vpc_id
  subnet_ids            = module.network.private_subnet_ids
  assign_public_ip      = false
  app_sg_id             = module.security.app_sg_id
  image                 = "${module.ecr.repository_url}:${var.image_tag}"
  container_port        = 8000
  desired_count         = var.desired_count
  target_group_arn      = module.alb.target_group_arn
  environment           = local.environment
  secrets               = local.secrets
  task_role_policy_arns = [aws_iam_policy.s3_access.arn]

  # 수평 확장 롤링 배포
  min_healthy_percent = 100
  max_percent         = 200
}
