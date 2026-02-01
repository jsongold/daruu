# Daru PDF AWS Infrastructure

This directory contains the AWS infrastructure configuration for Daru PDF, using Terraform for Infrastructure as Code.

## Architecture Overview

```
                    ┌─────────────────────────────────────────┐
                    │          CloudFront (Web UI)            │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────┴──────────────────────────┐
                    │      Application Load Balancer (ALB)    │
                    └──────────────┬──────────────────────────┘
                                   │
                        ┌──────────┴──────────┐
                        │                     │
                    ┌───▼────┐         ┌──────▼────┐
                    │  ECS   │         │  S3 +     │
                    │ Fargate│         │ CloudFront│
                    │ (API)  │         │  (Web UI) │
                    └───┬────┘         └───────────┘
                        │
                        │ HTTP/Contract
                    ┌───▼──────────────────────┐
                    │   ECS Fargate            │
                    │   (Orchestrator)         │
                    └───┬──────────────────────┘
                        │
                    ┌───▼──────────────────────────────┐
                    │   S3 Buckets                     │
                    │   - documents (PDF originals)    │
                    │   - previews (page thumbnails)   │
                    │   - crops (OCR crops)            │
                    │   - outputs (generated PDFs)     │
                    └──────────────────────────────────┘
                        │
                    ┌───▼──────────────┐
                    │  ElastiCache     │
                    │  (Redis)         │
                    └──────────────────┘
```

## Prerequisites

- AWS CLI v2 installed and configured
- Terraform v1.5.0 or later
- Docker installed
- AWS account with appropriate permissions

### Required AWS Permissions

The IAM user/role running Terraform needs permissions for:
- EC2 (VPC, Subnets, Security Groups, NAT Gateway)
- ECS (Clusters, Services, Task Definitions)
- ECR (Repositories)
- S3 (Buckets)
- ElastiCache (Redis)
- ELB (Application Load Balancer)
- CloudFront (Distributions)
- IAM (Roles, Policies)
- CloudWatch (Log Groups)
- Secrets Manager

## Quick Start

### 1. Initial Setup

```bash
cd infra/aws/scripts

# Run setup script (creates Terraform backend, initializes Terraform)
./setup.sh dev
```

### 2. Configure Variables

Copy and edit the environment variables:

```bash
cp .env.aws.example .env.aws
# Edit .env.aws with your values
```

Edit Terraform variables:

```bash
cd terraform
# Edit terraform.tfvars with your configuration
```

### 3. Deploy Infrastructure

```bash
cd terraform

# Review the plan
terraform plan

# Apply the configuration
terraform apply
```

### 4. Deploy Services

```bash
cd scripts

# Deploy API service
./deploy.sh api

# Deploy Orchestrator service
./deploy.sh orchestrator

# Deploy Web UI
./deploy.sh web

# Or deploy all at once
./deploy.sh all
```

## Directory Structure

```
infra/aws/
├── terraform/
│   ├── main.tf              # Main infrastructure configuration
│   ├── variables.tf         # Input variables
│   ├── outputs.tf           # Output values
│   ├── provider.tf          # AWS provider configuration
│   └── modules/
│       ├── ecs/             # ECS Fargate service module
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── elasticache/     # ElastiCache Redis module
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── s3/              # S3 buckets module
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       └── alb/             # Application Load Balancer module
│           ├── main.tf
│           ├── variables.tf
│           └── outputs.tf
├── ecs/
│   ├── api/
│   │   ├── Dockerfile       # API Docker image
│   │   └── task-definition.json
│   └── web/
│       └── s3-cloudfront.yaml  # CloudFormation alternative
├── scripts/
│   ├── deploy.sh            # Deployment script
│   └── setup.sh             # Initial setup script
├── .env.aws.example         # Environment variables template
└── README.md                # This file
```

## Terraform Modules

### ECS Module

Creates ECS Fargate services with auto-scaling.

**Variables:**
| Name | Description | Default |
|------|-------------|---------|
| `name` | Service name | - |
| `image` | Docker image | - |
| `cpu` | CPU units (1 vCPU = 1024) | 256 |
| `memory` | Memory in MiB | 512 |
| `desired_count` | Desired task count | 1 |
| `min_count` | Minimum tasks | 1 |
| `max_count` | Maximum tasks | 10 |
| `env_vars` | Environment variables | {} |

**Outputs:**
- `service_name`: ECS service name
- `task_arn`: Task definition ARN

### ElastiCache Module

Creates ElastiCache Redis cluster.

