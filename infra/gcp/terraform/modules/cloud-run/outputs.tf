# Outputs for Cloud Run Module

output "service_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.uri
}

output "service_name" {
  description = "Name of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.name
}

output "service_id" {
  description = "Full ID of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.id
}

output "latest_revision" {
  description = "Latest revision of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.latest_ready_revision
}

output "service_account" {
  description = "Service account used by the Cloud Run service"
  value       = google_cloud_run_v2_service.service.template[0].service_account
}
