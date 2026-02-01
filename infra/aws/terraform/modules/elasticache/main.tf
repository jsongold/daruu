# ElastiCache Redis Module
# Creates an ElastiCache Redis cluster for caching and Celery broker

# -----------------------------------------------------------------------------
# Subnet Group
# -----------------------------------------------------------------------------

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.name}-subnet-group"
  subnet_ids = var.subnet_ids

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Parameter Group
# -----------------------------------------------------------------------------

resource "aws_elasticache_parameter_group" "main" {
  name   = "${var.name}-params"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Redis Cluster
# -----------------------------------------------------------------------------

resource "aws_elasticache_cluster" "main" {
  cluster_id           = var.name
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_nodes      = var.num_cache_nodes
  parameter_group_name = aws_elasticache_parameter_group.main.name
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = var.security_group_ids
  port                 = 6379

  # Maintenance and backup settings
  maintenance_window       = "sun:05:00-sun:06:00"
  snapshot_retention_limit = var.num_cache_nodes > 1 ? 7 : 0
  snapshot_window          = var.num_cache_nodes > 1 ? "04:00-05:00" : null

  # Apply changes immediately in non-production environments
  apply_immediately = true

  tags = var.tags
}
