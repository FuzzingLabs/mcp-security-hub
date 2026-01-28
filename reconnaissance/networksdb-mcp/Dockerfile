# NetworksDB MCP Server
# Built from MorDavid/NetworksDB-MCP source
# Based on: https://github.com/MorDavid/NetworksDB-MCP

FROM python:3.12-alpine

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="NetworksDB MCP Server - IP/ASN/DNS lookups"
LABEL org.opencontainers.image.licenses="MIT"

RUN addgroup -g 1000 mcpuser && \
    adduser -D -u 1000 -G mcpuser mcpuser

RUN apk add --no-cache git tini

WORKDIR /app

RUN git clone --depth 1 https://github.com/MorDavid/NetworksDB-MCP.git . && \
    pip install --no-cache-dir -r requirements.txt && \
    chown -R mcpuser:mcpuser /app

USER mcpuser

ENV NETWORKSDB_API_KEY=

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "NetworksDB-MCP.py"]
