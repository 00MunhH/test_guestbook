variable "name" {
  description = "리소스 이름 접두사 (예: prd01)"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "사용할 가용영역 목록"
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "퍼블릭 서브넷 CIDR 목록 (azs와 길이 일치)"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "프라이빗 서브넷 CIDR 목록 (azs와 길이 일치)"
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "프라이빗 서브넷용 NAT 게이트웨이 생성 여부"
  type        = bool
  default     = false
}

variable "tags" {
  description = "공통 태그"
  type        = map(string)
  default     = {}
}
