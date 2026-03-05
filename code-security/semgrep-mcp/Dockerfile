# Semgrep MCP Server
# Custom MCP server wrapping the Semgrep CLI for static code analysis.
# Follows the same pattern as every other mcp-security-hub tool.
#
# The old ghcr.io/semgrep/mcp image is deprecated (all tags removed).
# Instead of monkey-patching semgrep internals, this image ships a clean
# server.py that calls the semgrep CLI via asyncio subprocess.
#
# Transport: streamable-http on port 8000 (default), also supports stdio.

FROM semgrep/semgrep:latest

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="Semgrep MCP Server - Static code security analysis"
LABEL org.opencontainers.image.licenses="MIT"

COPY server.py /app/server.py

EXPOSE 8000

ENTRYPOINT ["python3", "/app/server.py", "streamable-http"]
