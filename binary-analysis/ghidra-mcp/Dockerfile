# Ghidra MCP Server (Headless)
# Using clearbluejar/pyghidra-mcp
# Based on: https://github.com/clearbluejar/pyghidra-mcp

FROM ghcr.io/clearbluejar/pyghidra-mcp:latest

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="Ghidra MCP Server - Headless AI-powered reverse engineering"
LABEL org.opencontainers.image.licenses="Apache-2.0"

# Default to stdio transport for MCP compatibility
ENTRYPOINT ["pyghidra-mcp", "-t", "stdio"]
