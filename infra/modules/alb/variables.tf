variable "name" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "alb_sg_id" { type = string }
variable "target_port" {
  type    = number
  default = 8000
}
variable "health_check_path" {
  type    = string
  default = "/"
}
variable "target_type" {
  description = "ip (Fargate) 또는 instance (EC2)"
  type        = string
  default     = "ip"
}
variable "tags" {
  type    = map(string)
  default = {}
}
