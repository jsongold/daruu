# Daru PDF GCP Infrastructure

This directory contains the infrastructure configuration for deploying Daru PDF to Google Cloud Platform.

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │         Cloud Load Balancer             │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
              ┌─────▼─────┐               ┌───────▼───────┐
              │  Cloud    │               │    Cloud      │
              │  Run      │               │    Run        │
              │  (API)    │               │    (Web UI)   │
              │ 2CPU/4GiB │               │  1CPU/1GiB    │
              └─────┬─────┘               └───────────────┘
                    │
                    │ HTTP/Contract
              ┌─────▼──────────────────┐
              │   Cloud Run            │
              │   (Orchestrator)       │
              │   1CPU/2GiB            │
              └─────┬──────────────────┘
                    │
     ┌──────────────┼──────────────────┐
     │              │                  │
┌────▼────┐   ┌─────▼─────┐    ┌───────▼───────┐
│ Cloud   │   │  Cloud    │    │   Supabase    │
│ Storage │   │ Memorystore│   │  (External)   │
│ (GCS)   │   │  (Redis)  │    │  DB/Auth/     │
│         │   │           │    │  Storage      │
└─────────┘   └───────────┘    └───────────────┘
```

## Directory Structure

```
infra/gcp/
├── terraform/                  # Infrastructure as Code
│   ├── main.tf                 # Main configuration
│   ├── variables.tf            # Variable definitions
│   ├── outputs.tf              # Output definitions
│   ├── provider.tf             # Provider configuration
│   └── modules/
│       ├── cloud-run/          # Cloud Run service module
│       ├── memorystore/        # Redis module
│       └── storage/            # GCS bucket module
├── cloud-run/                  # Docker configurations
│   ├── api/
│   │   ├── Dockerfile
│   │   └── cloudbuild.yaml
│   └── web/
│       ├── Dockerfile
│       ├── nginx.conf
│       └── cloudbuild.yaml
├── scripts/
│   ├── setup.sh                # Initial setup script
│   └── deploy.sh               # Deployment script
├── .env.gcp.example            # Environment variables template
└── README.md                   # This file
```

## Prerequisites

1. **GCP Account** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Terraform** >= 1.5.0 installed
4. **Docker** installed (for local builds)

## Quick Start

### 1. Initial Setup

```bash
cd infra/gcp/scripts
chmod +x setup.sh deploy.sh

# Run setup (creates APIs, Artifact Registry, Terraform state bucket)
./setup.sh YOUR_PROJECT_ID asia-northeast1
```

### 2. Configure Variables

```bash
cd infra/gcp/terraform

# Edit terraform.tfvars with your configuration
vim terraform.tfvars

# Set sensitive variables via environment
export TF_VAR_supabase_url="https://your-project.supabase.co"
export TF_VAR_supabase_service_key="your-service-key"
export TF_VAR_openai_api_key="your-openai-key"
```

### 3. Deploy Infrastructure

```bash
cd infra/gcp/terraform

# Preview changes
terraform plan

# Apply changes
terraform apply
```

### 4. Deploy Services

```bash
cd infra/gcp/scripts

# Deploy all services
./deploy.sh all

