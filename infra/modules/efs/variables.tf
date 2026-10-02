variable "name" { type = string }
variable "subnet_ids" {
  description = "마운트 타깃을 생성할 서브넷"
  type        = list(string)
}
variable "security_group_id" {
  description = "EFS 마운트 타깃에 적용할 SG"
  type        = string
}
variable "access_point_path" {
  description = "액세스 포인트 루트 디렉터리"
  type        = string
  default     = "/data"
}
variable "posix_uid" {
  type    = number
  default = 1000
}
variable "posix_gid" {
  type    = number
  default = 1000
}
variable "tags" {
  type    = map(string)
  default = {}
}
