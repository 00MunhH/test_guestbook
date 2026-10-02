terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # 원격 상태를 쓰려면 아래 주석을 해제하고 버킷/락 테이블을 지정하세요.
  # backend "s3" {
  #   bucket         = "<TFSTATE_BUCKET>"
  #   key            = "guestbook/prd01/terraform.tfstate"
  #   region         = "ap-northeast-2"
  #   dynamodb_table = "<TFLOCK_TABLE>"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project = "guestbook"
      Env     = "prd01"
    }
  }
}
