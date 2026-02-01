# Variables for Storage Module

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "location" {
  description = "Location for the buckets"
  type        = string
  default     = "ASIA-NORTHEAST1"
}

variable "storage_class" {
  description = "Storage class for the buckets"
  type        = string
  default     = "STANDARD"

  validation {
    condition     = contains(["STANDARD", "NEARLINE", "COLDLINE", "ARCHIVE"], var.storage_class)
    error_message = "Storage class must be STANDARD, NEARLINE, COLDLINE, or ARCHIVE"
  }
}

variable "bucket_names" {
  description = "List of bucket names to create"
  type        = list(string)
  default     = ["documents", "previews", "crops", "outputs"]
}

variable "lifecycle_days" {
  description = "Days before objects are moved to coldline storage (0 to disable)"
  type        = number
  default     = 30
}

variable "delete_days" {
  description = "Days before objects are deleted (0 to disable)"
  type        = number
  default     = 90
}

variable "versioning_enabled" {
  description = "Enable versioning for the buckets"
  type        = bool
  default     = true
}

variable "noncurrent_version_delete_days" {
  description = "Days before non-current versions are deleted"
  type        = number
  default     = 30
}

variable "force_destroy" {
  description = "Allow bucket deletion even if not empty"
  type        = bool
  default     = false
}

variable "uniform_bucket_level_access" {
  description = "Enable uniform bucket-level access"
  type        = bool
  default     = true
}

variable "cors_enabled" {
  description = "Enable CORS for web uploads"
  type        = bool
  default     = true
}

variable "cors_origins" {
  description = "Allowed origins for CORS"
  type        = list(string)
  default     = ["*"]
}

variable "cors_max_age_seconds" {
  description = "Max age for CORS preflight cache"
  type        = number
  default     = 3600
}

variable "labels" {
  description = "Labels to apply to the buckets"
  type        = map(string)
  default     = {}
}
