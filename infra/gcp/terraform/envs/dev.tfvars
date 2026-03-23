# Dev environment configuration

environment = "dev"

# Cloud Run - scale to zero for cost savings
api_min_instances = 0
api_max_instances = 3
api_cpu           = "1"
api_memory        = "2Gi"

web_min_instances = 0
web_max_instances = 2
web_cpu           = "1"
web_memory        = "512Mi"

orchestrator_min_instances = 0
orchestrator_max_instances = 2
orchestrator_cpu           = "1"
orchestrator_memory        = "1Gi"

rule_service_min_instances = 0
rule_service_max_instances = 2
rule_service_cpu           = "1"
rule_service_memory        = "1Gi"

# Redis - minimal
redis_tier           = "BASIC"
redis_memory_size_gb = 1

# Storage
storage_lifecycle_days = 30
storage_delete_days    = 90

# CORS - restrict to dev domain (update with your actual dev URL)
cors_origins = ["http://localhost:5173", "http://localhost:3000"]
