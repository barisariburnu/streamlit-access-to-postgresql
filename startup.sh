#!/bin/bash
set -e

# Determine writable secrets directory with fallback options
# Priority: 1. App's .streamlit dir, 2. User home, 3. /tmp as last resort
if [ -w "/usr/src/app/.streamlit" ]; then
    SECRETS_DIR="/usr/src/app/.streamlit"
elif [ -n "$HOME" ] && [ -d "$HOME" ]; then
    SECRETS_DIR="$HOME/.streamlit"
    mkdir -p "$SECRETS_DIR" 2>/dev/null || SECRETS_DIR="/tmp/.streamlit"
else
    SECRETS_DIR="/tmp/.streamlit"
fi

mkdir -p "$SECRETS_DIR" 2>/dev/null || {
    echo "Error: Cannot create secrets directory at $SECRETS_DIR"
    exit 1
}

echo "Creating secrets file at $SECRETS_DIR/secrets.toml..."

# Set STREAMLIT_CONFIG_DIR so Streamlit knows where to look
export STREAMLIT_CONFIG_DIR="$SECRETS_DIR"

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

# Copy config.toml if it exists and SECRETS_DIR is different from app dir
if [ "$SECRETS_DIR" != "/usr/src/app/.streamlit" ] && [ -f "/usr/src/app/.streamlit/config.toml" ]; then
    cp /usr/src/app/.streamlit/config.toml "$SECRETS_DIR/config.toml" 2>/dev/null || true
fi

echo "Secrets file created successfully at $SECRETS_DIR"
echo "Starting Streamlit..."

exec streamlit run app.py --server.address=0.0.0.0