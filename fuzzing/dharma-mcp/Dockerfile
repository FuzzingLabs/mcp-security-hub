# Dharma MCP Server
# Grammar-based test case generation

# We use 3.10 instead of 3.12 for compatibility with dharma
FROM python:3.10-slim

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/offensive-security-mcps"
LABEL org.opencontainers.image.description="Dharma MCP Server - Grammar-based fuzzer"
LABEL org.opencontainers.image.licenses="MIT"

# Security: Create non-root user
RUN groupadd -g 1000 mcpuser && \
    useradd -u 1000 -g mcpuser -m mcpuser

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Dharma from source
# The grammars are located at /tmp/dharma/dharma/grammars inside the repo
RUN git clone --depth 1 https://github.com/MozillaSecurity/dharma.git /tmp/dharma && \
    pip install --no-cache-dir /tmp/dharma && \
    mkdir -p /app/grammars && \
    cp -r /tmp/dharma/dharma/grammars/* /app/grammars/ && \
    rm -rf /tmp/dharma

COPY --chown=mcpuser:mcpuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser . .

RUN mkdir -p /app/output && chown -R mcpuser:mcpuser /app

USER mcpuser

ENV DHARMA_GRAMMAR_DIR=/app/grammars
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "server.py"]