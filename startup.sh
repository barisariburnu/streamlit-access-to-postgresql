#!/bin/bash
set -e

echo "=== Environment Variables Debug ==="
echo "DB_HOST: ${DB_HOST:-NOT_SET}"
echo "DB_PORT: ${DB_PORT:-NOT_SET}"
echo "DB_NAME: ${DB_NAME:-NOT_SET}"
echo "DB_USER: ${DB_USER:-NOT_SET}"
echo "DB_PASSWORD: ${DB_PASSWORD:+***SET***}"

# Eğer değişkenler boşsa hata ver
if [ -z "$DB_HOST" ] || [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "ERROR: Required environment variables are not set!"
    echo "Please set DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD in Coolify"
    exit 1
fi

echo "=== Creating secrets file ==="
mkdir -p .streamlit

cat > .streamlit/secrets.toml << EOF
[postgres]
host = "${DB_HOST}"
port = "${DB_PORT:-5432}"
database = "${DB_NAME}"
user = "${DB_USER}"
password = "${DB_PASSWORD}"

[app]
max_file_size = 1073741824
upload_folder = "/usr/src/app/uploads"
EOF

echo "✓ Secrets file created successfully"
echo "File content (password hidden):"
grep -v "password" .streamlit/secrets.toml || true

echo "=== Starting Streamlit ==="
exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0