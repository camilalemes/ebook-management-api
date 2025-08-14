#!/bin/bash

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "[INFO] Creating user ebook-api with UID=${PUID} and GID=${PGID}"

# Create group first
groupadd -g "$PGID" ebook-api 2>/dev/null || true
# Create user with specific UID and primary group
useradd -u "$PUID" -g ebook-api -M -s /bin/bash ebook-api 2>/dev/null || true

echo "[INFO] Fixing ownership of app and config directories"
chown -R ebook-api:ebook-api /app /config

echo "[INFO] Starting FastAPI as UID=$PUID GID=$PGID..."
exec setpriv --reuid=$PUID --regid=$PGID --init-groups uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload