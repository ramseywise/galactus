project_name     = "CHANGE_ME" # e.g. "acme-lg-agent" — keep in sync with the copier project_slug
environment      = "dev"
aws_region       = "eu-central-1" # keep in sync with the aws_region copier variable
data_sensitivity = "internal" # keep in sync with the data_sensitivity copier variable
desired_count    = 1
cpu              = 256
memory           = 512

# container_image is left unset here on purpose — the ECS task definition falls
# back to "<ecr_repository_url>:latest" (see main.tf) until you push a real image
# and set this explicitly, e.g.:
# container_image = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/acme-lg-agent-dev:latest"
