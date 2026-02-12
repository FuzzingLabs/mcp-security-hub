# daml-viewer MCP Server
# DAML access-control analysis as MCP tools

# =============================================================================
# Build Stage (build daml-viewer from source)
# =============================================================================
FROM rust:1.88-slim-bookworm AS builder

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="daml-viewer MCP Server - DAML access-control analysis"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.vendor="FuzzingLabs"

ARG DAML_VIEWER_REPO="https://github.com/FuzzingLabs/daml-viewer.git"
ARG DAML_VIEWER_REF="master"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

RUN git clone "${DAML_VIEWER_REPO}" daml-viewer

WORKDIR /tmp/daml-viewer

RUN git checkout "${DAML_VIEWER_REF}"
RUN cargo build --release

# =============================================================================
# Production Stage (Python MCP server + daml-viewer binary)
# =============================================================================
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/FuzzingLabs/mcp-security-hub"
LABEL org.opencontainers.image.description="daml-viewer MCP Server - DAML access-control analysis"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.vendor="FuzzingLabs"

RUN groupadd -g 1000 mcpuser && \
    useradd -u 1000 -g mcpuser -m mcpuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /tmp/daml-viewer/target/release/daml-viewer /usr/local/bin/daml-viewer

COPY --chown=mcpuser:mcpuser requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mcpuser:mcpuser server.py ./

RUN mkdir -p /app/output /app/uploads && chown -R mcpuser:mcpuser /app

USER mcpuser

ENV DAML_VIEWER_OUTPUT_DIR=/app/output
ENV DAML_VIEWER_UPLOAD_DIR=/app/uploads
ENV DAML_VIEWER_TIMEOUT=120
ENV DAML_VIEWER_MAX_CONCURRENT=3
ENV DAML_VIEWER_MAX_FILE_SIZE=104857600
ENV DAML_VIEWER_ALLOW_ANY_PATH=0
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD pgrep -f "python.*server.py" > /dev/null || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "server.py"]
