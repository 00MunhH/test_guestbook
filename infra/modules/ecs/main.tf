locals {
  use_efs = var.efs_file_system_id != ""

  container_env = [for k, v in var.environment : { name = k, value = v }]
  container_secrets = [for k, v in var.secrets : { name = k, valueFrom = v }]

  mount_points = local.use_efs ? [{
    sourceVolume  = "efs-data"
    containerPath = var.efs_container_path
    readOnly      = false
  }] : []

  container_def = merge(
    {
      name         = "web"
      image        = var.image
      essential    = true
      portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]
      environment  = local.container_env
      secrets      = local.container_secrets
      mountPoints  = local.mount_points
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "web"
        }
      }
    },
    length(var.command) > 0 ? { command = var.command } : {}
  )
}

resource "aws_ecs_cluster" "this" {
  name = "${var.name}-cluster"
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name}"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_ecs_task_definition" "this" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([local.container_def])

  dynamic "volume" {
    for_each = local.use_efs ? [1] : []
    content {
      name = "efs-data"
      efs_volume_configuration {
        file_system_id     = var.efs_file_system_id
        transit_encryption = "ENABLED"
        authorization_config {
          access_point_id = var.efs_access_point_id
          iam             = "ENABLED"
        }
      }
    }
  }
  tags = var.tags
}

resource "aws_ecs_service" "this" {
  name            = "${var.name}-svc"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = var.min_healthy_percent
  deployment_maximum_percent         = var.max_percent

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.app_sg_id]
    assign_public_ip = var.assign_public_ip
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "web"
    container_port   = var.container_port
  }
  tags = var.tags
}
