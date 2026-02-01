# Output definitions for Daru PDF GCP Infrastructure

# -----------------------------------------------------------------------------
# Cloud Run Service URLs
# -----------------------------------------------------------------------------

output "api_service_url" {
  description = "URL of the API Cloud Run service"
  value       = module.cloud_run_api.service_url
}

output "web_service_url" {
  description = "URL of the Web Cloud Run service"
  value       = module.cloud_run_web.service_url
}

output "orchestrator_service_url" {
  description = "URL of the Orchestrator Cloud Run service"
  value       = module.cloud_run_orchestrator.service_url
}

# -----------------------------------------------------------------------------
# Storage Bucket URLs
# -----------------------------------------------------------------------------

output "storage_bucket_documents" {
  description = "URL of the documents storage bucket"
  value       = module.storage.bucket_urls["documents"]
}

output "storage_bucket_previews" {
  description = "URL of the previews storage bucket"
  value       = module.storage.bucket_urls["previews"]
}

output "storage_bucket_crops" {
  description = "URL of the crops storage bucket"
  value       = module.storage.bucket_urls["crops"]
}

output "storage_bucket_outputs" {
  description = "URL of the outputs storage bucket"
  value       = module.storage.bucket_urls["outputs"]
}

# -----------------------------------------------------------------------------
# Redis Configuration
# -----------------------------------------------------------------------------

output "redis_host" {
  description = "Memorystore Redis host"
  value       = module.memorystore.host
}

output "redis_port" {
  description = "Memorystore Redis port"
  value       = module.memorystore.port
}

# -----------------------------------------------------------------------------
# Network Configuration
# -----------------------------------------------------------------------------

output "vpc_connector_id" {
  description = "VPC connector ID for Cloud Run services"
  value       = google_vpc_access_connector.connector.id
}

# -----------------------------------------------------------------------------
# Artifact Registry
# -----------------------------------------------------------------------------

output "artifact_registry_url" {
  description = "Artifact Registry URL for container images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.daru_pdf.name}"
}
