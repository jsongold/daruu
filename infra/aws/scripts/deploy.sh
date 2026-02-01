#!/bin/bash
# Deployment script for Daru PDF AWS services
# Usage: ./deploy.sh [api|orchestrator|web|all]

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

# AWS Configuration
AWS_REGION="${AWS_REGION:-ap-northeast-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Project Configuration
PROJECT_NAME="${PROJECT_NAME:-daru-pdf}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')}"

# ECS Configuration
ECS_CLUSTER="${PROJECT_NAME}-${ENVIRONMENT}-cluster"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed."
        exit 1
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials are not configured."
        exit 1
    fi
}

ecr_login() {
    log_step "Logging into ECR..."
    aws ecr get-login-password --region "${AWS_REGION}" | \
        docker login --username AWS --password-stdin "${ECR_REGISTRY}"
}

# -----------------------------------------------------------------------------
# API Deployment
# -----------------------------------------------------------------------------

deploy_api() {
    log_info "Deploying API service..."

    local SERVICE_NAME="${PROJECT_NAME}-${ENVIRONMENT}-api"
    local ECR_REPO="${ECR_REGISTRY}/${SERVICE_NAME}"

    # Build Docker image
    log_step "Building Docker image..."
    cd "${PROJECT_ROOT}"
    docker build \
        -f infra/aws/ecs/api/Dockerfile \
        -t "${SERVICE_NAME}:${IMAGE_TAG}" \
        -t "${SERVICE_NAME}:latest" \
        .

    # Tag for ECR
    docker tag "${SERVICE_NAME}:${IMAGE_TAG}" "${ECR_REPO}:${IMAGE_TAG}"
    docker tag "${SERVICE_NAME}:latest" "${ECR_REPO}:latest"

    # Push to ECR
    log_step "Pushing image to ECR..."
    docker push "${ECR_REPO}:${IMAGE_TAG}"
    docker push "${ECR_REPO}:latest"

    # Update ECS service
    log_step "Updating ECS service..."
    aws ecs update-service \
        --cluster "${ECS_CLUSTER}" \
        --service "${SERVICE_NAME}" \
        --force-new-deployment \
        --region "${AWS_REGION}"

    # Wait for deployment
    log_step "Waiting for deployment to complete..."
    aws ecs wait services-stable \
        --cluster "${ECS_CLUSTER}" \
        --services "${SERVICE_NAME}" \
        --region "${AWS_REGION}"

    log_info "API deployment complete!"
}

# -----------------------------------------------------------------------------
# Orchestrator Deployment
# -----------------------------------------------------------------------------

deploy_orchestrator() {
    log_info "Deploying Orchestrator service..."

    local SERVICE_NAME="${PROJECT_NAME}-${ENVIRONMENT}-orchestrator"
    local ECR_REPO="${ECR_REGISTRY}/${SERVICE_NAME}"

    # Build Docker image
    log_step "Building Docker image..."
    cd "${PROJECT_ROOT}"

    # Create Dockerfile for orchestrator if it doesn't exist
    if [[ ! -f "infra/aws/ecs/orchestrator/Dockerfile" ]]; then
        log_warn "Creating Dockerfile for orchestrator..."
        mkdir -p infra/aws/ecs/orchestrator
        cat > infra/aws/ecs/orchestrator/Dockerfile <<'DOCKERFILE'
# Daru PDF Orchestrator Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8001

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/orchestrator/pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

COPY apps/orchestrator/app ./app

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
DOCKERFILE
    fi

    docker build \
        -f infra/aws/ecs/orchestrator/Dockerfile \
        -t "${SERVICE_NAME}:${IMAGE_TAG}" \
        -t "${SERVICE_NAME}:latest" \
        .

    # Tag for ECR
    docker tag "${SERVICE_NAME}:${IMAGE_TAG}" "${ECR_REPO}:${IMAGE_TAG}"
    docker tag "${SERVICE_NAME}:latest" "${ECR_REPO}:latest"

    # Push to ECR
    log_step "Pushing image to ECR..."
    docker push "${ECR_REPO}:${IMAGE_TAG}"
    docker push "${ECR_REPO}:latest"

    # Update ECS service
    log_step "Updating ECS service..."
    aws ecs update-service \
        --cluster "${ECS_CLUSTER}" \
        --service "${SERVICE_NAME}" \
        --force-new-deployment \
        --region "${AWS_REGION}"

    # Wait for deployment
    log_step "Waiting for deployment to complete..."
    aws ecs wait services-stable \
        --cluster "${ECS_CLUSTER}" \
        --services "${SERVICE_NAME}" \
        --region "${AWS_REGION}"

    log_info "Orchestrator deployment complete!"
}

