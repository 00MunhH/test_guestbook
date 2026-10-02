variable "region" {
  type    = string
  default = "ap-northeast-2"
}
variable "name" {
  type    = string
  default = "prd03"
}
variable "vpc_cidr" {
  type    = string
  default = "10.3.0.0/16"
}
variable "azs" {
  type    = list(string)
  default = ["ap-northeast-2a", "ap-northeast-2c"]
}
variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.3.0.0/24", "10.3.1.0/24"]
}
variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.3.10.0/24", "10.3.11.0/24"]
}
variable "image_tag" {
  type    = string
  default = "latest"
}
variable "desired_count" {
  type    = number
  default = 2
}
variable "db_username" {
  type    = string
  default = "guestbook"
}
variable "db_password" {
  description = "RDS 마스터 비밀번호 (tfvars/환경변수로 주입, 커밋 금지)"
  type        = string
  sensitive   = true
}
variable "s3_bucket_name" {
  description = "업로드 버킷 이름 (전역 유일)"
  type        = string
}
variable "kakao_redirect_uri" {
  type    = string
  default = "http://<ALB_DNS>/auth/kakao/callback"
}
variable "admin_username" {
  type    = string
  default = "admin"
}
variable "ssm_prefix" {
  type    = string
  default = "/guestbook/prd03"
}
