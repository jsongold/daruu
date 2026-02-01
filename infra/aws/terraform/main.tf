# Main Terraform Configuration for Daru PDF AWS Infrastructure
# This file orchestrates all resources: VPC, ECS, S3, ElastiCache, ALB, CloudFront

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# -----------------------------------------------------------------------------
# Random Suffix for Unique Naming
# -----------------------------------------------------------------------------

resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# -----------------------------------------------------------------------------
# VPC Configuration
# -----------------------------------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${local.name_prefix}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-igw"
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${local.name_prefix}-public-${var.availability_zones[count.index]}"
    Type = "public"
  }
}

# Private Subnets
resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + length(var.availability_zones))
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${local.name_prefix}-private-${var.availability_zones[count.index]}"
    Type = "private"
  }
}

# Elastic IP for NAT Gateway
resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"

  tags = {
    Name = "${local.name_prefix}-nat-eip-${count.index}"
  }

  depends_on = [aws_internet_gateway.main]
}

# NAT Gateway
resource "aws_nat_gateway" "main" {
  count = length(var.availability_zones)

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name = "${local.name_prefix}-nat-${var.availability_zones[count.index]}"
  }

  depends_on = [aws_internet_gateway.main]
}

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${local.name_prefix}-public-rt"
  }
}

# Private Route Tables
resource "aws_route_table" "private" {
  count = length(var.availability_zones)

  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = {
    Name = "${local.name_prefix}-private-rt-${var.availability_zones[count.index]}"
  }
}

# Public Subnet Route Table Associations
resource "aws_route_table_association" "public" {
  count = length(var.availability_zones)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private Subnet Route Table Associations
resource "aws_route_table_association" "private" {
  count = length(var.availability_zones)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# -----------------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------------

# ALB Security Group
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-alb-sg"
  }
}

# ECS Tasks Security Group
resource "aws_security_group" "ecs_tasks" {
  name        = "${local.name_prefix}-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Traffic from ALB"
    from_port       = var.api_container_port
    to_port         = var.api_container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description     = "Traffic from ALB to Orchestrator"
    from_port       = var.orchestrator_container_port
    to_port         = var.orchestrator_container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Allow inter-service communication
  ingress {
    description = "Internal service communication"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-ecs-tasks-sg"
  }
}

# Redis Security Group
resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis from ECS tasks"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-redis-sg"
  }
}

# -----------------------------------------------------------------------------
# ECR Repositories
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "api" {
  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${local.name_prefix}-api"
  }
}

resource "aws_ecr_repository" "orchestrator" {
  name                 = "${local.name_prefix}-orchestrator"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${local.name_prefix}-orchestrator"
  }
}

# ECR Lifecycle Policy
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 30 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "orchestrator" {
  repository = aws_ecr_repository.orchestrator.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 30 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# CloudWatch Log Groups
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name_prefix}-api"
  retention_in_days = 30

  tags = {
    Name = "${local.name_prefix}-api-logs"
  }
}

resource "aws_cloudwatch_log_group" "orchestrator" {
  name              = "/ecs/${local.name_prefix}-orchestrator"
  retention_in_days = 30

  tags = {
    Name = "${local.name_prefix}-orchestrator-logs"
  }
}

# -----------------------------------------------------------------------------
# IAM Role for ECS Task Execution
# -----------------------------------------------------------------------------

resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.name_prefix}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-ecs-task-execution"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Tasks (Application)
resource "aws_iam_role" "ecs_task" {
  name = "${local.name_prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-ecs-task"
  }
}

# S3 Access Policy for ECS Tasks
resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "${local.name_prefix}-ecs-task-s3"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = concat(
          [for arn in values(module.s3.bucket_arns) : arn],
          [for arn in values(module.s3.bucket_arns) : "${arn}/*"]
        )
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# ECS Cluster
# -----------------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${local.name_prefix}-cluster"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

# -----------------------------------------------------------------------------
# Module: ALB
# -----------------------------------------------------------------------------

