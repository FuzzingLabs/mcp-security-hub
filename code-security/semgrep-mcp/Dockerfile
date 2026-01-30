# Semgrep MCP Server
# Wrapper for official semgrep/mcp
# Based on: https://github.com/semgrep/mcp

FROM ghcr.io/semgrep/mcp:latest

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="Semgrep MCP Server - Static code security analysis"
LABEL org.opencontainers.image.licenses="MIT"

ENTRYPOINT ["semgrep-mcp"]
CMD ["-t", "stdio"]
