# Variables for Cloud Run Module

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "name" {
  description = "Name of the Cloud Run service"
  type        = string
}

variable "location" {
  description = "Location/region for the Cloud Run service"
  type        = string
}

variable "image" {
  description = "Container image to deploy"
  type        = string
}

variable "cpu" {
  description = "CPU allocation (e.g., '1', '2', '4')"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory allocation (e.g., '512Mi', '1Gi', '2Gi')"
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "timeout" {
  description = "Request timeout in seconds"
  type        = number
  default     = 300
}

variable "port" {
  description = "Container port"
  type        = number
  default     = 8080
}

variable "env_vars" {
  description = "Environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "secret_env_var_refs" {
  description = "Map of env var name to pre-existing Secret Manager secret ID. Secret values are managed out-of-band (not in Terraform) to keep plaintext out of state."
  type        = map(string)
  default     = {}
}

variable "labels" {
  description = "Labels to apply to resources"
  type        = map(string)
  default     = {}
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated access to the service"
  type        = bool
  default     = false
}

variable "vpc_connector_id" {
  description = "VPC connector ID for private network access"
  type        = string
  default     = ""
}

variable "service_account" {
  description = "Service account email for the Cloud Run service"
  type        = string
  default     = null
}

variable "cpu_idle" {
  description = "Whether CPU should be throttled when idle"
  type        = bool
  default     = true
}

variable "startup_cpu_boost" {
  description = "Enable CPU boost during startup"
  type        = bool
  default     = true
}

variable "execution_environment" {
  description = "Execution environment (EXECUTION_ENVIRONMENT_GEN1 or EXECUTION_ENVIRONMENT_GEN2)"
  type        = string
  default     = "EXECUTION_ENVIRONMENT_GEN2"
}

variable "health_check_path" {
  description = "Path for health check probes"
  type        = string
  default     = "/health"
}

variable "startup_probe_initial_delay" {
  description = "Initial delay for startup probe in seconds"
  type        = number
  default     = 0
}

variable "startup_probe_period" {
  description = "Period between startup probe checks in seconds"
  type        = number
  default     = 10
}

variable "startup_probe_failure_threshold" {
  description = "Number of failures before container is considered failed"
  type        = number
  default     = 3
}

variable "startup_probe_timeout" {
  description = "Timeout for startup probe in seconds"
  type        = number
  default     = 3
}

variable "liveness_probe_period" {
  description = "Period between liveness probe checks in seconds"
  type        = number
  default     = 30
}

variable "liveness_probe_failure_threshold" {
  description = "Number of failures before container is restarted"
  type        = number
  default     = 3
}

variable "liveness_probe_timeout" {
  description = "Timeout for liveness probe in seconds"
  type        = number
  default     = 3
}
