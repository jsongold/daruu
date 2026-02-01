# ALB Module Variables

variable "name" {
  description = "Name of the Application Load Balancer"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "subnets" {
  description = "List of subnet IDs for the ALB"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs"
  type        = list(string)
}

variable "internal" {
  description = "Whether the ALB should be internal"
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Enable deletion protection for the ALB"
  type        = bool
  default     = false
}

variable "target_groups" {
  description = "List of target group configurations"
  type = list(object({
    name        = string
    port        = number
    protocol    = string
    target_type = string
    health_check = object({
      enabled             = bool
      path                = string
      port                = string
      protocol            = string
      healthy_threshold   = number
      unhealthy_threshold = number
      timeout             = number
      interval            = number
      matcher             = string
    })
  }))
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
