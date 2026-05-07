FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Tk + X11 + VNC + noVNC
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-tk \
    xvfb fluxbox x11vnc novnc websockify \
    gosu ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY ics_editor_gui.py /app/ics_editor_gui.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Default: mount your host folder here
VOLUME ["/data", "/config"]

EXPOSE 8080 5900

ENV ICS_DIR=/data
ENV NOVNC_PORT=8080
ENV VNC_PORT=5900
ENV RESOLUTION=1280x720

ENTRYPOINT ["/start.sh"]
