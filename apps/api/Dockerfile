# =============================================================================
# Daru PDF API - Production Dockerfile
# =============================================================================
# Multi-stage build for optimized production image.
#
# Features:
#   - Multi-stage build for smaller image size
#   - Non-root user for security
#   - Health check included
#   - All optional dependencies included
#
# Build:
#   docker build -t daru-pdf-api .
#
# Run:
#   docker run -p 8000:8000 --env-file .env daru-pdf-api
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy project files
WORKDIR /build
COPY pyproject.toml ./

# Install dependencies with all optional extras
RUN pip install --upgrade pip && \
    pip install . && \
    pip install ".[integrations]"

# -----------------------------------------------------------------------------
# Stage 2: Production
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS production

# Labels
LABEL maintainer="Daru PDF Team" \
      version="0.1.0" \
      description="Daru PDF API - Document processing service"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    # Application settings
    DARU_UPLOAD_DIR=/app/uploads

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # For health checks
    curl \
    # For PDF processing (PyMuPDF, reportlab)
    libmupdf-dev \
    libfreetype6 \
    libharfbuzz0b \
    libjpeg62-turbo \
    libopenjp2-7 \
    # For OpenCV (opencv-python-headless)
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    # For fonts in PDF generation
    fonts-dejavu-core \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Create directories with correct permissions
RUN mkdir -p /app/uploads && \
    chown -R appuser:appgroup /app

# Copy application code
COPY --chown=appuser:appgroup app/ ./app/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - production with multiple workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
