# Aegis Intelligence — Terraform scaffold for the managed Qdrant/RDS/
# compute resources described in docs/architecture.md §4.
#
# Phase 9 (PROJECT_HANDBOOK.md §6). This is a SCAFFOLD, not a fully
# hardened production IaC setup — never `terraform apply`d against a real
# AWS account this phase (no AWS credentials in this session, by design;
# see docs/DECISIONS_LOG.md). Every deliberate simplification is called
# out inline rather than silently baked in — see variables.tf's own header
# comment for the networking one (default VPC, public subnets) that
# applies throughout this file.
#
# What this provisions: RDS Postgres, ElastiCache Redis, two ECR
# repositories, an ECS (Fargate) cluster running the api service (behind
# an ALB) and the ingestion-worker service (no public endpoint — it only
# consumes from the Redis broker). Qdrant itself is NOT provisioned here —
# see variables.tf's qdrant_cloud_url/qdrant_cloud_api_key comment for why
# (no official Terraform provider for Qdrant Cloud) — its endpoint/key are
# only *consumed* below, passed through to both ECS task definitions.

terraform {
  required_version = ">= 1.7"

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
  name_prefix = "${var.project_name}-${var.environment}"
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ---------------------------------------------------------------------------
# Networking — default VPC/subnets. See variables.tf's header comment for
# why this scaffold doesn't provision a dedicated VPC.
# ---------------------------------------------------------------------------

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ---------------------------------------------------------------------------
# Security groups
# ---------------------------------------------------------------------------

resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb"
  description = "Ingress from the internet to the api load balancer."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  dynamic "ingress" {
    # Only opened when a real ACM cert is supplied (var.alb_certificate_arn)
    # — matches the HTTPS-listener condition below.
    for_each = var.alb_certificate_arn != "" ? [443] : []
    content {
      description = "HTTPS"
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "ecs_tasks" {
  name        = "${local.name_prefix}-ecs-tasks"
  description = "Both ECS services (api, ingestion-worker) — api's inbound container port only accepts traffic from the ALB, not the open internet."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "api container port, ALB only"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds"
  description = "Postgres, reachable only from the ECS tasks security group."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Postgres from ECS tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis"
  description = "Redis, reachable only from the ECS tasks security group."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Redis from ECS tasks"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Postgres (RDS) — replaces docker-compose.yml's local `postgres` container
# ---------------------------------------------------------------------------

resource "aws_db_subnet_group" "aegis" {
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = data.aws_subnets.default.ids
  tags       = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier     = "${local.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  max_allocated_storage = var.db_allocated_storage * 2 # cheap autoscaling headroom, not a hard cap

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.aegis.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  # SIMPLIFICATION, flagged: skip_final_snapshot=true and a short backup
  # window are appropriate for a portfolio-scale staging environment, not
  # for a real prod database holding real customer data — a genuine prod
  # deployment of this stack should flip both.
  skip_final_snapshot     = true
  backup_retention_period = 1
  deletion_protection     = false

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Redis (ElastiCache) — replaces docker-compose.yml's local `redis`
# container (Celery broker/backend)
# ---------------------------------------------------------------------------

resource "aws_elasticache_subnet_group" "aegis" {
  name       = "${local.name_prefix}-redis-subnets"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${local.name_prefix}-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.aegis.name
  security_group_ids   = [aws_security_group.redis.id]
  parameter_group_name = "default.redis7"

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Container registry — one repo per service, matching the two Dockerfiles
# (services/api/Dockerfile, services/ingestion/Dockerfile)
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "api" {
  name                 = "${var.project_name}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

resource "aws_ecr_repository" "ingestion" {
  name                 = "${var.project_name}-ingestion"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Secrets — SSM Parameter Store SecureStrings, referenced by the ECS task
# definitions' `secrets` block below rather than plaintext `environment`
# entries. Plaintext env vars on a Fargate task definition are visible to
# anyone with read access to the task definition in the AWS console/API;
# SecureString params are KMS-encrypted at rest and only resolved into the
# container's actual environment at task-start time.
# ---------------------------------------------------------------------------

resource "aws_ssm_parameter" "db_password" {
  name  = "/${local.name_prefix}/db-password"
  type  = "SecureString"
  value = var.db_password
  tags  = local.tags
}

resource "aws_ssm_parameter" "qdrant_cloud_api_key" {
  name  = "/${local.name_prefix}/qdrant-cloud-api-key"
  type  = "SecureString"
  value = var.qdrant_cloud_api_key
  tags  = local.tags
}

resource "aws_ssm_parameter" "cohere_api_key" {
  name  = "/${local.name_prefix}/cohere-api-key"
  type  = "SecureString"
  value = var.cohere_api_key
  tags  = local.tags
}

resource "aws_ssm_parameter" "openai_api_key" {
  name  = "/${local.name_prefix}/openai-api-key"
  type  = "SecureString"
  value = var.openai_api_key
  tags  = local.tags
}

# ---------------------------------------------------------------------------
# ECS cluster + IAM
# ---------------------------------------------------------------------------

resource "aws_ecs_cluster" "aegis" {
  name = local.name_prefix
  tags = local.tags
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.name_prefix}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# The default execution-role policy above covers pulling from ECR and
# writing to CloudWatch Logs, but NOT reading the SSM SecureString params
# above — that needs its own explicit grant.
resource "aws_iam_role_policy" "ecs_read_ssm_secrets" {
  name = "${local.name_prefix}-read-ssm-secrets"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["ssm:GetParameters"]
      Resource = [
        aws_ssm_parameter.db_password.arn,
        aws_ssm_parameter.qdrant_cloud_api_key.arn,
        aws_ssm_parameter.cohere_api_key.arn,
        aws_ssm_parameter.openai_api_key.arn,
      ]
    }]
  })
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name_prefix}-api"
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/ecs/${local.name_prefix}-ingestion"
  retention_in_days = 14
  tags              = local.tags
}

# ---------------------------------------------------------------------------
# api service — Fargate task behind an ALB
# ---------------------------------------------------------------------------

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:${var.container_image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "DATABASE_URL", value = "postgresql+psycopg2://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${var.db_name}" },
      { name = "QDRANT_URL", value = var.qdrant_cloud_url },
      { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0" },
    ]
    secrets = [
      { name = "QDRANT_API_KEY", valueFrom = aws_ssm_parameter.qdrant_cloud_api_key.arn },
      { name = "COHERE_API_KEY", valueFrom = aws_ssm_parameter.cohere_api_key.arn },
      { name = "OPENAI_API_KEY", valueFrom = aws_ssm_parameter.openai_api_key.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])

  tags = local.tags
}

resource "aws_lb" "api" {
  name               = "${local.name_prefix}-api"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids

  tags = local.tags
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name_prefix}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  # Hits the same real readiness probe services/api/Dockerfile's own
  # HEALTHCHECK does (src/api/v1/routes/health.py's GET /health/ready) —
  # one definition of "healthy" for this service, not two.
  health_check {
    path                = "/health/ready"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200"
  }

  tags = local.tags
}

resource "aws_lb_listener" "api_http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  # When a real ACM cert is supplied, the port-80 listener redirects to
  # HTTPS instead of forwarding directly — see the conditional HTTPS
  # listener below. Without one, this scaffold serves plain HTTP so it's
  # still usable for a first deploy/smoke test.
  dynamic "default_action" {
    for_each = var.alb_certificate_arn != "" ? [1] : []
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  dynamic "default_action" {
    for_each = var.alb_certificate_arn == "" ? [1] : []
    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.api.arn
    }
  }
}

