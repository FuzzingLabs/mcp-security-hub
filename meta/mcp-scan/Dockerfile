# MCP-Scan Server
# Scan MCP servers for security vulnerabilities
# Based on: https://github.com/invariantlabs-ai/mcp-scan

FROM python:3.13-alpine

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="MCP-Scan - Scan MCP servers for vulnerabilities"
LABEL org.opencontainers.image.licenses="Apache-2.0"

RUN addgroup -g 1000 mcpuser && \
    adduser -D -u 1000 -G mcpuser mcpuser

RUN apk add --no-cache tini

RUN pip install --no-cache-dir mcp-scan

USER mcpuser

ENV PATH="/usr/local/bin:$PATH"

ENTRYPOINT ["/sbin/tini", "--", "mcp-scan"]
CMD ["--help"]
