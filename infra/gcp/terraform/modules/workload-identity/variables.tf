variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format (e.g. myorg/daru-pdf)"
  type        = string
}

variable "state_bucket_name" {
  description = "Name of the Terraform state GCS bucket (for scoped IAM)"
  type        = string
  default     = ""
}
