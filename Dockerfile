# Build stage
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
# unixodbc-dev and g++ are required for building pyodbc/other drivers
RUN apt-get update && apt-get install -y \
    unixodbc-dev \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and setuptools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.10-slim

WORKDIR /usr/src/app

# Install runtime dependencies
# mdbtools is required for Access file processing (used in app.py)
# unixodbc is required for database connections
# curl is required for healthcheck
RUN apt-get update && apt-get install -y \
    mdbtools \
    unixodbc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Copy .streamlit config
COPY .streamlit/config.toml /usr/src/app/.streamlit/config.toml

# Copy startup script and make executable
COPY startup.sh .
RUN chmod +x startup.sh

# Create required directories with secure permissions
# appuser needs write access to .streamlit for secrets.toml creation in startup.sh
RUN mkdir -p /usr/src/app/uploads \
    && mkdir -p /usr/src/app/.streamlit \
    && chmod -R 755 /usr/src/app

# Create non-root user for security
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /usr/src/app && \
    chmod 775 /usr/src/app/.streamlit

# Set HOME environment variable explicitly for container environments
ENV HOME=/home/appuser

# Switch to non-root user
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["./startup.sh"]
