# Terraform Variables for Daru PDF AWS Infrastructure

# -----------------------------------------------------------------------------
# General Configuration
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "ap-northeast-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "daru-pdf"
}

# -----------------------------------------------------------------------------
# VPC Configuration
# -----------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones to use"
  type        = list(string)
  default     = ["ap-northeast-1a", "ap-northeast-1c"]
}

# -----------------------------------------------------------------------------
# ECS Configuration - API Service
# -----------------------------------------------------------------------------

variable "api_cpu" {
  description = "CPU units for API service (1 vCPU = 1024)"
  type        = number
  default     = 2048 # 2 vCPU
}

variable "api_memory" {
  description = "Memory for API service in MiB"
  type        = number
  default     = 4096 # 4 GiB
}

variable "api_desired_count" {
  description = "Desired number of API tasks"
  type        = number
  default     = 1
}

variable "api_min_count" {
  description = "Minimum number of API tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "api_max_count" {
  description = "Maximum number of API tasks for auto-scaling"
  type        = number
  default     = 10
}

variable "api_health_check_path" {
  description = "Health check path for API service"
  type        = string
  default     = "/health"
}

# -----------------------------------------------------------------------------
# ECS Configuration - Orchestrator Service
# -----------------------------------------------------------------------------

variable "orchestrator_cpu" {
  description = "CPU units for Orchestrator service (1 vCPU = 1024)"
  type        = number
  default     = 1024 # 1 vCPU
}

variable "orchestrator_memory" {
  description = "Memory for Orchestrator service in MiB"
  type        = number
  default     = 2048 # 2 GiB
}

variable "orchestrator_desired_count" {
  description = "Desired number of Orchestrator tasks"
  type        = number
  default     = 0
}

variable "orchestrator_min_count" {
  description = "Minimum number of Orchestrator tasks for auto-scaling"
  type        = number
  default     = 0
}

variable "orchestrator_max_count" {
  description = "Maximum number of Orchestrator tasks for auto-scaling"
  type        = number
  default     = 5
}

variable "orchestrator_health_check_path" {
  description = "Health check path for Orchestrator service"
  type        = string
  default     = "/health"
}

# -----------------------------------------------------------------------------
# ElastiCache Configuration
# -----------------------------------------------------------------------------

variable "redis_node_type" {
  description = "ElastiCache node type for Redis"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes in the Redis cluster"
  type        = number
  default     = 1
}

variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

# -----------------------------------------------------------------------------
# S3 Configuration
# -----------------------------------------------------------------------------

variable "s3_lifecycle_days" {
  description = "Days before transitioning objects to Glacier"
  type        = number
  default     = 30
}

variable "s3_expiration_days" {
  description = "Days before deleting objects"
  type        = number
  default     = 90
}

# -----------------------------------------------------------------------------
# ALB Configuration
# -----------------------------------------------------------------------------

variable "alb_internal" {
  description = "Whether the ALB should be internal"
  type        = bool
  default     = false
}

variable "alb_deletion_protection" {
  description = "Enable deletion protection for ALB"
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Application Configuration
# -----------------------------------------------------------------------------

variable "api_container_port" {
  description = "Container port for API service"
  type        = number
  default     = 8000
}

variable "orchestrator_container_port" {
  description = "Container port for Orchestrator service"
  type        = number
  default     = 8001
}

# -----------------------------------------------------------------------------
# External Service Configuration (Supabase)
# -----------------------------------------------------------------------------

variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
  default     = ""
  sensitive   = true
}

variable "supabase_service_key" {
  description = "Supabase service role key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "supabase_anon_key" {
  description = "Supabase anonymous key"
  type        = string
  default     = ""
  sensitive   = true
}

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_model" {
  description = "OpenAI model to use"
  type        = string
  default     = "gpt-4o-mini"
}

# -----------------------------------------------------------------------------
# CloudFront Configuration (for Web UI)
# -----------------------------------------------------------------------------

variable "cloudfront_price_class" {
  description = "CloudFront price class"
  type        = string
  default     = "PriceClass_200" # Asia, Europe, North America
}

variable "web_domain" {
  description = "Custom domain for web UI (optional)"
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for custom domain (required if web_domain is set)"
  type        = string
  default     = ""
}
