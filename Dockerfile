FROM debian:bookworm-slim

ARG VERSION=dev

ENV DEBIAN_FRONTEND=noninteractive
ENV APP_VERSION=${VERSION}

LABEL org.opencontainers.image.title="ICS Editor" \
      org.opencontainers.image.description="Browser-accessible ICS editor for Unraid and Docker hosts" \
      org.opencontainers.image.source="https://github.com/Jens26bw/ICS-Editor" \
      org.opencontainers.image.version="${VERSION}"

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

VOLUME ["/data", "/config"]

EXPOSE 8080 5900

ENV ICS_DIR=/data
ENV NOVNC_PORT=8080
ENV VNC_PORT=5900
ENV RESOLUTION=1280x720
ENV DISPLAY=:0

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/' % os.environ.get('NOVNC_PORT', '8080'), timeout=3).read()" || exit 1

ENTRYPOINT ["/start.sh"]
