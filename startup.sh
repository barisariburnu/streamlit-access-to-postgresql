#!/bin/bash
set -e

echo "Creating secrets file..."
mkdir -p .streamlit

cat > .streamlit/secrets.toml << EOF
[postgresql]
host = "${DB_HOST}"
port = "${DB_PORT}"
database = "${DB_NAME}"
user = "${DB_USER}"
password = "${DB_PASSWORD}"
EOF

echo "Secrets file created successfully"
echo "Starting Streamlit..."

exec streamlit run app.py --server.address=0.0.0.0