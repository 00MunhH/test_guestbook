terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # backend "s3" { ... prd02 ... }  # 필요 시 원격 상태 설정
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project = "guestbook"
      Env     = "prd02"
    }
  }
}