# -----------------------------------------------------------------------------
# Web UI Deployment
# -----------------------------------------------------------------------------

deploy_web() {
    log_info "Deploying Web UI..."

    # Get S3 bucket and CloudFront distribution from Terraform outputs
    cd "${TERRAFORM_DIR}"
    local WEB_BUCKET=$(terraform output -raw web_bucket_name 2>/dev/null || echo "")
    local CF_DISTRIBUTION=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")

    if [[ -z "${WEB_BUCKET}" ]]; then
        log_error "Could not get S3 bucket name from Terraform outputs."
        log_error "Make sure Terraform has been applied."
        exit 1
    fi

    # Build web application
    log_step "Building web application..."
    cd "${PROJECT_ROOT}/apps/web"

    if [[ -f "package.json" ]]; then
        npm ci
        npm run build
    else
        log_error "No package.json found in apps/web"
        exit 1
    fi

    # Sync to S3
    log_step "Uploading to S3..."
    aws s3 sync dist/ "s3://${WEB_BUCKET}/" \
        --delete \
        --cache-control "max-age=31536000,public" \
        --exclude "index.html" \
        --region "${AWS_REGION}"

    # Upload index.html with no-cache
    aws s3 cp dist/index.html "s3://${WEB_BUCKET}/index.html" \
        --cache-control "no-cache,no-store,must-revalidate" \
        --content-type "text/html" \
        --region "${AWS_REGION}"

    # Invalidate CloudFront cache
    if [[ -n "${CF_DISTRIBUTION}" ]]; then
        log_step "Invalidating CloudFront cache..."
        aws cloudfront create-invalidation \
            --distribution-id "${CF_DISTRIBUTION}" \
            --paths "/*" \
            --region "${AWS_REGION}"
    fi

    log_info "Web UI deployment complete!"
}

# -----------------------------------------------------------------------------
# Deploy All
# -----------------------------------------------------------------------------

deploy_all() {
    log_info "Deploying all services..."
    ecr_login
    deploy_api
    deploy_orchestrator
    deploy_web
    log_info "All services deployed!"
}

# -----------------------------------------------------------------------------
# Status Check
# -----------------------------------------------------------------------------

check_status() {
    log_info "Checking deployment status..."

    echo ""
    log_step "ECS Services:"
    aws ecs describe-services \
        --cluster "${ECS_CLUSTER}" \
        --services "${PROJECT_NAME}-${ENVIRONMENT}-api" "${PROJECT_NAME}-${ENVIRONMENT}-orchestrator" \
        --query 'services[*].{Service:serviceName,Status:status,Running:runningCount,Desired:desiredCount}' \
        --output table \
        --region "${AWS_REGION}" 2>/dev/null || log_warn "Could not fetch ECS service status"

    echo ""
    log_step "ALB DNS Name:"
    cd "${TERRAFORM_DIR}"
    terraform output -raw alb_dns_name 2>/dev/null || log_warn "Could not fetch ALB DNS"

    echo ""
    log_step "CloudFront URL:"
    terraform output -raw web_url 2>/dev/null || log_warn "Could not fetch CloudFront URL"

    echo ""
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

usage() {
    echo "Usage: $0 [api|orchestrator|web|all|status]"
    echo ""
    echo "Commands:"
    echo "  api          Deploy API service to ECS"
    echo "  orchestrator Deploy Orchestrator service to ECS"
    echo "  web          Deploy Web UI to S3/CloudFront"
    echo "  all          Deploy all services"
    echo "  status       Check deployment status"
    echo ""
    echo "Environment variables:"
    echo "  AWS_REGION   AWS region (default: ap-northeast-1)"
    echo "  ENVIRONMENT  Environment name (default: dev)"
    echo "  IMAGE_TAG    Docker image tag (default: git short SHA)"
    echo ""
}

main() {
    local COMMAND="${1:-}"

    if [[ -z "${COMMAND}" ]]; then
        usage
        exit 1
    fi

    check_prerequisites

    case "${COMMAND}" in
        api)
            ecr_login
            deploy_api
            ;;
        orchestrator)
            ecr_login
            deploy_orchestrator
            ;;
        web)
            deploy_web
            ;;
        all)
            deploy_all
            ;;
        status)
            check_status
            ;;
        *)
            log_error "Unknown command: ${COMMAND}"
            usage
            exit 1
            ;;
    esac
}

main "$@"
