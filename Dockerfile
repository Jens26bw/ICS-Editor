FROM debian:bookworm-slim

ARG VERSION=dev

ENV DEBIAN_FRONTEND=noninteractive
ENV APP_VERSION=${VERSION}

LABEL org.opencontainers.image.title="ICS Editor" \
      org.opencontainers.image.description="Dark-mode web editor for ICS files on Unraid and Docker hosts" \
      org.opencontainers.image.source="https://github.com/Jens26bw/ICS-Editor" \
      org.opencontainers.image.icon="https://raw.githubusercontent.com/Jens26bw/ICS-Editor/main/ICS-Editor_Logo.png" \
      org.opencontainers.image.version="${VERSION}"

# Python web app
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-flask \
    gosu ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY ics_core.py /app/ics_core.py
COPY web_app.py /app/web_app.py
COPY ICS-Editor_Logo.png /app/ICS-Editor_Logo.png
COPY start.sh /start.sh
RUN chmod +x /start.sh

VOLUME ["/data", "/config"]

EXPOSE 8080

ENV ICS_DIR=/data
ENV WEB_PORT=8080
ENV MAX_UPLOAD_MB=32

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('WEB_PORT', '8080'), timeout=3).read()" || exit 1

ENTRYPOINT ["/start.sh"]
