output "state_bucket_name" {
  description = "Name of the Terraform state GCS bucket"
  value       = google_storage_bucket.terraform_state.name
}

output "state_bucket_url" {
  description = "URL of the Terraform state GCS bucket"
  value       = google_storage_bucket.terraform_state.url
}
