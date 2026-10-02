variable "region" {
  type    = string
  default = "ap-northeast-2"
}
variable "name" {
  type    = string
  default = "prd02"
}
variable "vpc_cidr" {
  type    = string
  default = "10.2.0.0/16"
}
variable "azs" {
  type    = list(string)
  default = ["ap-northeast-2a", "ap-northeast-2c"]
}
variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.2.0.0/24", "10.2.1.0/24"]
}
variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.2.10.0/24", "10.2.11.0/24"]
}
variable "image_tag" {
  description = "배포할 컨테이너 이미지 태그"
  type        = string
  default     = "latest"
}

# 앱 환경변수/시크릿 (시크릿은 미리 SSM 파라미터로 등록 후 ARN 지정)
variable "kakao_redirect_uri" {
  type    = string
  default = "http://<ALB_DNS>/auth/kakao/callback"
}
variable "admin_username" {
  type    = string
  default = "admin"
}
variable "ssm_prefix" {
  description = "SSM 파라미터 경로 접두사"
  type        = string
  default     = "/guestbook/prd02"
}
