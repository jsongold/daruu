# Dockerfile for Daru PDF Web Service
# Multi-stage build for optimized production image

# =============================================================================
# Stage 1: Build
# =============================================================================
FROM node:20-slim as builder

# Set working directory
WORKDIR /build

# Copy package files
COPY apps/web/package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY apps/web/ ./

# Build the application
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# =============================================================================
# Stage 2: Production with Nginx
# =============================================================================
FROM nginx:1.25-alpine as production

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY infra/gcp/cloud-run/web/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /build/dist /usr/share/nginx/html

# Create non-root user for nginx
RUN addgroup -g 1000 -S app && \
    adduser -u 1000 -S app -G app && \
    chown -R app:app /var/cache/nginx && \
    chown -R app:app /var/log/nginx && \
    chown -R app:app /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R app:app /var/run/nginx.pid && \
    chown -R app:app /usr/share/nginx/html

# Use non-root user
USER app

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
