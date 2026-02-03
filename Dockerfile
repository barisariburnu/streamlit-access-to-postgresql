# Streamlit PostgreSQL Access Application
FROM python:3.10-slim

# Set environment variables for Python optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /usr/src/app

# Install system dependencies in a single layer
# Combine apt-get update, install, and cleanup to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    mdbtools \
    unixodbc \
    unixodbc-dev \
    g++ \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy and install Python dependencies first (better layer caching)
# This layer only rebuilds when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create required directories before copying app code
RUN mkdir -p /usr/src/app/uploads /usr/src/app/.streamlit

# Copy application code
# Using specific COPY commands for better cache utilization
COPY app.py config.py ./
COPY .streamlit/config.toml .streamlit/
COPY startup.sh .

# Set permissions
RUN chmod +x startup.sh \
    && chmod -R 755 /usr/src/app

EXPOSE 8501

# Enhanced healthcheck with proper timing
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["./startup.sh"]
