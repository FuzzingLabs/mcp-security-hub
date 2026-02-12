# Nikto MCP Server
# Wrapper for nikto-mcp web server scanner
# Based on: https://github.com/weldpua2008/nikto-mcp

FROM node:20-alpine

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="Nikto MCP Server - Web server vulnerability scanner"
LABEL org.opencontainers.image.licenses="MIT"

# Security: Use existing node user (uid/gid 1000 in node:alpine)
# The node:alpine image already has a 'node' user with uid/gid 1000

# Install Nikto and dependencies
RUN apk add --no-cache \
    ca-certificates \
    tini \
    git \
    perl \
    perl-net-ssleay \
    perl-json \
    perl-xml-writer \
    && rm -rf /var/cache/apk/*

# Clone and install Nikto
RUN git clone --depth 1 https://github.com/sullo/nikto.git /opt/nikto && \
    ln -s /opt/nikto/program/nikto.pl /usr/local/bin/nikto && \
    chmod +x /opt/nikto/program/nikto.pl

# Verify nikto installation
RUN nikto -Version

WORKDIR /app

# Clone nikto-mcp
RUN git clone --depth 1 https://github.com/weldpua2008/nikto-mcp.git /tmp/nikto-mcp && \
    cp -r /tmp/nikto-mcp/* /app/ && \
    rm -rf /tmp/nikto-mcp

# Install Node.js dependencies and build
RUN npm ci && npm run build

# Set ownership
RUN mkdir -p /app/output && chown -R node:node /app /opt/nikto

USER node

# Environment variables
ENV NIKTO_OUTPUT_DIR=/app/output
ENV NIKTO_TIMEOUT=600
ENV NODE_ENV=production

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "node.*index" > /dev/null || exit 1

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "dist/index.js"]
