variable "region" {
  type    = string
  default = "ap-northeast-2"
}
variable "name" {
  type    = string
  default = "prd01"
}
variable "vpc_cidr" {
  type    = string
  default = "10.1.0.0/16"
}
variable "azs" {
  type    = list(string)
  default = ["ap-northeast-2a", "ap-northeast-2c"]
}
variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.1.0.0/24", "10.1.1.0/24"]
}
variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.1.10.0/24", "10.1.11.0/24"]
}
variable "instance_type" {
  type    = string
  default = "t3.small"
}
variable "key_name" {
  description = "SSH 키페어 이름 (선택)"
  type        = string
  default     = ""
}
variable "ssh_ingress_cidrs" {
  description = "SSH 허용 CIDR (본인 IP 권장)"
  type        = list(string)
  default     = []
}
variable "app_ingress_cidrs" {
  description = "앱 포트(8000) 직접 접근 허용 CIDR"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
