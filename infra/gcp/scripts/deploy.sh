#!/bin/bash
# Deployment script for Daru PDF GCP Services
#
# This script builds and deploys services to Cloud Run.
#
# Usage: ./deploy.sh [api|web|orchestrator|all]
#
# Options:
#   api          - Deploy API service only
#   web          - Deploy Web service only
#   orchestrator - Deploy Orchestrator service only
#   all          - Deploy all services

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../../.."
INFRA_DIR="${SCRIPT_DIR}/.."

# Default values (can be overridden by environment variables)
GCP_PROJECT_ID="${GCP_PROJECT_ID:-}"
GCP_REGION="${GCP_REGION:-asia-northeast1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

check_dependencies() {
    log_info "Checking dependencies..."

    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed"
    fi

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
    fi

    log_success "All dependencies are available"
}

get_project_id() {
    if [ -z "$GCP_PROJECT_ID" ]; then
        GCP_PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
        if [ -z "$GCP_PROJECT_ID" ]; then
            log_error "No project ID set. Use: export GCP_PROJECT_ID=your-project-id"
        fi
    fi
    echo "$GCP_PROJECT_ID"
}

configure_docker() {
    log_info "Configuring Docker for Artifact Registry..."
    gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet
}

get_image_tag() {
    # Use git short SHA if available, otherwise use timestamp
    if command -v git &> /dev/null && git rev-parse --short HEAD &> /dev/null; then
        echo "$(git rev-parse --short HEAD)"
    else
        echo "$(date +%Y%m%d%H%M%S)"
    fi
}

deploy_api() {
    local project_id="$1"
    local region="$2"
    local tag="$3"
    local image="${region}-docker.pkg.dev/${project_id}/daru-pdf/api"
    local service_name="daru-pdf-${ENVIRONMENT}-api"

    log_info "Building API service..."

    cd "$PROJECT_ROOT"
    docker build \
        -t "${image}:${tag}" \
        -t "${image}:latest" \
        -f "${INFRA_DIR}/cloud-run/api/Dockerfile" \
        .

    log_info "Pushing API image..."
    docker push "${image}:${tag}"
    docker push "${image}:latest"

    log_info "Deploying API service to Cloud Run..."
    gcloud run deploy "$service_name" \
        --image "${image}:${tag}" \
        --region "$region" \
        --platform managed \
        --allow-unauthenticated \
        --cpu 2 \
        --memory 4Gi \
        --min-instances 0 \
        --max-instances 10 \
        --timeout 300s \
        --port 8080 \
        --set-env-vars "DARU_API_PREFIX=/api/v1,DARU_DEBUG=$([ "$ENVIRONMENT" = "prod" ] && echo "false" || echo "true")"

    log_success "API service deployed: $(gcloud run services describe "$service_name" --region "$region" --format 'value(status.url)')"
}

deploy_web() {
    local project_id="$1"
    local region="$2"
    local tag="$3"
    local image="${region}-docker.pkg.dev/${project_id}/daru-pdf/web"
    local service_name="daru-pdf-${ENVIRONMENT}-web"

    # Get API URL for frontend
    local api_service_name="daru-pdf-${ENVIRONMENT}-api"
    local api_url=""

    if gcloud run services describe "$api_service_name" --region "$region" &> /dev/null; then
        api_url=$(gcloud run services describe "$api_service_name" --region "$region" --format 'value(status.url)')
    else
        log_warning "API service not found. Web UI may not function correctly."
        api_url=""
    fi

    log_info "Building Web service..."

    cd "$PROJECT_ROOT"
    docker build \
        -t "${image}:${tag}" \
        -t "${image}:latest" \
        -f "${INFRA_DIR}/cloud-run/web/Dockerfile" \
        --build-arg "VITE_API_URL=${api_url}" \
        .

    log_info "Pushing Web image..."
    docker push "${image}:${tag}"
    docker push "${image}:latest"

    log_info "Deploying Web service to Cloud Run..."
    gcloud run deploy "$service_name" \
        --image "${image}:${tag}" \
        --region "$region" \
        --platform managed \
        --allow-unauthenticated \
        --cpu 1 \
        --memory 1Gi \
        --min-instances 1 \
        --max-instances 3 \
        --port 8080

    log_success "Web service deployed: $(gcloud run services describe "$service_name" --region "$region" --format 'value(status.url)')"
}

