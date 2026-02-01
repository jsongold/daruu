# Terraform Outputs for Daru PDF AWS Infrastructure

# -----------------------------------------------------------------------------
# VPC Outputs
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

# -----------------------------------------------------------------------------
# ECS Outputs
# -----------------------------------------------------------------------------

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "api_service_name" {
  description = "Name of the API ECS service"
  value       = module.ecs_api.service_name
}

output "api_task_arn" {
  description = "ARN of the API task definition"
  value       = module.ecs_api.task_arn
}

output "orchestrator_service_name" {
  description = "Name of the Orchestrator ECS service"
  value       = module.ecs_orchestrator.service_name
}

output "orchestrator_task_arn" {
  description = "ARN of the Orchestrator task definition"
  value       = module.ecs_orchestrator.task_arn
}

# -----------------------------------------------------------------------------
# ALB Outputs
# -----------------------------------------------------------------------------

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.alb.dns_name
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = module.alb.arn
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = module.alb.zone_id
}

# -----------------------------------------------------------------------------
# ElastiCache Outputs
# -----------------------------------------------------------------------------

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.endpoint
}

output "redis_port" {
  description = "ElastiCache Redis port"
  value       = module.elasticache.port
}

output "redis_connection_string" {
  description = "Redis connection string for application configuration"
  value       = "redis://${module.elasticache.endpoint}:${module.elasticache.port}"
  sensitive   = true
}

# -----------------------------------------------------------------------------
# S3 Outputs
# -----------------------------------------------------------------------------

output "s3_bucket_documents" {
  description = "S3 bucket name for documents"
  value       = module.s3.bucket_names["documents"]
}

output "s3_bucket_previews" {
  description = "S3 bucket name for previews"
  value       = module.s3.bucket_names["previews"]
}

output "s3_bucket_crops" {
  description = "S3 bucket name for crops"
  value       = module.s3.bucket_names["crops"]
}

output "s3_bucket_outputs" {
  description = "S3 bucket name for outputs"
  value       = module.s3.bucket_names["outputs"]
}

output "s3_bucket_arns" {
  description = "ARNs of all S3 buckets"
  value       = module.s3.bucket_arns
}

# -----------------------------------------------------------------------------
# CloudFront Outputs (Web UI)
# -----------------------------------------------------------------------------

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for web UI"
  value       = aws_cloudfront_distribution.web.id
}

output "cloudfront_domain_name" {
  description = "CloudFront domain name for web UI"
  value       = aws_cloudfront_distribution.web.domain_name
}

output "web_bucket_name" {
  description = "S3 bucket name for web UI static files"
  value       = aws_s3_bucket.web.id
}

# -----------------------------------------------------------------------------
# ECR Outputs
# -----------------------------------------------------------------------------

output "ecr_api_repository_url" {
  description = "ECR repository URL for API image"
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_orchestrator_repository_url" {
  description = "ECR repository URL for Orchestrator image"
  value       = aws_ecr_repository.orchestrator.repository_url
}

# -----------------------------------------------------------------------------
# Security Group Outputs
# -----------------------------------------------------------------------------

output "alb_security_group_id" {
  description = "Security group ID for ALB"
  value       = aws_security_group.alb.id
}

output "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.ecs_tasks.id
}

output "redis_security_group_id" {
  description = "Security group ID for Redis"
  value       = aws_security_group.redis.id
}

# -----------------------------------------------------------------------------
# Application URLs
# -----------------------------------------------------------------------------

output "api_url" {
  description = "URL for accessing the API"
  value       = "http://${module.alb.dns_name}/api/v1"
}

output "web_url" {
  description = "URL for accessing the Web UI"
  value       = "https://${aws_cloudfront_distribution.web.domain_name}"
}

# -----------------------------------------------------------------------------
# CloudWatch Log Groups
# -----------------------------------------------------------------------------

output "api_log_group" {
  description = "CloudWatch Log Group for API service"
  value       = aws_cloudwatch_log_group.api.name
}

output "orchestrator_log_group" {
  description = "CloudWatch Log Group for Orchestrator service"
  value       = aws_cloudwatch_log_group.orchestrator.name
}
