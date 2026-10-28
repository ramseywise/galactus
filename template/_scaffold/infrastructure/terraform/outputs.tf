output "alb_dns_name" {
  description = "Public DNS name of the ALB — the service URL (HTTP only, see README)."
  value       = aws_lb.this.dns_name
}

output "service_url" {
  description = "Convenience http:// URL built from alb_dns_name."
  value       = "http://${aws_lb.this.dns_name}"
}

output "ecr_repository_url" {
  description = "Push images here (docker build/tag/push) before pointing container_image at them."
  value       = aws_ecr_repository.lg_agent.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  value = aws_ecs_service.lg_agent.name
}

output "anthropic_api_key_secret_arn" {
  description = "ARN of the Secrets Manager secret to populate with the real ANTHROPIC_API_KEY value."
  value       = local.anthropic_secret_arn
}
