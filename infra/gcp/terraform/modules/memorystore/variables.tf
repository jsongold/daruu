# Variables for Memorystore Redis Module

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "name" {
  description = "Name of the Redis instance"
  type        = string
}

variable "region" {
  description = "Region for the Redis instance"
  type        = string
}

variable "tier" {
  description = "Service tier (BASIC or STANDARD_HA)"
  type        = string
  default     = "BASIC"

  validation {
    condition     = contains(["BASIC", "STANDARD_HA"], var.tier)
    error_message = "Tier must be BASIC or STANDARD_HA"
  }
}

variable "memory_size_gb" {
  description = "Memory size in GB"
  type        = number
  default     = 1

  validation {
    condition     = var.memory_size_gb >= 1 && var.memory_size_gb <= 300
    error_message = "Memory size must be between 1 and 300 GB"
  }
}

variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "REDIS_7_0"

  validation {
    condition     = contains(["REDIS_6_X", "REDIS_7_0"], var.redis_version)
    error_message = "Redis version must be REDIS_6_X or REDIS_7_0"
  }
}

variable "display_name" {
  description = "Display name for the Redis instance"
  type        = string
  default     = ""
}

variable "authorized_network" {
  description = "VPC network for the Redis instance"
  type        = string
  default     = "default"
}

variable "connect_mode" {
  description = "Connection mode (DIRECT_PEERING or PRIVATE_SERVICE_ACCESS)"
  type        = string
  default     = "DIRECT_PEERING"
}

variable "auth_enabled" {
  description = "Enable AUTH for Redis"
  type        = bool
  default     = false
}

variable "transit_encryption_mode" {
  description = "Transit encryption mode (DISABLED or SERVER_AUTHENTICATION)"
  type        = string
  default     = "DISABLED"
}

variable "maintenance_window_day" {
  description = "Day of week for maintenance (MONDAY, TUESDAY, etc.)"
  type        = string
  default     = null
}

variable "maintenance_window_hour" {
  description = "Hour of day for maintenance (0-23)"
  type        = number
  default     = 3
}

variable "persistence_mode" {
  description = "Persistence mode for STANDARD_HA tier"
  type        = string
  default     = "RDB"
}

variable "rdb_snapshot_period" {
  description = "RDB snapshot period"
  type        = string
  default     = "TWENTY_FOUR_HOURS"
}

variable "labels" {
  description = "Labels to apply to the Redis instance"
  type        = map(string)
  default     = {}
}
