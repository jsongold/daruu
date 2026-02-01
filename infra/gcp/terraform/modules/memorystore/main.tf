# Memorystore Redis Module for Daru PDF
#
# Creates a Cloud Memorystore Redis instance for caching,
# session storage, and Celery task queue.

resource "google_redis_instance" "redis" {
  name           = var.name
  project        = var.project_id
  region         = var.region
  tier           = var.tier
  memory_size_gb = var.memory_size_gb

  # Redis version
  redis_version = var.redis_version

  # Display name
  display_name = var.display_name != "" ? var.display_name : var.name

  # Network configuration
  authorized_network = var.authorized_network
  connect_mode       = var.connect_mode

  # Auth configuration
  auth_enabled = var.auth_enabled

  # Transit encryption
  transit_encryption_mode = var.transit_encryption_mode

  # Maintenance policy
  dynamic "maintenance_policy" {
    for_each = var.maintenance_window_day != null ? [1] : []
    content {
      weekly_maintenance_window {
        day = var.maintenance_window_day
        start_time {
          hours   = var.maintenance_window_hour
          minutes = 0
          seconds = 0
          nanos   = 0
        }
      }
    }
  }

  # Persistence configuration (for STANDARD_HA tier)
  dynamic "persistence_config" {
    for_each = var.tier == "STANDARD_HA" ? [1] : []
    content {
      persistence_mode    = var.persistence_mode
      rdb_snapshot_period = var.rdb_snapshot_period
    }
  }

  labels = var.labels

  lifecycle {
    prevent_destroy = false
  }
}
