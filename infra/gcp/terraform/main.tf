# Main Terraform configuration for Daru PDF GCP Infrastructure
#
# This configuration deploys:
# - Cloud Run services (API, Web, Orchestrator)
# - Cloud Storage buckets (documents, previews, crops, outputs)
# - Memorystore Redis instance
# - VPC connector for Cloud Run to Redis connectivity
# - Artifact Registry for container images

locals {
  # Common labels for all resources
  common_labels = {
    project     = "daru-pdf"
    environment = var.environment
    managed_by  = "terraform"
  }

  # Service naming convention
  service_prefix = "daru-pdf-${var.environment}"
}

# -----------------------------------------------------------------------------
# Enable Required APIs
# -----------------------------------------------------------------------------

resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "vpcaccess.googleapis.com",
    "redis.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Artifact Registry for Container Images
# -----------------------------------------------------------------------------

resource "google_artifact_registry_repository" "daru_pdf" {
  location      = var.region
  repository_id = "daru-pdf"
  description   = "Container images for Daru PDF services"
  format        = "DOCKER"
  labels        = local.common_labels

  depends_on = [google_project_service.required_apis]
}

# -----------------------------------------------------------------------------
# VPC Connector for Cloud Run to Redis
# -----------------------------------------------------------------------------

resource "google_vpc_access_connector" "connector" {
  name          = var.vpc_connector_name
  region        = var.region
  ip_cidr_range = var.vpc_connector_cidr
  network       = "default"

  depends_on = [google_project_service.required_apis]
}

# -----------------------------------------------------------------------------
# Storage Buckets Module
# -----------------------------------------------------------------------------

module "storage" {
  source = "./modules/storage"

  project_id     = var.project_id
  environment    = var.environment
  location       = var.storage_location
  lifecycle_days = var.storage_lifecycle_days
  delete_days    = var.storage_delete_days
  labels         = local.common_labels

  bucket_names = ["documents", "previews", "crops", "outputs"]

  depends_on = [google_project_service.required_apis]
}

# -----------------------------------------------------------------------------
# Memorystore Redis Module
# -----------------------------------------------------------------------------

module "memorystore" {
  source = "./modules/memorystore"

  project_id     = var.project_id
  name           = "${local.service_prefix}-redis"
  region         = var.region
  tier           = var.redis_tier
  memory_size_gb = var.redis_memory_size_gb
  labels         = local.common_labels

  depends_on = [google_project_service.required_apis]
}

# -----------------------------------------------------------------------------
# Cloud Run Services
# -----------------------------------------------------------------------------

# API Service
module "cloud_run_api" {
  source = "./modules/cloud-run"

  project_id    = var.project_id
  name          = "${local.service_prefix}-api"
  location      = var.region
  image         = var.api_image != "" ? var.api_image : "${var.region}-docker.pkg.dev/${var.project_id}/daru-pdf/api:latest"
  cpu           = var.api_cpu
  memory        = var.api_memory
  min_instances = var.api_min_instances
  max_instances = var.api_max_instances
  timeout       = var.api_timeout
  labels        = local.common_labels

  # Allow public access
  allow_unauthenticated = true

  # VPC connector for Redis access
  vpc_connector_id = google_vpc_access_connector.connector.id

  env_vars = {
    DARU_DEBUG                        = var.environment == "prod" ? "false" : "true"
    DARU_API_PREFIX                   = "/api/v1"
    DARU_DEFAULT_CONFIDENCE_THRESHOLD = "0.7"
    DARU_MAX_STEPS_PER_RUN            = "100"
    GCP_PROJECT_ID                    = var.project_id
    GCP_REGION                        = var.region
    GCP_STORAGE_BUCKET_DOCUMENTS      = module.storage.bucket_names["documents"]
    GCP_STORAGE_BUCKET_PREVIEWS       = module.storage.bucket_names["previews"]
    GCP_STORAGE_BUCKET_CROPS          = module.storage.bucket_names["crops"]
    GCP_STORAGE_BUCKET_OUTPUTS        = module.storage.bucket_names["outputs"]
    GCP_REDIS_HOST                    = module.memorystore.host
    GCP_REDIS_PORT                    = tostring(module.memorystore.port)
    ORCHESTRATOR_URL                  = "https://${local.service_prefix}-orchestrator-${data.google_project.current.number}.${var.region}.run.app"
  }

  secret_env_vars = {
    DARU_SUPABASE_URL         = var.supabase_url
    DARU_SUPABASE_SERVICE_KEY = var.supabase_service_key
    DARU_SUPABASE_ANON_KEY    = var.supabase_anon_key
    DARU_OPENAI_API_KEY       = var.openai_api_key
  }

