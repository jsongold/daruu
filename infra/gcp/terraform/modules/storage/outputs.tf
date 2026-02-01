# Outputs for Storage Module

output "bucket_names" {
  description = "Map of logical bucket names to actual bucket names"
  value = {
    for key, bucket in google_storage_bucket.buckets :
    key => bucket.name
  }
}

output "bucket_urls" {
  description = "Map of logical bucket names to bucket URLs"
  value = {
    for key, bucket in google_storage_bucket.buckets :
    key => bucket.url
  }
}

output "bucket_self_links" {
  description = "Map of logical bucket names to bucket self links"
  value = {
    for key, bucket in google_storage_bucket.buckets :
    key => bucket.self_link
  }
}

output "bucket_ids" {
  description = "Map of logical bucket names to bucket IDs"
  value = {
    for key, bucket in google_storage_bucket.buckets :
    key => bucket.id
  }
}