module "alb" {
  source = "./modules/alb"

  name                = "${local.name_prefix}-alb"
  vpc_id              = aws_vpc.main.id
  subnets             = aws_subnet.public[*].id
  security_group_ids  = [aws_security_group.alb.id]
  internal            = var.alb_internal
  deletion_protection = var.alb_deletion_protection

  target_groups = [
    {
      name        = "api"
      port        = var.api_container_port
      protocol    = "HTTP"
      target_type = "ip"
      health_check = {
        enabled             = true
        path                = var.api_health_check_path
        port                = "traffic-port"
        protocol            = "HTTP"
        healthy_threshold   = 2
        unhealthy_threshold = 3
        timeout             = 5
        interval            = 30
        matcher             = "200"
      }
    },
    {
      name        = "orchestrator"
      port        = var.orchestrator_container_port
      protocol    = "HTTP"
      target_type = "ip"
      health_check = {
        enabled             = true
        path                = var.orchestrator_health_check_path
        port                = "traffic-port"
        protocol            = "HTTP"
        healthy_threshold   = 2
        unhealthy_threshold = 3
        timeout             = 5
        interval            = 30
        matcher             = "200"
      }
    }
  ]

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Module: S3 Buckets
# -----------------------------------------------------------------------------

module "s3" {
  source = "./modules/s3"

  bucket_names = {
    documents = "${local.name_prefix}-documents-${random_id.suffix.hex}"
    previews  = "${local.name_prefix}-previews-${random_id.suffix.hex}"
    crops     = "${local.name_prefix}-crops-${random_id.suffix.hex}"
    outputs   = "${local.name_prefix}-outputs-${random_id.suffix.hex}"
  }

  lifecycle_days   = var.s3_lifecycle_days
  expiration_days  = var.s3_expiration_days

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Module: ElastiCache (Redis)
# -----------------------------------------------------------------------------

module "elasticache" {
  source = "./modules/elasticache"

  name             = "${local.name_prefix}-redis"
  node_type        = var.redis_node_type
  num_cache_nodes  = var.redis_num_cache_nodes
  engine_version   = var.redis_engine_version
  subnet_ids       = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.redis.id]

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Module: ECS Services
# -----------------------------------------------------------------------------

module "ecs_api" {
  source = "./modules/ecs"

  name           = "${local.name_prefix}-api"
  cluster_arn    = aws_ecs_cluster.main.arn

  # Container configuration
  image          = "${aws_ecr_repository.api.repository_url}:latest"
  cpu            = var.api_cpu
  memory         = var.api_memory
  container_port = var.api_container_port

  # Scaling configuration
  desired_count = var.api_desired_count
  min_count     = var.api_min_count
  max_count     = var.api_max_count

  # Network configuration
  subnets            = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.ecs_tasks.id]
  target_group_arn   = module.alb.target_group_arns["api"]

  # IAM configuration
  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  # Logging
  log_group_name = aws_cloudwatch_log_group.api.name
  aws_region     = var.aws_region

  # Environment variables
  env_vars = {
    DARU_DEBUG                   = var.environment != "prod" ? "true" : "false"
    DARU_API_PREFIX              = "/api/v1"
    DARU_SUPABASE_URL            = var.supabase_url
    DARU_SUPABASE_SERVICE_KEY    = var.supabase_service_key
    DARU_SUPABASE_ANON_KEY       = var.supabase_anon_key
    DARU_OPENAI_API_KEY          = var.openai_api_key
    DARU_OPENAI_MODEL            = var.openai_model
    AWS_S3_BUCKET_DOCUMENTS      = module.s3.bucket_names["documents"]
    AWS_S3_BUCKET_PREVIEWS       = module.s3.bucket_names["previews"]
    AWS_S3_BUCKET_CROPS          = module.s3.bucket_names["crops"]
    AWS_S3_BUCKET_OUTPUTS        = module.s3.bucket_names["outputs"]
    AWS_REDIS_ENDPOINT           = module.elasticache.endpoint
    AWS_REDIS_PORT               = tostring(module.elasticache.port)
    ORCHESTRATOR_URL             = "http://${local.name_prefix}-orchestrator.${local.name_prefix}:${var.orchestrator_container_port}"
  }

