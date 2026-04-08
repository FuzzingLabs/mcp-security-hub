# Trivy MCP Server
# Official Aqua Security trivy-mcp plugin
# Based on: https://github.com/aquasecurity/trivy-mcp

FROM aquasecurity/trivy:latest

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="Trivy MCP Server - Official Aqua Security MCP plugin"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Install the official MCP plugin
RUN trivy plugin install mcp

# Create cache directory
RUN mkdir -p /root/.cache/trivy

# Environment variables
ENV TRIVY_CACHE_DIR=/root/.cache/trivy

ENTRYPOINT ["trivy", "mcp"]
