variable "name" { type = string }
variable "region" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" {
  description = "태스크를 배치할 서브넷 (프라이빗 권장)"
  type        = list(string)
}
variable "assign_public_ip" {
  type    = bool
  default = true
}
variable "app_sg_id" { type = string }
variable "image" {
  description = "컨테이너 이미지 URI (ECR:tag)"
  type        = string
}
variable "container_port" {
  type    = number
  default = 8000
}
variable "desired_count" {
  type    = number
  default = 1
}
variable "cpu" {
  type    = string
  default = "512"
}
variable "memory" {
  type    = string
  default = "1024"
}
variable "target_group_arn" { type = string }

variable "environment" {
  description = "컨테이너 환경변수 (비밀 아님)"
  type        = map(string)
  default     = {}
}
variable "secrets" {
  description = "SSM 파라미터에서 주입할 시크릿 (name => parameter ARN)"
  type        = map(string)
  default     = {}
}

# EFS 마운트 (옵션)
variable "efs_file_system_id" {
  type    = string
  default = ""
}
variable "efs_access_point_id" {
  type    = string
  default = ""
}
variable "efs_container_path" {
  type    = string
  default = "/data"
}

# Task Role에 부여할 추가 정책 ARN (S3 등)
variable "task_role_policy_arns" {
  type    = list(string)
  default = []
}

# 컨테이너 시작 커맨드 오버라이드 (옵션)
variable "command" {
  type    = list(string)
  default = []
}

variable "min_healthy_percent" {
  type    = number
  default = 100
}
variable "max_percent" {
  type    = number
  default = 200
}

variable "tags" {
  type    = map(string)
  default = {}
}