deploy_orchestrator() {
    local project_id="$1"
    local region="$2"
    local tag="$3"
    local image="${region}-docker.pkg.dev/${project_id}/daru-pdf/orchestrator"
    local service_name="daru-pdf-${ENVIRONMENT}-orchestrator"

    # Check if orchestrator directory exists
    if [ ! -d "${PROJECT_ROOT}/apps/orchestrator" ]; then
        log_warning "Orchestrator app directory not found. Skipping deployment."
        return 0
    fi

    log_info "Building Orchestrator service..."

    # Create a temporary Dockerfile for orchestrator if it doesn't exist
    local dockerfile="${INFRA_DIR}/cloud-run/orchestrator/Dockerfile"
    if [ ! -f "$dockerfile" ]; then
        mkdir -p "$(dirname "$dockerfile")"
        cat > "$dockerfile" << 'DOCKERFILE'
# Dockerfile for Daru PDF Orchestrator Service
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

WORKDIR /app
COPY apps/orchestrator/pyproject.toml .
RUN pip install --no-cache-dir .

COPY apps/orchestrator/app ./app/

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app && \
    chown -R app:app /app
USER app

EXPOSE ${PORT}
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
DOCKERFILE
    fi

    cd "$PROJECT_ROOT"
    docker build \
        -t "${image}:${tag}" \
        -t "${image}:latest" \
        -f "$dockerfile" \
        .

    log_info "Pushing Orchestrator image..."
    docker push "${image}:${tag}"
    docker push "${image}:latest"

    log_info "Deploying Orchestrator service to Cloud Run..."
    gcloud run deploy "$service_name" \
        --image "${image}:${tag}" \
        --region "$region" \
        --platform managed \
        --no-allow-unauthenticated \
        --cpu 1 \
        --memory 2Gi \
        --min-instances 0 \
        --max-instances 5 \
        --port 8080

    log_success "Orchestrator service deployed: $(gcloud run services describe "$service_name" --region "$region" --format 'value(status.url)')"
}

print_usage() {
    echo "Usage: $0 [api|web|orchestrator|all]"
    echo ""
    echo "Services:"
    echo "  api          - Deploy API service only"
    echo "  web          - Deploy Web service only"
    echo "  orchestrator - Deploy Orchestrator service only"
    echo "  all          - Deploy all services"
    echo ""
    echo "Environment variables:"
    echo "  GCP_PROJECT_ID - GCP project ID (required if not set in gcloud)"
    echo "  GCP_REGION     - GCP region (default: asia-northeast1)"
    echo "  ENVIRONMENT    - Environment name (default: dev)"
}

# Main
main() {
    local service="${1:-}"

    if [ -z "$service" ]; then
        print_usage
        exit 1
    fi

    echo "=============================================="
    echo "Daru PDF GCP Deployment"
    echo "=============================================="
    echo ""

    check_dependencies

    local project_id
    project_id=$(get_project_id)
    local tag
    tag=$(get_image_tag)

    log_info "Project ID: $project_id"
    log_info "Region: $GCP_REGION"
    log_info "Environment: $ENVIRONMENT"
    log_info "Image tag: $tag"
    echo ""

    configure_docker

    case "$service" in
        api)
            deploy_api "$project_id" "$GCP_REGION" "$tag"
            ;;
        web)
            deploy_web "$project_id" "$GCP_REGION" "$tag"
            ;;
        orchestrator)
            deploy_orchestrator "$project_id" "$GCP_REGION" "$tag"
            ;;
        all)
            deploy_api "$project_id" "$GCP_REGION" "$tag"
            deploy_web "$project_id" "$GCP_REGION" "$tag"
            deploy_orchestrator "$project_id" "$GCP_REGION" "$tag"
            ;;
        *)
            log_error "Unknown service: $service"
            print_usage
            exit 1
            ;;
    esac

    echo ""
    log_success "Deployment complete!"
}

main "$@"
