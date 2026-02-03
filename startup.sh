#!/bin/bash
set -e

echo "Creating secrets file..."
mkdir -p .streamlit

# Debug: Print environment variables (without passwords)
echo "DB_HOST: ${DB_HOST:-NOT_SET}"
echo "DB_PORT: ${DB_PORT:-NOT_SET}"
echo "DB_NAME: ${DB_NAME:-NOT_SET}"
echo "DB_USER: ${DB_USER:-NOT_SET}"
echo "DB_PASSWORD: ${DB_PASSWORD:+SET}"

# Validate required environment variables
if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ] || [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "ERROR: Missing required environment variables!"
    echo "Required: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD"
    exit 1
fi

cat > .streamlit/secrets.toml << EOF
[postgres]
host = "${DB_HOST}"
port = "${DB_PORT}"
database = "${DB_NAME}"
user = "${DB_USER}"
password = "${DB_PASSWORD}"

[app]
max_file_size = 1073741824
upload_folder = "/usr/src/app/uploads"
EOF

echo "Secrets file created successfully"
echo "Content of secrets.toml (without password):"
grep -v password .streamlit/secrets.toml

echo "Starting Streamlit..."
exec streamlit run app.py --server.address=0.0.0.0