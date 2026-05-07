#!/bin/sh
set -e

: "${NOVNC_PORT:=8080}"
: "${VNC_PORT:=5900}"
: "${RESOLUTION:=1280x720}"
: "${DISPLAY:=:0}"
: "${ICS_DIR:=/data}"

export NOVNC_PORT VNC_PORT RESOLUTION DISPLAY ICS_DIR

mkdir -p /data /config

# Optional: run as specific UID/GID (Unraid-style)
RUN_AS=""
if [ -n "${PUID:-}" ] && [ -n "${PGID:-}" ]; then
  addgroup --gid "$PGID" app 2>/dev/null || true
  adduser  --disabled-password --gecos "" --uid "$PUID" --gid "$PGID" app 2>/dev/null || true
  chown -R "$PUID:$PGID" /data /config 2>/dev/null || true
  RUN_AS="gosu app"
fi

# VNC password optional
VNC_AUTH="-nopw"
if [ -n "${VNC_PASSWORD:-}" ]; then
  x11vnc -storepasswd "${VNC_PASSWORD}" /config/vnc.pass >/dev/null 2>&1
  VNC_AUTH="-rfbauth /config/vnc.pass"
fi

# X server
Xvfb "${DISPLAY}" -screen 0 "${RESOLUTION}x24" -ac +extension GLX +render -noreset &
sleep 0.3

# simple window manager
fluxbox >/config/fluxbox.log 2>&1 &
sleep 0.2

# VNC server
x11vnc -display "${DISPLAY}" -forever -shared -listen 0.0.0.0 -rfbport "${VNC_PORT}" ${VNC_AUTH} >/config/x11vnc.log 2>&1 &

# noVNC web
websockify --web /usr/share/novnc/ "${NOVNC_PORT}" "localhost:${VNC_PORT}" >/config/novnc.log 2>&1 &

# Run the app
if [ -n "$RUN_AS" ]; then
  exec ${RUN_AS} env DISPLAY="$DISPLAY" ICS_DIR="$ICS_DIR" python3 /app/ics_editor_gui.py
fi

exec env DISPLAY="$DISPLAY" ICS_DIR="$ICS_DIR" python3 /app/ics_editor_gui.py
