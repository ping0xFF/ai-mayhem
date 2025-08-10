FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    "litellm[proxy]==1.45.8" \
    python-dotenv==1.0.0 \
    requests==2.31.0 \
    pyyaml==6.0.1

# Create necessary directories
RUN mkdir -p /app/logs

# Copy configuration and code
COPY config.yaml .
COPY test.py .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run litellm server
# CMD ["litellm", "--config", "config.yaml", "--port", "8000", "--debug"]
CMD ["litellm", "--config", "config.yaml", "--port", "8000", "--debug"]