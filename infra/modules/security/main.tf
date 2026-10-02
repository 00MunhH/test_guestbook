# 환경별로 필요한 보안그룹을 플래그로 생성.
# app SG는 항상 생성. ALB SG가 있으면 app은 ALB로부터만 app_port 허용.
locals {
  tags = merge(var.tags, { Env = var.name })
}

# ----- ALB SG (선택) -----
resource "aws_security_group" "alb" {
  count       = var.create_alb_sg ? 1 : 0
  name        = "${var.name}-alb-sg"
  description = "ALB ingress 80/443"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${var.name}-alb-sg" })

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ----- App SG (항상 생성: EC2 또는 ECS 태스크) -----
resource "aws_security_group" "app" {
  name        = "${var.name}-app-sg"
  description = "App instance/task"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${var.name}-app-sg" })

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ALB → app (ALB SG가 있을 때)
resource "aws_security_group_rule" "app_from_alb" {
  count                    = var.create_alb_sg ? 1 : 0
  type                     = "ingress"
  from_port                = var.app_port
  to_port                  = var.app_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.alb[0].id
  description              = "App port from ALB"
}

# 직접 노출(EC2) — app_ingress_cidrs
resource "aws_security_group_rule" "app_from_cidr" {
  count             = length(var.app_ingress_cidrs) > 0 ? 1 : 0
  type              = "ingress"
  from_port         = var.app_port
  to_port           = var.app_port
  protocol          = "tcp"
  security_group_id = aws_security_group.app.id
  cidr_blocks       = var.app_ingress_cidrs
  description       = "App port direct"
}

# SSH (EC2)
resource "aws_security_group_rule" "app_ssh" {
  count             = length(var.ssh_ingress_cidrs) > 0 ? 1 : 0
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  security_group_id = aws_security_group.app.id
  cidr_blocks       = var.ssh_ingress_cidrs
  description       = "SSH"
}

# ----- EFS SG (선택): app SG → 2049 -----
resource "aws_security_group" "efs" {
  count       = var.create_efs_sg ? 1 : 0
  name        = "${var.name}-efs-sg"
  description = "EFS NFS from app"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${var.name}-efs-sg" })

  ingress {
    description     = "NFS from app"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ----- RDS SG (선택): app SG → 5432 -----
resource "aws_security_group" "rds" {
  count       = var.create_rds_sg ? 1 : 0
  name        = "${var.name}-rds-sg"
  description = "RDS Postgres from app"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${var.name}-rds-sg" })

  ingress {
    description     = "Postgres from app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ----- Redis SG (선택): app SG → 6379 -----
resource "aws_security_group" "redis" {
  count       = var.create_redis_sg ? 1 : 0
  name        = "${var.name}-redis-sg"
  description = "Redis from app"
  vpc_id      = var.vpc_id
  tags        = merge(local.tags, { Name = "${var.name}-redis-sg" })

  ingress {
    description     = "Redis from app"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
