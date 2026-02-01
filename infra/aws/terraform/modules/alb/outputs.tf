# ALB Module Outputs

output "dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = aws_lb.main.zone_id
}

output "target_group_arns" {
  description = "Map of target group names to ARNs"
  value       = { for k, v in aws_lb_target_group.main : k => v.arn }
}

output "listener_arn" {
  description = "ARN of the HTTP listener"
  value       = aws_lb_listener.http.arn
}
