#!/bin/bash
# Initial setup script for Daru PDF AWS infrastructure
# Usage: ./setup.sh [environment]

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

# Default environment
ENVIRONMENT="${1:-dev}"

# AWS Configuration
AWS_REGION="${AWS_REGION:-ap-northeast-1}"
PROJECT_NAME="daru-pdf"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    # Check Terraform
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install it first."
        exit 1
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials are not configured. Please run 'aws configure' first."
        exit 1
    fi

    log_info "All prerequisites are met."
}

create_terraform_backend() {
    log_info "Creating Terraform state backend..."

    local BUCKET_NAME="${PROJECT_NAME}-terraform-state-${ENVIRONMENT}"
    local TABLE_NAME="terraform-state-lock-${ENVIRONMENT}"

    # Create S3 bucket for state
    if ! aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
        log_info "Creating S3 bucket: ${BUCKET_NAME}"
        aws s3api create-bucket \
            --bucket "${BUCKET_NAME}" \
            --region "${AWS_REGION}" \
            --create-bucket-configuration LocationConstraint="${AWS_REGION}"

        aws s3api put-bucket-versioning \
            --bucket "${BUCKET_NAME}" \
            --versioning-configuration Status=Enabled

        aws s3api put-bucket-encryption \
            --bucket "${BUCKET_NAME}" \
            --server-side-encryption-configuration '{
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            }'

        aws s3api put-public-access-block \
            --bucket "${BUCKET_NAME}" \
            --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    else
        log_info "S3 bucket already exists: ${BUCKET_NAME}"
    fi

    # Create DynamoDB table for state locking
    if ! aws dynamodb describe-table --table-name "${TABLE_NAME}" &>/dev/null; then
        log_info "Creating DynamoDB table: ${TABLE_NAME}"
        aws dynamodb create-table \
            --table-name "${TABLE_NAME}" \
            --attribute-definitions AttributeName=LockID,AttributeType=S \
            --key-schema AttributeName=LockID,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --region "${AWS_REGION}"
    else
        log_info "DynamoDB table already exists: ${TABLE_NAME}"
    fi
}

create_secrets() {
    log_info "Setting up AWS Secrets Manager..."

    local SECRET_NAME="${PROJECT_NAME}-${ENVIRONMENT}-secrets"

    # Check if secret exists
    if ! aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" &>/dev/null; then
        log_info "Creating secret: ${SECRET_NAME}"

        # Read from .env.aws if it exists
        local ENV_FILE="${SCRIPT_DIR}/../.env.aws"
        if [[ -f "${ENV_FILE}" ]]; then
            log_info "Reading secrets from ${ENV_FILE}"

            # Parse .env file and create secret
            local SECRET_STRING="{"
            local FIRST=true

            while IFS='=' read -r key value; do
                # Skip comments and empty lines
                [[ -z "$key" || "$key" =~ ^# ]] && continue

                # Remove quotes from value
                value="${value%\"}"
                value="${value#\"}"

                if [[ "$FIRST" == "true" ]]; then
                    SECRET_STRING+="\"${key}\": \"${value}\""
                    FIRST=false
                else
                    SECRET_STRING+=", \"${key}\": \"${value}\""
                fi
            done < "${ENV_FILE}"

            SECRET_STRING+="}"

            aws secretsmanager create-secret \
                --name "${SECRET_NAME}" \
                --secret-string "${SECRET_STRING}" \
                --region "${AWS_REGION}"
        else
            log_warn "No .env.aws file found. Creating empty secret placeholder."
            aws secretsmanager create-secret \
                --name "${SECRET_NAME}" \
                --secret-string '{"PLACEHOLDER": "Update with actual secrets"}' \
                --region "${AWS_REGION}"
            log_warn "Please update the secret ${SECRET_NAME} with actual values."
        fi
    else
        log_info "Secret already exists: ${SECRET_NAME}"
    fi
}

init_terraform() {
    log_info "Initializing Terraform..."

    cd "${TERRAFORM_DIR}"

    # Create terraform.tfvars if it doesn't exist
    if [[ ! -f "terraform.tfvars" ]]; then
        log_info "Creating terraform.tfvars from template..."
        cat > terraform.tfvars <<EOF
# Terraform variables for ${PROJECT_NAME} - ${ENVIRONMENT}
# Generated by setup.sh on $(date)

aws_region  = "${AWS_REGION}"
environment = "${ENVIRONMENT}"
project_name = "${PROJECT_NAME}"

# Update these values as needed
api_cpu     = 2048
api_memory  = 4096
api_min_count = 1
api_max_count = 10

orchestrator_cpu    = 1024
orchestrator_memory = 2048
orchestrator_min_count = 0
orchestrator_max_count = 5

redis_node_type      = "cache.t3.micro"
redis_num_cache_nodes = 1

s3_lifecycle_days  = 30
s3_expiration_days = 90

# Sensitive values - set via environment variables or update here
# supabase_url        = ""
# supabase_service_key = ""
# supabase_anon_key    = ""
# openai_api_key       = ""
EOF
    fi

    terraform init \
        -upgrade \
        -input=false

    log_info "Terraform initialized successfully."
}

validate_terraform() {
    log_info "Validating Terraform configuration..."

    cd "${TERRAFORM_DIR}"
    terraform validate

    log_info "Terraform configuration is valid."
}

plan_terraform() {
    log_info "Running Terraform plan..."

    cd "${TERRAFORM_DIR}"
    terraform plan \
        -var="environment=${ENVIRONMENT}" \
        -out=tfplan

    log_info "Terraform plan saved to tfplan."
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
    log_info "Setting up Daru PDF AWS infrastructure for environment: ${ENVIRONMENT}"
    log_info "AWS Region: ${AWS_REGION}"

    check_prerequisites
    create_terraform_backend
    create_secrets
    init_terraform
    validate_terraform
    plan_terraform

    echo ""
    log_info "Setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Review the Terraform plan above"
    echo "  2. Update terraform.tfvars with your configuration"
    echo "  3. Update AWS Secrets Manager with actual secrets"
    echo "  4. Run: cd ${TERRAFORM_DIR} && terraform apply tfplan"
    echo ""
    echo "To deploy services after infrastructure is ready:"
    echo "  ./deploy.sh api       # Deploy API service"
    echo "  ./deploy.sh orchestrator  # Deploy Orchestrator service"
    echo "  ./deploy.sh web       # Deploy Web UI"
    echo "  ./deploy.sh all       # Deploy all services"
}

main "$@"
