# Storage Module for Daru PDF
#
# Creates Google Cloud Storage buckets for:
# - documents: Original uploaded PDFs and images
# - previews: Generated preview images
# - crops: OCR cropped regions
# - outputs: Generated/filled PDFs

resource "google_storage_bucket" "buckets" {
  for_each = toset(var.bucket_names)

  name          = "${var.project_id}-daru-pdf-${var.environment}-${each.key}"
  project       = var.project_id
  location      = var.location
  storage_class = var.storage_class

  # Prevent accidental deletion
  force_destroy = var.force_destroy

  # Versioning
  versioning {
    enabled = var.versioning_enabled
  }

  # Uniform bucket-level access
  uniform_bucket_level_access = var.uniform_bucket_level_access

  # Lifecycle rules
  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_days > 0 ? [1] : []
    content {
      condition {
        age = var.lifecycle_days
      }
      action {
        type          = "SetStorageClass"
        storage_class = "COLDLINE"
      }
    }
  }

  dynamic "lifecycle_rule" {
    for_each = var.delete_days > 0 ? [1] : []
    content {
      condition {
        age = var.delete_days
      }
      action {
        type = "Delete"
      }
    }
  }

  # Delete non-current versions after specified days
  dynamic "lifecycle_rule" {
    for_each = var.versioning_enabled && var.noncurrent_version_delete_days > 0 ? [1] : []
    content {
      condition {
        num_newer_versions = 3
        with_state         = "ARCHIVED"
      }
      action {
        type = "Delete"
      }
    }
  }

  # CORS configuration for web uploads
  dynamic "cors" {
    for_each = var.cors_enabled ? [1] : []
    content {
      origin          = var.cors_origins
      method          = ["GET", "HEAD", "PUT", "POST", "DELETE"]
      response_header = ["*"]
      max_age_seconds = var.cors_max_age_seconds
    }
  }

  labels = merge(var.labels, {
    bucket_type = each.key
  })
}

# NOTE: Bucket IAM for Cloud Run service accounts is managed in main.tf
# using per-service SAs for least privilege (not default compute SA).
