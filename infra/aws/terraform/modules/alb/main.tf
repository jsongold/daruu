# ALB Module
# Creates an Application Load Balancer with target groups

# -----------------------------------------------------------------------------
# Application Load Balancer
# -----------------------------------------------------------------------------

resource "aws_lb" "main" {
  name               = var.name
  internal           = var.internal
  load_balancer_type = "application"
  security_groups    = var.security_group_ids
  subnets            = var.subnets

  enable_deletion_protection = var.deletion_protection
  enable_http2               = true

  idle_timeout = 60

  tags = merge(var.tags, {
    Name = var.name
  })
}

# -----------------------------------------------------------------------------
# Target Groups
# -----------------------------------------------------------------------------

resource "aws_lb_target_group" "main" {
  for_each = { for tg in var.target_groups : tg.name => tg }

  name        = "${var.name}-${each.value.name}"
  port        = each.value.port
  protocol    = each.value.protocol
  vpc_id      = var.vpc_id
  target_type = each.value.target_type

  health_check {
    enabled             = each.value.health_check.enabled
    path                = each.value.health_check.path
    port                = each.value.health_check.port
    protocol            = each.value.health_check.protocol
    healthy_threshold   = each.value.health_check.healthy_threshold
    unhealthy_threshold = each.value.health_check.unhealthy_threshold
    timeout             = each.value.health_check.timeout
    interval            = each.value.health_check.interval
    matcher             = each.value.health_check.matcher
  }

  deregistration_delay = 30

  tags = merge(var.tags, {
    Name = "${var.name}-${each.value.name}"
  })
}

# -----------------------------------------------------------------------------
# HTTP Listener (redirect to HTTPS or forward if no certificate)
# -----------------------------------------------------------------------------

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main["api"].arn
  }
}

# -----------------------------------------------------------------------------
# Listener Rules for Path-Based Routing
# -----------------------------------------------------------------------------

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main["api"].arn
  }

  condition {
    path_pattern {
      values = ["/api/*", "/health", "/docs", "/openapi.json", "/redoc", "/metrics"]
    }
  }
}

resource "aws_lb_listener_rule" "orchestrator" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main["orchestrator"].arn
  }

  condition {
    path_pattern {
      values = ["/orchestrator/*"]
    }
  }
}
