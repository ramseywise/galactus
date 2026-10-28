# AWS deployment skeleton for the example lg_agent service.
#
# CHOICE: ECS Fargate + ALB, not AWS App Runner.
# App Runner would be meaningfully less code for a single-container HTTP service
# (it manages its own load balancing/scaling and needs no VPC/ALB/SG wiring), and
# is a reasonable alternative worth considering. We chose ECS Fargate + ALB instead
# because it's the more common "next step" people build on (multiple services
# behind one ALB, custom autoscaling policies, VPC-private networking, blue/green
# deploys via CodeDeploy) — i.e. it's a better skeleton to extend, even though it's
# more resources up front. If you don't need any of that, App Runner is a valid
# swap-in and would remove roughly the ALB + security group + target group blocks
# below in exchange for an `aws_apprunner_service` resource.
#
# SCOPE: deliberately minimal. Uses the account's default VPC/subnets instead of
# provisioning a VPC module, one Fargate service (no blue/green, no autoscaling
# policy beyond a fixed `desired_count`), and no HTTPS/custom domain (HTTP only on
# the ALB). See README.md for what you should add before using this for anything
# beyond a demo/starter deployment.

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name = "${var.project_name}-${var.environment}"

  # Secret ARN to reference in the task definition: either the one passed in, or
  # the one this stack creates below (see aws_secretsmanager_secret.anthropic_api_key).
  anthropic_secret_arn = var.anthropic_api_key_secret_arn != "" ? var.anthropic_api_key_secret_arn : aws_secretsmanager_secret.anthropic_api_key[0].arn

  common_tags = {
    Project         = var.project_name
    Environment     = var.environment
    DataSensitivity = var.data_sensitivity
    ManagedBy       = "terraform"
  }
}

# --- Networking: reuse the account's default VPC to keep this skeleton small. ---
# A real deployment would likely use a dedicated VPC (private subnets for the
# ECS tasks, public subnets only for the ALB) — swap this data source block for
# a VPC module/resources if/when you outgrow the default VPC.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# --- ECR repository for the lg_agent image ---
resource "aws_ecr_repository" "lg_agent" {
  name                 = local.name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

# --- Secrets Manager: ANTHROPIC_API_KEY ---
# Created empty when the caller doesn't supply an existing secret ARN — populate
# it out-of-band (console, CLI, or a separate secure pipeline), never via a
# Terraform variable/tfvars file.
resource "aws_secretsmanager_secret" "anthropic_api_key" {
  count       = var.anthropic_api_key_secret_arn == "" ? 1 : 0
  name        = "${local.name}-anthropic-api-key"
  description = "ANTHROPIC_API_KEY for ${local.name} lg_agent. Populate the secret value manually after apply."

  tags = local.common_tags
}

# --- CloudWatch log group for the ECS task ---
resource "aws_cloudwatch_log_group" "lg_agent" {
  name              = "/ecs/${local.name}"
  retention_in_days = 14

  tags = local.common_tags
}

# --- IAM: task execution role (pulls image, writes logs, reads the secret) ---
data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [local.anthropic_secret_arn]
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "${local.name}-read-anthropic-secret"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

# --- IAM: task role (the app's own runtime permissions) ---
# Empty by default — lg_agent doesn't call any AWS APIs at runtime today. Attach
# policies here as the app grows (e.g. S3 read for a corpus bucket).
resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
  tags               = local.common_tags
}

# --- Security groups ---
resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Allow inbound HTTP to the ALB"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP from anywhere (no HTTPS/custom domain in this skeleton, see README)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_security_group" "service" {
  name        = "${local.name}-service"
  description = "Allow inbound traffic from the ALB to the lg_agent container port"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "From ALB"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

# --- ALB ---
resource "aws_lb" "this" {
  name               = local.name
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids

  tags = local.common_tags
}

resource "aws_lb_target_group" "lg_agent" {
  name        = local.name
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip" # required for Fargate

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
    matcher             = "200"
  }

  tags = local.common_tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.lg_agent.arn
  }
}

# --- ECS cluster / task definition / service ---
resource "aws_ecs_cluster" "this" {
  name = local.name
  tags = local.common_tags
}

resource "aws_ecs_task_definition" "lg_agent" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  # container_image defaults to "" — plan/apply with a real image URI (see
  # variables.tf) once you've pushed one to the aws_ecr_repository above.
  container_definitions = jsonencode([
    {
      name      = "lg_agent"
      image     = var.container_image != "" ? var.container_image : "${aws_ecr_repository.lg_agent.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "LG_MODEL", value = var.lg_model },
        { name = "LG_PORT", value = tostring(var.container_port) },
        { name = "VECTORDB_PATH", value = var.vectordb_path },
        { name = "LG_CHECKPOINTER", value = var.lg_checkpointer },
      ]
      secrets = [
        { name = "ANTHROPIC_API_KEY", valueFrom = local.anthropic_secret_arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.lg_agent.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "lg-agent"
        }
      }
    }
  ])

  tags = local.common_tags
}

resource "aws_ecs_service" "lg_agent" {
  name            = local.name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.lg_agent.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = true # default VPC subnets here are public; see README
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.lg_agent.arn
    container_name   = "lg_agent"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]

  tags = local.common_tags
}