  tags = local.common_tags
}

module "ecs_orchestrator" {
  source = "./modules/ecs"

  name           = "${local.name_prefix}-orchestrator"
  cluster_arn    = aws_ecs_cluster.main.arn

  # Container configuration
  image          = "${aws_ecr_repository.orchestrator.repository_url}:latest"
  cpu            = var.orchestrator_cpu
  memory         = var.orchestrator_memory
  container_port = var.orchestrator_container_port

  # Scaling configuration
  desired_count = var.orchestrator_desired_count
  min_count     = var.orchestrator_min_count
  max_count     = var.orchestrator_max_count

  # Network configuration
  subnets            = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.ecs_tasks.id]
  target_group_arn   = module.alb.target_group_arns["orchestrator"]

  # IAM configuration
  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  # Logging
  log_group_name = aws_cloudwatch_log_group.orchestrator.name
  aws_region     = var.aws_region

  # Environment variables
  env_vars = {
    DARU_DEBUG                   = var.environment != "prod" ? "true" : "false"
    DARU_SUPABASE_URL            = var.supabase_url
    DARU_SUPABASE_SERVICE_KEY    = var.supabase_service_key
    DARU_OPENAI_API_KEY          = var.openai_api_key
    DARU_OPENAI_MODEL            = var.openai_model
    AWS_S3_BUCKET_DOCUMENTS      = module.s3.bucket_names["documents"]
    AWS_S3_BUCKET_PREVIEWS       = module.s3.bucket_names["previews"]
    AWS_S3_BUCKET_CROPS          = module.s3.bucket_names["crops"]
    AWS_S3_BUCKET_OUTPUTS        = module.s3.bucket_names["outputs"]
    AWS_REDIS_ENDPOINT           = module.elasticache.endpoint
    AWS_REDIS_PORT               = tostring(module.elasticache.port)
    API_URL                      = "http://${local.name_prefix}-api.${local.name_prefix}:${var.api_container_port}"
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# S3 Bucket for Web UI Static Files
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "web" {
  bucket = "${local.name_prefix}-web-${random_id.suffix.hex}"

  tags = {
    Name = "${local.name_prefix}-web"
  }
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket = aws_s3_bucket.web.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_website_configuration" "web" {
  bucket = aws_s3_bucket.web.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

# CloudFront Origin Access Identity
resource "aws_cloudfront_origin_access_identity" "web" {
  comment = "OAI for ${local.name_prefix} web UI"
}

# S3 Bucket Policy for CloudFront
resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_cloudfront_origin_access_identity.web.iam_arn
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.web.arn}/*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# CloudFront Distribution for Web UI
# -----------------------------------------------------------------------------

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class
  comment             = "${local.name_prefix} Web UI"

  origin {
    domain_name = aws_s3_bucket.web.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.web.id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.web.cloudfront_access_identity_path
    }
  }

  # API origin for /api/* requests
  origin {
    domain_name = module.alb.dns_name
    origin_id   = "ALB-API"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.web.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }

  # Cache behavior for API requests
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "ALB-API"

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Origin", "Access-Control-Request-Headers", "Access-Control-Request-Method"]
      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 0
    max_ttl                = 0
    compress               = true
  }

  # SPA routing - return index.html for all 404s
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.acm_certificate_arn == ""
    acm_certificate_arn            = var.acm_certificate_arn != "" ? var.acm_certificate_arn : null
    ssl_support_method             = var.acm_certificate_arn != "" ? "sni-only" : null
    minimum_protocol_version       = "TLSv1.2_2021"
  }

  tags = {
    Name = "${local.name_prefix}-web-cdn"
  }
}
