#!/bin/bash
set -e

# Use user's home directory for secrets to avoid permission issues with bind mounts
SECRETS_DIR="$HOME/.streamlit"
mkdir -p "$SECRETS_DIR"

echo "Creating secrets file at $SECRETS_DIR/secrets.toml..."

cat > "$SECRETS_DIR/secrets.toml" << EOF
[postgres]
host = "${DB_HOST}"
port = "${DB_PORT}"
database = "${DB_NAME}"
user = "${DB_USER}"
password = "${DB_PASSWORD}"

[app]
max_file_size = 1073741824
upload_folder = "/home/appuser/uploads"
EOF

echo "Secrets file created successfully"
echo "Starting Streamlit..."

exec streamlit run app.py --server.address=0.0.0.0