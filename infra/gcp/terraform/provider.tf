# GCP Provider Configuration for Daru PDF
# Terraform provider configuration for Google Cloud Platform

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # State stored in GCS. Bucket and prefix set via -backend-config flags:
  #   terraform init \
  #     -backend-config="bucket=<project-id>-terraform-state" \
  #     -backend-config="prefix=terraform/staging"
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
