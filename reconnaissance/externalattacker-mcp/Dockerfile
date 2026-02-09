# ExternalAttacker MCP Server
# Built from MorDavid/ExternalAttacker-MCP source
# Based on: https://github.com/MorDavid/ExternalAttacker-MCP

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="ExternalAttacker MCP Server - Attack surface mapping"
LABEL org.opencontainers.image.licenses="MIT"

RUN apt-get update && \
    apt-get install -y --no-install-recommends git golang-go tini ca-certificates libpcap-dev gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*

ENV GOPATH=/go
ENV PATH="/go/bin:$PATH"
ENV CGO_ENABLED=1

# Install ProjectDiscovery tools
RUN go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest && \
    go install github.com/projectdiscovery/httpx/cmd/httpx@latest && \
    go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest && \
    go install github.com/projectdiscovery/cdncheck/cmd/cdncheck@latest && \
    go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest

RUN useradd -m -u 1000 mcpuser

WORKDIR /app

RUN git clone --depth 1 https://github.com/MorDavid/ExternalAttacker-MCP.git . && \
    pip install --no-cache-dir -r requirements.txt fastmcp && \
    chown -R mcpuser:mcpuser /app

USER mcpuser

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "ExternalAttacker-MCP.py"]