  depends_on = [
    google_project_service.required_apis,
    google_artifact_registry_repository.daru_pdf,
    module.storage,
    module.memorystore,
  ]
}

# Web Service
module "cloud_run_web" {
  source = "./modules/cloud-run"

  project_id    = var.project_id
  name          = "${local.service_prefix}-web"
  location      = var.region
  image         = var.web_image != "" ? var.web_image : "${var.region}-docker.pkg.dev/${var.project_id}/daru-pdf/web:latest"
  cpu           = var.web_cpu
  memory        = var.web_memory
  min_instances = var.web_min_instances
  max_instances = var.web_max_instances
  labels        = local.common_labels

  # Allow public access
  allow_unauthenticated = true

  env_vars = {
    VITE_API_URL = module.cloud_run_api.service_url
  }

  depends_on = [
    google_project_service.required_apis,
    google_artifact_registry_repository.daru_pdf,
    module.cloud_run_api,
  ]
}

# Orchestrator Service
module "cloud_run_orchestrator" {
  source = "./modules/cloud-run"

  project_id    = var.project_id
  name          = "${local.service_prefix}-orchestrator"
  location      = var.region
  image         = var.orchestrator_image != "" ? var.orchestrator_image : "${var.region}-docker.pkg.dev/${var.project_id}/daru-pdf/orchestrator:latest"
  cpu           = var.orchestrator_cpu
  memory        = var.orchestrator_memory
  min_instances = var.orchestrator_min_instances
  max_instances = var.orchestrator_max_instances
  labels        = local.common_labels

  # Internal service - not publicly accessible
  allow_unauthenticated = false

  # VPC connector for Redis access
  vpc_connector_id = google_vpc_access_connector.connector.id

  env_vars = {
    DARU_DEBUG     = var.environment == "prod" ? "false" : "true"
    GCP_PROJECT_ID = var.project_id
    GCP_REGION     = var.region
    GCP_REDIS_HOST = module.memorystore.host
    GCP_REDIS_PORT = tostring(module.memorystore.port)
    API_URL        = module.cloud_run_api.service_url
  }

  secret_env_vars = {
    DARU_SUPABASE_URL         = var.supabase_url
    DARU_SUPABASE_SERVICE_KEY = var.supabase_service_key
    DARU_OPENAI_API_KEY       = var.openai_api_key
  }

  depends_on = [
    google_project_service.required_apis,
    google_artifact_registry_repository.daru_pdf,
    module.storage,
    module.memorystore,
    module.cloud_run_api,
  ]
}

# Rule Service
module "cloud_run_rule_service" {
  source = "./modules/cloud-run"

  project_id    = var.project_id
  name          = "${local.service_prefix}-rule-service"
  location      = var.region
  image         = var.rule_service_image != "" ? var.rule_service_image : "${var.region}-docker.pkg.dev/${var.project_id}/daru-pdf/rule-service:latest"
  cpu           = var.rule_service_cpu
  memory        = var.rule_service_memory
  min_instances = var.rule_service_min_instances
  max_instances = var.rule_service_max_instances
  labels        = local.common_labels

  # Internal service - not publicly accessible
  allow_unauthenticated = false

  # VPC connector for Redis access
  vpc_connector_id = google_vpc_access_connector.connector.id

  env_vars = {
    DARU_DEBUG     = var.environment == "prod" ? "false" : "true"
    GCP_PROJECT_ID = var.project_id
    GCP_REGION     = var.region
    GCP_REDIS_HOST = module.memorystore.host
    GCP_REDIS_PORT = tostring(module.memorystore.port)
    API_URL        = module.cloud_run_api.service_url
  }

  secret_env_vars = {
    DARU_SUPABASE_URL         = var.supabase_url
    DARU_SUPABASE_SERVICE_KEY = var.supabase_service_key
    DARU_OPENAI_API_KEY       = var.openai_api_key
  }

  depends_on = [
    google_project_service.required_apis,
    google_artifact_registry_repository.daru_pdf,
    module.memorystore,
    module.cloud_run_api,
  ]
}

# -----------------------------------------------------------------------------
# Workload Identity Federation (GitHub Actions)
# -----------------------------------------------------------------------------

module "workload_identity" {
  source = "./modules/workload-identity"

  project_id  = var.project_id
  github_repo = var.github_repo

  depends_on = [google_project_service.required_apis]
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "google_project" "current" {
  project_id = var.project_id
}
