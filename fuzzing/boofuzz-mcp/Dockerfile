# Boofuzz MCP Server
# Network Protocol Fuzzing Framework

FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="Boofuzz MCP Server - Protocol Fuzzing"
LABEL org.opencontainers.image.licenses="MIT"

# Security: Create non-root user
RUN groupadd -g 1000 mcpuser && \
    useradd -u 1000 -g mcpuser -m mcpuser

# Install system dependencies
# gcc and python3-dev are needed for compiling boofuzz dependencies like netifaces
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    netcat-openbsd \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser . .

# Create directories for scripts and results
RUN mkdir -p /app/scripts /app/results /app/archives && chown -R mcpuser:mcpuser /app

USER mcpuser

# Environment variables
ENV BOOFUZZ_SCRIPT_DIR=/app/scripts
ENV BOOFUZZ_RESULTS_DIR=/app/results
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "server.py"]