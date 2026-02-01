# Cloud Run Module for Daru PDF
#
# Creates a Cloud Run service with configurable resources,
# environment variables, and IAM policies.

resource "google_cloud_run_v2_service" "service" {
  name     = var.name
  location = var.location
  project  = var.project_id

  labels = var.labels

  template {
    labels = var.labels

    # Service account
    service_account = var.service_account

    # VPC connector for private network access
    dynamic "vpc_access" {
      for_each = var.vpc_connector_id != "" ? [1] : []
      content {
        connector = var.vpc_connector_id
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }

    # Scaling configuration
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Container configuration
    containers {
      image = var.image

      # Resource limits
      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = var.cpu_idle
        startup_cpu_boost = var.startup_cpu_boost
      }

      # Startup probe
      startup_probe {
        http_get {
          path = var.health_check_path
          port = var.port
        }
        initial_delay_seconds = var.startup_probe_initial_delay
        period_seconds        = var.startup_probe_period
        failure_threshold     = var.startup_probe_failure_threshold
        timeout_seconds       = var.startup_probe_timeout
      }

      # Liveness probe
      liveness_probe {
        http_get {
          path = var.health_check_path
          port = var.port
        }
        period_seconds    = var.liveness_probe_period
        failure_threshold = var.liveness_probe_failure_threshold
        timeout_seconds   = var.liveness_probe_timeout
      }

      # Port configuration
      ports {
        container_port = var.port
        name           = "http1"
      }

      # Environment variables
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Secret environment variables (from Secret Manager)
      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets[env.key].secret_id
              version = "latest"
            }
          }
        }
      }
    }

    # Request timeout
    timeout = "${var.timeout}s"

    # Execution environment
    execution_environment = var.execution_environment
  }

  # Traffic configuration
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      # Ignore changes to client annotations set by Cloud Console/gcloud
      annotations,
      template[0].annotations,
    ]
  }
}

# -----------------------------------------------------------------------------
# Secret Manager Secrets
# -----------------------------------------------------------------------------

resource "google_secret_manager_secret" "secrets" {
  for_each = var.secret_env_vars

  secret_id = "${var.name}-${lower(replace(each.key, "_", "-"))}"
  project   = var.project_id

  labels = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "secret_versions" {
  for_each = var.secret_env_vars

  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value
}

# Grant Cloud Run service account access to secrets
resource "google_secret_manager_secret_iam_member" "secret_access" {
  for_each = var.secret_env_vars

  project   = var.project_id
  secret_id = google_secret_manager_secret.secrets[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

# -----------------------------------------------------------------------------
# IAM Policy for Public Access
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count = var.allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = var.location
  name     = google_cloud_run_v2_service.service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "google_project" "current" {
  project_id = var.project_id
}
