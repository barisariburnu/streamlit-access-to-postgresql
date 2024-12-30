FROM python:3.10-slim

WORKDIR /usr/src/app

# Install system dependencies including mdbtools
RUN apt-get update && apt-get install -y \
    mdbtools \
    unixodbc \
    unixodbc-dev \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create required directories
RUN mkdir -p /usr/src/app/uploads

# Set permissions
RUN chmod -R 755 /usr/src/app

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
