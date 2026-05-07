#!/bin/sh
set -e

: "${WEB_PORT:=${NOVNC_PORT:-8080}}"
: "${ICS_DIR:=/data}"
: "${MAX_UPLOAD_MB:=32}"

export WEB_PORT ICS_DIR MAX_UPLOAD_MB

mkdir -p /data /config

# Optional: run as specific UID/GID (Unraid-style)
RUN_AS=""
if [ -n "${PUID:-}" ] && [ -n "${PGID:-}" ]; then
  addgroup --gid "$PGID" app 2>/dev/null || true
  adduser  --disabled-password --gecos "" --uid "$PUID" --gid "$PGID" app 2>/dev/null || true
  chown -R "$PUID:$PGID" /data /config 2>/dev/null || true
  RUN_AS="gosu app"
fi

# Run the web app
if [ -n "$RUN_AS" ]; then
  exec ${RUN_AS} env WEB_PORT="$WEB_PORT" ICS_DIR="$ICS_DIR" MAX_UPLOAD_MB="$MAX_UPLOAD_MB" python3 /app/web_app.py
fi

exec env WEB_PORT="$WEB_PORT" ICS_DIR="$ICS_DIR" MAX_UPLOAD_MB="$MAX_UPLOAD_MB" python3 /app/web_app.py
