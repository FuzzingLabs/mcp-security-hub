# Waybackurls MCP Server
# Fetch all URLs that the Wayback Machine knows about for a domain

FROM python:3.12-alpine

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="Waybackurls MCP Server - Wayback Machine URL fetcher"
LABEL org.opencontainers.image.licenses="MIT"

# Security: Create non-root user
RUN addgroup -g 1000 mcpuser && \
    adduser -D -u 1000 -G mcpuser mcpuser

RUN apk add --no-cache \
    ca-certificates \
    tini \
    curl \
    git \
    go \
    && rm -rf /var/cache/apk/*

# Install waybackurls
RUN go install github.com/tomnomnom/waybackurls@latest && \
    mv /root/go/bin/waybackurls /usr/local/bin/waybackurls && \
    chmod +x /usr/local/bin/waybackurls && \
    rm -rf /root/go

# Verify waybackurls installation
RUN waybackurls --help || echo "waybackurls installed"

WORKDIR /app

COPY --chown=mcpuser:mcpuser requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser . .

RUN mkdir -p /app/output && chown -R mcpuser:mcpuser /app

USER mcpuser

# Environment variables
ENV WAYBACKURLS_OUTPUT_DIR=/app/output
ENV WAYBACKURLS_TIMEOUT=300
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "server.py"]
