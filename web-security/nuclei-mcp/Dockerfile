# Nuclei MCP Server
# Custom implementation wrapping ProjectDiscovery's Nuclei scanner

FROM python:3.12-alpine

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="Nuclei MCP Server - Vulnerability scanner with Nuclei"
LABEL org.opencontainers.image.licenses="MIT"

# Security: Create non-root user
RUN addgroup -g 1000 mcpuser && \
    adduser -D -u 1000 -G mcpuser mcpuser

RUN apk add --no-cache \
    ca-certificates \
    tini \
    git \
    curl \
    unzip \
    && rm -rf /var/cache/apk/*

# Install Nuclei from ProjectDiscovery releases
ARG NUCLEI_VERSION=3.7.0
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; fi && \
    if [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi && \
    curl -fsSL "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_${ARCH}.zip" -o /tmp/nuclei.zip && \
    unzip -q /tmp/nuclei.zip -d /tmp && \
    mv /tmp/nuclei /usr/local/bin/nuclei && \
    chmod +x /usr/local/bin/nuclei && \
    rm -rf /tmp/*

# Verify nuclei installation
RUN nuclei -version

WORKDIR /app

COPY --chown=mcpuser:mcpuser requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser . .

RUN mkdir -p /app/output && chown -R mcpuser:mcpuser /app

USER mcpuser

# Download nuclei templates on first run (or mount volume)
RUN mkdir -p /home/mcpuser/nuclei-templates

# Environment variables
ENV NUCLEI_TEMPLATES_PATH=/home/mcpuser/nuclei-templates
ENV NUCLEI_OUTPUT_DIR=/app/output
ENV NUCLEI_TIMEOUT=600
ENV NUCLEI_MAX_CONCURRENT=2
ENV NUCLEI_RATE_LIMIT=150

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "server.py"]
