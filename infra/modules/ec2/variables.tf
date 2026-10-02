variable "name" { type = string }
variable "subnet_id" { type = string }
variable "security_group_id" { type = string }
variable "instance_type" {
  type    = string
  default = "t3.small"
}
variable "ami_id" {
  description = "비우면 최신 Amazon Linux 2023 AMI 자동 조회"
  type        = string
  default     = ""
}
variable "key_name" {
  description = "SSH 키페어 이름 (선택)"
  type        = string
  default     = ""
}
variable "user_data" {
  description = "부팅 스크립트"
  type        = string
  default     = ""
}
variable "iam_instance_profile" {
  type    = string
  default = ""
}
variable "associate_eip" {
  type    = bool
  default = true
}
variable "tags" {
  type    = map(string)
  default = {}
}
