# ECS Module Outputs

output "service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.main.name
}

output "service_id" {
  description = "ID of the ECS service"
  value       = aws_ecs_service.main.id
}

output "task_arn" {
  description = "ARN of the task definition"
  value       = aws_ecs_task_definition.main.arn
}

output "task_family" {
  description = "Family of the task definition"
  value       = aws_ecs_task_definition.main.family
}

output "task_revision" {
  description = "Revision of the task definition"
  value       = aws_ecs_task_definition.main.revision
}
