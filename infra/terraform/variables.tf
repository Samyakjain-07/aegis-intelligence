# Aegis Intelligence — Terraform variables
#
# Phase 9 (PROJECT_HANDBOOK.md §6): a SCAFFOLD for the managed Qdrant/RDS/
# compute resources docs/architecture.md §4 describes, not a fully
# hardened production IaC setup. Simplifications are called out inline
# where they matter, per CLAUDE.md §4/§5's "flag it explicitly rather
# than silently pick a side" standard.

variable "aws_region" {
  description = "AWS region every resource in this stack is created in."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used as a prefix for every resource (ECR repos, ECS cluster, RDS instance, etc.)."
  type        = string
  default     = "aegis-intelligence"
}

variable "environment" {
  description = "Deployment environment name (\"staging\" or \"prod\") — appended to resource names/tags so both can eventually coexist in the same AWS account."
  type        = string
  default     = "staging"
}

# --- Networking -----------------------------------------------------------
#
# SIMPLIFICATION, flagged explicitly: this scaffold deploys into the AWS
# account's DEFAULT VPC and its default (public) subnets — main.tf's
# `data "aws_vpc" "default"` / `data "aws_subnets" "default"` — rather than
# provisioning a dedicated VPC with private subnets for RDS/ElastiCache and
# NAT-routed egress for ECS tasks. A real production deployment should put
# the database and cache in private subnets with no public IP and route
# ECS task egress through a NAT gateway; that's a real, known gap being
# traded for scaffold simplicity at portfolio scale, not an oversight. See
# docs/DECISIONS_LOG.md's entry for this file.

# --- Postgres (RDS) --------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class for the managed Postgres database."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage, in GB."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Postgres database name — matches DATABASE_URL's own /aegis convention (.env.example, docker-compose.yml)."
  type        = string
  default     = "aegis"
}

variable "db_username" {
  description = "Postgres master username."
  type        = string
  default     = "aegis_app"
}

variable "db_password" {
  description = "Postgres master password. No default on purpose — must be supplied via a *.tfvars file that is gitignored, or TF_VAR_db_password, never committed."
  type        = string
  sensitive   = true
}

# --- Redis (ElastiCache) ---------------------------------------------------

variable "redis_node_type" {
  description = "ElastiCache node type for the managed Redis broker/backend."
  type        = string
  default     = "cache.t4g.micro"
}

# --- Qdrant Cloud -----------------------------------------------------------
#
# Qdrant Cloud has no official Terraform provider as of this writing, so
# (unlike Postgres/Redis above) its cluster is provisioned manually through
# the Qdrant Cloud console, per PROJECT_HANDBOOK.md §7's managed-services
# checklist — this scaffold only carries the resulting endpoint/key through
# to the ECS task definitions in main.tf, it does not create the cluster
# itself. Flagged here rather than faked with a placeholder resource block
# that would silently do nothing.

variable "qdrant_cloud_url" {
  description = "Qdrant Cloud cluster URL, e.g. https://xxxx.us-east-1-0.aws.cloud.qdrant.io:6333. Provisioned manually in the Qdrant Cloud console — see this file's own header comment."
  type        = string
}

variable "qdrant_cloud_api_key" {
  description = "Qdrant Cloud API key for the cluster above."
  type        = string
  sensitive   = true
}

# --- External vendor keys (Cohere, OpenAI — CLAUDE.md §3's agreed stack) --

variable "cohere_api_key" {
  description = "Cohere API key (embeddings + rerank). Same key, both services — see .env.example's own note on this."
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key (agentic chunking, query pipeline, RAGAS eval judge). Optional at the application layer (falls back to deterministic heuristics — see .env.example), but still passed through here so a real deployment can opt in."
  type        = string
  sensitive   = true
  default     = ""
}

# --- Container images -------------------------------------------------------

variable "container_image_tag" {
  description = "Image tag to deploy for both the api and ingestion-worker ECS services. .github/workflows/cd-staging.yml pushes every build under two tags: the commit SHA (PROJECT_HANDBOOK.md §7's rollback guidance — set this to a known-good SHA and re-apply to roll back) and the mutable \"staging-latest\" (what cd-staging.yml's own `aws ecs update-service --force-new-deployment` step relies on to pick up new pushes without a re-apply on every merge)."
  type        = string
  default     = "staging-latest"
}

# --- ECS task sizing ---------------------------------------------------------

variable "api_cpu" {
  description = "Fargate task CPU units for the api service (1024 = 1 vCPU)."
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Fargate task memory, in MB, for the api service."
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Number of api tasks to run — independent of ingestion_desired_count on purpose (docs/architecture.md §4's \"API and ingestion scale independently\" principle)."
  type        = number
  default     = 1
}

variable "ingestion_cpu" {
  description = "Fargate task CPU units for the ingestion-worker service. Higher default than api_cpu — camelot/opencv table extraction is CPU-heavier than serving a query."
  type        = number
  default     = 1024
}

variable "ingestion_memory" {
  description = "Fargate task memory, in MB, for the ingestion-worker service."
  type        = number
  default     = 2048
}

variable "ingestion_desired_count" {
  description = "Number of ingestion-worker tasks to run — scaled on queue depth in a real deployment (docs/architecture.md §4), a manual variable here since no autoscaling policy is scaffolded yet."
  type        = number
  default     = 1
}

# --- TLS ----------------------------------------------------------------------

variable "alb_certificate_arn" {
  description = "ACM certificate ARN for the api load balancer's HTTPS listener. Left blank by default, in which case main.tf only creates an HTTP (port 80) listener — SIMPLIFICATION flagged explicitly: a real production deployment should always terminate TLS at the ALB. Supply a real ACM cert ARN (in the same region as aws_region) once one exists for the deployed domain."
  type        = string
  default     = ""
}
