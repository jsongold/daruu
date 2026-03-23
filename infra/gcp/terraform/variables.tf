# Variable definitions for Daru PDF GCP Infrastructure

# -----------------------------------------------------------------------------
# Project Configuration
# -----------------------------------------------------------------------------

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "asia-northeast1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

# -----------------------------------------------------------------------------
# Service Images
# -----------------------------------------------------------------------------

variable "api_image" {
  description = "Container image for the API service"
  type        = string
  default     = ""
}

variable "web_image" {
  description = "Container image for the Web service"
  type        = string
  default     = ""
}

variable "orchestrator_image" {
  description = "Container image for the Orchestrator service"
  type        = string
  default     = ""
}

variable "rule_service_image" {
  description = "Container image for the Rule Service"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Cloud Run Configuration
# -----------------------------------------------------------------------------

variable "api_cpu" {
  description = "CPU allocation for API service"
  type        = string
  default     = "2"
}

variable "api_memory" {
  description = "Memory allocation for API service"
  type        = string
  default     = "4Gi"
}

variable "api_min_instances" {
  description = "Minimum instances for API service"
  type        = number
  default     = 0
}

variable "api_max_instances" {
  description = "Maximum instances for API service"
  type        = number
  default     = 10
}

variable "api_timeout" {
  description = "Request timeout for API service in seconds"
  type        = number
  default     = 300
}

variable "web_cpu" {
  description = "CPU allocation for Web service"
  type        = string
  default     = "1"
}

variable "web_memory" {
  description = "Memory allocation for Web service"
  type        = string
  default     = "1Gi"
}

variable "web_min_instances" {
  description = "Minimum instances for Web service"
  type        = number
  default     = 1
}

variable "web_max_instances" {
  description = "Maximum instances for Web service"
  type        = number
  default     = 3
}

variable "orchestrator_cpu" {
  description = "CPU allocation for Orchestrator service"
  type        = string
  default     = "1"
}

variable "orchestrator_memory" {
  description = "Memory allocation for Orchestrator service"
  type        = string
  default     = "2Gi"
}

variable "orchestrator_min_instances" {
  description = "Minimum instances for Orchestrator service"
  type        = number
  default     = 0
}

variable "orchestrator_max_instances" {
  description = "Maximum instances for Orchestrator service"
  type        = number
  default     = 5
}

variable "rule_service_cpu" {
  description = "CPU allocation for Rule Service"
  type        = string
  default     = "1"
}

variable "rule_service_memory" {
  description = "Memory allocation for Rule Service"
  type        = string
  default     = "2Gi"
}

variable "rule_service_min_instances" {
  description = "Minimum instances for Rule Service"
  type        = number
  default     = 0
}

variable "rule_service_max_instances" {
  description = "Maximum instances for Rule Service"
  type        = number
  default     = 3
}

# -----------------------------------------------------------------------------
# GitHub Actions (Workload Identity Federation)
# -----------------------------------------------------------------------------

variable "github_repo" {
  description = "GitHub repository in owner/repo format (e.g. myorg/daru-pdf)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Memorystore Configuration
# -----------------------------------------------------------------------------

variable "redis_tier" {
  description = "Memorystore Redis tier (BASIC or STANDARD_HA)"
  type        = string
  default     = "BASIC"

  validation {
    condition     = contains(["BASIC", "STANDARD_HA"], var.redis_tier)
    error_message = "Redis tier must be BASIC or STANDARD_HA"
  }
}

variable "redis_memory_size_gb" {
  description = "Memorystore Redis memory size in GB"
  type        = number
  default     = 1
}

# -----------------------------------------------------------------------------
# Storage Configuration
# -----------------------------------------------------------------------------

variable "storage_location" {
  description = "Location for GCS buckets"
  type        = string
  default     = "ASIA-NORTHEAST1"
}

variable "storage_lifecycle_days" {
  description = "Days before objects are moved to coldline storage"
  type        = number
  default     = 30
}

variable "storage_delete_days" {
  description = "Days before objects are deleted"
  type        = number
  default     = 90
}

# -----------------------------------------------------------------------------
# CORS Configuration
# -----------------------------------------------------------------------------

variable "cors_origins" {
  description = "Allowed origins for CORS on storage buckets. NEVER use [\"*\"] in production."
  type        = list(string)

  validation {
    condition     = !contains(var.cors_origins, "*") || length(var.cors_origins) == 0
    error_message = "CORS wildcard '*' is not allowed. Specify explicit origins."
  }
}

# -----------------------------------------------------------------------------
# Network Configuration
# -----------------------------------------------------------------------------

variable "vpc_connector_name" {
  description = "Name of the VPC connector for Cloud Run"
  type        = string
  default     = "daru-pdf-vpc-connector"
}

variable "vpc_connector_cidr" {
  description = "CIDR range for VPC connector"
  type        = string
  default     = "10.8.0.0/28"
}
