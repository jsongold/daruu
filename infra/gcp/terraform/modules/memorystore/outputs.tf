# Outputs for Memorystore Redis Module

output "host" {
  description = "Hostname/IP of the Redis instance"
  value       = google_redis_instance.redis.host
}

output "port" {
  description = "Port of the Redis instance"
  value       = google_redis_instance.redis.port
}

output "id" {
  description = "Full ID of the Redis instance"
  value       = google_redis_instance.redis.id
}

output "name" {
  description = "Name of the Redis instance"
  value       = google_redis_instance.redis.name
}

output "current_location_id" {
  description = "Current location of the Redis instance"
  value       = google_redis_instance.redis.current_location_id
}

output "auth_string" {
  description = "AUTH string for the Redis instance (if auth_enabled)"
  value       = google_redis_instance.redis.auth_string
  sensitive   = true
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = "redis://${google_redis_instance.redis.host}:${google_redis_instance.redis.port}"
}
