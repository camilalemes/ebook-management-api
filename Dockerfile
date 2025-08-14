# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies (Calibre for metadata reading only)
RUN apt-get update && apt-get install -y \
    # Basic system tools
    curl \
    wget \
    gnupg2 \
    ca-certificates \
    util-linux \
    # Install Calibre from package manager (for metadata.db reading)
    calibre \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first (for better Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables for user/group IDs
ENV PUID=1000
ENV PGID=1000

# Create directories for volumes (read-only app)
RUN mkdir -p /app/data/replicas \
             /app/logs \
             /config/logs

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with entrypoint script as root, but drop privileges inside
USER root
ENTRYPOINT ["/entrypoint.sh"]