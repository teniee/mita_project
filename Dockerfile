# Production-ready Mita Finance Backend
# Multi-stage build for security and optimization

# Stage 1: Build dependencies
FROM python:3.10-slim AS builder

# Install build dependencies and security updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for building
RUN groupadd -r mita && useradd -r -g mita mita

WORKDIR /install
COPY requirements.txt .

# Install Python dependencies with security hardening
RUN pip install --upgrade pip setuptools wheel && \
    pip install --user --no-cache-dir --disable-pip-version-check \
    --no-warn-script-location -r requirements.txt

# Stage 2: Production image
FROM python:3.10-slim AS production

# Security updates and runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y

# Create non-root user
RUN groupadd -r mita && useradd -r -g mita -s /bin/false mita

# Set up directory structure
WORKDIR /app
RUN chown -R mita:mita /app

# Copy Python packages from builder
COPY --from=builder --chown=mita:mita /root/.local /home/mita/.local

# Set PATH for user-installed packages
ENV PATH=/home/mita/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY --chown=mita:mita . .

# Copy and set up scripts
COPY --chown=mita:mita ./wait-for-it.sh /app/wait-for-it.sh
COPY --chown=mita:mita ./start.sh /app/start.sh
COPY --chown=mita:mita ./start_optimized.py /app/start_optimized.py
RUN chmod +x /app/wait-for-it.sh /app/start.sh /app/start_optimized.py

# Switch to non-root user
USER mita

# Health check endpoint - Use PORT environment variable
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port
EXPOSE 8000

# Production startup command with optimizations
CMD ["python", "/app/start_optimized.py"]
