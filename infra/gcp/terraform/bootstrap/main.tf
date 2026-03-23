# Bootstrap Terraform State Bucket
#
# This configuration provisions the GCS bucket used for Terraform remote state.
# Apply this manually once before using the main Terraform configuration:
#
#   cd infra/gcp/terraform/bootstrap
#   terraform init
#   terraform apply -var="project_id=YOUR_PROJECT_ID"

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_storage_bucket" "terraform_state" {
  name     = "${var.project_id}-terraform-state"
  location = var.region

  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }

  uniform_bucket_level_access = true

  labels = {
    project    = "daru-pdf"
    managed_by = "terraform"
    purpose    = "terraform-state"
  }
}
