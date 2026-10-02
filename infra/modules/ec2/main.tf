data "aws_ami" "al2023" {
  count       = var.ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

locals {
  ami = var.ami_id != "" ? var.ami_id : data.aws_ami.al2023[0].id
}

resource "aws_instance" "this" {
  ami                    = local.ami
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  key_name               = var.key_name != "" ? var.key_name : null
  iam_instance_profile   = var.iam_instance_profile != "" ? var.iam_instance_profile : null
  user_data              = var.user_data != "" ? var.user_data : null

  metadata_options {
    http_tokens = "required" # IMDSv2 강제
  }
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }
  tags = merge(var.tags, { Name = "${var.name}-ec2" })
}

resource "aws_eip" "this" {
  count    = var.associate_eip ? 1 : 0
  instance = aws_instance.this.id
  domain   = "vpc"
  tags     = merge(var.tags, { Name = "${var.name}-eip" })
}
