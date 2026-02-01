# S3 Module Variables

variable "bucket_names" {
  description = "Map of bucket keys to bucket names"
  type        = map(string)
}

variable "lifecycle_days" {
  description = "Days before transitioning objects to Glacier"
  type        = number
  default     = 30
}

variable "expiration_days" {
  description = "Days before deleting objects"
  type        = number
  default     = 90
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
