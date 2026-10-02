variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "app_port" {
  description = "애플리케이션 컨테이너/인스턴스 포트"
  type        = number
  default     = 8000
}

variable "create_alb_sg" {
  description = "ALB용 SG 생성 여부"
  type        = bool
  default     = false
}

variable "app_ingress_cidrs" {
  description = "app_port로 직접 접근 허용할 CIDR (EC2 직접 노출용). ALB를 쓰면 보통 []"
  type        = list(string)
  default     = []
}

variable "ssh_ingress_cidrs" {
  description = "SSH(22) 허용 CIDR (EC2 전용)"
  type        = list(string)
  default     = []
}

variable "create_efs_sg" {
  description = "EFS용 SG 생성 여부"
  type        = bool
  default     = false
}

variable "create_rds_sg" {
  description = "RDS용 SG 생성 여부"
  type        = bool
  default     = false
}

variable "create_redis_sg" {
  description = "Redis용 SG 생성 여부"
  type        = bool
  default     = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