resource "aws_lb_listener" "api_https" {
  count = var.alb_certificate_arn != "" ? 1 : 0

  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.alb_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = aws_ecs_cluster.aegis.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets = data.aws_subnets.default.ids
    # SIMPLIFICATION, flagged (see variables.tf header comment): true only
    # because these are default-VPC public subnets with no NAT gateway
    # scaffolded for a private-subnet alternative. A real production setup
    # runs ECS tasks in private subnets with NAT egress instead.
    assign_public_ip = true
    security_groups  = [aws_security_group.ecs_tasks.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.api_http]
  tags       = local.tags
}

# ---------------------------------------------------------------------------
# ingestion-worker service — Fargate task, no load balancer (a Celery
# worker has nothing to accept inbound HTTP traffic for; docs/architecture.md
# §4's "API and ingestion scale independently" is enforced here by giving
# each its own ECS service with its own desired_count, not by any shared
# scaling trigger)
# ---------------------------------------------------------------------------

resource "aws_ecs_task_definition" "ingestion" {
  family                   = "${local.name_prefix}-ingestion"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ingestion_cpu
  memory                   = var.ingestion_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = "ingestion-worker"
    image     = "${aws_ecr_repository.ingestion.repository_url}:${var.container_image_tag}"
    essential = true
    environment = [
      { name = "DATABASE_URL", value = "postgresql+psycopg2://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${var.db_name}" },
      { name = "QDRANT_URL", value = var.qdrant_cloud_url },
      { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0" },
    ]
    secrets = [
      { name = "QDRANT_API_KEY", valueFrom = aws_ssm_parameter.qdrant_cloud_api_key.arn },
      { name = "COHERE_API_KEY", valueFrom = aws_ssm_parameter.cohere_api_key.arn },
      { name = "OPENAI_API_KEY", valueFrom = aws_ssm_parameter.openai_api_key.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ingestion.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ingestion"
      }
    }
  }])

  tags = local.tags
}

resource "aws_ecs_service" "ingestion" {
  name            = "${local.name_prefix}-ingestion"
  cluster         = aws_ecs_cluster.aegis.id
  task_definition = aws_ecs_task_definition.ingestion.arn
  desired_count   = var.ingestion_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    assign_public_ip = true # same simplification as aws_ecs_service.api above
    security_groups  = [aws_security_group.ecs_tasks.id]
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "alb_dns_name" {
  description = "Public DNS name of the api load balancer — point the frontend's API base URL / a real DNS CNAME at this."
  value       = aws_lb.api.dns_name
}

output "ecr_api_repository_url" {
  description = "Push services/api's image here — the target for .github/workflows/cd-staging.yml's `docker push`."
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_ingestion_repository_url" {
  description = "Push services/ingestion's image here."
  value       = aws_ecr_repository.ingestion.repository_url
}

output "rds_endpoint" {
  description = "Postgres endpoint (host:port)."
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis endpoint (host)."
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
  sensitive   = true
}

output "ecs_cluster_name" {
  description = "ECS cluster name — used by .github/workflows/cd-staging.yml's `aws ecs update-service` step."
  value       = aws_ecs_cluster.aegis.name
}