# Or deploy individually
./deploy.sh api
./deploy.sh web
./deploy.sh orchestrator
```

## Cloud Run Service Specifications

| Service      | CPU    | Memory | Min Instances | Max Instances | Timeout |
|--------------|--------|--------|---------------|---------------|---------|
| API          | 2 vCPU | 4 GiB  | 0             | 10            | 300s    |
| Web          | 1 vCPU | 1 GiB  | 1             | 3             | -       |
| Orchestrator | 1 vCPU | 2 GiB  | 0             | 5             | -       |

## Storage Buckets

Four GCS buckets are created for different purposes:

| Bucket Type | Purpose                           | Lifecycle         |
|-------------|-----------------------------------|-------------------|
| documents   | Original uploaded PDFs and images | 30d -> Coldline   |
| previews    | Generated preview images          | 30d -> Coldline   |
| crops       | OCR cropped regions               | 30d -> Coldline   |
| outputs     | Generated/filled PDFs             | 30d -> Coldline   |

## Terraform Modules

### cloud-run

Creates a Cloud Run service with:
- Configurable CPU, memory, instances
- Environment variables and secrets (via Secret Manager)
- VPC connector for Redis access
- Health check probes
- IAM for public/authenticated access

### memorystore

Creates a Cloud Memorystore Redis instance with:
- Configurable tier (BASIC or STANDARD_HA)
- Configurable memory size
- VPC network integration

### storage

Creates GCS buckets with:
- Lifecycle policies (transition to coldline, deletion)
- Versioning
- CORS configuration
- IAM bindings for Cloud Run access

## Environment Variables

### Required for All Services

| Variable                         | Description                    |
|----------------------------------|--------------------------------|
| `GCP_PROJECT_ID`                 | GCP project ID                 |
| `GCP_REGION`                     | GCP region                     |
| `DARU_SUPABASE_URL`              | Supabase project URL           |
| `DARU_SUPABASE_SERVICE_KEY`      | Supabase service role key      |
| `DARU_OPENAI_API_KEY`            | OpenAI API key                 |

### API Service Specific

| Variable                              | Default  | Description              |
|---------------------------------------|----------|--------------------------|
| `DARU_DEBUG`                          | false    | Enable debug mode        |
| `DARU_API_PREFIX`                     | /api/v1  | API route prefix         |
| `DARU_DEFAULT_CONFIDENCE_THRESHOLD`   | 0.7      | Auto-acceptance threshold|
| `GCP_STORAGE_BUCKET_DOCUMENTS`        | -        | Documents bucket name    |
| `GCP_REDIS_HOST`                      | -        | Redis host               |
| `GCP_REDIS_PORT`                      | 6379     | Redis port               |

## Cloud Build Triggers

To set up automatic deployments on push:

```bash
# Create trigger for API service
gcloud builds triggers create github \
    --name="daru-pdf-api-deploy" \
    --repo-owner="YOUR_GITHUB_ORG" \
    --repo-name="daru-pdf" \
    --branch-pattern="^main$" \
    --build-config="infra/gcp/cloud-run/api/cloudbuild.yaml"

# Create trigger for Web service
gcloud builds triggers create github \
    --name="daru-pdf-web-deploy" \
    --repo-owner="YOUR_GITHUB_ORG" \
    --repo-name="daru-pdf" \
    --branch-pattern="^main$" \
    --build-config="infra/gcp/cloud-run/web/cloudbuild.yaml"
```

## Monitoring and Logging

- **Logs**: Cloud Logging (automatic with Cloud Run)
- **Metrics**: Cloud Monitoring (automatic with Cloud Run)
- **Alerts**: Configure in Cloud Monitoring console

### Useful gcloud commands

```bash
# View service logs
gcloud run services logs read daru-pdf-dev-api --region asia-northeast1

# View service status
gcloud run services describe daru-pdf-dev-api --region asia-northeast1

# View revisions
gcloud run revisions list --service daru-pdf-dev-api --region asia-northeast1
```

## Cost Optimization

1. **Min instances = 0**: Services scale to zero when not in use
2. **CPU throttling**: CPU is throttled when idle (cpu_idle = true)
3. **Lifecycle policies**: Objects transition to coldline and are deleted automatically
4. **Regional resources**: All resources in single region (asia-northeast1)

## Security

1. **Secret Manager**: Sensitive values stored in Secret Manager
2. **VPC Connector**: Redis access via private network
3. **IAM**: Least privilege for service accounts
4. **HTTPS**: All Cloud Run services use HTTPS by default

## Troubleshooting

### Service not starting

```bash
# Check logs
gcloud run services logs read SERVICE_NAME --region asia-northeast1

# Check service status
gcloud run services describe SERVICE_NAME --region asia-northeast1 --format yaml
```

### Redis connection issues

1. Ensure VPC connector is properly configured
2. Check if Cloud Run service has the VPC connector attached
3. Verify Redis instance is in the same region

### Build failures

```bash
# View build logs
gcloud builds list --limit 5
gcloud builds log BUILD_ID
```

## Cleanup

To destroy all resources:

```bash
cd infra/gcp/terraform

# Preview destruction
terraform plan -destroy

# Destroy all resources
terraform destroy
```

**Warning**: This will delete all data in Cloud Storage buckets and Redis.
