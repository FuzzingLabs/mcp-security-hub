# FFUF MCP Server
# Fast web fuzzer for directory, vhost, and parameter discovery

FROM python:3.12-alpine

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="FFUF MCP Server - Fast web fuzzer"
LABEL org.opencontainers.image.licenses="MIT"

# Security: Create non-root user
RUN addgroup -g 1000 mcpuser && \
    adduser -D -u 1000 -G mcpuser mcpuser

RUN apk add --no-cache \
    ca-certificates \
    tini \
    curl \
    git \
    && rm -rf /var/cache/apk/*

# Install ffuf from GitHub releases
ARG FFUF_VERSION=2.1.0
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; fi && \
    if [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi && \
    curl -fsSL "https://github.com/ffuf/ffuf/releases/download/v${FFUF_VERSION}/ffuf_${FFUF_VERSION}_linux_${ARCH}.tar.gz" -o /tmp/ffuf.tar.gz && \
    tar -xzf /tmp/ffuf.tar.gz -C /usr/local/bin ffuf && \
    chmod +x /usr/local/bin/ffuf && \
    rm /tmp/ffuf.tar.gz

# Verify ffuf installation
RUN ffuf -V

WORKDIR /app

COPY --chown=mcpuser:mcpuser requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser . .

RUN mkdir -p /app/output /app/wordlists && chown -R mcpuser:mcpuser /app

USER mcpuser

# Download common wordlists
RUN mkdir -p /app/wordlists/seclists/Discovery/Web-Content && \
    mkdir -p /app/wordlists/seclists/Discovery/DNS && \
    mkdir -p /app/wordlists/dirb && \
    curl -sL https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/common.txt -o /app/wordlists/common.txt && \
    curl -sL https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/raft-large-directories.txt -o /app/wordlists/seclists/Discovery/Web-Content/raft-large-directories.txt && \
    curl -sL https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/raft-large-files.txt -o /app/wordlists/seclists/Discovery/Web-Content/raft-large-files.txt && \
    curl -sL https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/DNS/subdomains-top1million-5000.txt -o /app/wordlists/seclists/Discovery/DNS/subdomains-top1million-5000.txt && \
    curl -sL https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/burp-parameter-names.txt -o /app/wordlists/seclists/Discovery/Web-Content/burp-parameter-names.txt && \
    curl -sL https://raw.githubusercontent.com/v0re/dirb/master/wordlists/common.txt -o /app/wordlists/dirb/common.txt

# Environment variables
ENV FFUF_OUTPUT_DIR=/app/output
ENV FFUF_WORDLISTS_DIR=/app/wordlists
ENV FFUF_TIMEOUT=600
ENV FFUF_MAX_CONCURRENT=2
ENV FFUF_THREADS=40
ENV FFUF_RATE=0
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "server.py"]
