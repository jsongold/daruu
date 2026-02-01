# S3 Module Outputs

output "bucket_names" {
  description = "Map of bucket keys to bucket names"
  value       = { for k, v in aws_s3_bucket.main : k => v.id }
}

output "bucket_arns" {
  description = "Map of bucket keys to bucket ARNs"
  value       = { for k, v in aws_s3_bucket.main : k => v.arn }
}

output "bucket_domain_names" {
  description = "Map of bucket keys to bucket domain names"
  value       = { for k, v in aws_s3_bucket.main : k => v.bucket_domain_name }
}

output "bucket_regional_domain_names" {
  description = "Map of bucket keys to bucket regional domain names"
  value       = { for k, v in aws_s3_bucket.main : k => v.bucket_regional_domain_name }
}
