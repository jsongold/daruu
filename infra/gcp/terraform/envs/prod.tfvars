# Production environment configuration

environment = "prod"

# Cloud Run - keep warm for latency
api_min_instances = 1
api_max_instances = 10
api_cpu           = "2"
api_memory        = "4Gi"

web_min_instances = 1
web_max_instances = 3
web_cpu           = "1"
web_memory        = "1Gi"

orchestrator_min_instances = 0
orchestrator_max_instances = 5
orchestrator_cpu           = "1"
orchestrator_memory        = "2Gi"

rule_service_min_instances = 0
rule_service_max_instances = 3
rule_service_cpu           = "1"
rule_service_memory        = "2Gi"

# Redis - HA for production
redis_tier           = "STANDARD_HA"
redis_memory_size_gb = 2

# Storage
storage_lifecycle_days = 60
storage_delete_days    = 365

# CORS - restrict to production domain (update with your actual prod URL)
cors_origins = ["https://daru-pdf.example.com"]
