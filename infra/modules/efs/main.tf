resource "aws_efs_file_system" "this" {
  creation_token = "${var.name}-efs"
  encrypted      = true
  tags           = merge(var.tags, { Name = "${var.name}-efs" })
}

resource "aws_efs_mount_target" "this" {
  count           = length(var.subnet_ids)
  file_system_id  = aws_efs_file_system.this.id
  subnet_id       = var.subnet_ids[count.index]
  security_groups = [var.security_group_id]
}

resource "aws_efs_access_point" "this" {
  file_system_id = aws_efs_file_system.this.id
  posix_user {
    uid = var.posix_uid
    gid = var.posix_gid
  }
  root_directory {
    path = var.access_point_path
    creation_info {
      owner_uid   = var.posix_uid
      owner_gid   = var.posix_gid
      permissions = "0755"
    }
  }
  tags = merge(var.tags, { Name = "${var.name}-efs-ap" })
}
