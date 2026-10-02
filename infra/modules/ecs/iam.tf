data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# 실행 역할 (이미지 pull, 로그, 시크릿 주입)
resource "aws_iam_role" "execution" {
  name               = "${var.name}-ecs-exec-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# 시크릿(SSM) 읽기 권한 (secrets 사용 시)
data "aws_iam_policy_document" "exec_secrets" {
  count = length(var.secrets) > 0 ? 1 : 0
  statement {
    actions   = ["ssm:GetParameters", "ssm:GetParameter"]
    resources = values(var.secrets)
  }
}

resource "aws_iam_role_policy" "exec_secrets" {
  count  = length(var.secrets) > 0 ? 1 : 0
  name   = "${var.name}-exec-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.exec_secrets[0].json
}

# 태스크 역할 (앱이 S3 등 접근)
resource "aws_iam_role" "task" {
  name               = "${var.name}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "task_extra" {
  count      = length(var.task_role_policy_arns)
  role       = aws_iam_role.task.name
  policy_arn = var.task_role_policy_arns[count.index]
}