**Variables:**
| Name | Description | Default |
|------|-------------|---------|
| `name` | Cluster name | - |
| `node_type` | Instance type | cache.t3.micro |
| `num_cache_nodes` | Number of nodes | 1 |

**Outputs:**
- `endpoint`: Redis endpoint
- `port`: Redis port (6379)

### S3 Module

Creates S3 buckets with lifecycle policies.

**Variables:**
| Name | Description | Default |
|------|-------------|---------|
| `bucket_names` | Map of bucket names | - |
| `lifecycle_days` | Days to Glacier | 30 |
| `expiration_days` | Days to delete | 90 |

**Outputs:**
- `bucket_arns`: Map of bucket ARNs
- `bucket_names`: Map of bucket names

### ALB Module

Creates Application Load Balancer with target groups.

**Variables:**
| Name | Description | Default |
|------|-------------|---------|
| `name` | ALB name | - |
| `vpc_id` | VPC ID | - |
| `subnets` | Subnet IDs | - |
| `target_groups` | Target group configs | - |

**Outputs:**
- `dns_name`: ALB DNS name
- `arn`: ALB ARN

## ECS Service Specifications

### API Service
- **CPU**: 2 vCPU (2048 units)
- **Memory**: 4 GiB (4096 MiB)
- **Min Instances**: 1
- **Max Instances**: 10
- **Health Check**: `/health`

### Orchestrator Service
- **CPU**: 1 vCPU (1024 units)
- **Memory**: 2 GiB (2048 MiB)
- **Min Instances**: 0
- **Max Instances**: 5
- **Health Check**: `/health`

## Environment Variables

### Required for API Service
- `DARU_SUPABASE_URL`: Supabase project URL
- `DARU_SUPABASE_SERVICE_KEY`: Supabase service role key
- `DARU_OPENAI_API_KEY`: OpenAI API key

### S3 Bucket Configuration
- `AWS_S3_BUCKET_DOCUMENTS`: Documents bucket
- `AWS_S3_BUCKET_PREVIEWS`: Previews bucket
- `AWS_S3_BUCKET_CROPS`: OCR crops bucket
- `AWS_S3_BUCKET_OUTPUTS`: Output files bucket

### Redis Configuration
- `AWS_REDIS_ENDPOINT`: ElastiCache endpoint
- `AWS_REDIS_PORT`: Redis port (default: 6379)

## Deployment

### Deploy API

```bash
./scripts/deploy.sh api
```

This will:
1. Build the Docker image
2. Push to ECR
3. Update the ECS service
4. Wait for deployment to complete

### Deploy Web UI

```bash
./scripts/deploy.sh web
```

This will:
1. Build the web application (`npm run build`)
2. Sync files to S3
3. Invalidate CloudFront cache

### Check Status

```bash
./scripts/deploy.sh status
```

## Monitoring

### CloudWatch Logs

- API logs: `/ecs/daru-pdf-{environment}-api`
- Orchestrator logs: `/ecs/daru-pdf-{environment}-orchestrator`

### CloudWatch Metrics

ECS services publish metrics for:
- CPU utilization
- Memory utilization
- Request count (via ALB)

### Health Checks

All services expose `/health` endpoint returning:
```json
{"status": "healthy"}
```

## Secrets Management

Sensitive values are stored in AWS Secrets Manager:
- Secret name: `daru-pdf-{environment}-secrets`
- Keys: `DARU_SUPABASE_URL`, `DARU_SUPABASE_SERVICE_KEY`, `DARU_OPENAI_API_KEY`, etc.

## Cost Optimization

### Development Environment
- Use `cache.t3.micro` for Redis
- Set orchestrator `min_count = 0`
- Use Fargate Spot for non-critical workloads

### Production Environment
- Enable NAT Gateway for high availability
- Use reserved capacity for predictable workloads
- Enable S3 Intelligent-Tiering

## Troubleshooting

### ECS Service Won't Start

1. Check CloudWatch logs for errors
2. Verify ECR image exists
3. Check security group rules
4. Verify IAM roles and policies

### Cannot Connect to Redis

1. Check security group allows port 6379
2. Verify ECS tasks are in the same VPC
3. Check ElastiCache subnet group

### CloudFront 403 Errors

1. Check S3 bucket policy allows CloudFront OAI
2. Verify origin access identity is configured
3. Check S3 bucket public access block settings

## Cleanup

To destroy all resources:

```bash
cd terraform
terraform destroy
```

**Warning**: This will delete all infrastructure including data in S3 buckets.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review CloudWatch logs
3. Open an issue in the repository
