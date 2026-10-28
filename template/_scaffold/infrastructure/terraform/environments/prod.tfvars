project_name     = "CHANGE_ME" # e.g. "acme-lg-agent" — keep in sync with the copier project_slug
environment      = "prod"
aws_region       = "eu-central-1" # keep in sync with the aws_region copier variable
data_sensitivity = "internal" # keep in sync with the data_sensitivity copier variable
desired_count    = 2
cpu              = 512
memory           = 1024

# container_image left unset — see dev.tfvars. Before treating this as a real
# prod deploy, read infrastructure/terraform/README.md: this skeleton has no
# HTTPS/custom domain, no autoscaling policy, and desired_count here is a fixed
# floor, not a target driven by load.
