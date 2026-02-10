# Capa MCP Server
# Binary capability detection

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="Capa MCP Server - Binary capability detection"
LABEL org.opencontainers.image.licenses="MIT"

RUN groupadd -g 1000 mcpuser && \
    useradd -u 1000 -g mcpuser -m mcpuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install capa
ARG CAPA_VERSION=9.3.1
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then ARCH_SUFFIX="-arm64"; else ARCH_SUFFIX=""; fi && \
    curl -fsSL "https://github.com/mandiant/capa/releases/download/v${CAPA_VERSION}/capa-v${CAPA_VERSION}-linux${ARCH_SUFFIX}.zip" -o /tmp/capa.zip && \
    cd /tmp && unzip capa.zip && \
    mv capa /usr/local/bin/capa && \
    chmod +x /usr/local/bin/capa && \
    rm -rf /tmp/*

# Verify capa installation
RUN capa --version

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=mcpuser:mcpuser . .
RUN mkdir -p /app/output /app/rules /app/samples && chown -R mcpuser:mcpuser /app

USER mcpuser

ENV CAPA_OUTPUT_DIR=/app/output
ENV CAPA_RULES_DIR=/app/rules
ENV CAPA_TIMEOUT=300
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "server.py"]
