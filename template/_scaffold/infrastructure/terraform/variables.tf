variable "project_name" {
  description = "Short name used to prefix/tag all resources (e.g. \"acme-lg-agent\")."
  type        = string
}

variable "aws_region" {
  description = <<-EOT
    AWS region to deploy into. Defaults to "eu-central-1" to match this
    template's `aws_region` copier variable default — .tf files aren't
    Jinja-templated by this repo's convention, so this can't read the actual
    copier answer. Keep this in sync manually if you change `aws_region` at
    generation time (or just override it via -var / a .tfvars file, which is
    the normal Terraform way to do this anyway).
  EOT
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Deployment environment name (dev, prod, ...) — used in tags and resource names."
  type        = string
  default     = "dev"
}

variable "data_sensitivity" {
  description = <<-EOT
    Data classification tag applied to every resource (public/internal/restricted/secret).
    Defaults to "internal" to match this template's `data_sensitivity` copier variable
    default — .tf files aren't Jinja-templated by this repo's convention, so this can't
    read the actual copier answer. Keep this in sync manually if you change
    `data_sensitivity` at generation time (or just override it via -var / a .tfvars file).
  EOT
  type        = string
  default     = "internal"
}

variable "container_port" {
  description = "Port the lg_agent container listens on. Must match LG_PORT."
  type        = number
  default     = 8010
}

variable "cpu" {
  description = "Fargate task CPU units (256 = .25 vCPU). See AWS Fargate CPU/memory combinations."
  type        = number
  default     = 256
}

variable "memory" {
  description = "Fargate task memory in MiB. Must be a valid pairing with `cpu` (see AWS docs)."
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Number of Fargate tasks to run. Kept at 1 for a starter skeleton — no autoscaling policy is defined beyond this static count."
  type        = number
  default     = 1
}

variable "container_image" {
  description = <<-EOT
    Full image URI to deploy (e.g. "<account>.dkr.ecr.eu-central-1.amazonaws.com/acme-lg-agent:latest").
    Left unset by default — the ECR repo is created by this stack, but pushing
    an image to it and wiring the resulting URI here is a separate step (build
    + push happens in CI/CD, not in this Terraform).
  EOT
  type        = string
  default     = ""
}

variable "lg_model" {
  description = "Value for the LG_MODEL env var (see .env.example)."
  type        = string
  default     = "claude-haiku-4-5-20251001"
}

variable "vectordb_path" {
  description = "Value for the VECTORDB_PATH env var. NOTE: on Fargate this path is ephemeral container storage unless you attach an EFS volume — this skeleton does not provision one. See README."
  type        = string
  default     = "data/stores/vectordb.duckdb"
}

variable "lg_checkpointer" {
  description = "Value for the LG_CHECKPOINTER env var (memory | sqlite)."
  type        = string
  default     = "memory"
}

variable "anthropic_api_key_secret_arn" {
  description = <<-EOT
    ARN of an existing AWS Secrets Manager secret holding ANTHROPIC_API_KEY.
    Left blank by default, in which case this stack creates an empty secret
    for you to populate manually (see README) rather than accepting the key
    as a Terraform variable — never pass secrets as plain tfvars/CLI args.
  EOT
  type        = string
  default     = ""
}
