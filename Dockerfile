FROM python:3.11-slim

WORKDIR /app

# Install litellm and any other dependencies
RUN pip install litellm python-dotenv

# Copy configuration
COPY config.yaml .
COPY test.py .

# Create logs directory
RUN mkdir -p /app/logs

# Run litellm server
CMD ["litellm", "--config", "config.yaml"]
