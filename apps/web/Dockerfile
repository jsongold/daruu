# =============================================================================
# Daru PDF Web - Production Dockerfile
# =============================================================================
# Multi-stage build for optimized production image with nginx.
#
# Features:
#   - Multi-stage build for smaller image size
#   - Production-optimized React build
#   - Nginx for static file serving
#   - Custom nginx configuration for SPA routing
#
# Build:
#   docker build -t daru-pdf-web .
#
# Build with custom API URL:
#   docker build --build-arg VITE_API_URL=/api/v1 -t daru-pdf-web .
#
# Run:
#   docker run -p 80:80 daru-pdf-web
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Dependencies
# -----------------------------------------------------------------------------
FROM node:20-alpine AS deps

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --ignore-scripts

# -----------------------------------------------------------------------------
# Stage 2: Builder
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

# Build arguments
ARG VITE_API_URL=/api/v1
ARG VITE_APP_VERSION=0.1.0

# Set environment variables for build
ENV VITE_API_URL=$VITE_API_URL \
    VITE_APP_VERSION=$VITE_APP_VERSION

WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source files
COPY . .

# Build the application
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 3: Production
# -----------------------------------------------------------------------------
FROM nginx:1.25-alpine AS production

# Labels
LABEL maintainer="Daru PDF Team" \
      version="0.1.0" \
      description="Daru PDF Web - React frontend"

# Install curl for health checks
RUN apk add --no-cache curl

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy nginx config for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Create custom error page
RUN echo '<!DOCTYPE html><html><head><title>Error</title></head><body><h1>Service Unavailable</h1><p>Please try again later.</p></body></html>' > /usr/share/nginx/html/50x.html

# Create non-root user for nginx
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

# Switch to non-root user
USER nginx

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:80/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
