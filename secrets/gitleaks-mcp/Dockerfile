# Gitleaks MCP Server
# Custom MCP server wrapping Gitleaks for secrets detection

FROM python:3.12-alpine

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="Gitleaks MCP Server - Secrets detection in git repos and files"
LABEL org.opencontainers.image.licenses="MIT"

# Security: Create non-root user
RUN addgroup -g 1000 mcpuser && \
    adduser -D -u 1000 -G mcpuser mcpuser

RUN apk add --no-cache \
    ca-certificates \
    tini \
    git \
    curl \
    && rm -rf /var/cache/apk/*

# Install Gitleaks from releases
ARG GITLEAKS_VERSION=8.21.2
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then ARCH="x64"; fi && \
    if [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi && \
    curl -sL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${ARCH}.tar.gz" | tar xz -C /usr/local/bin gitleaks && \
    chmod +x /usr/local/bin/gitleaks

# Verify gitleaks installation
RUN gitleaks version

WORKDIR /app

COPY --chown=mcpuser:mcpuser requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser . .

RUN mkdir -p /app/output && chown -R mcpuser:mcpuser /app

USER mcpuser

# Environment variables
ENV GITLEAKS_OUTPUT_DIR=/app/output
ENV GITLEAKS_TIMEOUT=300
ENV GITLEAKS_MAX_CONCURRENT=2

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "server.py"]
